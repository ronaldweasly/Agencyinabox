import { NextResponse } from "next/server"
import { mockCampaigns } from "@/lib/mockData"

export async function GET() {
  return NextResponse.json(mockCampaigns.filter((c) => c.reply_sentiment === "positive"))
}
