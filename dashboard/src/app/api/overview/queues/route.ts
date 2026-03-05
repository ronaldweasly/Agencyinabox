import { NextResponse } from "next/server"
import { mockQueues } from "../../../../../lib/mockData"

export async function GET() {
  const queues = mockQueues.map((q) => ({
    ...q,
    depth: q.depth + Math.round((Math.random() - 0.5) * q.depth * 0.1),
    throughput: q.throughput + Math.round((Math.random() - 0.5) * q.throughput * 0.1),
    last_job_at: new Date().toISOString(),
  }))
  return NextResponse.json(queues)
}
