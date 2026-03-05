"use client"
import useSWR from "swr"
import { fetcher } from "@/lib/api"

export function useCampaigns() {
  return useSWR("/api/campaigns", fetcher, { refreshInterval: 60000 })
}

export function useCampaignReplies() {
  return useSWR("/api/campaigns/replies", fetcher, { refreshInterval: 30000 })
}
