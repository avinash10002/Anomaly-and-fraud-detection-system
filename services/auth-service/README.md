# MPLADS Auth Service

Standalone OTP-over-email authentication service for pre-registered MPLADS officials and reviewers. Built with **Node.js + Express + SQLite (sql.js WASM) + Nodemailer**.

> **Not a public sign-up service.** Officials are pre-registered by an admin. There is no registration endpoint.

---

## Architecture Overview

```
Browser/Client
     │
     ▼
POST /auth/request-otp  ──► check officials table
     │                       generate 6-digit OTP
     │                       bcrypt-hash OTP
     │                       store token in otp_tokens
     │                       send email via Nodemailer
     ▼
POST /auth/verify-otp   ──► load latest unused token for email
     │                       bcrypt.compare(otp, hash)
     │                       mark token used
     │                       issue HS256 JWT (2h)
     │                       set httpOnly cookie "mplads_auth"
     ▼
GET  /auth/me           ──► requireAuth() middleware validates cookie
GET  /protected-route   ──► requireAuth('admin') checks role
```

**Database**: SQLite (via `sql.js` WASM, zero native build tools or C++ toolchains required) for zero-infrastructure local development.
For production alongside the Postgres stack, apply `db/migrations/004_auth_officials.sql`.

---

## Environment Variables

Copy `.env.example` to `.env` and populate:

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORT` | no | `8086` | HTTP port |
| `NODE_ENV` | no | `development` | Set to `production` in prod |
| `JWT_SECRET` | **yes** | — | >=64-char random string for HS256 |
| `JWT_EXPIRES_IN` | no | `2h` | JWT lifetime |
| `SMTP_HOST` | **yes** | — | SMTP server hostname |
| `SMTP_PORT` | no | `587` | SMTP port |
| `SMTP_SECURE` | no | `false` | `true` for port 465 TLS |
| `SMTP_USER` | **yes** | — | SMTP login username |
| `SMTP_PASS` | **yes** | — | SMTP login password |
| `SMTP_FROM` | no | `MPLADS Audit System <no-reply@mplads.gov.in>` | Sender address |
| `BCRYPT_ROUNDS` | no | `10` | bcrypt cost factor (12+ for prod) |
| `OTP_EXPIRES_SECONDS` | no | `300` | OTP lifetime (5 min) |
| `OTP_MAX_FAILURES` | no | `5` | Failed attempts before lockout |
| `OTP_LOCKOUT_MINUTES` | no | `15` | Lockout duration |
| `OTP_PER_EMAIL_MAX` | no | `3` | Max OTP requests per email per window |
| `OTP_PER_EMAIL_WINDOW_MS` | no | `600000` | Rate limit window in ms (10 min) |
| `OTP_PER_IP_MAX` | no | `5` | Max OTP requests per IP per window |
| `OTP_PER_IP_WINDOW_MS` | no | `600000` | Rate limit window in ms (10 min) |
| `COOKIE_SECURE` | no | `false` | `true` in production (requires HTTPS) |
| `COOKIE_SAME_SITE` | no | `strict` | SameSite cookie policy |
| `AUTH_DB_PATH` | no | `./data/auth.sqlite` | Path to SQLite file |

**Generate a strong JWT secret:**
```bash
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

---

## Local Setup

```bash
cd services/auth-service

# 1. Install dependencies
npm install

# 2. Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET and SMTP credentials (see below)

# 3. Seed demo officials
npm run seed

# 4. Start dev server (auto-restarts on changes)
npm run dev
```

Service runs on **http://localhost:8086**.

---

## Testing with Ethereal or Mailtrap

These are **fake SMTP inboxes** — emails are captured but never delivered. Perfect for local testing.

### Option A — Ethereal (instant, free, no sign-up required)

```js
// Run once to get test credentials:
const nodemailer = require('nodemailer');
const account = await nodemailer.createTestAccount();
console.log(account);
```

Or visit https://ethereal.email → click **"Create Ethereal Account"**. Copy the credentials to `.env`:

```env
SMTP_HOST=smtp.ethereal.email
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=you@ethereal.email
SMTP_PASS=your_ethereal_password
```

After requesting an OTP, visit **https://ethereal.email/messages** to read the email and copy the 6-digit code.

### Option B — Mailtrap (free tier, richer UI)

1. Sign up at https://mailtrap.io
2. Go to **Email Testing → Inboxes → SMTP Settings**

```env
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=2525
SMTP_SECURE=false
SMTP_USER=<mailtrap_user>
SMTP_PASS=<mailtrap_password>
```

---

## API Reference

### `GET /health`

```json
{ "status": "ok", "service": "mplads-auth-service", "uptime": 42 }
```

### `POST /auth/request-otp`

Rate limited: max **3 per email / 5 per IP** per 10 minutes.

```json
// Request
{ "email": "priya.nair@mplads.test" }

// Response 202 (always identical — prevents email enumeration)
{ "message": "If this email address is registered, a one-time passcode has been sent. Check your inbox (and spam folder)." }
```

Errors: `400` (invalid email), `429` (rate limit, includes `Retry-After` header)

### `POST /auth/verify-otp`

```json
// Request
{ "email": "priya.nair@mplads.test", "otp": "481923" }

// Response 200 — sets httpOnly "mplads_auth" cookie
{ "message": "Login successful.", "official": { "id": "uuid", "name": "Priya Nair", "role": "reviewer" } }
```

Errors: `400` (bad format), `401` (wrong/expired, includes `attemptsRemaining`), `423` (locked, includes `lockedUntil`)

### `POST /auth/logout`

Clears the `mplads_auth` cookie. Returns `200`.

### `GET /auth/me`  *(requires auth)*

```json
{ "official": { "id": "uuid", "name": "Priya Nair", "role": "reviewer", "exp": 1730000000 } }
```

---

## Using `requireAuth` in Other Services

```js
const requireAuth = require('./path/to/auth-service/src/middleware/requireAuth');

// Any authenticated official
router.get('/review-queue', requireAuth(), getQueue);

// Admin only
router.delete('/officials/:id', requireAuth('admin'), deleteOfficial);
```

The middleware checks for the JWT in:
1. `mplads_auth` httpOnly cookie
2. `Authorization: Bearer <token>` header (API-to-API)

On success: `req.official = { id, name, role, iat, exp }`

**Required env var in consuming services:** `JWT_SECRET=<same value>`

---

## Demo Officials (seeded by `npm run seed`)

| Email | Role |
|---|---|
| `avinahgoel12@gmail.com` | admin |
| `avinashgoel6654@gmail.com` | reviewer |
| `arjun.sharma@mplads.test` | admin |
| `priya.nair@mplads.test` | reviewer |
| `vikram.rathod@mplads.test` | reviewer |
| `sunita.deshpande@mplads.test` | reviewer |
| `rahul.kaswan@mplads.test` | reviewer |
| `amheisenbergsprinciple@gmail.com` | admin |
| `kanak.s252007@gmail.com` | admin |
| `nehaksn190@gmail.com` | admin |
| `prernasubhi123@gmail.com` | admin |

---

## Security Design

| Concern | Implementation |
|---|---|
| Email enumeration | `/request-otp` always returns identical 202 + constant-time delay |
| OTP brute-force | 5 failed attempts → 15-min lockout; OTP expires in 5 min |
| Replay attacks | OTP is single-use; prior tokens invalidated on new request |
| OTP exposure | Never logged or in API responses; only embedded in email |
| JWT forgery | HS256 + >=64-char secret; `algorithms` pinned in `verify()` |
| Cookie security | `httpOnly`, `SameSite=strict`, `Secure=true` in production |
| Rate limiting | Per-email AND per-IP in sliding 10-minute windows |
| SMTP credentials | Loaded exclusively from env vars; zero hardcoded secrets |

---

## Docker / Production

```bash
docker-compose up --build auth-service
```

For Postgres-backed production, run the migration first:
```bash
psql -U mplad_user -d mplad -f db/migrations/004_auth_officials.sql
```

---

## Running Tests

```bash
npm test
```

Uses Node's built-in `node:test` runner — no Jest/Mocha required. Tests mock Nodemailer, use in-memory SQLite, and start a real HTTP server on a random port.
