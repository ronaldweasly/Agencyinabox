// ── Growth engine types ──────────────────────────────────────────────────────

export type ServiceType =
  | 'website_modernization'
  | 'ai_automation'
  | 'online_booking'
  | 'seo_local'
  | 'paid_ads'
  | 'none'

export interface PitchDecision {
  service_key: ServiceType
  headline: string
  hook: string
  pain_point: string
  proof_point: string
  cta: string
  confidence: number
}

export interface IntentSignal {
  type: 'hiring' | 'funding' | 'expansion' | 'tech_change' | 'pain'
  title: string
  url: string
  snippet: string
  detected_at: string
}

export interface CompetitorSignal {
  id: string
  lead_id: string
  competitor_name: string
  competitor_url: string
  signal_type: 'ad_copy' | 'pricing' | 'feature_gap' | 'review_weakness' | 'general'
  detail: string
  has_weakness: boolean
  found_at: string
}

export interface WinningAngle {
  campaign_id: string
  campaign_name: string
  reply_rate: number
  open_rate: number
  sent: number
  replies: number
}

// ── Core types ───────────────────────────────────────────────────────────────

export interface Company {
  id: string
  name: string
  domain: string
  city: string
  state: string
  country: string
  industry: string
  employee_count: number
  employee_range: string
  founded_year: number
  tech_stack: Record<string, string>
  uses_wordpress: boolean
  uses_shopify: boolean
  pagespeed_score: number
  is_hiring: boolean
  job_posting_count: number
  is_advertising: boolean
  enrichment_status: 'pending' | 'in_progress' | 'complete' | 'failed'
  ai_score: number
  qualified: boolean
  qualification_tier: 'hot' | 'warm' | 'cold' | 'suppressed'
  suppressed_until: string | null
  first_seen_source: string
  created_at: string
  recommended_service?: ServiceType
  pain_point?: string
}

export interface Contact {
  id: string
  company_id: string
  first_name: string
  last_name: string
  full_name: string
  email: string
  title: string
  title_normalized: string
  seniority: 'c_suite' | 'vp' | 'director' | 'manager'
  is_decision_maker: boolean
  dm_priority: number
  verification_status: 'pending' | 'valid' | 'invalid' | 'risky' | 'catch_all'
  verification_score: number
  linkedin_url: string | null
  source: string
  confidence: number
}

export interface AIScore {
  id: string
  company_id: string
  website_modernity: number
  tech_debt_signal: number
  automation_opp: number
  growth_signal: number
  company_maturity: number
  icp_fit: number
  digital_gap: number
  engagement_readiness: number
  composite_score: number
  score_tier: 'hot' | 'warm' | 'cold'
  reasoning_summary: string
  key_signals: Array<{ signal: string; direction: string; weight: number }>
  recommended_service: string
  email_hook: string
  model_version: string
  scored_at: string
}

export interface QueueStatus {
  name: string
  depth: number
  throughput: number
  workers: number
  status: 'healthy' | 'backlogged' | 'stalled' | 'error'
  last_job_at: string
  history: number[]
}

export interface Campaign {
  id: string
  company_id: string
  contact_id: string
  campaign_name: string
  service_type: string
  status: 'enrolled' | 'contacted' | 'opened' | 'clicked' | 'replied' | 'bounced' | 'converted'
  enrolled_at: string
  email_opens: number
  email_clicks: number
  email_replies: number
  reply_sentiment: 'positive' | 'negative' | 'neutral' | null
  reply_text_snippet: string | null
  ai_score_at_activation: number
}

export interface PipelineEvent {
  id: string
  type: 'discovery' | 'enrichment' | 'ai_score' | 'email_sent' | 'reply' | 'error'
  source: string
  message: string
  metadata: Record<string, unknown>
  timestamp: string
}

export interface ScrapeTarget {
  id: string
  type: 'state' | 'county' | 'city' | 'zipcode'
  value: string            // e.g. "TX", "Travis County", "Austin", "78701"
  label: string            // human-readable display name
  state: string            // 2-letter state code always
  estimated_leads: number  // rough estimate for UI display
  is_active: boolean
  priority: 'high' | 'medium' | 'low'
  added_at: string
}

export interface ScrapingCategory {
  id: string
  name: string             // e.g. "HVAC", "Plumber", "IT Consulting"
  keyword: string          // exact search keyword used
  is_active: boolean
  estimated_volume: number
}

export interface TargetingConfig {
  targets: ScrapeTarget[]
  categories: ScrapingCategory[]
  max_results_per_combo: number   // default 20
  schedule: 'continuous' | 'daily' | 'weekly' | 'manual'
  last_updated: string
}

export interface ApiKey {
  id: string
  service: string           // 'claude', 'hunter', 'neverbounce', etc.
  label: string             // display name
  key_masked: string        // e.g. "sk-ant-...xxxx"
  is_active: boolean
  is_connected: boolean     // last test result
  last_tested_at: string | null
  last_test_latency_ms: number | null
  usage_this_month: number  // API calls made this month
  usage_limit: number | null
  category: 'ai' | 'scraping' | 'enrichment' | 'email' | 'outreach' | 'infrastructure'
  required: boolean         // is this key required for the system to function?
  docs_url: string
}

export interface ToolStatus {
  id: string
  name: string
  description: string
  is_enabled: boolean
  is_healthy: boolean
  last_run_at: string | null
  runs_today: number
  error_count_today: number
  category: 'scraper' | 'enrichment' | 'ai' | 'outreach' | 'worker'
  depends_on: string[]      // list of ApiKey service names required
}

export type MessageDirection = 'outbound' | 'inbound'
export type SentimentType = 'positive' | 'negative' | 'neutral' | 'not_analyzed'
export type ConversationStatus =
  | 'active' | 'replied' | 'bounced' | 'unsubscribed'
  | 'meeting_booked' | 'not_interested' | 'no_reply'

export interface ConversationMessage {
  id: string
  direction: MessageDirection
  subject: string
  body: string
  sent_at: string
  opened_at: string | null
  clicked_at: string | null
  sentiment: SentimentType
  ai_analysis: string | null   // AI's interpretation of the reply
  is_ai_generated: boolean
}

export interface Conversation {
  id: string
  company_name: string
  contact_name: string
  contact_email: string
  contact_title: string
  company_domain: string
  ai_score: number
  score_tier: 'hot' | 'warm' | 'cold'
  status: ConversationStatus
  campaign_name: string
  messages: ConversationMessage[]
  last_activity_at: string
  email_hook: string
  recommended_service: string
}
