import { NextResponse } from "next/server"
import { mockCampaigns } from "@/lib/mockData"

export async function GET() {
  return NextResponse.json({
    data: mockCampaigns,
    stats: {
      sent: 12441,
      open_rate: 44.2,
      click_rate: 8.1,
      reply_rate: 3.7,
      positive_rate: 1.2,
    },
  })
}
