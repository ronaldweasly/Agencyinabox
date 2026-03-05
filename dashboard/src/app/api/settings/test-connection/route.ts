import { NextResponse } from "next/server"

export async function POST(req: Request) {
  const { service } = await req.json()
  // Simulate connection test
  await new Promise((r) => setTimeout(r, 500))
  const success = Math.random() > 0.2
  return NextResponse.json({
    ok: success,
    service,
    latency_ms: Math.round(Math.random() * 200 + 50),
  })
}
