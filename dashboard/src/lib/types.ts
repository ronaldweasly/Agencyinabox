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
  metadata: Record<string, any>
  timestamp: string
}
