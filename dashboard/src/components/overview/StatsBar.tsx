"use client"

import { motion } from "framer-motion"
import { AnimatedCounter } from "@/components/shared/AnimatedCounter"
import { usePipelineStats } from "@/hooks/usePipeline"
import { Building2, CheckCircle2, Brain, Zap, Send } from "lucide-react"

const stats = [
  { key: "discovered", label: "Companies Discovered", icon: Building2, color: "text-cyan" },
  { key: "enriched", label: "Enriched", icon: CheckCircle2, color: "text-purple" },
  { key: "scored", label: "AI Scored", icon: Brain, color: "text-system-green" },
  { key: "qualified", label: "Qualified Leads", icon: Zap, color: "text-system-yellow" },
  { key: "sent", label: "Emails Sent", icon: Send, color: "text-system-orange" },
] as const

export function StatsBar() {
  const { data } = usePipelineStats() as { data: Record<string, number> | undefined }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {stats.map((s, i) => {
        const Icon = s.icon
        const value = data?.[s.key] ?? 0
        return (
          <motion.div
            key={s.key}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.4 }}
            className="rounded-lg border border-border bg-card p-4"
          >
            <div className="mb-2 flex items-center gap-2">
              <Icon className={`h-4 w-4 ${s.color}`} />
              <span className="text-xs text-muted-foreground">{s.label}</span>
            </div>
            <AnimatedCounter value={value} className="text-2xl font-mono font-bold tracking-tight" />
          </motion.div>
        )
      })}
    </div>
  )
}
