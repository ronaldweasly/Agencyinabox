"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Shell } from "@/components/layout/Shell"
import { LeadCard } from "@/components/leads/LeadCard"
import { AnimatedCounter } from "@/components/shared/AnimatedCounter"
import { EmptyState } from "@/components/shared/EmptyState"
import { Button } from "@/components/ui/button"
import { useLeads } from "@/hooks/useLeads"
import { cn } from "@/lib/utils"
import { Rocket, Zap, Flame, Target } from "lucide-react"
import type { Company, Contact, AIScore } from "@/lib/types"

interface LeadItem {
  company: Company
  contact: Contact | null
  ai_score: AIScore | null
}

interface LeadsResponse {
  data: LeadItem[]
  total: number
}

const tierFilters = [
  { value: "", label: "All" },
  { value: "hot", label: "Hot 🔴" },
  { value: "warm", label: "Warm 🟡" },
]

const scoreFilters = [
  { value: 0, label: "Any" },
  { value: 65, label: "65+" },
  { value: 70, label: "70+" },
  { value: 80, label: "80+" },
]

export default function LeadsPage() {
  const { data, mutate } = useLeads() as { data: LeadsResponse | undefined; mutate: () => void }
  const [tierFilter, setTierFilter] = useState("")
  const [scoreFilter, setScoreFilter] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const leads = (data?.data ?? []).filter((l) => {
    if (tierFilter && l.company.qualification_tier !== tierFilter) return false
    if (l.company.ai_score < scoreFilter) return false
    return true
  })

  const hotCount = leads.filter((l) => l.company.qualification_tier === "hot").length
  const avgScore = leads.length > 0 ? Math.round(leads.reduce((a, l) => a + l.company.ai_score, 0) / leads.length) : 0

  function toggleSelect(id: string) {
    const next = new Set(selected)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelected(next)
  }

  return (
    <Shell>
      <div className="flex flex-col gap-6 p-6">
        {/* Header Stats */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Ready to Activate", value: leads.length, icon: Zap, color: "text-cyan" },
            { label: "Activated Today", value: 124, icon: Rocket, color: "text-system-green" },
            { label: "Avg Score", value: avgScore, icon: Target, color: "text-purple" },
            { label: "Hot Leads", value: hotCount, icon: Flame, color: "text-hot" },
          ].map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="rounded-lg border border-border bg-card p-4"
            >
              <div className="mb-1 flex items-center gap-2">
                <s.icon className={cn("h-4 w-4", s.color)} />
                <span className="text-xs text-muted-foreground">{s.label}</span>
              </div>
              <AnimatedCounter value={s.value} className="text-2xl font-mono font-bold" />
            </motion.div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex gap-1">
            {tierFilters.map((t) => (
              <button
                key={t.value}
                onClick={() => setTierFilter(t.value)}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                  tierFilter === t.value ? "bg-accent/20 text-accent" : "bg-muted text-muted-foreground hover:text-foreground"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-border" />
          <div className="flex gap-1">
            {scoreFilters.map((s) => (
              <button
                key={s.value}
                onClick={() => setScoreFilter(s.value)}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                  scoreFilter === s.value ? "bg-accent/20 text-accent" : "bg-muted text-muted-foreground hover:text-foreground"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Lead cards grid */}
        {leads.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {leads.map((l, i) => (
              <LeadCard
                key={l.company.id}
                company={l.company}
                contact={l.contact}
                aiScore={l.ai_score}
                index={i}
                selected={selected.has(l.company.id)}
                onSelect={toggleSelect}
                onActivated={mutate}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="No leads match your filters" description="Try lowering the score threshold or widening the tier filter." />
        )}

        {/* Bulk activate footer */}
        {selected.size > 0 && (
          <motion.div
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="fixed bottom-0 left-64 right-0 z-50 border-t border-border bg-card p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm">{selected.size} lead{selected.size > 1 ? "s" : ""} selected</span>
              <Button className="gap-1.5 bg-accent text-background hover:bg-accent/80">
                <Rocket className="h-4 w-4" /> Activate Selected ({selected.size})
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </Shell>
  )
}
