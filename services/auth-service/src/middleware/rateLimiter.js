/**
 * src/middleware/rateLimiter.js
 * ----------------------------
 * Per-email and per-IP rate limiters for OTP request endpoints.
 *
 * Two separate limiters run in sequence on POST /auth/request-otp:
 *   1. ipLimiter   — max OTP_PER_IP_MAX requests per IP per OTP_PER_IP_WINDOW_MS
 *   2. emailLimiter — max OTP_PER_EMAIL_MAX requests per email per OTP_PER_EMAIL_WINDOW_MS
 *
 * Both return HTTP 429 with a descriptive JSON body when the limit is hit.
 * The email limiter is applied after the body is parsed, so it extracts the
 * email from req.body.email.
 */

"use strict";

const rateLimit = require("express-rate-limit");
const config    = require("../config");

// In-memory store for per-email counts (keyed by email address).
// For production, swap out for a Redis-backed store using `rate-limit-redis`.
const emailCountStore = new Map(); // email -> { count, windowStart }

/**
 * Per-IP rate limiter (handled by express-rate-limit).
 * The library tracks counts by IP address automatically.
 */
const ipLimiter = rateLimit({
  windowMs:         config.rateLimits.ipWindow,
  max:              config.rateLimits.ipMax,
  standardHeaders:  true,
  legacyHeaders:    false,
  skipSuccessfulRequests: false,
  handler(req, res) {
    res.status(429).json({
      error:   "RATE_LIMIT_IP",
      message: `Too many OTP requests from this network. Please wait ${Math.ceil(config.rateLimits.ipWindow / 60000)} minutes before trying again.`,
      retryAfterMs: config.rateLimits.ipWindow,
    });
  },
});

/**
 * Per-email rate limiter (manual, keyed by req.body.email).
 * Must be applied AFTER express.json() middleware.
 */
function emailLimiter(req, res, next) {
  const email = (req.body && typeof req.body.email === "string")
    ? req.body.email.trim().toLowerCase()
    : null;

  if (!email) {
    // No email in body — let the route handler handle validation
    return next();
  }

  const now     = Date.now();
  const window  = config.rateLimits.emailWindow;
  const maxReqs = config.rateLimits.emailMax;

  let record = emailCountStore.get(email);

  if (!record || now - record.windowStart >= window) {
    // Start a new window
    record = { count: 0, windowStart: now };
  }

  record.count += 1;
  emailCountStore.set(email, record);

  // Prune old entries every 100 checks to avoid unbounded growth
  if (emailCountStore.size > 10_000) {
    for (const [k, v] of emailCountStore) {
      if (now - v.windowStart >= window) emailCountStore.delete(k);
    }
  }

  if (record.count > maxReqs) {
    const retryAfterMs = window - (now - record.windowStart);
    res.set("Retry-After", Math.ceil(retryAfterMs / 1000).toString());
    return res.status(429).json({
      error:   "RATE_LIMIT_EMAIL",
      message: `Too many OTP requests for this email address. You can request at most ${maxReqs} codes per ${Math.ceil(window / 60000)} minutes.`,
      retryAfterMs,
    });
  }

  next();
}

module.exports = { ipLimiter, emailLimiter };
