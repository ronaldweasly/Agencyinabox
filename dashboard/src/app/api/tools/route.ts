import { NextResponse } from 'next/server'
import { mockApiKeys, mockTools } from '@/lib/mockData'

export async function GET() {
  const isDev = process.env.NEXT_PUBLIC_DEV_MODE === 'true'
  if (isDev) {
    return NextResponse.json({ api_keys: mockApiKeys, tools: mockTools })
  }
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/tools`, { cache: 'no-store' }
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
    // Simulate test connection — random latency
    if (body.action === 'test') {
      await new Promise(r => setTimeout(r, 600 + Math.random() * 800))
      return NextResponse.json({
        success: true,
        latency_ms: Math.floor(200 + Math.random() * 600),
        connected: true,
      })
    }
    return NextResponse.json({ success: true })
  }
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/tools`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return NextResponse.json(await res.json())
  } catch {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }
}
