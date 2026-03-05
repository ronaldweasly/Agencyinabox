import { NextResponse } from 'next/server'
import { mockTargets, mockCategories } from '@/lib/mockData'

export async function GET() {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'
  if (isDev) {
    return NextResponse.json({
      targets: mockTargets,
      categories: mockCategories,
      total_estimated_leads: mockTargets
        .filter(t => t.is_active)
        .reduce((sum, t) => sum + t.estimated_leads, 0),
    })
  }
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/targeting`,
      { cache: 'no-store' }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}

export async function POST(request: Request) {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'
  const body = await request.json()
  if (isDev) {
    // In dev mode — just echo back success
    return NextResponse.json({ success: true, data: body })
  }
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/targeting`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}
