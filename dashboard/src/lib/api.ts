import {
  mockCompanies,
  mockContacts,
  mockAIScores,
  mockQueues,
  mockEvents,
  mockCampaigns,
} from "./mockData"
import type {
  Company,
  Contact,
  AIScore,
  QueueStatus,
  Campaign,
  PipelineEvent,
} from "./types"

const DEV_MODE = process.env.NEXT_PUBLIC_DEV_MODE === "true"
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"

/* ── generic fetcher for SWR ── */
export async function fetcher<T>(url: string): Promise<T> {
  if (DEV_MODE) return devFetcher<T>(url)
  const res = await fetch(`${API_URL}${url}`)
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

/* ── dev-mode router returning mock data with simulated variance ── */
function jitter(n: number, pct = 0.05): number {
  return Math.round(n * (1 + (Math.random() - 0.5) * 2 * pct))
}

function devFetcher<T>(url: string): T {
  // overview
  if (url === "/api/overview/stats") {
    return {
      discovered: jitter(2_847_291),
      enriched: jitter(1_204_847),
      scored: jitter(891_203),
      qualified: jitter(47_832),
      sent: jitter(12_441),
    } as T
  }

  if (url === "/api/overview/queues") {
    return mockQueues.map((q) => ({
      ...q,
      depth: jitter(q.depth, 0.1),
      throughput: jitter(q.throughput, 0.1),
    })) as T
  }

  if (url === "/api/overview/feed") {
    return mockEvents as T
  }

  if (url === "/api/overview/charts") {
    return {
      discovery_by_day: Array.from({ length: 7 }, (_, i) => ({
        date: new Date(Date.now() - (6 - i) * 86400000).toISOString().slice(0, 10),
        google_maps: jitter(4200),
        yelp: jitter(1800),
        ssl_certs: jitter(900),
      })),
      score_distribution: [
        { bucket: "0-20", count: jitter(12400) },
        { bucket: "21-40", count: jitter(34200) },
        { bucket: "41-60", count: jitter(58900) },
        { bucket: "61-80", count: jitter(41200) },
        { bucket: "81-100", count: jitter(18300) },
      ],
      funnel: {
        sent: 12441,
        opened: 5490,
        clicked: 1007,
        replied: 460,
        converted: 149,
      },
    } as T
  }

  // companies
  if (url.startsWith("/api/companies") && !url.includes("/api/companies/")) {
    return { data: mockCompanies, total: mockCompanies.length, page: 1, per_page: 50 } as T
  }

  const companyMatch = url.match(/\/api\/companies\/([^/]+)$/)
  if (companyMatch) {
    const id = companyMatch[1]
    const company = mockCompanies.find((c) => c.id === id) ?? mockCompanies[0]
    return {
      company,
      contacts: mockContacts[company.id] ?? [],
      ai_score: mockAIScores[company.id] ?? null,
      campaigns: mockCampaigns.filter((c) => c.company_id === company.id),
      events: mockEvents.slice(0, 10),
    } as T
  }

  // leads
  if (url.startsWith("/api/leads")) {
    const hot = mockCompanies.filter((c) => c.qualified)
    return {
      data: hot.map((c) => ({
        company: c,
        contact: (mockContacts[c.id] ?? [])[0] ?? null,
        ai_score: mockAIScores[c.id] ?? null,
      })),
      total: hot.length,
    } as T
  }

  // campaigns
  if (url === "/api/campaigns/replies") {
    return mockCampaigns.filter((c) => c.reply_sentiment === "positive") as T
  }
  if (url.startsWith("/api/campaigns")) {
    return {
      data: mockCampaigns,
      stats: {
        sent: 12441,
        open_rate: 44.2,
        click_rate: 8.1,
        reply_rate: 3.7,
        positive_rate: 1.2,
      },
    } as T
  }

  // scrapers
  if (url === "/api/scrapers/jobs") {
    return Array.from({ length: 20 }, (_, i) => ({
      id: `job_${i}`,
      source: ["google_maps", "yelp", "ssl_certs", "linkedin_jobs", "crunchbase", "meta_ads"][i % 6],
      parameters: "Austin TX · HVAC",
      status: i < 15 ? "completed" : i < 18 ? "running" : "error",
      records_found: jitter(847),
      duration_s: jitter(34),
      proxy: i % 2 === 0 ? "residential" : "datacenter",
    })) as T
  }

  if (url.startsWith("/api/scrapers")) {
    return [
      { name: "Google Maps", status: "running", jobs_per_hr: 847, last_query: "Austin TX · HVAC", progress: 12847, target: 50000 },
      { name: "Yelp", status: "running", jobs_per_hr: 423, last_query: "Dallas TX · Plumbing", progress: 8421, target: 30000 },
      { name: "SSL Certs", status: "rate_limited", jobs_per_hr: 112, last_query: "expiring < 30d", progress: 4501, target: 20000 },
      { name: "LinkedIn Jobs", status: "running", jobs_per_hr: 234, last_query: "HVAC hiring", progress: 2345, target: 10000 },
      { name: "Crunchbase", status: "paused", jobs_per_hr: 0, last_query: "Series A · SaaS", progress: 0, target: 5000 },
      { name: "Meta Ads", status: "error", jobs_per_hr: 0, last_query: "home services ads", progress: 1200, target: 15000 },
    ] as T
  }

  // settings
  if (url.startsWith("/api/settings")) {
    return {
      scoring: { hot_threshold: 70, warm_threshold: 50, auto_activate: 65, rescore_days: 7 },
      campaigns: { api_key: "sk-inst-****", daily_limit: 200, cooling_days: 60 },
      api_keys: {
        hunter: "****",
        neverbounce: "****",
        zerobounce: "****",
        clearbit: "****",
        pagespeed: "****",
      },
      notifications: {
        telegram_token: "****",
        telegram_chat_id: "****",
        alerts: { hot_lead: true, reply: true, queue_stalled: true, worker_crashed: true, daily_summary: true },
      },
    } as T
  }

  return {} as T
}

/* ── POST helpers ── */
export async function apiPost<T = unknown>(url: string, body?: Record<string, unknown>): Promise<T> {
  if (DEV_MODE) {
    await new Promise((r) => setTimeout(r, 600))
    return { ok: true } as T
  }
  const res = await fetch(`${API_URL}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}
