import { NextResponse } from 'next/server'
import { mockCompanies } from '@/lib/mockData'

export async function GET() {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'

  if (isDev) {
    const leads = mockCompanies.filter(
      (c) => c.qualification_tier === 'hot' || c.qualification_tier === 'warm'
    )
    return NextResponse.json({ leads, total: leads.length })
  }

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/leads`,
      { next: { revalidate: 15 } }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}
