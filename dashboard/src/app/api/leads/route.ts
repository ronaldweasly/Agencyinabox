import { NextResponse } from "next/server"
import { mockCompanies, mockContacts, mockAIScores } from "../../../../lib/mockData"

export async function GET() {
  const hot = mockCompanies.filter((c) => c.qualified)
  return NextResponse.json({
    data: hot.map((c) => ({
      company: c,
      contact: (mockContacts[c.id] ?? [])[0] ?? null,
      ai_score: mockAIScores[c.id] ?? null,
    })),
    total: hot.length,
  })
}
