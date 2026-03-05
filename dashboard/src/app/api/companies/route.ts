import { NextResponse } from 'next/server'
import { mockCompanies } from '@/lib/mockData'

export async function GET() {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'

  if (isDev) {
    return NextResponse.json({
      companies: mockCompanies,
      total: mockCompanies.length,
    })
  }

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/companies`,
      { next: { revalidate: 30 } }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}
