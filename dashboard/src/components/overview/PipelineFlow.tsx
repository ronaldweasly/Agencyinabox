"use client"

import { motion } from "framer-motion"
import { usePipelineQueues } from "@/hooks/usePipeline"
import { cn } from "@/lib/utils"

const stages = [
  { key: "discovery_queue", label: "Discovery", row: 0, col: 0 },
  { key: "dedup_queue", label: "Dedup", row: 0, col: 1 },
  { key: "enrichment_queue", label: "Enrichment", row: 0, col: 2 },
  { key: "contact_disc_queue", label: "Contact Disc", row: 0, col: 3 },
  { key: "email_verify_queue", label: "Email Verify", row: 1, col: 3 },
  { key: "ai_score_queue", label: "AI Scoring", row: 1, col: 2 },
  { key: "outreach_queue", label: "Outreach", row: 1, col: 1 },
  { key: "monitoring_queue", label: "Monitoring", row: 1, col: 0 },
]

function depthColor(depth: number) {
  if (depth > 10000) return "text-system-red"
  if (depth >= 1000) return "text-system-yellow"
  return "text-system-green"
}

function depthBorder(depth: number) {
  if (depth > 10000) return "border-system-red/40"
  if (depth >= 1000) return "border-system-yellow/30"
  return "border-border"
}

interface QueueData {
  name: string
  depth: number
  throughput: number
  workers: number
  status: string
}

export function PipelineFlow() {
  const { data } = usePipelineQueues() as { data: QueueData[] | undefined }
  const queueMap = new Map((data ?? []).map((q: QueueData) => [q.name, q]))

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.3, duration: 0.5 }}
      className="rounded-lg border border-border bg-card p-6"
    >
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-muted-foreground">
        Pipeline Flow
      </h2>

      {/* Top row */}
      <div className="relative mb-2">
        <div className="grid grid-cols-4 gap-4">
          {stages.filter((s) => s.row === 0).map((stage, i) => {
            const q = queueMap.get(stage.key)
            const depth = q?.depth ?? 0
            return (
              <div key={stage.key} className="relative">
                <div
                  className={cn(
                    "rounded-lg border bg-[var(--bg2)] p-3 transition-all",
                    depthBorder(depth),
                    depth > 10000 && "animate-pulse"
                  )}
                >
                  <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {stage.label}
                  </div>
                  <div className={cn("mt-1 font-mono text-lg font-bold", depthColor(depth))}>
                    {depth.toLocaleString()}
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>{q?.throughput ?? 0} jobs/min</span>
                    <span>{q?.workers ?? 0} workers</span>
                  </div>
                </div>
                {/* Arrow */}
                {i < 3 && (
                  <div className="absolute -right-4 top-1/2 z-10 flex -translate-y-1/2 items-center">
                    <div className="relative h-0.5 w-4 bg-border overflow-hidden">
                      <motion.div
                        className="absolute h-full w-1.5 rounded-full bg-cyan"
                        animate={{ x: [0, 16] }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Connecting arrow from col 3 top to col 3 bottom */}
        <div className="absolute right-[calc(12.5%-8px)] top-full z-10 flex h-6 items-center justify-center">
          <div className="relative h-6 w-0.5 bg-border overflow-hidden">
            <motion.div
              className="absolute w-full h-1.5 rounded-full bg-cyan"
              animate={{ y: [0, 24] }}
              transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
            />
          </div>
        </div>
      </div>

      {/* Spacer */}
      <div className="h-6" />

      {/* Bottom row (reversed direction) */}
      <div className="grid grid-cols-4 gap-4">
        {stages
          .filter((s) => s.row === 1)
          .sort((a, b) => b.col - a.col)
          .map((stage, i) => {
            const q = queueMap.get(stage.key)
            const depth = q?.depth ?? 0
            return (
              <div key={stage.key} className="relative">
                <div
                  className={cn(
                    "rounded-lg border bg-[var(--bg2)] p-3 transition-all",
                    depthBorder(depth),
                    depth > 10000 && "animate-pulse"
                  )}
                >
                  <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {stage.label}
                  </div>
                  <div className={cn("mt-1 font-mono text-lg font-bold", depthColor(depth))}>
                    {depth.toLocaleString()}
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>{q?.throughput ?? 0} jobs/min</span>
                    <span>{q?.workers ?? 0} workers</span>
                  </div>
                </div>
                {/* Arrow (left direction) */}
                {i < 3 && (
                  <div className="absolute -right-4 top-1/2 z-10 flex -translate-y-1/2 items-center">
                    <div className="relative h-0.5 w-4 bg-border overflow-hidden">
                      <motion.div
                        className="absolute h-full w-1.5 rounded-full bg-cyan"
                        animate={{ x: [16, 0] }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )
          })}
      </div>
    </motion.div>
  )
}
