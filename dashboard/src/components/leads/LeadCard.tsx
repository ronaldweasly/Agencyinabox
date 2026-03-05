"use client"

import { motion } from "framer-motion"
import { ScoreBadge } from "@/components/shared/ScoreBadge"
import { EmailHookPreview } from "./EmailHookPreview"
import { LeadActivateButton } from "./LeadActivateButton"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Copy, CheckCircle2 } from "lucide-react"
import type { Company, Contact, AIScore } from "@/lib/types"
import { cn } from "@/lib/utils"

interface LeadCardProps {
  company: Company
  contact: Contact | null
  aiScore: AIScore | null
  index: number
  selected: boolean
  onSelect: (id: string) => void
  onActivated: () => void
}

export function LeadCard({ company, contact, aiScore, index, selected, onSelect, onActivated }: LeadCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ delay: index * 0.04, duration: 0.35 }}
      className={cn(
        "rounded-lg border border-border bg-card p-4 transition-all",
        selected && "ring-1 ring-accent",
        company.qualification_tier === "hot" && "border-l-4 border-l-hot"
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onSelect(company.id)}
            className="rounded border-border"
          />
          <ScoreBadge score={company.ai_score} tier={company.qualification_tier === "suppressed" ? "suppressed" : company.qualification_tier} size="sm" />
        </div>
        <Badge variant="secondary" className="text-[10px]">{company.industry}</Badge>
      </div>

      {/* Company info */}
      <div className="mt-3">
        <h3 className="font-semibold">{company.name}</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {company.domain} · {company.city}, {company.state}
        </p>
        <p className="text-xs text-muted-foreground">
          {company.employee_count} employees · Founded {company.founded_year}
        </p>
      </div>

      {/* Email hook */}
      {aiScore?.email_hook && (
        <div className="mt-3 rounded-md border border-border bg-[var(--bg2)] p-2.5">
          <EmailHookPreview hook={aiScore.email_hook} />
        </div>
      )}

      {/* Contact */}
      {contact && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">Contact:</span>
          <span className="font-medium">{contact.full_name}</span>
          <span className="text-muted-foreground">({contact.title})</span>
        </div>
      )}
      {contact && (
        <div className="mt-1 flex items-center gap-1.5 text-xs">
          <CheckCircle2 className="h-3 w-3 text-system-green" />
          <span className="font-mono text-muted-foreground">{contact.email}</span>
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex items-center gap-2">
        {aiScore?.email_hook && (
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5 text-xs"
            onClick={() => navigator.clipboard.writeText(aiScore.email_hook)}
          >
            <Copy className="h-3 w-3" /> Copy Hook
          </Button>
        )}
        <LeadActivateButton leadId={company.id} onActivated={onActivated} />
      </div>
    </motion.div>
  )
}
