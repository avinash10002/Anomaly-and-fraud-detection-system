import { NextRequest, NextResponse } from "next/server";

const AUTH_SERVICE_URL = process.env.AUTH_SERVICE_URL || "http://127.0.0.1:8086";

export async function GET(
  request: NextRequest,
  { params }: { params: { slug: string[] } }
) {
  return proxyAuth(request, params.slug);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { slug: string[] } }
) {
  return proxyAuth(request, params.slug);
}

async function proxyAuth(request: NextRequest, slug: string[]) {
  const path = slug.join("/");
  const targetUrl = `${AUTH_SERVICE_URL}/auth/${path}`;

  try {
    const headers = new Headers();
    const cookieHeader = request.headers.get("cookie");
    if (cookieHeader) {
      headers.set("cookie", cookieHeader);
    }
    headers.set("Content-Type", "application/json");

    // Extract client IP if present
    const forwardedFor = request.headers.get("x-forwarded-for") || request.ip;
    if (forwardedFor) {
      headers.set("x-forwarded-for", forwardedFor);
    }

    let bodyText: string | undefined = undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      try {
        const bodyJson = await request.json();
        bodyText = JSON.stringify(bodyJson);
      } catch {
        // body could be empty
      }
    }

    headers.set("x-dispatch-caller", "vercel");

    const backendRes = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: bodyText,
      cache: "no-store",
    });

    const data = await backendRes.json().catch(() => ({}));

    // If request-otp returned a delegated dispatch, send email directly via Gmail from Vercel
    if (slug[0] === "request-otp" && data?._dispatch) {
      const { email, name, otp } = data._dispatch;
      delete data._dispatch; // Ensure browser never sees dispatch metadata

      try {
        const { sendOtpFromVercel } = await import("@/lib/mailer");
        await sendOtpFromVercel(email, name, otp);
        console.log(`[vercel-mailer] OTP successfully delivered via Gmail to ${email}`);
      } catch (mailErr: unknown) {
        const mailMsg = mailErr instanceof Error ? mailErr.message : String(mailErr);
        console.error(`[vercel-mailer] Failed to send via Gmail to ${email}:`, mailMsg);
      }
    }

    const clientRes = NextResponse.json(data, {
      status: backendRes.status,
    });

    // Forward Set-Cookie headers
    const setCookie = backendRes.headers.get("set-cookie");
    if (setCookie) {
      clientRes.headers.set("set-cookie", setCookie);
    }

    return clientRes;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Auth service unreachable";
    return NextResponse.json(
      {
        error: "AUTH_SERVICE_UNAVAILABLE",
        message: `Could not reach authentication service at ${AUTH_SERVICE_URL}. (${message})`,
      },
      { status: 503 }
    );
  }
}
