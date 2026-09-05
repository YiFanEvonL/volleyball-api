from sqlalchemy import String, Integer, Date, Time, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location: Mapped[str] = mapped_column(String(255))
    date: Mapped[Date] = mapped_column(Date)
    start_time: Mapped[Time] = mapped_column(Time)
    max_players: Mapped[int] = mapped_column(Integer, default=18)
    fee_cents: Mapped[int] = mapped_column(Integer)  # e.g. 1500 = $15.00
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|full|completed|cancelled
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    registrations = relationship("Registration", back_populates="session")
    waitlist_entries = relationship("WaitlistEntry", back_populates="session")
