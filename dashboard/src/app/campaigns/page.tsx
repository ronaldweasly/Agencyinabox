"use client"

import { motion } from "framer-motion"
import { Shell } from "@/components/layout/Shell"
import { KPICard } from "@/components/campaigns/CampaignStats"
import { FunnelChart } from "@/components/campaigns/FunnelChart"
import { ReplyIntelligence } from "@/components/campaigns/ReplyIntelligence"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCampaigns, useCampaignReplies } from "@/hooks/useCampaigns"
import { Send, Eye, MousePointerClick, MessageSquare, ThumbsUp } from "lucide-react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts"
import type { Campaign } from "@/lib/types"
import { cn } from "@/lib/utils"

interface CampaignsResponse {
  data: Campaign[]
  stats: {
    sent: number
    open_rate: number
    click_rate: number
    reply_rate: number
    positive_rate: number
  }
}

export default function CampaignsPage() {
  const { data } = useCampaigns() as { data: CampaignsResponse | undefined }
  const { data: replies } = useCampaignReplies() as { data: Campaign[] | undefined }
  const stats = data?.stats
  const campaigns = data?.data ?? []

  const funnelData = stats ? [
    { stage: "Sent", value: stats.sent, fill: "#00e5ff" },
    { stage: "Opened", value: Math.round(stats.sent * stats.open_rate / 100), fill: "#7c3aed" },
    { stage: "Clicked", value: Math.round(stats.sent * stats.click_rate / 100), fill: "#ffd166" },
    { stage: "Replied", value: Math.round(stats.sent * stats.reply_rate / 100), fill: "#00d68f" },
    { stage: "Converted", value: Math.round(stats.sent * stats.positive_rate / 100), fill: "#ff6b35" },
  ] : []

  // Mock time series for line chart
  const timeSeries = Array.from({ length: 30 }, (_, i) => ({
    day: i + 1,
    open_rate: 40 + Math.random() * 10,
    reply_rate: 2 + Math.random() * 3,
  }))

  // Sentiment donut
  const sentimentData = [
    { name: "Positive", value: 45, color: "#00d68f" },
    { name: "Negative", value: 15, color: "#ff4d6d" },
    { name: "Neutral", value: 25, color: "#ffd166" },
    { name: "No Reply", value: 415, color: "#5a6478" },
  ]

  return (
    <Shell>
      <div className="flex flex-col gap-6 p-6">
        {/* KPI Row */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <KPICard label="Emails Sent" value={stats?.sent ?? 0} icon={<Send className="h-4 w-4" />} delay={0} sparkData={[8000, 9200, 10500, 11400, 12441]} />
          <KPICard label="Open Rate" value={stats?.open_rate ?? 0} format="percent" suffix="%" icon={<Eye className="h-4 w-4" />} delay={0.06} delta={2.3} />
          <KPICard label="Click Rate" value={stats?.click_rate ?? 0} format="percent" suffix="%" icon={<MousePointerClick className="h-4 w-4" />} delay={0.12} delta={-0.4} />
          <KPICard label="Reply Rate" value={stats?.reply_rate ?? 0} format="percent" suffix="%" icon={<MessageSquare className="h-4 w-4" />} delay={0.18} delta={0.8} />
          <KPICard label="Positive Rate" value={stats?.positive_rate ?? 0} format="percent" suffix="%" icon={<ThumbsUp className="h-4 w-4" />} delay={0.24} delta={0.2} />
        </div>

        {/* Campaigns Table */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.4 }}>
          <div className="rounded-lg border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead>Campaign</TableHead>
                  <TableHead>Service</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Opens</TableHead>
                  <TableHead className="text-right">Clicks</TableHead>
                  <TableHead className="text-right">Replies</TableHead>
                  <TableHead>Sentiment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaigns.map((c) => (
                  <TableRow key={c.id} className="border-border cursor-pointer hover:bg-muted/50">
                    <TableCell className="font-medium">{c.campaign_name}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{c.service_type}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize text-[10px]">{c.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.email_opens}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.email_clicks}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{c.email_replies}</TableCell>
                    <TableCell>
                      {c.reply_sentiment ? (
                        <Badge variant="outline" className={cn(
                          "text-[10px]",
                          c.reply_sentiment === "positive" ? "text-system-green border-system-green/30" :
                          c.reply_sentiment === "negative" ? "text-system-red border-system-red/30" : "text-muted-foreground"
                        )}>
                          {c.reply_sentiment}
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </motion.div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Line chart: rates over time */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, duration: 0.4 }} className="rounded-lg border border-border bg-card p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Open & Reply Rate (30d)</h3>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeSeries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2a38" />
                  <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#8b949e" }} />
                  <YAxis tick={{ fontSize: 10, fill: "#8b949e" }} width={30} />
                  <Tooltip contentStyle={{ backgroundColor: "#0d1117", border: "1px solid #1e2a38", borderRadius: 8, fontSize: 12 }} />
                  <Line type="monotone" dataKey="open_rate" stroke="#00e5ff" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="reply_rate" stroke="#7c3aed" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Donut chart: sentiment */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.4 }} className="rounded-lg border border-border bg-card p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Reply Sentiment</h3>
            <div className="h-52 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={2}>
                    {sentimentData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: "#0d1117", border: "1px solid #1e2a38", borderRadius: 8, fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap justify-center gap-3">
              {sentimentData.map((s) => (
                <div key={s.name} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <div className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
                  {s.name}
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Reply Intelligence */}
        <ReplyIntelligence replies={replies ?? []} />
      </div>
    </Shell>
  )
}
