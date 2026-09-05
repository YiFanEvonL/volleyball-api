from fastapi import FastAPI
from app.routers import auth, sessions, registrations, waitlist, users, webhooks

app = FastAPI(
    title="Volleyball League API",
    description="Waitlist and payment management for recreational volleyball leagues.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(registrations.router)
app.include_router(waitlist.router)
app.include_router(users.router)
app.include_router(webhooks.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
