"use client"

import { useState } from "react"
import { Shell } from "@/components/layout/Shell"
import { CompanyFilters } from "@/components/companies/CompanyFilters"
import { CompanyTable } from "@/components/companies/CompanyTable"
import { EmptyState } from "@/components/shared/EmptyState"
import { useCompanies } from "@/hooks/useCompanies"
import type { Company } from "@/lib/types"

interface CompaniesResponse {
  data: Company[]
  total: number
  page: number
  per_page: number
}

export default function CompaniesPage() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    search: "",
    scoreMin: 0,
    scoreMax: 100,
    tier: "",
    enrichment: "All",
    employees: "Any",
  })

  const { data } = useCompanies() as { data: CompaniesResponse | undefined }

  // Client-side filtering on mock data
  const allCompanies = data?.data ?? []
  const filtered = allCompanies.filter((c) => {
    if (filters.search) {
      const q = filters.search.toLowerCase()
      if (!c.name.toLowerCase().includes(q) && !c.domain.toLowerCase().includes(q) && !c.city.toLowerCase().includes(q)) return false
    }
    if (c.ai_score < filters.scoreMin || c.ai_score > filters.scoreMax) return false
    if (filters.tier && c.qualification_tier !== filters.tier) return false
    if (filters.enrichment !== "All" && c.enrichment_status !== filters.enrichment.toLowerCase()) return false
    return true
  })

  return (
    <Shell>
      <div className="flex flex-col gap-4 p-6">
        <CompanyFilters filters={filters} onChange={setFilters} />
        {filtered.length > 0 ? (
          <CompanyTable
            companies={filtered}
            total={filtered.length}
            page={page}
            onPageChange={setPage}
          />
        ) : (
          <EmptyState
            title="No companies match your filters"
            description="Try broadening your search or adjusting the score range."
          />
        )}
      </div>
    </Shell>
  )
}
