import { NextResponse } from "next/server"
import { mockCompanies } from "../../../../lib/mockData"

export async function GET() {
  return NextResponse.json({
    data: mockCompanies,
    total: mockCompanies.length,
    page: 1,
    per_page: 50,
  })
}
