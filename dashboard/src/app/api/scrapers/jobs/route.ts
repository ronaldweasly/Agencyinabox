import { NextResponse } from "next/server"

function jitter(n: number) {
  return Math.round(n * (1 + (Math.random() - 0.5) * 0.2))
}

export async function GET() {
  const sources = ["google_maps", "yelp", "ssl_certs", "linkedin_jobs", "crunchbase", "meta_ads"]
  return NextResponse.json(
    Array.from({ length: 20 }, (_, i) => ({
      id: `job_${i}`,
      source: sources[i % 6],
      parameters: "Austin TX · HVAC",
      status: i < 15 ? "completed" : i < 18 ? "running" : "error",
      records_found: jitter(847),
      duration_s: jitter(34),
      proxy: i % 2 === 0 ? "residential" : "datacenter",
    }))
  )
}
