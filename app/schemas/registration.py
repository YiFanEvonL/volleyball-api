from pydantic import BaseModel
from uuid import UUID

class RegisterResponse(BaseModel):
    registration_id: UUID
    client_secret: str  # 回給前端讓 Stripe SDK 完成付款
    amount_cents: int
