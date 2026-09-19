/**
 * src/index.js
 * ------------
 * Entry point for the MPLADS Auth Service.
 * Binds to PORT (default 8086).
 *
 * Routes:
 *   GET  /health               — liveness probe
 *   POST /auth/request-otp    — generate & email a 6-digit OTP
 *   POST /auth/verify-otp     — verify OTP, set JWT cookie
 *   POST /auth/logout         — clear auth cookie
 *   GET  /auth/me             — current official profile (requires auth)
 */

"use strict";

// Load env vars FIRST before requiring any module that reads them
require("dotenv").config();

const express      = require("express");
const cookieParser = require("cookie-parser");
const config       = require("./config");
const db           = require("./db");

const authRouter = require("./routes/auth");

// ---------------------------------------------------------------------------
// App bootstrap
// ---------------------------------------------------------------------------
const app = express();

// Trust the first proxy hop (needed for X-Forwarded-For IP extraction)
app.set("trust proxy", 1);

// ---------------------------------------------------------------------------
// Global middleware
// ---------------------------------------------------------------------------
app.use(express.json({ limit: "16kb" }));
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());

// Security headers (minimal, no external dependency)
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options",        "DENY");
  res.setHeader("X-XSS-Protection",       "0");
  res.setHeader("Referrer-Policy",        "no-referrer");
  if (config.cookie.secure) {
    res.setHeader("Strict-Transport-Security", "max-age=63072000; includeSubDomains");
  }
  next();
});

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

// Root service info
app.get("/", (req, res) => {
  res.status(200).json({
    status:  "online",
    service: "mplads-auth-service",
    healthCheck: "/health",
    message: "MPLADS Authentication Microservice is running.",
  });
});

// Health probe — no auth required
app.get("/health", (req, res) => {
  res.status(200).json({
    status:  "ok",
    service: "mplads-auth-service",
    version: process.env.npm_package_version || "1.0.0",
    env:     config.nodeEnv,
    uptime:  Math.floor(process.uptime()),
  });
});

app.use("/auth", authRouter);

// ---------------------------------------------------------------------------
// 404 handler
// ---------------------------------------------------------------------------
app.use((req, res) => {
  res.status(404).json({
    error:   "NOT_FOUND",
    message: `No route found for ${req.method} ${req.path}`,
  });
});

// ---------------------------------------------------------------------------
// Global error handler
// ---------------------------------------------------------------------------
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, _next) => {
  const isDev = config.nodeEnv !== "production";
  console.error("[auth-service] Unhandled error:", err.message);
  if (isDev) console.error(err.stack);

  res.status(err.status || 500).json({
    error:   err.code || "INTERNAL_ERROR",
    message: isDev ? err.message : "An unexpected error occurred. Please try again.",
    ...(isDev && { stack: err.stack }),
  });
});

// ---------------------------------------------------------------------------
// Start — must await DB initialisation before listening
// ---------------------------------------------------------------------------
async function start() {
  await db.init();
  console.log("[auth-service] Database ready");

  const server = app.listen(config.port, () => {
    console.log(`[auth-service] Running on http://localhost:${config.port}`);
    console.log(`[auth-service] ENV=${config.nodeEnv} | SMTP=${config.smtp.host}:${config.smtp.port}`);
  });

  function shutdown(signal) {
    console.log(`[auth-service] ${signal} received — shutting down gracefully`);
    server.close(() => {
      console.log("[auth-service] HTTP server closed");
      process.exit(0);
    });
    setTimeout(() => process.exit(1), 5000);
  }

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT",  () => shutdown("SIGINT"));

  return server;
}

// Export for testing (tests call start() manually)
module.exports = { app, start };

// Only start automatically when run directly
if (require.main === module) {
  start().catch((err) => {
    console.error("[auth-service] Fatal startup error:", err);
    process.exit(1);
  });
}
