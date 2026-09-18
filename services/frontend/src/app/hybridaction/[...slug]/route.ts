import { NextResponse } from "next/server";

/**
 * Handle third-party browser extension / device tracker probes
 * (e.g. zybTrackerStatisticsAction) cleanly with 204 No Content
 * to prevent 404 console noise and aggressive retry loops.
 */
export async function GET() {
  return new NextResponse(null, { status: 204 });
}

export async function POST() {
  return new NextResponse(null, { status: 204 });
}
