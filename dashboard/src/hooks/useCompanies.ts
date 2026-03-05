"use client"
import useSWR from "swr"
import { fetcher } from "@/lib/api"

export function useCompanies(params?: string) {
  const query = params ? `?${params}` : ""
  return useSWR(`/api/companies${query}`, fetcher, { refreshInterval: 30000 })
}

export function useCompany(id: string) {
  return useSWR(id ? `/api/companies/${id}` : null, fetcher, { refreshInterval: 30000 })
}
