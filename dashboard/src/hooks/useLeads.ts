"use client"
import useSWR from "swr"
import { fetcher } from "@/lib/api"

export function useLeads(params?: string) {
  const query = params ? `?${params}` : ""
  return useSWR(`/api/leads${query}`, fetcher, { refreshInterval: 15000 })
}
