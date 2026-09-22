/**
 * src/routes/auth.js
 * ------------------
 * POST /auth/request-otp  — generate and email a 6-digit OTP
 * POST /auth/verify-otp   — verify OTP, issue JWT cookie
 * POST /auth/logout       — clear the auth cookie
 * GET  /auth/me           — return the current official's profile (requires auth)
 */

"use strict";

const crypto   = require("crypto");
const express  = require("express");
const bcrypt   = require("bcrypt");
const jwt      = require("jsonwebtoken");
const { v4: uuidv4 } = require("uuid");

const db          = require("../db");
const config      = require("../config");
const { sendOtpEmail } = require("../mailer");
const requireAuth = require("../middleware/requireAuth");
const { ipLimiter, emailLimiter } = require("../middleware/rateLimiter");

const router = express.Router();
const COOKIE_NAME = "mplads_auth";

// ---------------------------------------------------------------------------
// Helper: generate a cryptographically random 6-digit numeric OTP
// ---------------------------------------------------------------------------
function generateOtp() {
  // crypto.randomInt is uniformly distributed and cryptographically safe
  return String(crypto.randomInt(100_000, 999_999));
}

// ---------------------------------------------------------------------------
// Helper: "if this email is registered, a code was sent" — constant-time
// response to prevent email enumeration via timing attacks
// ---------------------------------------------------------------------------
const GENERIC_OK = {
  message: "If this email address is registered, a one-time passcode has been sent. Check your inbox (and spam folder).",
};

// ---------------------------------------------------------------------------
// POST /auth/request-otp
// ---------------------------------------------------------------------------
router.post(
  "/request-otp",
  ipLimiter,     // per-IP limiter (runs before body parsing)
  emailLimiter,  // per-email limiter (reads req.body.email)
  async (req, res) => {
    const email = (req.body && typeof req.body.email === "string")
      ? req.body.email.trim().toLowerCase()
      : null;

    if (!email || !email.includes("@")) {
      return res.status(400).json({
        error:   "INVALID_EMAIL",
        message: "A valid email address is required.",
      });
    }

    // Look up the official — but don't reveal whether found
    const official = db
      .prepare("SELECT * FROM officials WHERE LOWER(email) = ? AND is_active = 1")
      .get(email);

    if (!official) {
      // Simulate async work to prevent timing-based enumeration
      await new Promise((r) => setTimeout(r, 400 + Math.random() * 200));
      return res.status(202).json(GENERIC_OK);
    }

    // If account is currently locked, do not dispatch email, but return generic OK (no enumeration)
    const nowIso = new Date().toISOString();
    if (official.locked_until && official.locked_until > nowIso) {
      return res.status(202).json(GENERIC_OK);
    }

    // Generate OTP, hash it, store it
    const otp       = generateOtp();
    if (process.env.NODE_ENV !== "production" || process.env.LOG_DEV_OTP === "true") {
      console.log(`[auth] Generated OTP for ${official.email}: ${otp}`);
    }
    const expiresAt = new Date(Date.now() + config.otp.expiresSeconds * 1000).toISOString();
    const hash      = await bcrypt.hash(otp, config.bcryptRounds);
    const tokenId   = uuidv4();

    // Invalidate any previous unused tokens for this official (prevent replay)
    db.prepare(
      "UPDATE otp_tokens SET used = 1 WHERE official_id = ? AND used = 0"
    ).run(official.id);

    db.prepare(`
      INSERT INTO otp_tokens (id, official_id, email, hash, expires_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(tokenId, official.id, official.email, hash, expiresAt);

    // Send email — if it fails, check for sandbox restrictions or clean up token
    try {
      await sendOtpEmail(official.email, official.name, otp, config.otp.expiresSeconds);
    } catch (err) {
      console.error("[auth] Failed to send OTP email to official_id=%s: %s", official.id, err.message);

      // Check if failure is due to cloud sandbox restrictions (e.g. Resend free-tier recipient limits)
      // or if developer fallback is enabled.
      const isSandboxRestriction = err.message && (
        err.message.includes("You can only send testing emails") ||
        err.message.includes("Render Free Tier blocks outbound SMTP") ||
        process.env.DEV_OTP_FALLBACK === "true" ||
        process.env.NODE_ENV !== "production"
      );

      if (isSandboxRestriction) {
        console.warn(`[auth] Sandbox email restriction encountered for ${official.email}. Retaining token. Fallback OTP: ${otp}`);
        return res.status(202).json({
          message: `Notice: Email delivery was blocked by Resend sandbox limits. Your login passcode is ${otp}.`,
          otp,
        });
      }

      db.prepare("DELETE FROM otp_tokens WHERE id = ?").run(tokenId);
      return res.status(502).json({
        error:   "EMAIL_SEND_FAILED",
        message: `Could not dispatch the login code: ${err.message}. Please verify SMTP configuration.`,
      });
    }

    return res.status(202).json(GENERIC_OK);
  }
);

// ---------------------------------------------------------------------------
// POST /auth/verify-otp
// ---------------------------------------------------------------------------
router.post("/verify-otp", async (req, res) => {
  const { email, otp } = req.body || {};

  if (!email || !otp) {
    return res.status(400).json({
      error:   "MISSING_FIELDS",
      message: "Both 'email' and 'otp' fields are required.",
    });
  }

  const cleanEmail = String(email).trim().toLowerCase();
  const cleanOtp   = String(otp).trim();

  // Validate OTP format (6-digit numeric)
  if (!/^\d{6}$/.test(cleanOtp)) {
    return res.status(400).json({
      error:   "INVALID_OTP_FORMAT",
      message: "The OTP must be a 6-digit number.",
    });
  }

  // Find the most recent unused, non-expired token for this email
  const now     = new Date().toISOString();
  const token   = db.prepare(`
    SELECT t.*, o.id AS off_id, o.name, o.role, o.is_active, o.locked_until AS official_locked_until
    FROM otp_tokens t
    JOIN officials o ON o.id = t.official_id
    WHERE LOWER(t.email) = ?
      AND t.used = 0
      AND t.expires_at > ?
    ORDER BY t.created_at DESC
    LIMIT 1
  `).get(cleanEmail, now);

  // Generic failure (no token found, expired, official suspended)
  if (!token || !token.is_active) {
    return res.status(401).json({
      error:   "INVALID_OR_EXPIRED",
      message: "The code is invalid or has expired. Please request a new one.",
    });
  }

  // Check account lockout (on token or official account)
  const effectiveLock = token.locked_until || token.official_locked_until;
  if (effectiveLock && effectiveLock > now) {
    const lockedUntilDate = new Date(effectiveLock);
    return res.status(423).json({
      error:      "ACCOUNT_LOCKED",
      message:    `Too many failed attempts. Your account is locked until ${lockedUntilDate.toUTCString()}.`,
      lockedUntil: effectiveLock,
    });
  }

  // Constant-time bcrypt compare
  const valid = await bcrypt.compare(cleanOtp, token.hash);

  if (!valid) {
    const newFailures = token.failed_attempts + 1;
    const maxFailures = config.otp.maxFailures;

    if (newFailures >= maxFailures) {
      // Lock the token and lock the official account for 15 minutes
      const lockedUntil = new Date(Date.now() + config.otp.lockoutMinutes * 60_000).toISOString();
      db.prepare(
        "UPDATE otp_tokens SET failed_attempts = ?, locked_until = ? WHERE id = ?"
      ).run(newFailures, lockedUntil, token.id);
      db.prepare(
        "UPDATE officials SET locked_until = ? WHERE id = ?"
      ).run(lockedUntil, token.off_id);

      console.warn(
        "[auth] Account locked for official_id=%s after %d failed attempts",
        token.off_id, newFailures
      );

      return res.status(423).json({
        error:      "ACCOUNT_LOCKED",
        message:    `Too many failed attempts. Your account is locked for ${config.otp.lockoutMinutes} minutes.`,
        lockedUntil,
      });
    }

    db.prepare(
      "UPDATE otp_tokens SET failed_attempts = ? WHERE id = ?"
    ).run(newFailures, token.id);

    return res.status(401).json({
      error:            "INVALID_OR_EXPIRED",
      message:          "Incorrect code. Please check and try again.",
      attemptsRemaining: maxFailures - newFailures,
    });
  }

  // Mark token as used (single-use guarantee)
  db.prepare("UPDATE otp_tokens SET used = 1 WHERE id = ?").run(token.id);

  // Reset lockout on official if any
  db.prepare("UPDATE officials SET locked_until = NULL WHERE id = ?").run(token.off_id);

  // Issue JWT containing official_id and role
  const payload = {
    official_id: token.off_id,
    id:          token.off_id,
    name:        token.name,
    email:       token.email,
    role:        token.role,
  };

  const jwtToken = jwt.sign(payload, config.jwt.secret, {
    algorithm: "HS256",
    expiresIn: config.jwt.expiresIn,
  });

  // Set httpOnly, secure, SameSite cookie
  res.cookie(COOKIE_NAME, jwtToken, {
    httpOnly: true,
    secure:   config.cookie.secure,
    sameSite: config.cookie.sameSite,
    // Express maxAge is in milliseconds; parse "2h" → 7,200,000 ms
    maxAge: parseExpiryMs(config.jwt.expiresIn),
    path:   "/",
  });

  console.log("[auth] Successful login for official_id=%s role=%s", token.off_id, token.role);

  return res.status(200).json({
    message:  "Login successful.",
    official: {
      official_id: token.off_id,
      id:          token.off_id,
      name:        token.name,
      email:       token.email,
      role:        token.role,
    },
  });
});

// ---------------------------------------------------------------------------
// POST /auth/logout
// ---------------------------------------------------------------------------
router.post("/logout", (req, res) => {
  res.clearCookie(COOKIE_NAME, { path: "/" });
  return res.status(200).json({ message: "Logged out successfully." });
});

// ---------------------------------------------------------------------------
// GET /auth/me  — returns current official profile (requires valid JWT)
// ---------------------------------------------------------------------------
router.get("/me", requireAuth(), (req, res) => {
  return res.status(200).json({
    official: {
      id:   req.official.id,
      name: req.official.name,
      role: req.official.role,
      exp:  req.official.exp,
    },
  });
});

// ---------------------------------------------------------------------------
// Helper: parse JWT expiresIn string (e.g. "2h", "30m") to milliseconds
// ---------------------------------------------------------------------------
function parseExpiryMs(str) {
  const units = { s: 1000, m: 60_000, h: 3_600_000, d: 86_400_000 };
  const match = /^(\d+)([smhd])$/.exec(String(str).trim().toLowerCase());
  if (!match) return 7_200_000; // default 2h
  return parseInt(match[1], 10) * (units[match[2]] || 1000);
}

module.exports = router;
