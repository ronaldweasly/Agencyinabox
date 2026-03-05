"use client"

import { motion } from "framer-motion"
import { usePipelineCharts } from "@/hooks/usePipeline"
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts"

interface ChartData {
  discovery_by_day: Array<{ date: string; google_maps: number; yelp: number; ssl_certs: number }>
  score_distribution: Array<{ bucket: string; count: number }>
  funnel: { sent: number; opened: number; clicked: number; replied: number; converted: number }
}

const tooltipStyle = {
  contentStyle: {
    backgroundColor: "#0d1117",
    border: "1px solid #1e2a38",
    borderRadius: 8,
    fontSize: 12,
  },
  labelStyle: { color: "#8b949e" },
}

export function OverviewCharts() {
  const { data } = usePipelineCharts() as { data: ChartData | undefined }
  if (!data) return null

  const funnelData = [
    { stage: "Sent", value: data.funnel.sent, fill: "#00e5ff" },
    { stage: "Opened", value: data.funnel.opened, fill: "#7c3aed" },
    { stage: "Clicked", value: data.funnel.clicked, fill: "#ffd166" },
    { stage: "Replied", value: data.funnel.replied, fill: "#00d68f" },
    { stage: "Converted", value: data.funnel.converted, fill: "#ff6b35" },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Discovery by Day */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.4 }}
        className="rounded-lg border border-border bg-card p-4"
      >
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Companies Discovered (7d)
        </h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.discovery_by_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#8b949e" }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 10, fill: "#8b949e" }} width={40} />
              <Tooltip {...tooltipStyle} />
              <defs>
                <linearGradient id="gm" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00e5ff" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#00e5ff" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="yelp" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#7c3aed" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="ssl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ff6b35" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#ff6b35" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="google_maps" stackId="1" stroke="#00e5ff" fill="url(#gm)" strokeWidth={1.5} />
              <Area type="monotone" dataKey="yelp" stackId="1" stroke="#7c3aed" fill="url(#yelp)" strokeWidth={1.5} />
              <Area type="monotone" dataKey="ssl_certs" stackId="1" stroke="#ff6b35" fill="url(#ssl)" strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Score Distribution */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.4 }}
        className="rounded-lg border border-border bg-card p-4"
      >
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          AI Score Distribution
        </h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.score_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
              <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: "#8b949e" }} />
              <YAxis tick={{ fontSize: 10, fill: "#8b949e" }} width={40} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.score_distribution.map((entry, idx) => {
                  const colors = ["#5a6478", "#5a6478", "#ffd166", "#ff6b35", "#ff4d6d"]
                  return <rect key={idx} fill={colors[idx] ?? "#5a6478"} />
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Campaign Funnel */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7, duration: 0.4 }}
        className="rounded-lg border border-border bg-card p-4"
      >
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Campaign Funnel
        </h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={funnelData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10, fill: "#8b949e" }} />
              <YAxis dataKey="stage" type="category" tick={{ fontSize: 10, fill: "#8b949e" }} width={70} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {funnelData.map((entry, idx) => (
                  <rect key={idx} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </motion.div>
    </div>
  )
}
