import { NextResponse } from "next/server"
import { mockCompanies, mockContacts, mockAIScores, mockCampaigns, mockEvents } from "../../../../../lib/mockData"

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const company = mockCompanies.find((c) => c.id === id) ?? mockCompanies[0]
  return NextResponse.json({
    company,
    contacts: mockContacts[company.id] ?? [],
    ai_score: mockAIScores[company.id] ?? null,
    campaigns: mockCampaigns.filter((c) => c.company_id === company.id),
    events: mockEvents.slice(0, 10),
  })
}
