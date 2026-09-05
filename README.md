# Volleyball League API

Waitlist and payment management for recreational volleyball leagues.

## Tech Stack
- **FastAPI** + Python 3.12
- **PostgreSQL** (via asyncpg)
- **SQLAlchemy 2.0** (async ORM)
- **Alembic** (migrations)
- **Stripe** (payments)
- **Expo Push** (notifications)
- **Google / Apple OAuth** (auth)

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```
Fill in your values:
| Variable | Where to get it |
|----------|----------------|
| `DATABASE_URL` | Your PostgreSQL connection string |
| `STRIPE_SECRET_KEY` | Stripe Dashboard → Developers → API keys |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard → Webhooks → signing secret |
| `GOOGLE_CLIENT_ID` | Google Cloud Console → OAuth 2.0 |
| `APPLE_CLIENT_ID` | Apple Developer → Certificates → Service ID |
| `JWT_SECRET` | Any long random string |

### 3. Run migrations
```bash
alembic upgrade head
```

### 4. Start the server
```bash
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

---

## API Overview

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/google` | Login with Google |
| POST | `/auth/apple` | Login with Apple |
| POST | `/auth/logout` | Logout |

### Sessions
| Method | Path | Auth |
|--------|------|------|
| GET | `/sessions` | All users |
| GET | `/sessions/{id}` | All users |
| POST | `/sessions` | Admin only |
| PATCH | `/sessions/{id}` | Admin only |
| DELETE | `/sessions/{id}` | Admin only |

### Registration
| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions/{id}/register` | Register + create Stripe PaymentIntent |
| DELETE | `/registrations/{id}` | Cancel → credit refund → notify waitlist |

### Waitlist
| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions/{id}/waitlist` | Join waitlist |
| POST | `/waitlist/{id}/claim` | Claim an offered spot |

### Users
| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/me` | Profile + credit balance |
| GET | `/users/me/registrations` | Registration history |
| GET | `/users/me/transactions` | Transaction history |

---

## Key Flows

### Registration
```
POST /sessions/{id}/register
  → Validate session is open + user not already registered
  → Create Stripe PaymentIntent
  → Return client_secret to frontend
  → Frontend completes payment via Stripe SDK
  → Stripe webhook → confirm_registration()
  → Write Transaction, update session status if full
```

### Cancellation → Waitlist Notify
```
DELETE /registrations/{id}
  → Mark registration cancelled
  → Add fee to user credit_balance
  → Reopen session
  → Notify first waiting player (2-hour claim window)
```

### Waitlist Claim
```
POST /waitlist/{id}/claim
  → Check not expired
  → Deduct credit first, charge Stripe for remainder
  → Confirm registration
  → Mark waitlist entry as converted
```

## Stripe Webhook Events Handled
- `payment_intent.succeeded` → confirms registration
