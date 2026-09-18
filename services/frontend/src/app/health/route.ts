import { NextResponse } from "next/server";

/** Docker / compose healthcheck endpoint */
export async function GET() {
  return NextResponse.json({ status: "ok" });
}
