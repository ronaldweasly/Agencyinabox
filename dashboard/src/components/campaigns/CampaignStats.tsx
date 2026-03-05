"use client"

import { motion } from "framer-motion"
import { AnimatedCounter } from "@/components/shared/AnimatedCounter"
import { cn } from "@/lib/utils"
import { Area, AreaChart, ResponsiveContainer } from "recharts"

interface KPICardProps {
  label: string
  value: number
  format?: "number" | "percent"
  suffix?: string
  delta?: number
  sparkData?: number[]
  icon: React.ReactNode
  delay?: number
}

function KPICard({ label, value, format = "number", suffix, delta, sparkData, icon, delay = 0 }: KPICardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      className="rounded-lg border border-border bg-card p-4"
    >
      <div className="mb-2 flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className="flex items-end justify-between">
        <AnimatedCounter
          value={value}
          format={format}
          suffix={suffix}
          className="text-2xl font-mono font-bold"
        />
        {delta !== undefined && (
          <span className={cn("text-xs font-medium", delta >= 0 ? "text-system-green" : "text-system-red")}>
            {delta >= 0 ? "↑" : "↓"} {Math.abs(delta)}%
          </span>
        )}
      </div>
      {sparkData && sparkData.length > 1 && (
        <div className="mt-2 h-6">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkData.map((v, i) => ({ i, v }))}>
              <defs>
                <linearGradient id="kpiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00e5ff" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#00e5ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v" stroke="#00e5ff" strokeWidth={1} fill="url(#kpiGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  )
}

export { KPICard }
export type { KPICardProps }
