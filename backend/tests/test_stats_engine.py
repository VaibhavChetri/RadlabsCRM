"""Phase 6: the Stats engine, over a hand-made dataset with fixed times.

Times in the DB are naive UTC. The team is in IST (UTC+5:30), so the period
is read in IST local dates: tz_offset = 330.
"""

from datetime import date, datetime, timedelta

import pytest

import stats_engine
from models import Call, Lead, Status, StatusChange

IST = 330


def ist(day: str, hh: int = 12, mm: int = 0) -> datetime:
    """An IST wall-clock time, stored as naive UTC."""
    local = datetime.fromisoformat(day).replace(hour=hh, minute=mm)
    return local - timedelta(minutes=IST)


def period(start: str, end: str) -> stats_engine.Period:
    return stats_engine.Period(start=date.fromisoformat(start), end=date.fromisoformat(end),
                               tz_offset=IST)


def _status_id(db, name):
    return db.query(Status).filter(Status.name == name).one().id


def add_lead(db, user, added: datetime, owner="creator", status="New", source="Other",
             name="Ravi", **fields):
    """A lead added at `added`, with its first none -> New history row."""
    owner_user = user if owner == "creator" else owner
    lead = Lead(first_name=name, email=f"{name.lower()}-{added.timestamp()}@acme.com",
                source=source, status_id=_status_id(db, status),
                owner_id=owner_user.id if owner_user else None,
                created_by=user.id, created_at=added, updated_at=added, **fields)
    db.add(lead)
    db.flush()
    db.add(StatusChange(lead_id=lead.id, from_status_id=None, to_status_id=_status_id(db, "New"),
                        user_id=user.id, changed_at=added))
    db.commit()
    return lead


def add_call(db, lead, user, at: datetime):
    db.add(Call(lead_id=lead.id, user_id=user.id, called_at=at))
    db.commit()


def test_team_calls_count_only_calls_inside_the_period(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    lead = add_lead(db, asha, ist("2026-11-01"))
    add_call(db, lead, asha, ist("2026-11-02", 0, 10))   # first minutes of the 2nd, IST
    add_call(db, lead, asha, ist("2026-11-08", 23, 50))  # last minutes of the 8th, IST
    add_call(db, lead, asha, ist("2026-11-01", 23, 59))  # day before: out
    add_call(db, lead, asha, ist("2026-11-09", 0, 1))    # day after: out

    result = stats_engine.summary(db, period("2026-11-02", "2026-11-08"), user=None)

    assert result["cards"]["calls"] == 2


def test_me_scope_counts_only_my_calls(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    lead = add_lead(db, asha, ist("2026-11-01"))
    add_call(db, lead, asha, ist("2026-11-03"))
    add_call(db, lead, vikram, ist("2026-11-03"))
    add_call(db, lead, vikram, ist("2026-11-04"))

    week = period("2026-11-02", "2026-11-08")

    assert stats_engine.summary(db, week, user=asha)["cards"]["calls"] == 1
    assert stats_engine.summary(db, week, user=vikram)["cards"]["calls"] == 2
    assert stats_engine.summary(db, week, user=None)["cards"]["calls"] == 3


def test_calls_per_day_has_every_day_of_the_period_by_local_date(db, make_user):
    asha = make_user()
    lead = add_lead(db, asha, ist("2026-11-01"))
    add_call(db, lead, asha, ist("2026-11-02", 0, 15))  # 1 Nov in UTC, 2 Nov in IST
    add_call(db, lead, asha, ist("2026-11-04", 9))
    add_call(db, lead, asha, ist("2026-11-04", 18))

    result = stats_engine.summary(db, period("2026-11-02", "2026-11-05"), user=None)

    assert result["calls_per_day"] == [
        {"date": "2026-11-02", "count": 1},
        {"date": "2026-11-03", "count": 0},
        {"date": "2026-11-04", "count": 2},
        {"date": "2026-11-05", "count": 0},
    ]


def test_leads_added_counts_leads_added_in_the_period_me_means_owned_by_me(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    add_lead(db, asha, ist("2026-11-02", 9), name="A1")
    add_lead(db, asha, ist("2026-11-04", 9), name="A2")
    add_lead(db, asha, ist("2026-11-04", 10), owner=vikram, name="V1")  # Asha imported it for Vikram
    add_lead(db, asha, ist("2026-11-04", 11), owner=None, name="U1")    # unassigned
    add_lead(db, asha, ist("2026-11-06", 9), name="Late")               # after the period

    days = period("2026-11-02", "2026-11-04")
    team = stats_engine.summary(db, days, user=None)
    mine = stats_engine.summary(db, days, user=asha)

    assert team["cards"]["leads_added"] == 4
    assert [d["count"] for d in team["added_per_day"]] == [1, 0, 3]
    assert mine["cards"]["leads_added"] == 2
    assert [d["count"] for d in mine["added_per_day"]] == [1, 0, 1]
    assert stats_engine.summary(db, days, user=vikram)["cards"]["leads_added"] == 1


def move(db, lead, to_status, user, at: datetime):
    """A status change at a fixed time (what lead_service writes, with a chosen time)."""
    to_id = _status_id(db, to_status)
    db.add(StatusChange(lead_id=lead.id, from_status_id=lead.status_id, to_status_id=to_id,
                        user_id=user.id, changed_at=at))
    lead.status_id = to_id
    db.commit()


def test_meetings_booked_and_won_count_status_changes_made_in_the_period(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    a = add_lead(db, asha, ist("2026-10-20"), name="A")
    b = add_lead(db, asha, ist("2026-10-20"), name="B")
    c = add_lead(db, asha, ist("2026-10-20"), name="C")
    move(db, a, "Meeting booked", asha, ist("2026-11-03"))
    move(db, a, "Won", asha, ist("2026-11-05"))
    move(db, a, "Lost", vikram, ist("2026-11-20"))          # later: still Won in the period
    move(db, b, "Meeting booked", vikram, ist("2026-11-04"))
    move(db, c, "Meeting booked", asha, ist("2026-10-30"))  # before the period
    move(db, c, "Won", vikram, ist("2026-11-06"))

    week = period("2026-11-02", "2026-11-08")
    team = stats_engine.summary(db, week, user=None)["cards"]
    asha_cards = stats_engine.summary(db, week, user=asha)["cards"]

    assert (team["meetings_booked"], team["won"]) == (2, 2)
    assert (asha_cards["meetings_booked"], asha_cards["won"]) == (1, 1)


def test_a_lead_moved_into_a_stage_twice_counts_once(db, make_user):
    asha = make_user()
    a = add_lead(db, asha, ist("2026-10-20"))
    move(db, a, "Won", asha, ist("2026-11-03"))
    move(db, a, "Proposal sent", asha, ist("2026-11-04"))
    move(db, a, "Won", asha, ist("2026-11-05"))

    cards = stats_engine.summary(db, period("2026-11-02", "2026-11-08"), user=None)["cards"]

    assert cards["won"] == 1


def test_conversion_is_won_divided_by_leads_added_in_the_period(db, make_user):
    asha = make_user()
    old = add_lead(db, asha, ist("2026-10-20"), name="Old")  # added before, won inside
    for n in range(3):
        add_lead(db, asha, ist("2026-11-03"), name=f"New{n}")
    move(db, old, "Won", asha, ist("2026-11-04"))

    week = stats_engine.summary(db, period("2026-11-02", "2026-11-08"), user=None)["cards"]
    empty = stats_engine.summary(db, period("2026-12-01", "2026-12-07"), user=None)["cards"]

    assert week["conversion_pct"] == 33.3  # 1 won / 3 added
    assert empty["conversion_pct"] is None  # nothing added: no rate, not 0 %


def test_total_leads_and_funnel_show_current_status_of_every_lead(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    add_lead(db, asha, ist("2025-01-01"), name="Ancient")  # added long ago: still counted
    add_lead(db, asha, ist("2026-11-03"), status="Interested", name="I1")
    add_lead(db, asha, ist("2026-11-03"), owner=vikram, status="Interested", name="I2")
    add_lead(db, asha, ist("2026-11-03"), owner=vikram, status="Won", name="W1")

    week = period("2026-11-02", "2026-11-08")
    team = stats_engine.summary(db, week, user=None)
    mine = stats_engine.summary(db, week, user=asha)

    assert team["cards"]["total_leads"] == 4
    assert mine["cards"]["total_leads"] == 2
    assert [row["status"] for row in team["funnel"]] == [
        "New", "Attempted", "Connected", "Interested", "Meeting booked", "Proposal sent",
        "Won", "Lost", "Not interested", "Do not call",
    ]
    counts = {row["status"]: row["count"] for row in team["funnel"]}
    assert (counts["New"], counts["Interested"], counts["Won"], counts["Lost"]) == (1, 2, 1, 0)
    assert team["funnel"][6]["is_exit"] is True
    assert {row["status"]: row["count"] for row in mine["funnel"]}["Interested"] == 1


def test_follow_ups_due_counts_open_leads_with_a_follow_up_in_the_period(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    for name, follow_up, status, owner in [
        ("First", date(2026, 11, 2), "Attempted", asha),
        ("Last", date(2026, 11, 8), "New", asha),
        ("Theirs", date(2026, 11, 5), "Connected", vikram),
        ("Before", date(2026, 11, 1), "Attempted", asha),
        ("After", date(2026, 11, 9), "Attempted", asha),
        ("Closed", date(2026, 11, 5), "Won", asha),        # exit stage: nothing to call
        ("Dnc", date(2026, 11, 5), "Do not call", asha),
    ]:
        add_lead(db, asha, ist("2026-10-20"), owner=owner, status=status, name=name,
                 next_follow_up=follow_up)

    week = period("2026-11-02", "2026-11-08")

    assert stats_engine.summary(db, week, user=None)["cards"]["follow_ups_due"] == 3
    assert stats_engine.summary(db, week, user=asha)["cards"]["follow_ups_due"] == 2


def test_by_source_counts_leads_added_in_the_period_for_every_source(db, make_user):
    asha = make_user()
    add_lead(db, asha, ist("2026-11-03"), source="Apollo", name="A1")
    add_lead(db, asha, ist("2026-11-04"), source="Apollo", name="A2")
    add_lead(db, asha, ist("2026-11-04"), source="Referral", name="R1")
    add_lead(db, asha, ist("2026-10-01"), source="Event", name="Old")  # before the period

    result = stats_engine.summary(db, period("2026-11-02", "2026-11-08"), user=None)

    assert result["by_source"] == [
        {"source": "Apollo", "count": 2},
        {"source": "LinkedIn", "count": 0},
        {"source": "Referral", "count": 1},
        {"source": "Event", "count": 0},
        {"source": "Cold list", "count": 0},
        {"source": "Other", "count": 0},
    ]


def test_team_table_has_one_row_per_person_with_their_numbers(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    a = add_lead(db, asha, ist("2026-10-20"), name="A")
    b = add_lead(db, asha, ist("2026-10-20"), owner=vikram, name="B")
    add_lead(db, asha, ist("2026-10-20"), owner=vikram, status="Interested", name="C")
    add_call(db, a, asha, ist("2026-11-03"))
    add_call(db, b, asha, ist("2026-11-03"))
    add_call(db, b, vikram, ist("2026-11-04"))
    add_call(db, b, vikram, ist("2026-10-30"))  # before the period
    move(db, b, "Meeting booked", vikram, ist("2026-11-04"))
    move(db, a, "Won", asha, ist("2026-11-05"))

    table = stats_engine.team_table(db, period("2026-11-02", "2026-11-08"))

    assert table["statuses"][0] == "New" and len(table["statuses"]) == 10
    rows = {row["name"]: row for row in table["rows"]}
    assert list(rows) == ["Asha", "Vikram"]
    assert rows["Asha"]["uuid"] == asha.uuid and rows["Asha"]["is_active"] is True
    assert (rows["Asha"]["calls"], rows["Asha"]["meetings_booked"], rows["Asha"]["won"]) == (2, 0, 1)
    assert (rows["Vikram"]["calls"], rows["Vikram"]["meetings_booked"], rows["Vikram"]["won"]) == (1, 1, 0)
    # Leads by status = leads they own now.
    assert rows["Asha"]["leads"] == 1 and rows["Asha"]["by_status"]["Won"] == 1
    assert rows["Vikram"]["leads"] == 2
    assert rows["Vikram"]["by_status"]["Meeting booked"] == 1
    assert rows["Vikram"]["by_status"]["Interested"] == 1
    assert rows["Vikram"]["by_status"]["New"] == 0


def test_team_table_keeps_deactivated_users_only_when_they_had_activity(db, make_user):
    asha = make_user(name="Asha", email="asha@example.com")
    left = make_user(name="Left", email="left@example.com", is_active=False)
    gone = make_user(name="Gone", email="gone@example.com", is_active=False)
    lead = add_lead(db, asha, ist("2026-10-20"))
    add_call(db, lead, left, ist("2026-11-03"))  # Left called in the period, then left the team
    add_call(db, lead, gone, ist("2026-10-01"))  # Gone's activity is all before the period

    table = stats_engine.team_table(db, period("2026-11-02", "2026-11-08"))
    rows = {row["name"]: row for row in table["rows"]}

    assert list(rows) == ["Asha", "Left"]
    assert rows["Left"]["is_active"] is False and rows["Left"]["calls"] == 1

    older = stats_engine.team_table(db, period("2026-09-28", "2026-10-04"))
    assert [row["name"] for row in older["rows"]] == ["Asha", "Gone"]


@pytest.fixture
def five_weeks(db, make_user):
    """Two callers, five leads, seven calls and five stage moves from 27 Oct to 19 Nov.

    Lead  added   owner   source    later
    L1    27 Oct  Asha    Apollo    Meeting booked 4 Nov (Asha), Won 10 Nov (Asha)
    L2     3 Nov  Asha    Apollo    Lost 13 Nov (Asha)
    L3     5 Nov  Vikram  LinkedIn  Meeting booked 7 Nov (Vikram), Won 14 Nov (Vikram)
    L4    12 Nov  Vikram  Referral
    L5    18 Nov  Asha    Apollo
    Calls: Asha 28 Oct, 2 Nov, 4 Nov, 13 Nov · Vikram 6 Nov (x2), 19 Nov
    """
    asha = make_user(name="Asha", email="asha@example.com")
    vikram = make_user(name="Vikram", email="vikram@example.com")
    l1 = add_lead(db, asha, ist("2026-10-27"), source="Apollo", name="L1")
    l2 = add_lead(db, asha, ist("2026-11-03"), source="Apollo", name="L2")
    l3 = add_lead(db, asha, ist("2026-11-05"), owner=vikram, source="LinkedIn", name="L3")
    l4 = add_lead(db, asha, ist("2026-11-12"), owner=vikram, source="Referral", name="L4")
    add_lead(db, asha, ist("2026-11-18"), source="Apollo", name="L5")
    for lead, user, day in [(l1, asha, "2026-10-28"), (l1, asha, "2026-11-02"),
                            (l2, asha, "2026-11-04"), (l2, asha, "2026-11-13"),
                            (l3, vikram, "2026-11-06"), (l3, vikram, "2026-11-06"),
                            (l4, vikram, "2026-11-19")]:
        add_call(db, lead, user, ist(day))
    move(db, l1, "Meeting booked", asha, ist("2026-11-04"))
    move(db, l3, "Meeting booked", vikram, ist("2026-11-07"))
    move(db, l1, "Won", asha, ist("2026-11-10"))
    move(db, l2, "Lost", asha, ist("2026-11-13"))
    move(db, l3, "Won", vikram, ist("2026-11-14"))
    return asha, vikram


CARD_KEYS = ("leads_added", "calls", "meetings_booked", "won", "conversion_pct")


@pytest.mark.parametrize("start, end, expected", [
    ("2026-11-02", "2026-11-08", (2, 4, 2, 0, 0.0)),   # this week
    ("2026-11-01", "2026-11-30", (4, 6, 2, 2, 50.0)),  # this month
    ("2026-10-26", "2026-11-14", (4, 6, 2, 2, 50.0)),  # custom, both ends included
])
def test_team_cards_match_the_hand_count(db, five_weeks, start, end, expected):
    cards = stats_engine.summary(db, period(start, end), user=None)["cards"]

    assert tuple(cards[key] for key in CARD_KEYS) == expected
    assert cards["total_leads"] == 5


def test_me_cards_and_team_table_match_the_hand_count(db, five_weeks):
    asha, _ = five_weeks
    month = period("2026-11-01", "2026-11-30")

    cards = stats_engine.summary(db, month, user=asha)["cards"]
    rows = {row["name"]: row for row in stats_engine.team_table(db, month)["rows"]}

    assert tuple(cards[key] for key in CARD_KEYS) == (2, 3, 1, 1, 50.0)  # added = L2, L5
    assert cards["total_leads"] == 3
    assert (rows["Asha"]["calls"], rows["Asha"]["meetings_booked"], rows["Asha"]["won"]) == (3, 1, 1)
    assert (rows["Vikram"]["calls"], rows["Vikram"]["meetings_booked"], rows["Vikram"]["won"]) == (3, 1, 1)
    assert rows["Asha"]["by_status"] == {**dict.fromkeys(rows["Asha"]["by_status"], 0),
                                         "Won": 1, "Lost": 1, "New": 1}
