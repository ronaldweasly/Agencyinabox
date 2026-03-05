import { NextResponse } from "next/server"

const settings = {
  scoring: { hot_threshold: 70, warm_threshold: 50, auto_activate: 65, rescore_days: 7 },
  campaigns: { api_key: "sk-inst-****", daily_limit: 200, cooling_days: 60 },
  api_keys: {
    hunterio: "****",
    neverbounce: "****",
    zerobounce: "****",
    clearbit: "****",
    pagespeedapi: "****",
  },
  notifications: {
    telegram_token: "****",
    telegram_chat_id: "****",
    alerts: { hot_lead: true, reply: true, queue_stalled: true, worker_crashed: true, daily_summary: true },
  },
}

export async function GET() {
  return NextResponse.json(settings)
}

export async function POST(req: Request) {
  const body = await req.json()
  Object.assign(settings, body)
  return NextResponse.json({ ok: true })
}
