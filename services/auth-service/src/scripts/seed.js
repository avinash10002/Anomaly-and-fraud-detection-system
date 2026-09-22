/**
 * src/scripts/seed.js
 * -------------------
 * Seeds the officials table with 5 demo accounts for local testing.
 *
 * Usage:
 *   node src/scripts/seed.js
 *   npm run seed
 *
 * The script is idempotent — running it multiple times will not create
 * duplicate officials (it uses INSERT OR IGNORE).
 *
 * DEMO ACCOUNTS (use these emails in POST /auth/request-otp during testing):
 *
 *   avinahgoel12@gmail.com          — role: admin
 *   avinashgoel6654@gmail.com       — role: reviewer
 *   arjun.sharma@mplads.test        — role: admin
 *   priya.nair@mplads.test          — role: reviewer
 *   vikram.rathod@mplads.test       — role: reviewer
 *   sunita.deshpande@mplads.test    — role: reviewer
 *   rahul.kaswan@mplads.test        — role: reviewer
 */

"use strict";

require("dotenv").config();

const { v4: uuidv4 } = require("uuid");
const db             = require("../db");

const DEMO_OFFICIALS = [
  { email: "avinashgoel1568@gmail.com",      name: "Avinash Goel (Sender)", role: "admin" },
  { email: "avinahgoel12@gmail.com",         name: "Avinash Goel (Admin)", role: "admin" },
  { email: "avinashgoel6654@gmail.com",      name: "Avinash Goel",         role: "reviewer" },
  { email: "arjun.sharma@mplads.test",       name: "Arjun Sharma",         role: "admin" },
  { email: "priya.nair@mplads.test",         name: "Priya Nair",           role: "reviewer" },
  { email: "vikram.rathod@mplads.test",      name: "Vikram Rathod",        role: "reviewer" },
  { email: "sunita.deshpande@mplads.test",   name: "Sunita Deshpande",     role: "reviewer" },
  { email: "rahul.kaswan@mplads.test",       name: "Rahul Kaswan",         role: "reviewer" },
  { email: "amheisenbergsprinciple@gmail.com", name: "Admin Heisenberg",     role: "admin" },
  { email: "kanak.s252007@gmail.com",         name: "Kanak",                role: "admin" },
  { email: "nehaksn190@gmail.com",            name: "Neha",                 role: "admin" },
  { email: "prernasubhi123@gmail.com",        name: "Prerna Subhi",         role: "admin" },
];

async function seed() {
  await db.init();

  console.log("\n─── MPLADS Auth Service — Official Seed ───\n");

  let inserted = 0;
  for (const official of DEMO_OFFICIALS) {
    // Check if already exists
    const existing = db.get(
      "SELECT id FROM officials WHERE LOWER(email) = ?",
      official.email.toLowerCase()
    );

    if (existing) {
      console.log(`  [${official.role.padEnd(8)}] ${official.email} → already exists — skipped`);
    } else {
      db.run(
        "INSERT OR IGNORE INTO officials (id, email, name, role) VALUES (?, ?, ?, ?)",
        uuidv4(), official.email, official.name, official.role
      );
      inserted += 1;
      console.log(`  [${official.role.padEnd(8)}] ${official.email} → INSERTED`);
    }
  }

  console.log(`\n✓ Done. ${inserted} new official(s) inserted.\n`);
  console.log("Demo emails you can use with POST /auth/request-otp:");
  for (const o of DEMO_OFFICIALS) {
    console.log(`  ${o.email.padEnd(38)} [${o.role}]`);
  }
  console.log("");

  // Give debounced save time to flush
  await new Promise((r) => setTimeout(r, 500));
  process.exit(0);
}

seed().catch((err) => {
  console.error("Seed failed:", err);
  process.exit(1);
});
