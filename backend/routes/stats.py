"""
routes/stats.py
---------------
Numbers for the analytics strip and the Team stats page. Any logged-in user.

GET /stats/summary?scope=me|team&from=YYYY-MM-DD&to=YYYY-MM-DD&tz_offset=330
    cards, 10-stage funnel, calls per day, leads added per day, leads by source
GET /stats/team?from=&to=&tz_offset=
    one row per person: calls, meetings booked, won, leads by current status

`from` and `to` are the user's local dates, both included. `tz_offset` is the
user's local time minus UTC in minutes (IST = 330).
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import stats_engine
from auth import get_current_user
from database import get_db
from models import User
from schemas import StatsSummary, TeamStats

router = APIRouter(prefix="/stats", tags=["stats"])


def stats_period(
    start: date = Query(alias="from"),
    end: date = Query(alias="to"),
    tz_offset: int = Query(default=0, ge=-14 * 60, le=14 * 60,
                           description="local time minus UTC, in minutes (IST = 330)"),
) -> stats_engine.Period:
    try:
        return stats_engine.Period(start=start, end=end, tz_offset=tz_offset)
    except stats_engine.PeriodError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err))


@router.get("/summary", response_model=StatsSummary)
def summary(
    scope: Literal["me", "team"] = "me",
    period: stats_engine.Period = Depends(stats_period),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stats_engine.summary(db, period, user=user if scope == "me" else None)


@router.get("/team", response_model=TeamStats)
def team(
    period: stats_engine.Period = Depends(stats_period),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stats_engine.team_table(db, period)
