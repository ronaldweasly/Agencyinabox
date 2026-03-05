import { NextResponse } from "next/server"

function jitter(n: number) {
  return Math.round(n * (1 + (Math.random() - 0.5) * 0.1))
}

export async function GET() {
  return NextResponse.json({
    discovery_by_day: Array.from({ length: 7 }, (_, i) => ({
      date: new Date(Date.now() - (6 - i) * 86400000).toISOString().slice(0, 10),
      google_maps: jitter(4200),
      yelp: jitter(1800),
      ssl_certs: jitter(900),
    })),
    score_distribution: [
      { bucket: "0-20", count: jitter(12400) },
      { bucket: "21-40", count: jitter(34200) },
      { bucket: "41-60", count: jitter(58900) },
      { bucket: "61-80", count: jitter(41200) },
      { bucket: "81-100", count: jitter(18300) },
    ],
    funnel: {
      sent: 12441,
      opened: 5490,
      clicked: 1007,
      replied: 460,
      converted: 149,
    },
  })
}
