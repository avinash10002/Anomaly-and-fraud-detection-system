/**
 * src/mailer.js
 * -------------
 * Nodemailer transport configuration with dual-port fallback (465 SSL / 587 STARTTLS),
 * forced IPv4 family resolution (critical for cloud hosts like Render), and connection timeouts.
 */

"use strict";

const nodemailer = require("nodemailer");
const config     = require("./config");

function cleanPass(pass) {
  return (pass || "").toString().replace(/\s+/g, "");
}

function makeTransport(port, secure) {
  return nodemailer.createTransport({
    host:   config.smtp.host,
    port:   port,
    secure: secure,
    family: 4,               // CRITICAL FOR RENDER: Forces IPv4 to bypass cloud IPv6 connection drops
    connectionTimeout: 12000,
    greetingTimeout: 10000,
    socketTimeout: 15000,
    auth: {
      user: config.smtp.user,
      pass: cleanPass(config.smtp.pass),
    },
    tls: {
      rejectUnauthorized: false,
      minVersion: "TLSv1.2",
    },
  });
}

const primaryTransport = makeTransport(config.smtp.port, config.smtp.secure);
const fallbackPort = config.smtp.port === 465 ? 587 : 465;
const fallbackSecure = fallbackPort === 465;
const fallbackTransport = makeTransport(fallbackPort, fallbackSecure);

/**
 * Send an OTP email to a pre-registered official.
 *
 * @param {string} toEmail   - recipient address
 * @param {string} toName    - recipient display name
 * @param {string} otp       - plaintext 6-digit code
 * @param {number} expiresIn - seconds until expiry (for display in email)
 */
async function sendOtpEmail(toEmail, toName, otp, expiresIn = 300) {
  const minutesStr = Math.round(expiresIn / 60);

  const html = `
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>MPLADS Audit — Login Code</title></head>
    <body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:40px 0">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center">
          <table width="520" style="background:#ffffff;border-radius:8px;border:1px solid #e2e8f0;padding:40px">
            <tr>
              <td style="text-align:center;padding-bottom:24px">
                <span style="font-size:14px;font-weight:700;letter-spacing:2px;color:#64748b;text-transform:uppercase">
                  MPLADS Fraud &amp; Anomaly Detection System
                </span>
              </td>
            </tr>
            <tr>
              <td style="color:#1e293b;font-size:22px;font-weight:700;padding-bottom:8px">
                Your login code, ${toName.split(" ")[0]}
              </td>
            </tr>
            <tr>
              <td style="color:#475569;font-size:14px;padding-bottom:28px;line-height:1.6">
                Use the following one-time passcode to sign in to the MPLADS Audit
                Dashboard. This code expires in <strong>${minutesStr} minute${minutesStr !== 1 ? "s" : ""}</strong>
                and can only be used once.
              </td>
            </tr>
            <tr>
              <td align="center" style="padding-bottom:28px">
                <div style="
                  display:inline-block;
                  background:#f1f5f9;
                  border:2px dashed #94a3b8;
                  border-radius:10px;
                  padding:20px 48px;
                  font-family:monospace;
                  font-size:40px;
                  font-weight:700;
                  letter-spacing:12px;
                  color:#0f172a
                ">
                  ${otp}
                </div>
              </td>
            </tr>
            <tr>
              <td style="background:#fef3c7;border:1px solid #fde68a;border-radius:6px;padding:12px 16px;font-size:13px;color:#92400e;margin-bottom:24px">
                ⚠️ <strong>Security notice:</strong> MPLADS Audit team will never ask for this code
                over phone or email. Do not share it with anyone.
              </td>
            </tr>
            <tr>
              <td style="color:#94a3b8;font-size:12px;padding-top:24px;border-top:1px solid #e2e8f0">
                If you did not request this code, you can safely ignore this email.
                Your account has not been accessed.
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
  `;

  const text = `Your MPLADS Audit login code: ${otp}\n\nExpires in ${minutesStr} minutes. Do not share this code.`;

  // ── 1. HTTP API: Resend (Bypasses cloud SMTP port blocks via standard HTTPS 443) ──
  if (process.env.RESEND_API_KEY) {
    const resendApiKey = process.env.RESEND_API_KEY.trim();
    const resendFrom = process.env.RESEND_FROM || "MPLADS Audit <onboarding@resend.dev>";

    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${resendApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: resendFrom,
        to: [toEmail],
        subject: `${otp} — Your MPLADS Audit login code`,
        html,
        text,
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(`Resend API error: ${data.message || res.statusText}`);
    }

    console.log(`[auth-service] OTP email dispatched via Resend HTTP API to ${toEmail}`);
    return { info: data };
  }

  // ── 2. HTTP API: Brevo (Bypasses cloud SMTP port blocks via standard HTTPS 443) ───
  if (process.env.BREVO_API_KEY) {
    const brevoKey = process.env.BREVO_API_KEY.trim();
    const brevoSender = process.env.BREVO_FROM || config.smtp.user;

    const res = await fetch("https://api.brevo.com/v3/smtp/email", {
      method: "POST",
      headers: {
        "api-key": brevoKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sender: { name: "MPLADS Audit System", email: brevoSender },
        to: [{ email: toEmail, name: toName }],
        subject: `${otp} — Your MPLADS Audit login code`,
        htmlContent: html,
        textContent: text,
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(`Brevo API error: ${data.message || res.statusText}`);
    }

    console.log(`[auth-service] OTP email dispatched via Brevo HTTP API to ${toEmail}`);
    return { info: data };
  }

  // ── 3. Standard SMTP Transport (Works on localhost, paid instances, & non-blocked hosts) ──
  let info;
  try {
    info = await primaryTransport.sendMail({
      from:    config.smtp.from,
      to:      toEmail,
      subject: `${otp} — Your MPLADS Audit login code`,
      text,
      html,
    });
  } catch (primaryErr) {
    console.warn(`[auth-service] Primary SMTP on port ${config.smtp.port} failed: ${primaryErr.message}. Attempting fallback port ${fallbackPort}...`);
    try {
      info = await fallbackTransport.sendMail({
        from:    config.smtp.from,
        to:      toEmail,
        subject: `${otp} — Your MPLADS Audit login code`,
        text,
        html,
      });
    } catch (fallbackErr) {
      if (fallbackErr.message.includes("timeout") || primaryErr.message.includes("timeout")) {
        throw new Error(
          "SMTP Connection Timeout: Render Free Tier blocks outbound SMTP ports 25, 465, and 587. Use a free HTTP email API key (e.g. RESEND_API_KEY from resend.com) in Render environment variables."
        );
      }
      throw fallbackErr;
    }
  }

  console.log(`[auth-service] OTP email dispatched successfully to ${toEmail}`);
  return { info };
}

module.exports = { transport: primaryTransport, sendOtpEmail };
