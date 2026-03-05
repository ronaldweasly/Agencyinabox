"use client"

import { motion } from "framer-motion"
import { usePipelineQueues } from "@/hooks/usePipeline"
import { StatusDot } from "@/components/shared/StatusDot"
import { cn } from "@/lib/utils"
import {
  Area,
  AreaChart,
  ResponsiveContainer,
} from "recharts"

interface QueueData {
  name: string
  depth: number
  throughput: number
  workers: number
  status: "healthy" | "backlogged" | "stalled" | "error"
  last_job_at: string
  history: number[]
}

function borderColor(status: string) {
  if (status === "healthy") return "border-l-system-green"
  if (status === "backlogged") return "border-l-system-yellow"
  if (status === "stalled") return "border-l-system-orange"
  return "border-l-system-red"
}

function sparkColor(status: string) {
  if (status === "healthy") return "#00d68f"
  if (status === "backlogged") return "#ffd166"
  if (status === "stalled") return "#ff6b35"
  return "#ff4d6d"
}

function timeSince(iso: string) {
  const diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  return `${Math.round(diff / 60)}m ago`
}

export function QueueDepthCards() {
  const { data } = usePipelineQueues() as { data: QueueData[] | undefined }
  const queues = (data ?? []) as QueueData[]

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {queues.map((q, i) => {
        const chartData = (q.history ?? []).map((v, j) => ({ i: j, v }))
        return (
          <motion.div
            key={q.name}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 + i * 0.06, duration: 0.35 }}
            className={cn(
              "rounded-lg border border-border border-l-4 bg-card p-4",
              borderColor(q.status),
              q.depth > 10000 && "ring-1 ring-system-red/20"
            )}
          >
            <div className="flex items-center justify-between">
              <span className="truncate text-xs font-semibold text-muted-foreground">{q.name}</span>
              <StatusDot status={q.status} />
            </div>
            <div
              className={cn(
                "mt-1 font-mono text-2xl font-bold tracking-tight",
                q.depth > 10000 ? "text-system-red" : q.depth >= 1000 ? "text-system-yellow" : "text-foreground"
              )}
            >
              {q.depth.toLocaleString()}
            </div>
            <div className="my-2 h-8">
              {chartData.length > 1 && (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id={`grad-${q.name}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={sparkColor(q.status)} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={sparkColor(q.status)} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="v"
                      stroke={sparkColor(q.status)}
                      strokeWidth={1.5}
                      fill={`url(#grad-${q.name})`}
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <span className="uppercase font-semibold">
                {q.status}
              </span>
              <span>Last: {timeSince(q.last_job_at)}</span>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
