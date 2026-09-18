/**
 * src/config.js
 * -------------
 * Centralised, validated config loaded from environment variables.
 * Throws at startup if any required variable is missing or invalid.
 */

"use strict";

require("dotenv").config();

function required(name) {
  const v = process.env[name];
  if (!v || !v.trim()) {
    throw new Error(`[auth-service] Required environment variable "${name}" is not set. Check your .env file.`);
  }
  return v.trim();
}

function optional(name, defaultValue) {
  const v = process.env[name];
  return v && v.trim() ? v.trim() : defaultValue;
}

function optionalInt(name, defaultValue) {
  const v = process.env[name];
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : defaultValue;
}

function optionalBool(name, defaultValue) {
  const v = (process.env[name] || "").toLowerCase().trim();
  if (v === "true" || v === "1" || v === "yes") return true;
  if (v === "false" || v === "0" || v === "no") return false;
  return defaultValue;
}

const config = {
  port:    optionalInt("PORT", 8086),
  nodeEnv: optional("NODE_ENV", "development"),

  jwt: {
    secret:    required("JWT_SECRET"),
    expiresIn: optional("JWT_EXPIRES_IN", "2h"),
  },

  smtp: {
    host:   required("SMTP_HOST"),
    port:   optionalInt("SMTP_PORT", 587),
    secure: optionalBool("SMTP_SECURE", false),
    user:   required("SMTP_USER"),
    pass:   required("SMTP_PASS"),
    from:   optional("SMTP_FROM", "MPLADS Audit System <no-reply@mplads.gov.in>"),
  },

  bcryptRounds: optionalInt("BCRYPT_ROUNDS", 10),

  otp: {
    expiresSeconds:  optionalInt("OTP_EXPIRES_SECONDS", 300),       // 5 min
    maxFailures:     optionalInt("OTP_MAX_FAILURES", 5),
    lockoutMinutes:  optionalInt("OTP_LOCKOUT_MINUTES", 15),
  },

  rateLimits: {
    emailMax:    optionalInt("OTP_PER_EMAIL_MAX", 3),
    emailWindow: optionalInt("OTP_PER_EMAIL_WINDOW_MS", 600_000),   // 10 min
    ipMax:       optionalInt("OTP_PER_IP_MAX", 5),
    ipWindow:    optionalInt("OTP_PER_IP_WINDOW_MS", 600_000),
  },

  cookie: {
    secure:   optionalBool("COOKIE_SECURE", false),
    sameSite: optional("COOKIE_SAME_SITE", "strict"),
  },
};

module.exports = config;
