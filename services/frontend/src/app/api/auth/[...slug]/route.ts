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

    const backendRes = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: bodyText,
      cache: "no-store",
    });

    const data = await backendRes.json().catch(() => ({}));

    const clientRes = NextResponse.json(data, {
      status: backendRes.status,
    });

    // Forward Set-Cookie headers (e.g. mplads_auth JWT cookie or logout clear-cookie)
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
        message: `Could not reach authentication service at ${AUTH_SERVICE_URL}. Please ensure auth-service is running. (${message})`,
      },
      { status: 503 }
    );
  }
}
