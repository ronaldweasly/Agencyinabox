"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ScoreBadge } from "@/components/shared/ScoreBadge"
import { StatusDot } from "@/components/shared/StatusDot"
import { TechStackPills } from "./TechStackPills"
import { Button } from "@/components/ui/button"
import { ArrowRight, MoreHorizontal, Sparkles, Zap } from "lucide-react"
import type { Company } from "@/lib/types"
import { cn } from "@/lib/utils"

interface CompanyTableProps {
  companies: Company[]
  total: number
  page: number
  onPageChange: (p: number) => void
}

function enrichmentStatus(s: string) {
  const map: Record<string, { dotStatus: "healthy" | "stalled" | "error" | "paused"; label: string }> = {
    complete: { dotStatus: "healthy", label: "Enriched" },
    pending: { dotStatus: "paused", label: "Pending" },
    in_progress: { dotStatus: "stalled", label: "In Progress" },
    failed: { dotStatus: "error", label: "Failed" },
  }
  return map[s] ?? map.pending
}

export function CompanyTable({ companies, total, page, onPageChange }: CompanyTableProps) {
  const perPage = 50
  const totalPages = Math.ceil(total / perPage)

  return (
    <div>
      {/* Results bar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>
          Showing <span className="font-mono text-foreground">{companies.length}</span> of{" "}
          <span className="font-mono text-foreground">{total.toLocaleString()}</span> companies
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
            <Sparkles className="h-3 w-3" /> Re-enrich
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
            <Zap className="h-3 w-3" /> Force Score
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="w-10"><input type="checkbox" className="rounded border-border" /></TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Domain</TableHead>
              <TableHead>Score</TableHead>
              <TableHead>Tech Stack</TableHead>
              <TableHead>Employees</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {companies.map((c, i) => {
              const es = enrichmentStatus(c.enrichment_status)
              return (
                <motion.tr
                  key={c.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.02 }}
                  className="border-border transition-colors hover:bg-muted/50 cursor-pointer"
                >
                  <TableCell><input type="checkbox" className="rounded border-border" /></TableCell>
                  <TableCell>
                    <Link href={`/companies/${c.id}`} className="font-medium hover:text-accent transition-colors">
                      {c.name}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{c.domain}</TableCell>
                  <TableCell>
                    <ScoreBadge score={c.ai_score} tier={c.qualification_tier === "suppressed" ? "suppressed" : c.qualification_tier} size="sm" />
                  </TableCell>
                  <TableCell>
                    <TechStackPills stack={c.tech_stack} max={3} />
                  </TableCell>
                  <TableCell className="font-mono text-xs">{c.employee_count}</TableCell>
                  <TableCell className="text-xs">{c.state}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <StatusDot status={es.dotStatus} />
                      <span className="text-xs">{es.label}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs">
                        <ArrowRight className="h-3 w-3" /> View
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </motion.tr>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <div className="flex gap-1">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            Prev
          </Button>
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => i + 1).map((p) => (
            <Button
              key={p}
              variant={p === page ? "default" : "outline"}
              size="sm"
              onClick={() => onPageChange(p)}
              className={cn(p === page && "bg-accent text-background")}
            >
              {p}
            </Button>
          ))}
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
