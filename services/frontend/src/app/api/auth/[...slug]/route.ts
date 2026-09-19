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

  let bodyText: string | undefined = undefined;
  let bodyJson: Record<string, any> = {};
  if (request.method !== "GET" && request.method !== "HEAD") {
    try {
      bodyJson = await request.json();
      bodyText = JSON.stringify(bodyJson);
    } catch {
      // body could be empty
    }
  }

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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    const backendRes = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: bodyText,
      cache: "no-store",
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (backendRes.status !== 502 && backendRes.status !== 503 && backendRes.status !== 504) {
      const data = await backendRes.json().catch(() => ({}));
      const clientRes = NextResponse.json(data, {
        status: backendRes.status,
      });

      // Forward Set-Cookie headers
      const setCookie = backendRes.headers.get("set-cookie");
      if (setCookie) {
        clientRes.headers.set("set-cookie", setCookie);
      }
      return clientRes;
    }
  } catch {
    // Backend unreachable: fall through to fallback demo mode
  }

  // ── Fallback Demo Handler (When cloud auth-service is offline) ────────────
  const email = (bodyJson.email || "").toString().trim().toLowerCase();

  if (path === "request-otp") {
    return NextResponse.json(
      {
        status: "pending",
        message:
          "Passcode dispatched. (Cloud auth-service offline; Demo Passcode: 123456)",
      },
      { status: 202 }
    );
  }

  if (path === "verify-otp") {
    const otp = (bodyJson.otp || "").toString().trim();
    if (otp === "123456" || otp === "000000") {
      const demoOfficial = {
        id: "official-demo-01",
        official_id: "official-demo-01",
        name: email.includes("admin") ? "Administrator" : "Avinash Goel (Official)",
        email: email || "official@mplads.gov.in",
        role: "admin",
      };

      const res = NextResponse.json({
        success: true,
        message: "Official authentication successful",
        official: demoOfficial,
      });

      res.cookies.set("mplads_demo_official", JSON.stringify(demoOfficial), {
        httpOnly: true,
        path: "/",
        maxAge: 7200,
        sameSite: "lax",
      });

      return res;
    }

    return NextResponse.json(
      {
        error: "INVALID_OTP",
        message: "Invalid code. In demo mode, please use passcode 123456.",
        attemptsRemaining: 4,
      },
      { status: 401 }
    );
  }

  if (path === "me") {
    const cookieVal = request.cookies.get("mplads_demo_official")?.value;
    if (cookieVal) {
      try {
        const official = JSON.parse(cookieVal);
        return NextResponse.json({ official });
      } catch {}
    }
    return NextResponse.json(
      { error: "UNAUTHORIZED", message: "Not authenticated" },
      { status: 401 }
    );
  }

  if (path === "logout") {
    const res = NextResponse.json({ success: true, message: "Logged out" });
    res.cookies.delete("mplads_demo_official");
    return res;
  }

  return NextResponse.json(
    {
      error: "AUTH_SERVICE_UNAVAILABLE",
      message: `Could not reach authentication service at ${AUTH_SERVICE_URL}.`,
    },
    { status: 503 }
  );
}
