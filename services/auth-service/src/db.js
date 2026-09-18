/**
 * src/db.js
 * ---------
 * SQLite-backed persistent store using sql.js (pure JavaScript/WASM —
 * no native compilation required, works on any platform including Windows
 * without Visual Studio Build Tools).
 *
 * Data is persisted to a file on disk via manual save-on-write logic.
 * In-memory mode is used when AUTH_DB_PATH=":memory:" (e.g. in tests).
 *
 * Tables:
 *   officials  — pre-registered MPLADS reviewers and admins
 *   otp_tokens — single-use OTP records with expiry and bcrypt hash
 */

"use strict";

const fs   = require("fs");
const path = require("path");
const initSqlJs = require("sql.js");

const DB_PATH = (process.env.AUTH_DB_PATH || path.join(__dirname, "..", "data", "auth.sqlite")).trim();
const IN_MEMORY = DB_PATH === ":memory:";

if (!IN_MEMORY) {
  fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
}

// sql.js is async on init — we use a synchronous wrapper by pre-initialising
// and caching the DB instance. The module exports a proxy that is ready
// after the init Promise resolves.

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS officials (
    id          TEXT    PRIMARY KEY,
    email       TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    role        TEXT    NOT NULL CHECK (role IN ('reviewer', 'admin')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    locked_until TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS otp_tokens (
    id              TEXT    PRIMARY KEY,
    official_id     TEXT    NOT NULL REFERENCES officials(id) ON DELETE CASCADE,
    email           TEXT    NOT NULL,
    hash            TEXT    NOT NULL,
    expires_at      TEXT    NOT NULL,
    used            INTEGER NOT NULL DEFAULT 0,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
  );

  CREATE INDEX IF NOT EXISTS idx_otp_email     ON otp_tokens(email);
  CREATE INDEX IF NOT EXISTS idx_otp_official  ON otp_tokens(official_id);
`;

let _db = null; // sql.js Database instance
let _saveTimer = null;

function saveSync() {
  if (IN_MEMORY || !_db) return;
  try {
    const data = _db.export();
    fs.writeFileSync(DB_PATH, Buffer.from(data));
  } catch (err) {
    console.error("[auth-db] Failed to persist database:", err.message);
  }
}

/**
 * Persist the in-memory database to the file on disk.
 */
function scheduleSave() {
  saveSync();
}

/**
 * A thin synchronous-style API that wraps sql.js.
 * sql.js executes SQL synchronously in WASM; only the init() call is async.
 */
const dbProxy = {
  /**
   * Initialise sql.js and load (or create) the database file.
   * Must be awaited before any other operation.
   */
  async init() {
    const SQL = await initSqlJs();

    if (!IN_MEMORY && fs.existsSync(DB_PATH)) {
      const fileData = fs.readFileSync(DB_PATH);
      _db = new SQL.Database(fileData);
    } else {
      _db = new SQL.Database();
    }

    _db.run(SCHEMA);
    try {
      _db.run("ALTER TABLE officials ADD COLUMN locked_until TEXT;");
    } catch {
      // column already exists
    }
    saveSync();
    return this;
  },

  /**
   * Save database changes to disk immediately.
   */
  save() {
    saveSync();
  },

  /**
   * Execute a parameterised SELECT and return the first matching row as a plain object,
   * or undefined if no row matches.
   *
   * @param {string} sql  — SQL with ? placeholders
   * @param {...*}   args — positional bind values
   */
  get(sql, ...args) {
    const stmt = _db.prepare(sql);
    if (args.length) stmt.bind(args);
    let row = undefined;
    if (stmt.step()) {
      row = stmt.getAsObject();
    }
    stmt.free();
    return row;
  },

  /**
   * Execute a parameterised SELECT and return all matching rows as plain objects.
   */
  all(sql, ...args) {
    const stmt = _db.prepare(sql);
    if (args.length) stmt.bind(args);
    const rows = [];
    while (stmt.step()) rows.push(stmt.getAsObject());
    stmt.free();
    return rows;
  },

  /**
   * Execute a DML statement (INSERT / UPDATE / DELETE).
   * Returns { changes: number }.
   */
  run(sql, ...args) {
    _db.run(sql, args.length ? args : undefined);
    saveSync();
    return { changes: _db.getRowsModified() };
  },

  /**
   * Prepare a statement with a chainable .run(...args) that also auto-saves.
   * Mirrors the better-sqlite3 API used in routes and scripts.
   */
  prepare(sql) {
    const self = this;
    return {
      run(...args) {
        return self.run(sql, ...args);
      },
      get(...args) {
        return self.get(sql, ...args);
      },
      all(...args) {
        return self.all(sql, ...args);
      },
    };
  },

  /**
   * Execute raw SQL (no parameters, for schema setup).
   */
  exec(sql) {
    _db.run(sql);
    scheduleSave();
  },
};

module.exports = dbProxy;
