"use client"

import { use } from "react"
import { motion } from "framer-motion"
import { Shell } from "@/components/layout/Shell"
import { useCompany } from "@/hooks/useCompanies"
import { ScoreBadge } from "@/components/shared/ScoreBadge"
import { StatusDot } from "@/components/shared/StatusDot"
import { TechStackPills } from "@/components/companies/TechStackPills"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ExternalLink,
  Copy,
  RotateCw,
  Brain,
  Rocket,
  Ban,
  Briefcase,
  Megaphone,
  DollarSign,
  Newspaper,
  CheckCircle2,
  XCircle,
  Linkedin,
  Mail,
  Shield,
  Clock,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { Company, Contact, AIScore, Campaign, PipelineEvent } from "@/lib/types"

interface CompanyDetail {
  company: Company
  contacts: Contact[]
  ai_score: AIScore | null
  campaigns: Campaign[]
  events: PipelineEvent[]
}

const dimensions = [
  { key: "website_modernity", label: "Website Modernity" },
  { key: "tech_debt_signal", label: "Tech Debt Signal" },
  { key: "automation_opp", label: "Automation Opp" },
  { key: "growth_signal", label: "Growth Signal" },
  { key: "company_maturity", label: "Company Maturity" },
  { key: "icp_fit", label: "ICP Fit" },
  { key: "digital_gap", label: "Digital Gap" },
  { key: "engagement_readiness", label: "Engagement Ready" },
] as const

function DimensionBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-36 shrink-0 text-xs text-muted-foreground">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
        <motion.div
          className={cn(
            "h-full rounded-full",
            value >= 80 ? "bg-system-green" : value >= 60 ? "bg-cyan" : value >= 40 ? "bg-system-yellow" : "bg-system-red"
          )}
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span className="w-8 text-right font-mono text-xs font-medium">{value}</span>
    </div>
  )
}

function verificationColor(s: string) {
  if (s === "valid") return "text-system-green"
  if (s === "risky" || s === "catch_all") return "text-system-yellow"
  if (s === "invalid") return "text-system-red"
  return "text-muted-foreground"
}

function seniorityLabel(s: string) {
  const map: Record<string, string> = { c_suite: "C-SUITE", vp: "VP", director: "DIRECTOR", manager: "MANAGER" }
  return map[s] ?? s.toUpperCase()
}

export default function CompanyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data } = useCompany(id) as { data: CompanyDetail | undefined }

  if (!data) {
    return (
      <Shell>
        <div className="flex items-center justify-center p-20 text-muted-foreground">Loading...</div>
      </Shell>
    )
  }

  const { company, contacts, ai_score, campaigns, events } = data

  return (
    <Shell>
      <div className="flex flex-col gap-6 p-6 lg:flex-row">
        {/* LEFT — 60% */}
        <div className="flex min-w-0 flex-1 flex-col gap-6">
          {/* Header */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
            <div className="flex flex-wrap items-start gap-3">
              <div>
                <h1 className="text-2xl font-bold">{company.name}</h1>
                <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                  <a href={`https://${company.domain}`} target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-accent transition-colors">
                    {company.domain} <ExternalLink className="h-3 w-3" />
                  </a>
                  <Badge variant="secondary">{company.industry}</Badge>
                  <Badge variant="secondary">{company.employee_range} employees</Badge>
                  <Badge variant="secondary">Founded {company.founded_year}</Badge>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Score Panel */}
          {ai_score && (
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.4 }}>
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">AI Score Analysis</CardTitle>
                    <ScoreBadge score={ai_score.composite_score} tier={ai_score.score_tier} size="lg" />
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {dimensions.map((d) => (
                    <DimensionBar key={d.key} label={d.label} value={ai_score[d.key]} />
                  ))}

                  {/* AI Reasoning */}
                  <div className="mt-4 rounded-lg border border-border bg-[var(--bg2)] p-4">
                    <p className="text-sm italic text-muted-foreground leading-relaxed">
                      &ldquo;{ai_score.reasoning_summary}&rdquo;
                    </p>
                  </div>

                  {/* Email Hook */}
                  <div className="rounded-lg border border-accent/20 bg-accent/5 p-4">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-accent">
                      💡 AI-Generated Email Hook
                    </div>
                    <p className="text-sm leading-relaxed text-foreground/90">
                      {ai_score.email_hook}
                    </p>
                    <Button variant="outline" size="sm" className="mt-3 gap-1.5 text-xs" onClick={() => navigator.clipboard.writeText(ai_score.email_hook)}>
                      <Copy className="h-3 w-3" /> Copy Hook
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* Tech Stack */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.4 }}>
            <Card>
              <CardHeader><CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Tech Stack</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {Object.entries(company.tech_stack).map(([category, tech]) => (
                    <div key={category} className="rounded-lg border border-border bg-[var(--bg2)] p-3">
                      <div className="text-[10px] uppercase text-muted-foreground">{category}</div>
                      <div className="mt-1 text-sm font-medium">{tech}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Growth Signals */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.4 }}>
            <Card>
              <CardHeader><CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Growth Signals</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: "Hiring", active: company.is_hiring, detail: `${company.job_posting_count} open roles`, icon: Briefcase },
                    { label: "Running Ads", active: company.is_advertising, detail: "Facebook, Google", icon: Megaphone },
                    { label: "Recent Funding", active: false, detail: "No data", icon: DollarSign },
                    { label: "Press Releases", active: false, detail: "No data", icon: Newspaper },
                  ].map((s) => (
                    <div key={s.label} className="flex items-center gap-3 rounded-lg border border-border bg-[var(--bg2)] p-3">
                      <s.icon className={cn("h-4 w-4", s.active ? "text-system-green" : "text-muted-foreground")} />
                      <div>
                        <div className="flex items-center gap-1.5 text-sm font-medium">
                          {s.active ? <CheckCircle2 className="h-3.5 w-3.5 text-system-green" /> : <XCircle className="h-3.5 w-3.5 text-muted-foreground" />}
                          {s.label}
                        </div>
                        <div className="text-xs text-muted-foreground">{s.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Timeline */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.4 }}>
            <Card>
              <CardHeader><CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Timeline</CardTitle></CardHeader>
              <CardContent>
                <div className="relative ml-3 border-l border-border pl-6">
                  {events.map((evt, i) => (
                    <div key={evt.id} className="relative mb-4 last:mb-0">
                      <div className="absolute -left-[31px] top-1 h-2.5 w-2.5 rounded-full border-2 border-background bg-accent" />
                      <div className="text-xs text-muted-foreground">
                        {new Date(evt.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                      </div>
                      <div className="text-sm">{evt.message}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* RIGHT — 40% sidebar */}
        <div className="w-full space-y-6 lg:w-[380px]">
          {/* Contacts */}
          <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2, duration: 0.4 }}>
            <Card>
              <CardHeader><CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Contacts ({contacts.length})</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {contacts.map((c) => (
                  <div key={c.id} className="rounded-lg border border-border bg-[var(--bg2)] p-3">
                    <div className="flex items-center justify-between">
                      <div className="font-medium text-sm">{c.full_name}</div>
                      <Badge variant="outline" className="text-[10px]">{seniorityLabel(c.seniority)}</Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">{c.title}</div>
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex items-center gap-1">
                        <div className={cn("h-1.5 w-1.5 rounded-full", verificationColor(c.verification_status).replace("text-", "bg-"))} />
                        <span className="font-mono text-xs text-muted-foreground">{c.email}</span>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      {c.linkedin_url && (
                        <a href={`https://${c.linkedin_url}`} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-accent">
                          <Linkedin className="h-3.5 w-3.5" />
                        </a>
                      )}
                      {c.is_decision_maker && (
                        <Badge variant="secondary" className="text-[10px] bg-accent/10 text-accent">DM #{c.dm_priority}</Badge>
                      )}
                    </div>
                    <Button variant="outline" size="sm" className="mt-2 w-full gap-1.5 text-xs">
                      <Mail className="h-3 w-3" /> Add to Campaign
                    </Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          </motion.div>

          {/* Campaign History */}
          <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3, duration: 0.4 }}>
            <Card>
              <CardHeader><CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Campaign History</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {campaigns.length > 0 ? campaigns.map((camp) => (
                  <div key={camp.id} className="flex items-center justify-between rounded-lg border border-border bg-[var(--bg2)] p-3">
                    <div>
                      <div className="text-sm font-medium">{camp.campaign_name}</div>
                      <div className="text-xs text-muted-foreground">{camp.service_type}</div>
                    </div>
                    <Badge variant="outline" className="text-[10px] capitalize">{camp.status}</Badge>
                  </div>
                )) : (
                  <p className="text-sm text-muted-foreground">No campaigns yet.</p>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Actions */}
          <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4, duration: 0.4 }}>
            <Card>
              <CardHeader><CardTitle className="text-sm uppercase tracking-widest text-muted-foreground">Actions</CardTitle></CardHeader>
              <CardContent className="grid grid-cols-2 gap-2">
                <Button variant="outline" size="sm" className="gap-1.5 text-xs"><RotateCw className="h-3 w-3" /> Re-enrich</Button>
                <Button variant="outline" size="sm" className="gap-1.5 text-xs"><Brain className="h-3 w-3" /> Re-score</Button>
                <Button variant="default" size="sm" className="gap-1.5 text-xs bg-accent text-background hover:bg-accent/80"><Rocket className="h-3 w-3" /> Activate</Button>
                <Button variant="outline" size="sm" className="gap-1.5 text-xs text-system-red border-system-red/30 hover:bg-system-red/10"><Ban className="h-3 w-3" /> Suppress 90d</Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </Shell>
  )
}
