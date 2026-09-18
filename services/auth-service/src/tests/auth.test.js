/**
 * src/tests/auth.test.js
 * ----------------------
 * Built-in Node.js test runner (node:test) — no Jest or Mocha required.
 * Run with: npm test   OR   node --test src/tests/auth.test.js
 */

"use strict";

// Set up test environment BEFORE any module is loaded
process.env.NODE_ENV       = "test";
process.env.JWT_SECRET     = "test-secret-at-least-64-characters-for-hs256-validation-purposes-1234";
process.env.JWT_EXPIRES_IN = "2h";
process.env.SMTP_HOST      = "smtp.ethereal.email";
process.env.SMTP_PORT      = "587";
process.env.SMTP_SECURE    = "false";
process.env.SMTP_USER      = "test@ethereal.email";
process.env.SMTP_PASS      = "test_pass";
process.env.SMTP_FROM      = "test@mplads.test";
process.env.BCRYPT_ROUNDS  = "4";   // Low rounds for test speed
process.env.PORT            = "0";
process.env.COOKIE_SECURE      = "false";
process.env.AUTH_DB_PATH       = ":memory:";   // In-memory SQLite — no file created
process.env.OTP_PER_EMAIL_MAX  = "100";
process.env.OTP_PER_IP_MAX     = "100";

const { test, before, after, describe } = require("node:test");
const assert  = require("node:assert/strict");

// Mock nodemailer BEFORE requiring the app (prevents real emails)
const nodemailer = require("nodemailer");
let lastSentMail = null;
const mockTransport = {
  sendMail: async (msg) => { lastSentMail = msg; return { messageId: "test-id" }; },
};
nodemailer.createTransport = () => mockTransport;

const { app, start } = require("../index");
const db   = require("../db");
const http = require("http");
const { v4: uuidv4 } = require("uuid");

let server;
let baseUrl;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function seedTestOfficial() {
  db.run(
    "INSERT OR REPLACE INTO officials (id, email, name, role) VALUES (?, ?, ?, ?)",
    "test-official-id-001",
    "reviewer@mplads.test",
    "Test Reviewer",
    "reviewer"
  );
}

function makeRequest(method, path, body, cookies = "") {
  return new Promise((resolve, reject) => {
    const bodyStr = body ? JSON.stringify(body) : "";
    const options = {
      hostname: "127.0.0.1",
      port:     new URL(baseUrl).port,
      path,
      method,
      headers: {
        "Content-Type":   "application/json",
        "Content-Length": Buffer.byteLength(bodyStr),
        ...(cookies ? { Cookie: cookies } : {}),
      },
    };
    const req = http.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => {
        resolve({
          status:  res.statusCode,
          headers: res.headers,
          body:    data ? JSON.parse(data) : null,
        });
      });
    });
    req.on("error", reject);
    if (bodyStr) req.write(bodyStr);
    req.end();
  });
}

function extractCookie(headers) {
  const header = headers["set-cookie"];
  if (!header) return "";
  const raw = Array.isArray(header) ? header[0] : header;
  return raw.split(";")[0];
}

// ---------------------------------------------------------------------------
before(async () => {
  server  = await start();
  baseUrl = `http://127.0.0.1:${server.address().port}`;
  seedTestOfficial();
});

after(async () => {
  await new Promise((r) => server.close(r));
});
// ---------------------------------------------------------------------------

describe("GET /health", () => {
  test("returns 200 with status ok", async () => {
    const res = await makeRequest("GET", "/health", null);
    assert.equal(res.status, 200);
    assert.equal(res.body.status, "ok");
    assert.equal(res.body.service, "mplads-auth-service");
  });
});

describe("POST /auth/request-otp", () => {
  test("returns 400 when email is missing", async () => {
    const res = await makeRequest("POST", "/auth/request-otp", {});
    assert.equal(res.status, 400);
    assert.equal(res.body.error, "INVALID_EMAIL");
  });

  test("returns 400 for malformed email", async () => {
    const res = await makeRequest("POST", "/auth/request-otp", { email: "not-an-email" });
    assert.equal(res.status, 400);
    assert.equal(res.body.error, "INVALID_EMAIL");
  });

  test("returns generic 202 for unregistered email (no enumeration)", async () => {
    const res = await makeRequest("POST", "/auth/request-otp", { email: "ghost@mplads.test" });
    assert.equal(res.status, 202);
    assert.ok(res.body.message.toLowerCase().includes("if this email"));
  });

  test("returns 202 and sends email for registered official", async () => {
    lastSentMail = null;
    const res = await makeRequest("POST", "/auth/request-otp", { email: "reviewer@mplads.test" });
    assert.equal(res.status, 202);
    assert.ok(res.body.message.toLowerCase().includes("if this email"));
    assert.ok(lastSentMail, "sendMail was not called");
    assert.equal(lastSentMail.to, "reviewer@mplads.test");
    // Raw OTP must NOT appear in any API response body
    assert.ok(!JSON.stringify(res.body).match(/\d{6}/), "OTP must not appear in response body");
  });
});

describe("POST /auth/verify-otp", () => {
  test("returns 400 when fields are missing", async () => {
    const res = await makeRequest("POST", "/auth/verify-otp", { email: "reviewer@mplads.test" });
    assert.equal(res.status, 400);
    assert.equal(res.body.error, "MISSING_FIELDS");
  });

  test("returns 400 for non-6-digit OTP", async () => {
    const res = await makeRequest("POST", "/auth/verify-otp", { email: "reviewer@mplads.test", otp: "abc" });
    assert.equal(res.status, 400);
    assert.equal(res.body.error, "INVALID_OTP_FORMAT");
  });

  test("returns 401 for wrong OTP", async () => {
    await makeRequest("POST", "/auth/request-otp", { email: "reviewer@mplads.test" });
    const res = await makeRequest("POST", "/auth/verify-otp", { email: "reviewer@mplads.test", otp: "000000" });
    assert.equal(res.status, 401);
    assert.equal(res.body.error, "INVALID_OR_EXPIRED");
    assert.ok(typeof res.body.attemptsRemaining === "number");
  });

  test("successful verify returns 200 and sets httpOnly cookie", async () => {
    lastSentMail = null;
    await makeRequest("POST", "/auth/request-otp", { email: "reviewer@mplads.test" });

    // Extract OTP from email subject (format: "<OTP> — Your MPLADS Audit login code")
    const subject = lastSentMail.subject;
    const otp = subject.split("—")[0].trim();
    assert.match(otp, /^\d{6}$/, "Expected 6-digit OTP in email subject");

    const res = await makeRequest("POST", "/auth/verify-otp", { email: "reviewer@mplads.test", otp });
    assert.equal(res.status, 200);
    assert.equal(res.body.official.role, "reviewer");

    const setCookie = res.headers["set-cookie"];
    assert.ok(setCookie, "Cookie must be set");
    const cookieStr = Array.isArray(setCookie) ? setCookie.join("; ") : setCookie;
    assert.ok(cookieStr.toLowerCase().includes("httponly"), "Cookie must be httpOnly");
    assert.ok(cookieStr.includes("mplads_auth="), "Cookie must be named mplads_auth");
  });

  test("used OTP cannot be replayed", async () => {
    lastSentMail = null;
    await makeRequest("POST", "/auth/request-otp", { email: "reviewer@mplads.test" });
    const otp = lastSentMail.subject.split("—")[0].trim();

    await makeRequest("POST", "/auth/verify-otp", { email: "reviewer@mplads.test", otp });
    const res2 = await makeRequest("POST", "/auth/verify-otp", { email: "reviewer@mplads.test", otp });
    assert.equal(res2.status, 401);
    assert.equal(res2.body.error, "INVALID_OR_EXPIRED");
  });
  test("locks account after 5 failed attempts with 423 status", async () => {
    // Seed a fresh official specifically for lockout testing
    const lockEmail = "lockout-test@mplads.test";
    db.run(
      "INSERT OR REPLACE INTO officials (id, email, name, role) VALUES (?, ?, ?, ?)",
      "lockout-off-001",
      lockEmail,
      "Lockout Test",
      "reviewer"
    );

    // Request an OTP
    await makeRequest("POST", "/auth/request-otp", { email: lockEmail });

    // Submit 4 incorrect attempts
    for (let i = 0; i < 4; i++) {
      const failRes = await makeRequest("POST", "/auth/verify-otp", { email: lockEmail, otp: "999999" });
      assert.equal(failRes.status, 401);
    }

    // 5th incorrect attempt must lock the account and return 423
    const fifthRes = await makeRequest("POST", "/auth/verify-otp", { email: lockEmail, otp: "999999" });
    assert.equal(fifthRes.status, 423);
    assert.equal(fifthRes.body.error, "ACCOUNT_LOCKED");
    assert.ok(fifthRes.body.lockedUntil);
  });
});

describe("GET /auth/me", () => {
  test("returns 401 without a cookie", async () => {
    const res = await makeRequest("GET", "/auth/me", null);
    assert.equal(res.status, 401);
    assert.equal(res.body.error, "UNAUTHENTICATED");
  });

  test("returns 200 with official profile when cookie is valid", async () => {
    lastSentMail = null;
    await makeRequest("POST", "/auth/request-otp", { email: "reviewer@mplads.test" });
    const otp      = lastSentMail.subject.split("—")[0].trim();
    const loginRes = await makeRequest("POST", "/auth/verify-otp", { email: "reviewer@mplads.test", otp });
    const cookie   = extractCookie(loginRes.headers);

    const res = await makeRequest("GET", "/auth/me", null, cookie);
    assert.equal(res.status, 200);
    assert.equal(res.body.official.role, "reviewer");
    assert.ok(res.body.official.id || res.body.official.official_id);
  });
});

describe("POST /auth/logout", () => {
  test("clears the auth cookie", async () => {
    const res = await makeRequest("POST", "/auth/logout", {});
    assert.equal(res.status, 200);
    const setCookie = res.headers["set-cookie"] || [];
    const cookieStr = (Array.isArray(setCookie) ? setCookie : [setCookie]).join("; ");
    assert.ok(
      cookieStr.includes("mplads_auth="),
      "Logout should clear mplads_auth cookie"
    );
  });
});

describe("requireAuth Middleware", () => {
  const requireAuth = require("../middleware/requireAuth");
  const jwt = require("jsonwebtoken");
  const config = require("../config");

  test("blocks unauthenticated requests", () => {
    const req = { cookies: {}, headers: {} };
    let statusSet, jsonResult;
    const res = {
      status(s) { statusSet = s; return this; },
      json(j) { jsonResult = j; return this; },
    };
    const next = () => {};

    requireAuth()(req, res, next);
    assert.equal(statusSet, 401);
    assert.equal(jsonResult.error, "UNAUTHENTICATED");
  });

  test("allows authorized role and populates req.official", () => {
    const token = jwt.sign(
      { official_id: "off-123", role: "reviewer", name: "Priya" },
      config.jwt.secret,
      { expiresIn: "1h" }
    );
    const req = { cookies: { mplads_auth: token }, headers: {} };
    const res = {};
    let nextCalled = false;
    const next = () => { nextCalled = true; };

    requireAuth("reviewer")(req, res, next);
    assert.ok(nextCalled);
    assert.equal(req.official.role, "reviewer");
    assert.equal(req.official.official_id, "off-123");
  });

  test("forbids unauthorized role with 403", () => {
    const token = jwt.sign(
      { official_id: "off-123", role: "reviewer", name: "Priya" },
      config.jwt.secret,
      { expiresIn: "1h" }
    );
    const req = { cookies: { mplads_auth: token }, headers: {} };
    let statusSet, jsonResult;
    const res = {
      status(s) { statusSet = s; return this; },
      json(j) { jsonResult = j; return this; },
    };
    const next = () => {};

    requireAuth("admin")(req, res, next);
    assert.equal(statusSet, 403);
    assert.equal(jsonResult.error, "FORBIDDEN");
  });
});
