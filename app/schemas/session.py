from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date, time
from typing import Optional

class SessionCreate(BaseModel):
    location: str = Field(..., example="North York Community Centre, Court 1")
    date: date = Field(..., example="2026-09-15")
    start_time: time = Field(..., example="19:00:00")
    max_players: int = Field(default=18, ge=1, le=30)
    fee_cents: int = Field(..., ge=0, example=1500, description="Fee in cents, e.g. 1500 = $15.00")

class SessionUpdate(BaseModel):
    location: Optional[str] = None
    date: Optional[date] = None
    start_time: Optional[time] = None
    max_players: Optional[int] = Field(default=None, ge=1, le=30)
    fee_cents: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None, pattern="^(open|full|completed|cancelled)$")

class SessionResponse(BaseModel):
    id: UUID
    location: str
    date: date
    start_time: time
    max_players: int
    fee_cents: int
    status: str
    confirmed_count: int
    waitlist_count: int
    spots_remaining: int

    class Config:
        from_attributes = True
