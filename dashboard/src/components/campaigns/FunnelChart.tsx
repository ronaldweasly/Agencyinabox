"use client"

import { motion } from "framer-motion"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts"

interface FunnelChartProps {
  data: { stage: string; value: number; fill: string }[]
}

export function FunnelChart({ data }: FunnelChartProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3, duration: 0.4 }}
      className="rounded-lg border border-border bg-card p-4"
    >
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Campaign Funnel
      </h3>
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#8b949e" }} />
            <YAxis dataKey="stage" type="category" tick={{ fontSize: 10, fill: "#8b949e" }} width={70} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0d1117", border: "1px solid #1e2a38", borderRadius: 8, fontSize: 12 }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((entry, idx) => (
                <rect key={idx} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  )
}
