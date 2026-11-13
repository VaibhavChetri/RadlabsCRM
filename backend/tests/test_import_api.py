"""Phase 5: import over HTTP (preview, run, report, presets, history)."""

import json
from datetime import datetime
import os

from models import Import, Lead, StatusChange


def _run_import(client, headers, content: bytes, mapping: dict, file_name="leads.csv",
                source="Other", assign_to="unassigned"):
    return client.post(
        "/imports",
        files={"file": (file_name, content)},
        data={"mapping": json.dumps(mapping), "source": source, "assign_to": assign_to},
        headers=headers,
    )


SIMPLE_CSV = b"Name,Company,Email\nRavi Kumar,Acme,ravi@acme.com\nMeera Shah,Globex,meera@globex.io\n"
SIMPLE_MAPPING = {"Name": "full_name", "Company": "company", "Email": "email"}


def test_csv_import_adds_new_leads_and_returns_a_report(client, auth_headers, db):
    headers = auth_headers(name="Asha")

    res = _run_import(client, headers, SIMPLE_CSV, SIMPLE_MAPPING, source="Referral")

    assert res.status_code == 200, res.text
    report = res.json()
    assert (report["added"], report["updated"], report["skipped"]) == (2, 0, 0)
    leads = db.query(Lead).order_by(Lead.first_name).all()
    assert [(l.first_name, l.last_name, l.company, l.email, l.source) for l in leads] == [
        ("Meera", "Shah", "Globex", "meera@globex.io", "Referral"),
        ("Ravi", "Kumar", "Acme", "ravi@acme.com", "Referral"),
    ]
    assert all(l.status.name == "New" and l.creator.name == "Asha" for l in leads)
    assert db.query(StatusChange).count() == 2  # none -> New for each
    history = db.query(Import).one()
    assert (history.file_name, history.source, history.added) == ("leads.csv", "Referral", 2)


def test_reupload_adds_nothing_and_never_changes_sales_work(client, auth_headers, db):
    headers = auth_headers(name="Asha")
    _run_import(client, headers, SIMPLE_CSV, SIMPLE_MAPPING)
    ravi = db.query(Lead).filter(Lead.email == "ravi@acme.com").one()
    client.patch(f"/leads/{ravi.uuid}", headers=headers,
                 json={"status": "Interested", "priority": "hot", "next_follow_up": "2026-12-01"})
    client.post(f"/leads/{ravi.uuid}/call", headers=headers)
    client.post(f"/leads/{ravi.uuid}/notes", json={"body": "Wants a demo"}, headers=headers)
    before = client.get(f"/leads/{ravi.uuid}", headers=headers).json()

    res = _run_import(client, headers, SIMPLE_CSV.replace(b"Acme,", b"Acme Corp,"),
                      SIMPLE_MAPPING, source="Apollo", assign_to="split")

    report = res.json()
    assert (report["added"], report["updated"], report["skipped"]) == (0, 0, 2)
    assert {r["reason"] for r in report["rows"]} == {"already in CRM, nothing new"}
    assert db.query(Lead).count() == 2
    after = client.get(f"/leads/{ravi.uuid}", headers=headers).json()
    assert after == before  # status, owner, priority, calls, follow-up, company, source
    notes = client.get(f"/leads/{ravi.uuid}/notes", headers=headers).json()
    assert [n["body"] for n in notes] == ["Wants a demo"]


def test_new_phone_fills_an_existing_lead_only_if_its_phone_is_empty(client, auth_headers, db):
    headers = auth_headers()
    client.post("/leads", json={"first_name": "Ravi", "email": "ravi@acme.com"}, headers=headers)
    client.post("/leads", json={"first_name": "Meera", "email": "meera@globex.io",
                                "phone": "9000000001"}, headers=headers)
    csv_file = (b"Email,Phone,Company\n"
                b"RAVI@acme.com,+91 98765 43210,Acme\n"
                b"meera@globex.io,9111111111,Globex\n")

    res = _run_import(client, headers, csv_file,
                      {"Email": "email", "Phone": "phone", "Company": "company"})

    report = res.json()
    assert (report["added"], report["updated"], report["skipped"]) == (0, 2, 0)
    ravi = db.query(Lead).filter(Lead.first_name == "Ravi").one()
    meera = db.query(Lead).filter(Lead.first_name == "Meera").one()
    assert (ravi.phone, ravi.company) == ("+91 98765 43210", "Acme")
    assert (meera.phone, meera.company) == ("9000000001", "Globex")  # phone kept


def test_rows_without_email_phone_or_linkedin_are_skipped(client, auth_headers, db):
    headers = auth_headers()
    csv_file = (b"Name,Email,Phone,Company\n"
                b"Ravi Kumar,,,Acme\n"
                b"Junk Row,n/a,-,Globex\n"
                b"Meera Shah,MEERA@Globex.io ,,Globex\n")

    res = _run_import(client, headers, csv_file, {
        "Name": "full_name", "Email": "email", "Phone": "phone", "Company": "company"})

    report = res.json()
    assert (report["added"], report["updated"], report["skipped"]) == (1, 0, 2)
    assert [(r["row"], r["result"], r["reason"]) for r in report["rows"]] == [
        (2, "skipped", "no contact info"),
        (3, "skipped", "no contact info"),
        (4, "added", ""),
    ]
    assert db.query(Lead).one().email == "meera@globex.io"  # cleaned


def test_duplicate_rows_in_one_file_merge_into_one_lead(client, auth_headers, db):
    headers = auth_headers()
    client.post("/leads", json={"first_name": "Meera", "email": "meera@globex.io",
                                "phone": "9000000001"}, headers=headers)
    csv_file = (b"Name,Email,Phone,City\n"
                b"Ravi Kumar,ravi@acme.com,,\n"
                b"Ravi K,RAVI@ACME.COM,9876543210,\n"         # same email as row 2
                b"Ravi,,+91 98765 43210,Pune\n"               # same phone as row 3
                b"Meera Shah,meera@globex.io,,\n"             # existing lead
                b"Meera,,9000000001,Mumbai\n")               # same lead, found by phone

    res = _run_import(client, headers, csv_file, {
        "Name": "full_name", "Email": "email", "Phone": "phone", "City": "city"})

    report = res.json()
    assert [(r["row"], r["result"], r["reason"]) for r in report["rows"]] == [
        (2, "added", ""),
        (3, "skipped", "duplicate of row 2 in this file (merged)"),
        (4, "skipped", "duplicate of row 2 in this file (merged)"),
        (5, "updated", ""),
        (6, "skipped", "duplicate of row 5 in this file (merged)"),
    ]
    assert (report["added"], report["updated"], report["skipped"]) == (1, 1, 3)
    ravi = db.query(Lead).filter(Lead.email == "ravi@acme.com").one()
    assert (ravi.first_name, ravi.last_name, ravi.phone, ravi.city) == (
        "Ravi", "Kumar", "9876543210", "Pune")
    meera = db.query(Lead).filter(Lead.email == "meera@globex.io").one()
    assert (meera.last_name, meera.phone, meera.city) == ("Shah", "9000000001", "Mumbai")
    assert db.query(Lead).count() == 2


def _people_csv(count: int) -> bytes:
    rows = "".join(f"Person {i},p{i}@example.com\n" for i in range(1, count + 1))
    return f"Name,Email\n{rows}".encode()


PEOPLE_MAPPING = {"Name": "full_name", "Email": "email"}


def _owners_by_email(db):
    db.expire_all()
    return {l.email: (l.owner.name if l.owner else None) for l in db.query(Lead)}


def test_split_evenly_assigns_round_robin_across_active_users(client, auth_headers, make_user, db):
    headers = auth_headers(name="Asha", email="asha@example.com")
    make_user(name="Vikram", email="vikram@example.com")
    make_user(name="Gone", email="gone@example.com", is_active=False)
    make_user(name="Neha", email="neha@example.com")

    _run_import(client, headers, _people_csv(5), PEOPLE_MAPPING, assign_to="split")

    assert _owners_by_email(db) == {
        "p1@example.com": "Asha", "p2@example.com": "Vikram", "p3@example.com": "Neha",
        "p4@example.com": "Asha", "p5@example.com": "Vikram",
    }


def test_assign_to_one_user_or_nobody(client, auth_headers, make_user, db):
    headers = auth_headers(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")

    _run_import(client, headers, _people_csv(2), PEOPLE_MAPPING, assign_to=vikram.uuid)
    assert set(_owners_by_email(db).values()) == {"Vikram"}

    more = b"Name,Email\nNew One,new1@example.com\n"
    _run_import(client, headers, more, PEOPLE_MAPPING, assign_to="unassigned")
    assert _owners_by_email(db)["new1@example.com"] is None


def test_assign_to_an_inactive_or_unknown_user_is_refused(client, auth_headers, make_user, db):
    headers = auth_headers()
    gone = make_user(name="Gone", email="gone@example.com", is_active=False)

    for assign_to in (gone.uuid, "not-a-user"):
        res = _run_import(client, headers, _people_csv(2), PEOPLE_MAPPING, assign_to=assign_to)
        assert res.status_code == 422
        assert "active team member" in res.json()["detail"]
    assert db.query(Lead).count() == 0
    assert db.query(Import).count() == 0


def test_a_row_that_breaks_the_database_rolls_back_the_whole_import(client, auth_headers, db):
    headers = auth_headers()
    client.post("/leads", json={"first_name": "Meera", "email": "meera@globex.io"}, headers=headers)
    too_long = "X" * 300  # job title column holds 255 characters
    csv_file = (f"Name,Email,City,Title\n"
                f"Ravi Kumar,ravi@acme.com,,\n"
                f"Meera Shah,meera@globex.io,Mumbai,\n"
                f"Bad Row,bad@example.com,,{too_long}\n").encode()

    res = _run_import(client, headers, csv_file, {
        "Name": "full_name", "Email": "email", "City": "city", "Title": "job_title"})

    assert res.status_code == 422, res.text
    assert "row 4" in res.json()["detail"]
    assert "Nothing was imported" in res.json()["detail"]
    db.expire_all()
    assert [l.first_name for l in db.query(Lead)] == ["Meera"]
    assert db.query(Lead).one().city is None
    assert db.query(StatusChange).count() == 1
    assert db.query(Import).count() == 0


def test_wrong_file_type_is_refused(client, auth_headers):
    headers = auth_headers()
    for name in ("leads.xls", "leads.pdf", "leads"):
        res = _run_import(client, headers, SIMPLE_CSV, SIMPLE_MAPPING, file_name=name)
        assert res.status_code == 422
        assert res.json()["detail"] == "Only .xlsx and .csv files can be imported"
    res = _run_import(client, headers, b"not really excel", SIMPLE_MAPPING, file_name="leads.xlsx")
    assert res.status_code == 422
    assert "Could not read" in res.json()["detail"]


def test_too_large_file_or_too_many_rows_is_refused(client, auth_headers, db):
    headers = auth_headers()
    big = b"Name,Email\n" + b"x" * (5 * 1024 * 1024)
    res = _run_import(client, headers, big, PEOPLE_MAPPING)
    assert res.status_code == 422
    assert res.json()["detail"] == "The file is larger than 5 MB. Split it and import each part."

    res = _run_import(client, headers, _people_csv(5001), PEOPLE_MAPPING)
    assert res.status_code == 422
    assert res.json()["detail"] == (
        "The file has 5001 rows; the limit is 5000. Split it and import each part.")
    assert db.query(Lead).count() == 0


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def test_apollo_export_maps_with_the_builtin_preset_and_no_manual_change(client, auth_headers, db):
    headers = auth_headers()
    apollo = _fixture("apollo_export.csv")

    preview = client.post("/imports/preview", files={"file": ("apollo.csv", apollo)},
                          headers=headers)

    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["preset"] == "Apollo"
    assert body["row_count"] == 4
    mapping = body["mapping"]
    assert mapping["First Name"] == "first_name"
    assert mapping["Person Linkedin Url"] == "linkedin_url"
    assert mapping["Company Linkedin Url"] is None
    assert mapping["Apollo Contact Id"] is None

    res = _run_import(client, headers, apollo, mapping, file_name="apollo.csv", source="Apollo")

    report = res.json()
    assert (report["added"], report["updated"], report["skipped"]) == (3, 0, 1)
    neha = report["rows"][3]
    assert (neha["row"], neha["result"], neha["reason"]) == (5, "skipped", "no contact info")
    ravi = db.query(Lead).filter(Lead.first_name == "Ravi").one()
    assert (ravi.last_name, ravi.job_title, ravi.company, ravi.email) == (
        "Kumar", "Head of Growth", "Acme Analytics", "ravi.kumar@acmeanalytics.com")
    assert (ravi.phone, ravi.phone_2) == ("+91 98765 43210", "+91 80 4000 1000")
    assert ravi.linkedin_url == "http://www.linkedin.com/in/ravi-kumar-growth"
    assert (ravi.website, ravi.industry, ravi.company_size) == (
        "http://www.acmeanalytics.com", "Computer Software", "120")
    assert (ravi.city, ravi.country, ravi.source) == ("Pune", "India", "Apollo")
    meera = db.query(Lead).filter(Lead.first_name == "Meera").one()
    assert (meera.job_title, meera.phone, meera.city) == (
        "VP, Operations", "+91 22 6600 2000", "Mumbai")  # company city when person city is blank
    arjun = db.query(Lead).filter(Lead.first_name == "Arjun").one()
    assert (arjun.email, arjun.phone) == (None, "+91 99000 11122")


def _messy_workbook() -> bytes:
    """What a hand-made sheet looks like: a title, blank rows, odd headers."""
    from io import BytesIO

    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["Expo leads - Nov 2026"])
    sheet.append([])
    sheet.append(["Sr No", "Name", "Organisation", "Designation", " E-mail ID ", "Mobile No.",
                  "Phone", "City", None, "Remarks", "Remarks"])
    sheet.append([1, "Ravi Kumar", "Acme", "CEO", "Ravi@Acme.com ", 9876543210.0, None, "Pune",
                  None, "hot", "call Monday"])
    sheet.append([])
    sheet.append([2, "Meera Shah", "Globex", None, "meera@globex.io", None, None, None])
    sheet.append([3, "Arjun", "Initech", None, None, "+91-99000-11122", "080 4000 1000"])
    sheet.append([4, "Ravi K", None, None, None, "098765 43210", None, "Pune"])
    sheet.append([5, "No Contact", "Hooli", None, "-", None, None, "Delhi"])
    out = BytesIO()
    book.save(out)
    return out.getvalue()


def test_messy_excel_gets_sensible_suggestions_and_imports(client, auth_headers, db):
    headers = auth_headers()
    messy = _messy_workbook()

    preview = client.post("/imports/preview", files={"file": ("expo.xlsx", messy)},
                          headers=headers).json()

    assert preview["preset"] is None
    assert preview["row_count"] == 5
    assert preview["headers"] == ["Sr No", "Name", "Organisation", "Designation", "E-mail ID",
                                  "Mobile No.", "Phone", "City", "Column I", "Remarks",
                                  "Remarks (2)"]
    assert preview["mapping"] == {
        "Sr No": None, "Name": "full_name", "Organisation": "company",
        "Designation": "job_title", "E-mail ID": "email", "Mobile No.": "phone",
        "Phone": "phone_2", "City": "city", "Column I": None, "Remarks": None,
        "Remarks (2)": None,
    }
    assert preview["sample_rows"][0][:6] == ["1", "Ravi Kumar", "Acme", "CEO", "Ravi@Acme.com",
                                             "9876543210"]

    res = _run_import(client, headers, messy, preview["mapping"], file_name="expo.xlsx")

    report = res.json()
    assert [(r["row"], r["result"], r["reason"]) for r in report["rows"]] == [
        (4, "added", ""),
        (6, "added", ""),
        (7, "added", ""),
        (8, "skipped", "duplicate of row 4 in this file (merged)"),
        (9, "skipped", "no contact info"),
    ]
    ravi = db.query(Lead).filter(Lead.first_name == "Ravi").one()
    assert (ravi.last_name, ravi.email, ravi.phone, ravi.job_title) == (
        "Kumar", "ravi@acme.com", "9876543210", "CEO")
    arjun = db.query(Lead).filter(Lead.first_name == "Arjun").one()
    assert (arjun.phone, arjun.phone_2) == ("+91-99000-11122", "080 4000 1000")


def test_a_saved_preset_maps_the_next_file_from_the_same_tool(client, auth_headers):
    headers = auth_headers()
    mapping = {"Naam": "full_name", "Daak": "email", "Firm": "company", "Notes": None}

    res = client.post("/imports/presets", json={"name": "Expo sheet", "mapping": mapping},
                      headers=headers)
    assert res.status_code == 201, res.text

    presets = client.get("/imports/presets", headers=headers).json()
    assert [(p["name"], p["is_builtin"]) for p in presets] == [
        ("Apollo", True), ("Expo sheet", False)]
    assert presets[1]["mapping"] == mapping

    sheet = b"Naam,Daak,Firm,Notes\nRavi Kumar,ravi@acme.com,Acme,call later\n"
    preview = client.post("/imports/preview", files={"file": ("expo2.csv", sheet)},
                          headers=headers).json()
    assert preview["preset"] == "Expo sheet"
    assert preview["mapping"] == mapping


def test_saving_a_preset_again_replaces_it_but_builtin_ones_are_locked(client, auth_headers):
    headers = auth_headers()
    client.post("/imports/presets", json={"name": "Expo", "mapping": {"A": "email"}},
                headers=headers)

    res = client.post("/imports/presets", json={"name": "Expo", "mapping": {"B": "email"}},
                      headers=headers)
    assert res.status_code == 201
    expo = [p for p in client.get("/imports/presets", headers=headers).json()
            if p["name"] == "Expo"]
    assert [p["mapping"] for p in expo] == [{"B": "email"}]

    res = client.post("/imports/presets", json={"name": "apollo", "mapping": {"B": "email"}},
                      headers=headers)
    assert res.status_code == 409
    res = client.post("/imports/presets", json={"name": "Bad", "mapping": {"B": "salary"}},
                      headers=headers)
    assert res.status_code == 422


def test_preview_shows_the_first_rows_as_they_will_look_in_the_crm(client, auth_headers):
    headers = auth_headers()
    sheet = (b"Who,Mail,Mobile,Junk\n"
             + b"".join(f"Person {i} Kumar,P{i}@Acme.com,'98765 4321{i},x\n".encode()
                        for i in range(7)))
    mapping = {"Who": "full_name", "Mail": "email", "Mobile": "phone", "Junk": None}

    body = client.post("/imports/preview", files={"file": ("x.csv", sheet)},
                       data={"mapping": json.dumps(mapping)}, headers=headers).json()

    assert body["mapping"] == mapping
    assert body["row_count"] == 7
    assert len(body["sample_rows"]) == 5
    assert len(body["mapped_rows"]) == 5
    assert body["mapped_rows"][0] == {
        "first_name": "Person", "last_name": "0 Kumar", "email": "p0@acme.com",
        "phone": "98765 43210"}


def test_bad_import_settings_are_refused(client, auth_headers, db):
    headers = auth_headers()

    res = _run_import(client, headers, SIMPLE_CSV, SIMPLE_MAPPING, source="Facebook")
    assert res.status_code == 422
    res = _run_import(client, headers, SIMPLE_CSV, {"Name": "salary"})
    assert res.status_code == 422
    assert "mapping is not valid" in res.json()["detail"]
    res = _run_import(client, headers, SIMPLE_CSV, {"Name": "full_name", "Company": "company"})
    assert res.status_code == 422
    assert res.json()["detail"] == "Map at least one column to Email, Phone or LinkedIn URL"
    assert db.query(Lead).count() == 0


def test_new_rows_without_a_name_are_skipped_but_can_still_fill_an_existing_lead(
        client, auth_headers, db):
    headers = auth_headers()
    client.post("/leads", json={"first_name": "Meera", "email": "meera@globex.io"}, headers=headers)
    csv_file = b"Name,Email,City\n,nobody@acme.com,Pune\n,meera@globex.io,Mumbai\n"

    res = _run_import(client, headers, csv_file,
                      {"Name": "full_name", "Email": "email", "City": "city"})

    assert [(r["row"], r["result"], r["reason"]) for r in res.json()["rows"]] == [
        (2, "skipped", "no name"),
        (3, "updated", ""),
    ]
    assert db.query(Lead).one().city == "Mumbai"


def test_import_history_lists_who_when_file_source_and_counts(client, auth_headers, make_user):
    headers = auth_headers(name="Asha")
    _run_import(client, headers, SIMPLE_CSV, SIMPLE_MAPPING, file_name="first.csv",
                source="Event")
    _run_import(client, headers, SIMPLE_CSV, SIMPLE_MAPPING, file_name="again.csv",
                source="Apollo")

    res = client.get("/imports", headers=headers)

    assert res.status_code == 200
    history = res.json()
    assert [(h["file_name"], h["source"], h["user"], h["added"], h["updated"], h["skipped"])
            for h in history] == [
        ("again.csv", "Apollo", "Asha", 0, 0, 2),
        ("first.csv", "Event", "Asha", 2, 0, 0),
    ]
    assert datetime.fromisoformat(history[0]["created_at"]).tzinfo is not None


def test_report_downloads_as_xlsx_with_the_original_rows(client, auth_headers):
    from io import BytesIO

    from openpyxl import load_workbook

    headers = auth_headers()
    csv_file = b"Name,Email\nRavi Kumar,ravi@acme.com\nNo Contact,\n"
    report = _run_import(client, headers, csv_file, PEOPLE_MAPPING).json()
    assert report["headers"] == ["Name", "Email"]
    assert report["rows"][1]["values"] == ["No Contact", ""]

    res = client.post("/imports/report", json=report, headers=headers)

    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "import-report" in res.headers["content-disposition"]
    sheet = load_workbook(BytesIO(res.content)).active
    assert [list(r) for r in sheet.iter_rows(values_only=True)] == [
        ["Row", "Result", "Reason", "Name", "Email"],
        [2, "added", None, "Ravi Kumar", "ravi@acme.com"],
        [3, "skipped", "no contact info", "No Contact", None],
    ]


def test_report_rows_name_the_person_and_list_the_fields_filled(client, auth_headers):
    headers = auth_headers()
    _run_import(client, headers, b"Name,Email\nRavi Kumar,ravi@acme.com\n",
                {"Name": "full_name", "Email": "email"})
    csv_file = (b"Name,Email,Phone,City\n"
                b"Ravi Kumar,ravi@acme.com,9876543210,Pune\n"
                b"Meera Shah,meera@globex.io,,\n"
                b"No Contact,,,Delhi\n")

    res = _run_import(client, headers, csv_file,
                      {"Name": "full_name", "Email": "email", "Phone": "phone", "City": "city"})

    rows = {r["row"]: r for r in res.json()["rows"]}
    assert (rows[2]["result"], rows[2]["name"], rows[2]["filled"]) == ("updated", "Ravi Kumar", ["phone", "city"])
    assert (rows[3]["result"], rows[3]["name"], rows[3]["filled"]) == ("added", "Meera Shah", [])
    assert (rows[4]["result"], rows[4]["name"]) == ("skipped", "No Contact")


def test_leads_can_be_filtered_to_the_ones_one_import_added(client, auth_headers):
    headers = auth_headers()
    client.post("/leads", headers=headers, json={"first_name": "Old", "email": "old@acme.com"})
    _run_import(client, headers, b"Name,Email\nFirst Run,first@acme.com\n",
                {"Name": "full_name", "Email": "email"})
    csv_file = (b"Name,Email,City\n"
                b"Ravi Kumar,ravi@acme.com,\n"
                b"Meera Shah,meera@globex.io,\n"
                b"Old Lead,old@acme.com,Pune\n")  # existing lead: updated, not added

    report = _run_import(client, headers, csv_file,
                         {"Name": "full_name", "Email": "email", "City": "city"}).json()

    res = client.get("/leads", params={"import": report["import_uuid"]}, headers=headers)
    assert res.status_code == 200, res.text
    assert sorted(l["first_name"] for l in res.json()["items"]) == ["Meera", "Ravi"]
