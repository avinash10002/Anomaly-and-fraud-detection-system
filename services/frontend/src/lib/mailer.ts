import nodemailer from "nodemailer";

const SMTP_USER = process.env.SMTP_USER || "avinashgoel1568@gmail.com";
const SMTP_PASS = (process.env.SMTP_PASS || "xglxtvvaiiomvimu").replace(/\s+/g, "");
const SMTP_FROM = process.env.SMTP_FROM || `"MPLADS Audit System" <${SMTP_USER}>`;

const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: SMTP_USER,
    pass: SMTP_PASS,
  },
});

export async function sendOtpFromVercel(toEmail: string, toName: string, otp: string) {
  const minutesStr = 5;

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
                Dashboard. This code expires in <strong>${minutesStr} minutes</strong>
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

  return transporter.sendMail({
    from: SMTP_FROM,
    to: toEmail,
    subject: `${otp} — Your MPLADS Audit login code`,
    text,
    html,
  });
}
