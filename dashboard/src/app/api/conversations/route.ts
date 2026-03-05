import { NextResponse } from 'next/server'
import { mockConversations } from '@/lib/mockData'

export async function GET() {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'
  if (isDev) {
    return NextResponse.json({
      conversations: mockConversations,
      total: mockConversations.length,
      stats: {
        total: mockConversations.length,
        replied: mockConversations.filter(c => c.status === 'replied').length,
        positive: mockConversations.filter(c =>
          c.messages.some(m => m.sentiment === 'positive')).length,
        meeting_booked: mockConversations.filter(c => c.status === 'meeting_booked').length,
      }
    })
  }
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/conversations`, { cache: 'no-store' }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}

export async function POST(request: Request) {
  const body = await request.json()
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'
  if (isDev) return NextResponse.json({ success: true })
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/conversations`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}
