"""Phase 4: GET /leads/export — the current filtered list as an .xlsx file."""

from io import BytesIO

from openpyxl import load_workbook


def _add_lead(client, headers, first_name, **fields):
    body = {"first_name": first_name, "email": f"{first_name.lower()}@example.com", **fields}
    res = client.post("/leads", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _sheet_rows(res):
    sheet = load_workbook(BytesIO(res.content)).active
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    return header, [dict(zip(header, row)) for row in rows[1:]]


def test_export_is_an_xlsx_of_the_filtered_list_with_all_fields(client, auth_headers, db):
    from datetime import datetime
    from models import Lead

    headers = auth_headers(name="Asha")
    hot = _add_lead(client, headers, "Ravi", last_name="Kumar", company="Acme",
                    phone="+91 98765 43210", priority="hot", source="Apollo")
    _add_lead(client, headers, "Cold", priority="cold")
    client.patch(f"/leads/{hot['uuid']}", json={"status": "Interested"}, headers=headers)
    client.post(f"/leads/{hot['uuid']}/notes", json={"body": "Asked for pricing"}, headers=headers)
    client.post(f"/leads/{hot['uuid']}/notes", json={"body": "Call back Monday"}, headers=headers)
    lead = db.query(Lead).filter(Lead.first_name == "Ravi").one()
    lead.created_at = datetime(2026, 11, 10, 4, 30)  # 10:00 IST
    db.commit()

    res = client.get("/leads/export", params={"priority": "hot", "tz_offset": 330},
                     headers=headers)

    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "attachment" in res.headers["content-disposition"]
    assert ".xlsx" in res.headers["content-disposition"]
    header, rows = _sheet_rows(res)
    for column in ("First name", "Last name", "Company", "Email", "Phone", "LinkedIn URL",
                   "Source", "Priority", "Status", "Owner", "Calls", "Last called",
                   "Next follow-up", "Added to CRM", "Added by", "Notes"):
        assert column in header
    assert len(rows) == 1  # only the hot lead
    row = rows[0]
    assert (row["First name"], row["Company"], row["Phone"]) == ("Ravi", "Acme", "+91 98765 43210")
    assert (row["Status"], row["Owner"], row["Priority"], row["Source"]) == \
        ("Interested", "Asha", "Hot", "Apollo")
    assert row["Added to CRM"] == datetime(2026, 11, 10, 10, 0)  # shown in local time
    assert row["Added by"] == "Asha"
    # Every note, newest first, each signed.
    notes = row["Notes"].split("\n")
    assert len(notes) == 2
    assert notes[0].endswith("Asha: Call back Monday")
    assert notes[1].endswith("Asha: Asked for pricing")


def test_export_bulk_and_list_need_a_login(client):
    assert client.get("/leads/export").status_code == 401
    assert client.post("/leads/bulk", json={"uuids": ["x"], "action": "delete"}).status_code == 401
    assert client.get("/leads", params={"q": "x"}).status_code == 401
