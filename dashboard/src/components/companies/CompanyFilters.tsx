"use client"

import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Slider } from "@/components/ui/slider"
import { Search, X, SlidersHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"

interface Filters {
  search: string
  scoreMin: number
  scoreMax: number
  tier: string
  enrichment: string
  employees: string
}

interface CompanyFiltersProps {
  filters: Filters
  onChange: (f: Filters) => void
}

const tiers = [
  { value: "", label: "All" },
  { value: "hot", label: "Hot 🔴" },
  { value: "warm", label: "Warm 🟡" },
  { value: "cold", label: "Cold ⚪" },
  { value: "suppressed", label: "Suppressed" },
]

const enrichments = ["All", "Complete", "Pending", "Failed"]
const employeeRanges = ["Any", "1-10", "11-50", "51-200", "201-500", "500+"]

export function CompanyFilters({ filters, onChange }: CompanyFiltersProps) {
  const [expanded, setExpanded] = useState(false)

  const activeCount = [
    filters.search,
    filters.tier,
    filters.enrichment && filters.enrichment !== "All" ? filters.enrichment : "",
    filters.employees && filters.employees !== "Any" ? filters.employees : "",
    filters.scoreMin > 0 || filters.scoreMax < 100 ? "score" : "",
  ].filter(Boolean).length

  function clearAll() {
    onChange({ search: "", scoreMin: 0, scoreMax: 100, tier: "", enrichment: "All", employees: "Any" })
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search name, domain, city..."
            value={filters.search}
            onChange={(e) => onChange({ ...filters, search: e.target.value })}
            className="h-9 pl-9 bg-muted border-border text-sm"
          />
        </div>

        {/* Tier toggles */}
        <div className="flex gap-1">
          {tiers.map((t) => (
            <button
              key={t.value}
              onClick={() => onChange({ ...filters, tier: filters.tier === t.value ? "" : t.value })}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                filters.tier === t.value
                  ? "bg-accent/20 text-accent"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Expand toggle */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setExpanded(!expanded)}
          className="gap-1.5"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Filters
          {activeCount > 0 && (
            <Badge variant="secondary" className="ml-1 h-5 rounded-full px-1.5 text-[10px]">
              {activeCount}
            </Badge>
          )}
        </Button>

        {activeCount > 0 && (
          <button onClick={clearAll} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <X className="h-3 w-3" /> Clear all
          </button>
        )}
      </div>

      {expanded && (
        <div className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4 lg:grid-cols-4">
          {/* Score range */}
          <div>
            <label className="mb-2 block text-xs text-muted-foreground">AI Score Range</label>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs">{filters.scoreMin}</span>
              <Slider
                min={0}
                max={100}
                step={5}
                value={[filters.scoreMin, filters.scoreMax]}
                onValueChange={([min, max]) => onChange({ ...filters, scoreMin: min, scoreMax: max })}
                className="flex-1"
              />
              <span className="font-mono text-xs">{filters.scoreMax}</span>
            </div>
          </div>

          {/* Enrichment */}
          <div>
            <label className="mb-2 block text-xs text-muted-foreground">Enrichment</label>
            <div className="flex flex-wrap gap-1">
              {enrichments.map((e) => (
                <button
                  key={e}
                  onClick={() => onChange({ ...filters, enrichment: e })}
                  className={cn(
                    "rounded-md px-2 py-1 text-xs transition-colors",
                    filters.enrichment === e ? "bg-accent/20 text-accent" : "bg-muted text-muted-foreground hover:text-foreground"
                  )}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          {/* Employees */}
          <div>
            <label className="mb-2 block text-xs text-muted-foreground">Employees</label>
            <div className="flex flex-wrap gap-1">
              {employeeRanges.map((e) => (
                <button
                  key={e}
                  onClick={() => onChange({ ...filters, employees: e })}
                  className={cn(
                    "rounded-md px-2 py-1 text-xs transition-colors",
                    filters.employees === e ? "bg-accent/20 text-accent" : "bg-muted text-muted-foreground hover:text-foreground"
                  )}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          {/* Tech pills */}
          <div>
            <label className="mb-2 block text-xs text-muted-foreground">Tech Stack</label>
            <div className="flex flex-wrap gap-1">
              {["WordPress", "Shopify", "No CRM", "No Analytics"].map((t) => (
                <button
                  key={t}
                  className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent/20 hover:text-accent"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
