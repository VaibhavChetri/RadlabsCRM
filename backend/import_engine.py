"""
import_engine.py
----------------
Bring leads in from an .xlsx or .csv file.

    read_file -> apply mapping -> clean -> build plan -> apply plan

`build_plan` only reads the database; `apply_plan` writes everything in
the caller's transaction (the route commits once, so an import is all or
nothing).
"""

import csv
import io
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import lead_service
from lead_matcher import LeadIndex, email_key, fields_to_fill, has_contact, phone_key
from models import Import, ImportPreset, Lead, User

# CRM fields a file column can be mapped to. `full_name` is split into
# first and last name ("Ravi Kumar" -> Ravi / Kumar).
FIELDS = (
    "full_name", "first_name", "last_name", "job_title", "email", "phone", "phone_2",
    "linkedin_url", "company", "website", "industry", "company_size", "city", "country",
)
CONTACT_FIELDS = ("email", "phone", "linkedin_url")

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000


class ImportRefused(ValueError):
    """The file or the import settings cannot be used; nothing was written.
    The message tells the user what to fix."""


# Built-in presets: file header -> CRM field. Several columns may feed one
# field; the first non-empty one (left to right in the file) wins.
APOLLO_PRESET = {
    "First Name": "first_name",
    "Last Name": "last_name",
    "Title": "job_title",
    "Company": "company",
    "Company Name": "company",
    "Email": "email",
    "First Phone": "phone",
    "Work Direct Phone": "phone",
    "Mobile Phone": "phone",
    "Home Phone": "phone_2",
    "Corporate Phone": "phone_2",
    "Other Phone": "phone_2",
    "Person Linkedin Url": "linkedin_url",
    "Website": "website",
    "Industry": "industry",
    "# Employees": "company_size",
    "City": "city",
    "Company City": "city",
    "Country": "country",
    "Company Country": "country",
}
BUILTIN_PRESETS = {"Apollo": APOLLO_PRESET}
MIN_PRESET_OVERLAP = 3  # a preset "matches" a file sharing at least this many headers

# Header names people use for each field (compared after _norm), for files
# no preset knows.
SYNONYMS = {
    "full_name": ["name", "full name", "contact name", "contact", "person name", "lead name",
                  "customer name", "client name"],
    "first_name": ["first name", "firstname", "first", "given name", "fname"],
    "last_name": ["last name", "lastname", "surname", "family name", "last", "lname"],
    "job_title": ["title", "job title", "designation", "position", "role", "job role"],
    "email": ["email", "e mail", "email address", "e mail address", "email id", "e mail id",
              "mail", "mail id", "work email"],
    "phone": ["phone", "phone number", "phone no", "mobile", "mobile no", "mobile number",
              "mobile phone", "cell", "cell phone", "contact number", "contact no",
              "telephone", "tel", "whatsapp", "whatsapp number", "ph no"],
    "phone_2": ["phone 2", "second phone", "alternate phone", "alternate number", "alt phone",
                "alt number", "other phone", "landline", "office phone", "work phone"],
    "linkedin_url": ["linkedin", "linkedin url", "linkedin profile", "linkedin link",
                     "person linkedin url", "profile url"],
    "company": ["company", "company name", "organisation", "organization", "org",
                "business", "business name", "firm", "account name"],
    "website": ["website", "web", "site", "url", "company website", "domain", "web site"],
    "industry": ["industry", "sector", "vertical"],
    "company_size": ["company size", "employees", "employee count", "no of employees",
                     "number of employees", "headcount", "size", "team size"],
    "city": ["city", "town"],
    "country": ["country"],
}
_FIELD_FOR_SYNONYM = {name: f for f, names in SYNONYMS.items() for name in names}


def seed_builtin_presets(db: Session) -> None:
    """Insert or refresh the built-in presets (safe to run again)."""
    for name, mapping in BUILTIN_PRESETS.items():
        preset = db.query(ImportPreset).filter(ImportPreset.name == name).first()
        if preset is None:
            db.add(ImportPreset(name=name, mapping=mapping, is_builtin=True))
        else:
            preset.mapping, preset.is_builtin = mapping, True
    db.flush()


def _norm(header: str) -> str:
    """"E-mail Address " -> "e mail address", "# Employees" -> "employees"."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", header.lower()).split())


def suggest_mapping(headers: list[str], presets: list[ImportPreset]) -> tuple[dict, str | None]:
    """A CRM field (or None = skip) for every header, and the preset used, if any.
    The preset sharing the most headers with the file wins."""
    best, best_overlap = None, 0
    file_headers = {_norm(h) for h in headers}
    for preset in presets:
        overlap = len(file_headers & {_norm(h) for h in preset.mapping})
        if overlap >= MIN_PRESET_OVERLAP and overlap > best_overlap:
            best, best_overlap = preset, overlap
    known = {_norm(h): f for h, f in best.mapping.items()} if best else {}

    mapping = {h: known.get(_norm(h)) for h in headers}
    used = set(mapping.values())
    for header in headers:
        if _norm(header) in known:
            continue  # the preset decided (field or skip)
        target = _FIELD_FOR_SYNONYM.get(_norm(header))
        if target == "phone" and "phone" in used:
            target = "phone_2"  # a second phone-like column
        if target in used or (target in ("first_name", "last_name") and "full_name" in used):
            target = None
        mapping[header] = target
        used.add(target)
    return mapping, (best.name if best else None)


@dataclass
class FileData:
    file_name: str
    headers: list[str]
    rows: list[tuple[int, list[str]]]  # (row number in the file, cell texts)


@dataclass
class RowResult:
    row: int
    result: str  # added | updated | skipped
    reason: str = ""
    values: list[str] = field(default_factory=list)  # the row as in the file


@dataclass
class ImportPlan:
    creates: list[tuple[int, dict]] = field(default_factory=list)  # (row, fields)
    updates: dict[int, tuple[int, dict]] = field(default_factory=dict)  # lead id -> (row, fills)
    results: list[RowResult] = field(default_factory=list)


def read_file(file_name: str, content: bytes) -> FileData:
    """The file's header row and data rows, every cell as trimmed text.
    Blank rows are dropped; row numbers are kept as the user sees them."""
    extension = os.path.splitext(file_name or "")[1].lower()
    if extension not in (".xlsx", ".csv"):
        raise ImportRefused("Only .xlsx and .csv files can be imported")
    if len(content) > MAX_FILE_BYTES:
        raise ImportRefused("The file is larger than 5 MB. Split it and import each part.")
    try:
        lines = _xlsx_lines(content) if extension == ".xlsx" else _csv_lines(content)
    except Exception as err:  # openpyxl / csv raise many kinds of errors
        raise ImportRefused(f"Could not read {file_name}. Is it a real "
                              f"{extension} file?") from err

    numbered = [(number, [_text(c) for c in cells])
                for number, cells in enumerate(lines, start=1)]
    numbered = [(number, cells) for number, cells in numbered if any(cells)]
    # The header row is the first with 2+ cells; a title above it is ignored.
    start = next((i for i, (_, cells) in enumerate(numbered) if sum(map(bool, cells)) >= 2), None)
    if start is None:
        raise ImportRefused("No header row found. The first row should hold column names.")
    headers = _unique_headers(numbered[start][1])
    rows = [(number, (cells + [""] * len(headers))[:len(headers)])
            for number, cells in numbered[start + 1:]]
    if len(rows) > MAX_ROWS:
        raise ImportRefused(f"The file has {len(rows)} rows; the limit is {MAX_ROWS}. "
                              "Split it and import each part.")
    return FileData(file_name=file_name, headers=headers, rows=rows)


def _unique_headers(cells: list[str]) -> list[str]:
    """Blank header -> "Column C"; a repeated one -> "Remarks (2)"."""
    headers, seen = [], {}
    for position, cell in enumerate(cells, start=1):
        name = cell or f"Column {get_column_letter(position)}"
        seen[name] = seen.get(name, 0) + 1
        headers.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return headers


def _xlsx_lines(content: bytes) -> list[tuple]:
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        return list(book.worksheets[0].iter_rows(values_only=True))
    finally:
        book.close()


def _csv_lines(content: bytes) -> list[list[str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252", errors="replace")  # old Excel "CSV" exports
    return list(csv.reader(io.StringIO(text)))


def _text(value) -> str:
    """Cell -> text. Excel stores phone numbers as numbers: 9876543210.0 -> "9876543210"."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, (datetime, date)):
        value = value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value).strip()


def map_row(headers: list[str], cells: list[str], mapping: dict) -> dict:
    """File row -> CRM fields. Several columns on one field: first non-empty wins."""
    fields = {}
    for header, value in zip(headers, cells):
        target = mapping.get(header)
        if target and value and not fields.get(target):
            fields[target] = value
    full_name = fields.pop("full_name", None)
    if full_name:
        first, _, last = full_name.partition(" ")
        fields.setdefault("first_name", first)
        if last.strip():
            fields.setdefault("last_name", last.strip())
    return fields


def clean(fields: dict) -> dict:
    """Lowercase the email; drop an email or phone that is not usable ("n/a", "-")."""
    fields = dict(fields)
    if "email" in fields:
        fields["email"] = email_key(fields["email"])
    for name in ("phone", "phone_2"):
        if name in fields:
            # A leading ' is Excel's "keep as text" mark (Apollo phones have it).
            fields[name] = fields[name].lstrip("'").strip() if phone_key(fields[name]) else None
    if fields.get("phone_2") and phone_key(fields["phone_2"]) == phone_key(fields.get("phone")):
        fields["phone_2"] = None
    return {name: value for name, value in fields.items() if value}


def preview_rows(data: FileData, mapping: dict, limit: int) -> list[dict]:
    """The first rows as they will look in the CRM (mapped and cleaned)."""
    return [clean(map_row(data.headers, cells, mapping)) for _, cells in data.rows[:limit]]


@dataclass
class _Entry:
    """One person in the file: the first row they appear on, plus later duplicates."""
    row: int
    fields: dict
    lead_id: int | None  # existing lead it matches, or None = new lead


def build_plan(db: Session, data: FileData, mapping: dict) -> ImportPlan:
    """Decide what each row does. Reads the database, writes nothing."""
    crm = LeadIndex.load(db)
    in_file = LeadIndex()  # keys seen so far in this file -> entry number
    entries: list[_Entry] = []
    entry_for_lead: dict[int, int] = {}
    outcome: dict[int, RowResult] = {}  # rows decided now; entry rows decided at the end

    for number, cells in data.rows:
        fields = clean(map_row(data.headers, cells, mapping))
        if not has_contact(fields):
            outcome[number] = RowResult(number, "skipped", "no contact info")
            continue
        lead_id = None
        found = in_file.find(fields)
        if found is None:
            lead_id = crm.find(fields)
            found = entry_for_lead.get(lead_id)
        if found is not None:
            entry = entries[found]
            for name, value in fields.items():
                entry.fields.setdefault(name, value)  # first row wins, later rows fill blanks
            in_file.add(found, fields)
            outcome[number] = RowResult(
                number, "skipped", f"duplicate of row {entry.row} in this file (merged)")
            continue
        entries.append(_Entry(row=number, fields=fields, lead_id=lead_id))
        in_file.add(len(entries) - 1, fields)
        if lead_id is not None:
            entry_for_lead[lead_id] = len(entries) - 1

    plan = ImportPlan()
    for entry in entries:
        if entry.lead_id is None and not (entry.fields.get("first_name")
                                          or entry.fields.get("last_name")):
            outcome[entry.row] = RowResult(entry.row, "skipped", "no name")
        elif entry.lead_id is None:
            plan.creates.append((entry.row, entry.fields))
            outcome[entry.row] = RowResult(entry.row, "added")
        else:
            _plan_update(db, plan, entry, outcome)
    for number, cells in data.rows:
        outcome[number].values = cells
    plan.results = [outcome[number] for number in sorted(outcome)]
    return plan


def _plan_update(db: Session, plan: ImportPlan, entry: _Entry, outcome: dict) -> None:
    fills = fields_to_fill(db.get(Lead, entry.lead_id), entry.fields)
    if fills:
        plan.updates[entry.lead_id] = (entry.row, fills)
        outcome[entry.row] = RowResult(entry.row, "updated")
    else:
        outcome[entry.row] = RowResult(entry.row, "skipped", "already in CRM, nothing new")


def owners_for(db: Session, assign_to: str) -> list[User | None]:
    """New leads go to these owners in turn. "split" = every active user, in a
    stable order; "unassigned" = nobody; otherwise one active user's uuid."""
    if assign_to == "unassigned":
        return [None]
    if assign_to == "split":
        return db.query(User).filter(User.is_active.is_(True)).order_by(User.id).all()
    owner = db.query(User).filter(User.uuid == assign_to, User.is_active.is_(True)).first()
    if owner is None:
        raise ImportRefused("Assign to: choose an active team member")
    return [owner]


class ImportRowError(RuntimeError):
    """A row the database refused. The caller rolls the whole import back."""


@contextmanager
def _row_errors(row: int):
    try:
        yield
    except (SQLAlchemyError, lead_service.LeadError) as err:
        reason = err.orig.args[-1] if getattr(err, "orig", None) is not None else str(err)
        raise ImportRowError(f"Import failed at row {row}: {reason}. "
                             "Nothing was imported.") from err


def apply_plan(db: Session, plan: ImportPlan, data: FileData, source: str,
               owners: list[User | None], user: User) -> Import:
    """Write the plan in the caller's transaction. New leads take `owners` in turn."""
    for turn, (row, fields) in enumerate(plan.creates):
        owner = owners[turn % len(owners)]
        with _row_errors(row):
            lead_service.create_lead(db, {**fields, "source": source}, user, owner=owner)
    for lead_id, (row, fills) in plan.updates.items():
        with _row_errors(row):
            lead_service.update_lead(db, db.get(Lead, lead_id), fills, user)
    counts = {result: sum(r.result == result for r in plan.results)
              for result in ("added", "updated", "skipped")}
    record = Import(user_id=user.id, file_name=data.file_name, source=source, **counts)
    db.add(record)
    db.flush()
    return record


def report_workbook(headers: list[str], rows: list[dict]) -> bytes:
    """The import report as .xlsx: Row, Result, Reason, then the file's own
    columns, so skipped rows can be fixed and imported again."""
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Import report")
    sheet.append(["Row", "Result", "Reason", *headers])
    for row in rows:
        cells = [row["row"], row["result"], row["reason"], *row["values"]]
        sheet.append([cell if cell != "" else None for cell in cells])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
