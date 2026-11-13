"""
routes/imports.py
-----------------
Import leads from a file. All routes need a valid login.

POST /imports/preview   multipart: file, optional mapping -> { headers, row_count,
                        sample_rows, mapping (suggested, or the one sent), preset,
                        mapped_rows (first 5 rows as they will look in the CRM) }
POST /imports/report    the report body -> .xlsx (Row, Result, Reason + the file's columns)
GET  /imports           history, newest first -> [{ file_name, source, user, counts, created_at }]
GET  /imports/presets   saved column mappings, built-in first
POST /imports/presets   { name, mapping } save (same name = replace; built-in ones are locked)
POST /imports           multipart: file, mapping (JSON: file header -> CRM field),
                        source, assign_to (user uuid | split | unassigned)
                        -> report { import_uuid, added, updated, skipped, headers, rows }
                        (GET /leads?import=<import_uuid> lists the leads it added)
                        All or nothing: a row the database refuses rolls it all back.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session, joinedload

import import_engine
from auth import get_current_user
from database import get_db
from models import Import, ImportPreset, User
from schemas import (
    ImportMapping, ImportOut, ImportPreview, ImportReport, PresetIn, PresetOut, Source,
)

router = APIRouter(prefix="/imports", tags=["imports"])

PREVIEW_ROWS = 5
_mapping_adapter = TypeAdapter(ImportMapping)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _parse_mapping(raw: str) -> dict:
    """The mapping form field: JSON {file header: CRM field or null}."""
    try:
        return _mapping_adapter.validate_json(raw)
    except ValidationError:
        raise _unprocessable("The column mapping is not valid. Choose a CRM field "
                             "or Skip for each column.")


async def _read_upload(file: UploadFile) -> import_engine.FileData:
    try:
        return import_engine.read_file(
            file.filename, await file.read(import_engine.MAX_FILE_BYTES + 1))
    except import_engine.ImportRefused as err:
        raise _unprocessable(str(err))


@router.post("/preview", response_model=ImportPreview)
async def preview_import(
    file: UploadFile = File(...),
    mapping: str | None = Form(None, description="omit to get a suggested mapping"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await _read_upload(file)
    if mapping is None:
        chosen, preset = import_engine.suggest_mapping(data.headers, db.query(ImportPreset).all())
    else:
        chosen, preset = _parse_mapping(mapping), None
    return ImportPreview(
        file_name=data.file_name, headers=data.headers, row_count=len(data.rows),
        sample_rows=[cells for _, cells in data.rows[:PREVIEW_ROWS]],
        mapping=chosen, preset=preset,
        mapped_rows=import_engine.preview_rows(data, chosen, PREVIEW_ROWS),
    )


@router.post("", response_model=ImportReport)
async def run_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    source: Source = Form(...),
    assign_to: str = Form("unassigned"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = await _read_upload(file)
    chosen = _parse_mapping(mapping)
    if not set(import_engine.CONTACT_FIELDS) & set(chosen.values()):
        raise _unprocessable("Map at least one column to Email, Phone or LinkedIn URL")
    try:
        owners = import_engine.owners_for(db, assign_to)
    except import_engine.ImportRefused as err:
        raise _unprocessable(str(err))
    plan = import_engine.build_plan(db, data, chosen)
    try:
        record = import_engine.apply_plan(db, plan, data, source, owners, user)
    except import_engine.ImportRowError as err:
        db.rollback()
        raise _unprocessable(str(err))
    db.commit()
    return ImportReport(
        import_uuid=record.uuid, added=record.added, updated=record.updated, skipped=record.skipped,
        headers=data.headers, rows=[vars(r) for r in plan.results],
    )


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/report")
def download_report(report: ImportReport, user: User = Depends(get_current_user)):
    """The report a run returned, as .xlsx (nothing is stored server-side)."""
    content = import_engine.report_workbook(
        report.headers, [row.model_dump() for row in report.rows])
    return Response(content=content, media_type=XLSX_TYPE, headers={
        "Content-Disposition": 'attachment; filename="import-report.xlsx"'})


HISTORY_LIMIT = 200


@router.get("", response_model=list[ImportOut])
def import_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = (db.query(Import).options(joinedload(Import.user))
               .order_by(Import.created_at.desc(), Import.id.desc())
               .limit(HISTORY_LIMIT).all())
    return [ImportOut.from_import(r) for r in records]


@router.get("/presets", response_model=list[PresetOut])
def list_presets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (db.query(ImportPreset)
            .order_by(ImportPreset.is_builtin.desc(), ImportPreset.name).all())


@router.post("/presets", response_model=PresetOut, status_code=status.HTTP_201_CREATED)
def save_preset(
    payload: PresetIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Names compare without case (MySQL's default collation), so "apollo" is "Apollo".
    preset = db.query(ImportPreset).filter(ImportPreset.name == payload.name).first()
    if preset is not None and preset.is_builtin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"{preset.name} is a built-in preset. Choose another name.")
    if preset is None:
        preset = ImportPreset(name=payload.name, is_builtin=False)
        db.add(preset)
    preset.mapping = payload.mapping
    db.commit()
    return preset
