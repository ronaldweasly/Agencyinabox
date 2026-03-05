"use client"
import useSWR from "swr"
import { fetcher } from "@/lib/api"

export function usePipelineStats() {
  return useSWR("/api/overview/stats", fetcher, { refreshInterval: 5000 })
}

export function usePipelineQueues() {
  return useSWR("/api/overview/queues", fetcher, { refreshInterval: 3000 })
}

export function usePipelineFeed() {
  return useSWR("/api/overview/feed", fetcher, { refreshInterval: 2000 })
}

export function usePipelineCharts() {
  return useSWR("/api/overview/charts", fetcher, { refreshInterval: 30000 })
}
