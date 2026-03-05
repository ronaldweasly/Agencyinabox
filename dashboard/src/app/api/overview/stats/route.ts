import { NextResponse } from 'next/server'

export async function GET() {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'

  if (isDev) {
    return NextResponse.json({
      discovered: 2_847_291,
      enriched:   1_204_847,
      scored:       891_203,
      qualified:     47_832,
      sent:          12_441,
    })
  }

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/overview/stats`,
      { next: { revalidate: 5 } }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}
