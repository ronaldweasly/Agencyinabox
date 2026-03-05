import {
    Company,
    Contact,
    AIScore,
    QueueStatus,
    Campaign,
    PipelineEvent,
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
