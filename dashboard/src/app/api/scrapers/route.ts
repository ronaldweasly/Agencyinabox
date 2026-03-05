import { NextResponse } from "next/server"

export async function GET() {
  return NextResponse.json([
    { name: "Google Maps", status: "running", jobs_per_hr: 847, last_query: "Austin TX · HVAC", progress: 12847, target: 50000 },
    { name: "Yelp", status: "running", jobs_per_hr: 423, last_query: "Dallas TX · Plumbing", progress: 8421, target: 30000 },
    { name: "SSL Certs", status: "rate_limited", jobs_per_hr: 112, last_query: "expiring < 30d", progress: 4501, target: 20000 },
    { name: "LinkedIn Jobs", status: "running", jobs_per_hr: 234, last_query: "HVAC hiring", progress: 2345, target: 10000 },
    { name: "Crunchbase", status: "paused", jobs_per_hr: 0, last_query: "Series A · SaaS", progress: 0, target: 5000 },
    { name: "Meta Ads", status: "error", jobs_per_hr: 0, last_query: "home services ads", progress: 1200, target: 15000 },
  ])
}
