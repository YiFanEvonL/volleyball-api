from pydantic import BaseModel
from uuid import UUID

class WaitlistJoinResponse(BaseModel):
    waitlist_id: UUID
    position: int
    message: str

class ClaimSpotResponse(BaseModel):
    requires_payment: bool
    client_secret: str | None = None   # present only when Stripe charge is needed
    amount_cents: int | None = None
    registration_id: str | None = None  # present when fully covered by credit
