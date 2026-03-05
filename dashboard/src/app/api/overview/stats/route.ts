import { NextResponse } from "next/server"
import { mockCompanies } from "../../../../../lib/mockData"

export async function GET() {
  const discovered = 2_847_291 + Math.round(Math.random() * 1000)
  const enriched = 1_204_847 + Math.round(Math.random() * 500)
  const scored = 891_203 + Math.round(Math.random() * 300)
  const qualified = 47_832 + Math.round(Math.random() * 50)
  const sent = 12_441 + Math.round(Math.random() * 20)

  return NextResponse.json({ discovered, enriched, scored, qualified, sent })
}
