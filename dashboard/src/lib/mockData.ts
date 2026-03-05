import {
    Company,
    Contact,
    AIScore,
    QueueStatus,
    Campaign,
    PipelineEvent,
    ScrapeTarget,
    ScrapingCategory,
    ApiKey,
    ToolStatus,
    Conversation,
} from "./types";

const now = new Date();

export const mockCompanies: Company[] = Array.from({ length: 20 }, (_, i) => ({
    id: `comp_${i}`,
    name: `Acme Corp ${i}`,
    domain: `acme${i}.com`,
    city: "Austin",
    state: "TX",
    country: "USA",
    industry: "HVAC",
    employee_count: 45 + i * 5,
    employee_range: "11-50",
    founded_year: 2008 + (i % 5),
    tech_stack: { CMS: "WordPress", Analytics: "Google Analytics" },
    uses_wordpress: true,
    uses_shopify: false,
    pagespeed_score: 45 + i,
    is_hiring: i % 2 === 0,
    job_posting_count: i % 2 === 0 ? 3 : 0,
    is_advertising: true,
    enrichment_status: "complete",
    ai_score: 84 - i,
    qualified: true,
    qualification_tier: i < 5 ? "hot" : i < 15 ? "warm" : "cold",
    suppressed_until: null,
    first_seen_source: "Google Maps",
    created_at: new Date(now.getTime() - i * 86400000).toISOString(),
}));

export const mockContacts: Record<string, Contact[]> = {};
mockCompanies.forEach((comp) => {
    mockContacts[comp.id] = Array.from({ length: 5 }, (_, j) => ({
        id: `cont_${comp.id}_${j}`,
        company_id: comp.id,
        first_name: `John${j}`,
        last_name: `Doe${j}`,
        full_name: `John${j} Doe${j}`,
        email: `john${j}@${comp.domain}`,
        title: j === 0 ? "CEO" : "Manager",
        title_normalized: j === 0 ? "ceo" : "manager",
        seniority: j === 0 ? "c_suite" : "manager",
        is_decision_maker: j === 0,
        dm_priority: j === 0 ? 1 : 2,
        verification_status: "valid",
        verification_score: 99,
        linkedin_url: `linkedin.com/in/john${j}doe${j}`,
        source: "Apollo",
        confidence: 0.95,
    }));
});

export const mockAIScores: Record<string, AIScore> = {};
mockCompanies.forEach((comp, i) => {
    mockAIScores[comp.id] = {
        id: `score_${comp.id}`,
        company_id: comp.id,
        website_modernity: 78,
        tech_debt_signal: 88,
        automation_opp: 65,
        growth_signal: 72,
        company_maturity: 55,
        icp_fit: 80,
        digital_gap: 85,
        engagement_readiness: 68,
        composite_score: comp.ai_score,
        score_tier: comp.qualification_tier as "hot" | "warm" | "cold",
        reasoning_summary:
            "This company has an outdated website but shows strong growth signals by actively hiring.",
        key_signals: [
            { signal: "Hiring", direction: "positive", weight: 0.8 },
            { signal: "Old Tech", direction: "positive", weight: 0.6 },
        ],
        recommended_service: "Web Development",
        email_hook:
            "I noticed your team is growing (saw 3 recent job postings) but your booking process is still phone-only...",
        model_version: "v1.0",
        scored_at: new Date().toISOString(),
    };
});

export const mockQueues: QueueStatus[] = [
    {
        name: "discovery_queue",
        depth: 450,
        throughput: 120,
        workers: 4,
        status: "healthy",
        last_job_at: new Date().toISOString(),
        history: [100, 200, 300, 400, 450],
    },
    {
        name: "enrichment_queue",
        depth: 12050,
        throughput: 50,
        workers: 8,
        status: "backlogged",
        last_job_at: new Date().toISOString(),
        history: [10000, 11000, 11500, 11800, 12050],
    },
    {
        name: "ai_score_queue",
        depth: 15,
        throughput: 300,
        workers: 2,
        status: "healthy",
        last_job_at: new Date().toISOString(),
        history: [10, 12, 14, 15, 15],
    },
];

export const mockEvents: PipelineEvent[] = Array.from({ length: 50 }, (_, i) => ({
    id: `evt_${i}`,
    type: i % 4 === 0 ? "discovery" : i % 4 === 1 ? "ai_score" : i % 4 === 2 ? "email_sent" : "reply",
    source: i % 4 === 0 ? "GOOGLE_MAPS" : i % 4 === 1 ? "AI_SCORE" : i % 4 === 2 ? "EMAIL_SENT" : "REPLY",
    message:
        i % 4 === 0
            ? 'Discovered: "Austin HVAC Pro" · Austin, TX'
            : i % 4 === 1
                ? 'HOT 84/100 · "Midland Plumbing LLC" → outreach queue'
                : i % 4 === 2
                    ? "Campaign: web_dev_seq_3 → john@midlandplumbing.com"
                    : "🟢 Positive reply from sarah@acmeroofing.com",
    metadata: {},
    timestamp: new Date(now.getTime() - i * 10000).toISOString(),
}));

export const mockCampaigns: Campaign[] = Array.from({ length: 3 }, (_, i) => ({
    id: `camp_${i}`,
    company_id: mockCompanies[i].id,
    contact_id: mockContacts[mockCompanies[i].id][0].id,
    campaign_name: `web_dev_seq_${i}`,
    service_type: "Web Development",
    status: i === 0 ? "replied" : i === 1 ? "opened" : "enrolled",
    enrolled_at: new Date(now.getTime() - i * 86400000 * 5).toISOString(),
    email_opens: 2,
    email_clicks: 1,
    email_replies: i === 0 ? 1 : 0,
    reply_sentiment: i === 0 ? "positive" : null,
    reply_text_snippet: i === 0 ? "Yes, we are interested in a redesign." : null,
    ai_score_at_activation: 85,
}));

export const mockTargets: ScrapeTarget[] = [
    { id: 't1', type: 'state', value: 'TX', label: 'Texas', state: 'TX',
        estimated_leads: 450000, is_active: true, priority: 'high',
        added_at: new Date().toISOString() },
    { id: 't2', type: 'city', value: 'Austin', label: 'Austin, TX', state: 'TX',
        estimated_leads: 28000, is_active: true, priority: 'high',
        added_at: new Date().toISOString() },
    { id: 't3', type: 'city', value: 'Houston', label: 'Houston, TX', state: 'TX',
        estimated_leads: 62000, is_active: true, priority: 'medium',
        added_at: new Date().toISOString() },
    { id: 't4', type: 'county', value: 'Travis County', label: 'Travis County, TX',
        state: 'TX', estimated_leads: 35000, is_active: false, priority: 'medium',
        added_at: new Date().toISOString() },
    { id: 't5', type: 'zipcode', value: '78701', label: '78701 - Downtown Austin',
        state: 'TX', estimated_leads: 1200, is_active: true, priority: 'high',
        added_at: new Date().toISOString() },
    { id: 't6', type: 'state', value: 'CA', label: 'California', state: 'CA',
        estimated_leads: 820000, is_active: false, priority: 'low',
        added_at: new Date().toISOString() },
    { id: 't7', type: 'city', value: 'Denver', label: 'Denver, CO', state: 'CO',
        estimated_leads: 19000, is_active: true, priority: 'medium',
        added_at: new Date().toISOString() },
]

export const mockCategories: ScrapingCategory[] = [
    { id: 'c1', name: 'HVAC', keyword: 'HVAC contractor', is_active: true, estimated_volume: 8500 },
    { id: 'c2', name: 'Plumbing', keyword: 'plumber', is_active: true, estimated_volume: 12000 },
    { id: 'c3', name: 'Electrical', keyword: 'electrician', is_active: true, estimated_volume: 9800 },
    { id: 'c4', name: 'IT Consulting', keyword: 'IT consulting company', is_active: true, estimated_volume: 4200 },
    { id: 'c5', name: 'Digital Agency', keyword: 'digital marketing agency', is_active: true, estimated_volume: 6700 },
    { id: 'c6', name: 'Accounting', keyword: 'accounting firm', is_active: false, estimated_volume: 11000 },
    { id: 'c7', name: 'Law Firm', keyword: 'law firm', is_active: false, estimated_volume: 7300 },
    { id: 'c8', name: 'Dental', keyword: 'dental office', is_active: true, estimated_volume: 15000 },
    { id: 'c9', name: 'Real Estate', keyword: 'real estate agency', is_active: false, estimated_volume: 9100 },
    { id: 'c10', name: 'Insurance', keyword: 'insurance agency', is_active: true, estimated_volume: 8800 },
]

export const mockApiKeys: ApiKey[] = [
    {
        id: 'key_1', service: 'claude', label: 'Anthropic Claude',
        key_masked: 'sk-ant-api03-...xxxx', is_active: true, is_connected: true,
        last_tested_at: new Date(Date.now() - 300_000).toISOString(),
        last_test_latency_ms: 342, usage_this_month: 847203, usage_limit: 1000000,
        category: 'ai', required: true,
        docs_url: 'https://docs.anthropic.com',
    },
    {
        id: 'key_2', service: 'outscraper', label: 'Outscraper (Google Maps)',
        key_masked: 'out_...xxxx', is_active: true, is_connected: true,
        last_tested_at: new Date(Date.now() - 600_000).toISOString(),
        last_test_latency_ms: 891, usage_this_month: 12400, usage_limit: 50000,
        category: 'scraping', required: true,
        docs_url: 'https://outscraper.com/docs',
    },
    {
        id: 'key_3', service: 'apollo', label: 'Apollo.io',
        key_masked: 'apo_...xxxx', is_active: true, is_connected: true,
        last_tested_at: new Date(Date.now() - 900_000).toISOString(),
        last_test_latency_ms: 412, usage_this_month: 8230, usage_limit: 10000,
        category: 'enrichment', required: false,
        docs_url: 'https://docs.apollo.io',
    },
    {
        id: 'key_4', service: 'hunter', label: 'Hunter.io',
        key_masked: 'hun_...xxxx', is_active: true, is_connected: false,
        last_tested_at: new Date(Date.now() - 7_200_000).toISOString(),
        last_test_latency_ms: null, usage_this_month: 3100, usage_limit: 5000,
        category: 'enrichment', required: false,
        docs_url: 'https://hunter.io/api-documentation',
    },
    {
        id: 'key_5', service: 'neverbounce', label: 'NeverBounce',
        key_masked: 'nb_...xxxx', is_active: true, is_connected: true,
        last_tested_at: new Date(Date.now() - 1_200_000).toISOString(),
        last_test_latency_ms: 287, usage_this_month: 45230, usage_limit: 100000,
        category: 'email', required: false,
        docs_url: 'https://docs.neverbounce.com',
    },
    {
        id: 'key_6', service: 'instantly', label: 'Instantly.ai',
        key_masked: 'ins_...xxxx', is_active: true, is_connected: true,
        last_tested_at: new Date(Date.now() - 180_000).toISOString(),
        last_test_latency_ms: 523, usage_this_month: 1241, usage_limit: null,
        category: 'outreach', required: true,
        docs_url: 'https://app.instantly.ai/app/api-key',
    },
    {
        id: 'key_7', service: 'gemini', label: 'Google Gemini',
        key_masked: 'AIza...xxxx', is_active: true, is_connected: true,
        last_tested_at: new Date(Date.now() - 240_000).toISOString(),
        last_test_latency_ms: 198, usage_this_month: 234100, usage_limit: null,
        category: 'ai', required: false,
        docs_url: 'https://ai.google.dev',
    },
    {
        id: 'key_8', service: 'redis', label: 'Redis (Upstash)',
        key_masked: 'redis://...xxxx', is_active: true, is_connected: true,
        last_tested_at: new Date(Date.now() - 60_000).toISOString(),
        last_test_latency_ms: 4, usage_this_month: 0, usage_limit: null,
        category: 'infrastructure', required: true,
        docs_url: 'https://upstash.com/docs/redis',
    },
]

export const mockTools: ToolStatus[] = [
    {
        id: 'tool_1', name: 'Google Maps Scraper', is_enabled: true, is_healthy: true,
        description: 'Scrapes Google Maps for business listings by location + category',
        last_run_at: new Date(Date.now() - 900_000).toISOString(),
        runs_today: 48, error_count_today: 2,
        category: 'scraper', depends_on: ['outscraper'],
    },
    {
        id: 'tool_2', name: 'SSL Cert Monitor', is_enabled: true, is_healthy: true,
        description: 'Watches certificate transparency logs for new business domains',
        last_run_at: new Date(Date.now() - 30_000).toISOString(),
        runs_today: 1, error_count_today: 0,
        category: 'scraper', depends_on: [],
    },
    {
        id: 'tool_3', name: 'Apollo Enrichment', is_enabled: true, is_healthy: true,
        description: 'Enriches companies with Apollo.io contact and company data',
        last_run_at: new Date(Date.now() - 300_000).toISOString(),
        runs_today: 234, error_count_today: 5,
        category: 'enrichment', depends_on: ['apollo'],
    },
    {
        id: 'tool_4', name: 'NeverBounce Verify', is_enabled: true, is_healthy: false,
        description: 'Verifies email addresses before outreach',
        last_run_at: new Date(Date.now() - 3_600_000).toISOString(),
        runs_today: 0, error_count_today: 12,
        category: 'enrichment', depends_on: ['neverbounce'],
    },
    {
        id: 'tool_5', name: 'Claude AI Scorer', is_enabled: true, is_healthy: true,
        description: '8-dimension lead scoring using Claude Sonnet',
        last_run_at: new Date(Date.now() - 180_000).toISOString(),
        runs_today: 891, error_count_today: 0,
        category: 'ai', depends_on: ['claude'],
    },
    {
        id: 'tool_6', name: 'Instantly Outreach', is_enabled: true, is_healthy: true,
        description: 'Pushes qualified leads to Instantly.ai email campaigns',
        last_run_at: new Date(Date.now() - 3_600_000).toISOString(),
        runs_today: 124, error_count_today: 1,
        category: 'outreach', depends_on: ['instantly'],
    },
]

export const mockConversations: Conversation[] = [
    {
        id: 'conv_1',
        company_name: 'Midland Plumbing LLC',
        contact_name: 'John Smith',
        contact_email: 'john@midlandplumbing.com',
        contact_title: 'CEO',
        company_domain: 'midlandplumbing.com',
        ai_score: 84,
        score_tier: 'hot',
        status: 'replied',
        campaign_name: 'Web Dev Sequence 3',
        email_hook: 'I noticed your team is growing (3 job postings) but booking is still phone-only...',
        recommended_service: 'Website Modernization',
        last_activity_at: new Date(Date.now() - 3_600_000).toISOString(),
        messages: [
            {
                id: 'msg_1a', direction: 'outbound', subject: 'Quick question about Midland Plumbing\'s online booking',
                body: `Hi John,\n\nI noticed your team is growing (saw 3 recent job postings) but your booking process is still phone-only — most plumbing companies your size capture 30-40% more leads after adding online scheduling.\n\nI help contractors in Austin modernize their customer acquisition. Would a 15-minute call make sense this week?\n\nBest,\nAlex`,
                sent_at: new Date(Date.now() - 86_400_000 * 3).toISOString(),
                opened_at: new Date(Date.now() - 86_400_000 * 2).toISOString(),
                clicked_at: null, sentiment: 'not_analyzed', ai_analysis: null, is_ai_generated: true,
            },
            {
                id: 'msg_1b', direction: 'inbound', subject: 'Re: Quick question about Midland Plumbing\'s online booking',
                body: `Hi Alex,\n\nThat's actually really timely — we've been discussing updating our website for months but haven't pulled the trigger. The phone booking issue is real, we lose calls constantly.\n\nWhat would something like that cost? Are you local to Austin?\n\nJohn`,
                sent_at: new Date(Date.now() - 3_600_000).toISOString(), opened_at: null, clicked_at: null,
                sentiment: 'positive', ai_analysis: 'Strong positive reply. Prospect acknowledges the pain point directly ("we lose calls constantly") and asks about pricing — a clear buying signal. Mentions wanting to update website for months = warm lead that was waiting for the right prompt. Recommended action: book discovery call immediately.', is_ai_generated: false,
            },
        ],
    },
    {
        id: 'conv_2', company_name: 'Cedar Valley Dental', contact_name: 'Sarah Johnson', contact_email: 'sarah@cedarvalleydental.com', contact_title: 'Practice Owner', company_domain: 'cedarvalleydental.com', ai_score: 71, score_tier: 'hot', status: 'active', campaign_name: 'Healthcare Automation Seq', email_hook: 'Your Google reviews are great — but I noticed patients can\'t book online...', recommended_service: 'AI Automation + Online Booking', last_activity_at: new Date(Date.now() - 7_200_000).toISOString(), messages: [ { id: 'msg_2a', direction: 'outbound', subject: 'Cedar Valley Dental — patient booking question', body: `Hi Sarah,\n\nYour Google reviews are great (4.9 stars with 340 reviews) — but I noticed patients can't book appointments online, which is increasingly what patients expect before they even call.\n\nDental practices that add online booking typically see 25% more new patient inquiries within 60 days.\n\nWorth a quick chat?\n\nAlex`, sent_at: new Date(Date.now() - 86_400_000 * 2).toISOString(), opened_at: new Date(Date.now() - 86_400_000).toISOString(), clicked_at: new Date(Date.now() - 86_400_000).toISOString(), sentiment: 'not_analyzed', ai_analysis: null, is_ai_generated: true, }, ], },
    {
        id: 'conv_3', company_name: 'Acme Roofing Co', contact_name: 'Mike Davis', contact_email: 'mike@acmeroofing.com', contact_title: 'Owner', company_domain: 'acmeroofing.com', ai_score: 55, score_tier: 'warm', status: 'not_interested', campaign_name: 'Web Dev Sequence 3', email_hook: 'Your website loads in 8 seconds — here\'s what that\'s costing you...', recommended_service: 'Website Modernization', last_activity_at: new Date(Date.now() - 86_400_000).toISOString(), messages: [ { id: 'msg_3a', direction: 'outbound', subject: 'Acme Roofing website speed issue', body: `Hi Mike,\n\nYour website loads in 8 seconds on mobile — Google data shows 53% of visitors leave if a page takes more than 3 seconds. That's roughly half your ad spend going to waste.\n\nI fix this for roofing companies in Texas. Takes about 2 weeks.\n\nAlex`, sent_at: new Date(Date.now() - 86_400_000 * 5).toISOString(), opened_at: new Date(Date.now() - 86_400_000 * 4).toISOString(), clicked_at: null, sentiment: 'not_analyzed', ai_analysis: null, is_ai_generated: true, }, { id: 'msg_3b', direction: 'inbound', subject: 'Re: Acme Roofing website speed issue', body: `Not interested, please remove me from your list.`, sent_at: new Date(Date.now() - 86_400_000).toISOString(), opened_at: null, clicked_at: null, sentiment: 'negative', ai_analysis: 'Clear unsubscribe request. No further contact should be made. Lead suppressed. Sentiment: negative. No buying signals present.', is_ai_generated: false, }, ], },
]
