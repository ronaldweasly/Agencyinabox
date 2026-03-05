import { NextResponse } from 'next/server'
import { mockQueues } from '@/lib/mockData'

export async function GET() {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'

  if (isDev) {
    const data = mockQueues.map((q) => ({
      ...q,
      depth: Math.max(0, q.depth + Math.floor(Math.random() * 100 - 50)),
    }))
    return NextResponse.json(data)
  }

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/overview/queues`,
      { next: { revalidate: 3 } }
    )
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}
