import httpx
from uuid import UUID

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

async def send_push_notification(expo_token: str, title: str, body: str, data: dict = {}) -> None:
    """
    Send push notification via Expo Push API.
    expo_token: the player's Expo push token (stored on User model, to be added later)
    """
    message = {
        "to": expo_token,
        "title": title,
        "body": body,
        "data": data,
        "sound": "default",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(EXPO_PUSH_URL, json=message)
        response.raise_for_status()


async def notify_waitlist_spot_available(
    expo_token: str,
    session_date: str,
    session_location: str,
    waitlist_id: UUID,
    expires_minutes: int = 120,
) -> None:
    """Notify a waitlisted player that a spot has opened up."""
    await send_push_notification(
        expo_token=expo_token,
        title="A spot opened up! 🏐",
        body=f"Your waitlist spot for {session_date} at {session_location} is available. You have {expires_minutes} minutes to claim it.",
        data={"waitlist_id": str(waitlist_id), "action": "claim_spot"},
    )
