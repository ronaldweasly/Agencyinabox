"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import useSWR from "swr"
import { Shell } from "@/components/layout/Shell"
import { StatusDot } from "@/components/shared/StatusDot"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { fetcher, apiPost } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Pause, Play, Settings2, Wifi } from "lucide-react"

interface ScraperStatus {
  name: string
  status: "running" | "paused" | "rate_limited" | "error"
  jobs_per_hr: number
  last_query: string
  progress: number
  target: number
}

interface ScraperJob {
  id: string
  source: string
  parameters: string
  status: string
  records_found: number
  duration_s: number
  proxy: string
}

const statusMap: Record<string, { dot: "healthy" | "paused" | "stalled" | "error"; label: string; color: string }> = {
  running: { dot: "healthy", label: "Running", color: "text-system-green" },
  paused: { dot: "paused", label: "Paused", color: "text-muted-foreground" },
  rate_limited: { dot: "stalled", label: "Rate Limited", color: "text-system-yellow" },
  error: { dot: "error", label: "Error", color: "text-system-red" },
}

const proxyPools = [
  { name: "Residential (BrightData)", ips: 847, success: 94 },
  { name: "Datacenter (Oxylabs)", ips: 2341, success: 99 },
  { name: "ISP Static (SmartProxy)", ips: 156, success: 97 },
]

export default function ScrapersPage() {
  const { data: scrapers } = useSWR<ScraperStatus[]>("/api/scrapers", fetcher, { refreshInterval: 10000 })
  const { data: jobs } = useSWR<ScraperJob[]>("/api/scrapers/jobs", fetcher, { refreshInterval: 10000 })

  return (
    <Shell>
      <div className="flex flex-col gap-6 p-6">
        {/* Scraper Status Grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(scrapers ?? []).map((s, i) => {
            const st = statusMap[s.status] ?? statusMap.paused
            const pct = s.target > 0 ? Math.round((s.progress / s.target) * 100) : 0
            return (
              <motion.div
                key={s.name}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, duration: 0.35 }}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusDot status={st.dot} />
                    <span className="font-semibold">{s.name}</span>
                  </div>
                  <Badge variant="outline" className={cn("text-[10px]", st.color)}>{st.label}</Badge>
                </div>

                <div className="mt-3 font-mono text-lg font-bold">{s.jobs_per_hr.toLocaleString()} <span className="text-xs font-normal text-muted-foreground">jobs/hr</span></div>
                <div className="mt-1 text-xs text-muted-foreground">Last: {s.last_query}</div>

                <div className="mt-3">
                  <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                    <span>Progress</span>
                    <span className="font-mono">{s.progress.toLocaleString()}/{s.target.toLocaleString()}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <motion.div
                      className={cn("h-full rounded-full", s.status === "error" ? "bg-system-red" : "bg-accent")}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.8 }}
                    />
                  </div>
                  <div className="mt-1 text-right font-mono text-[10px] text-muted-foreground">{pct}%</div>
                </div>

                <div className="mt-3 flex gap-2">
                  {s.status === "running" ? (
                    <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => apiPost(`/api/scrapers/${s.name.toLowerCase().replace(/ /g, "_")}/pause`)}>
                      <Pause className="h-3 w-3" /> Pause
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => apiPost(`/api/scrapers/${s.name.toLowerCase().replace(/ /g, "_")}/resume`)}>
                      <Play className="h-3 w-3" /> Resume
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" className="gap-1.5 text-xs">
                    <Settings2 className="h-3 w-3" /> Config
                  </Button>
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Jobs Table */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.4 }}>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-muted-foreground">Recent Jobs</h2>
          <div className="rounded-lg border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead>Source</TableHead>
                  <TableHead>Parameters</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Records</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead>Proxy</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(jobs ?? []).map((j) => (
                  <TableRow key={j.id} className="border-border">
                    <TableCell className="font-medium capitalize text-sm">{j.source.replace(/_/g, " ")}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{j.parameters}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn(
                        "text-[10px] capitalize",
                        j.status === "completed" ? "text-system-green border-system-green/30" :
                        j.status === "running" ? "text-cyan border-cyan/30" :
                        "text-system-red border-system-red/30"
                      )}>
                        {j.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{j.records_found.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{j.duration_s}s</TableCell>
                    <TableCell className="text-xs capitalize text-muted-foreground">{j.proxy}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </motion.div>

        {/* Proxy Pool Status */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.4 }}>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-muted-foreground">Proxy Pool Status</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {proxyPools.map((p, i) => (
              <div key={p.name} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center gap-2">
                  <Wifi className="h-4 w-4 text-cyan" />
                  <span className="text-sm font-medium">{p.name}</span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-xs text-muted-foreground">Active IPs</div>
                    <div className="font-mono text-lg font-bold">{p.ips.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Success Rate</div>
                    <div className="font-mono text-lg font-bold text-system-green">{p.success}%</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </Shell>
  )
}
