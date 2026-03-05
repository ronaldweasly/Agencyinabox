"""
agency_config.py — single source of truth for the services the agency sells.

Every module that needs to know "what do we offer?" imports from here
instead of hard-coding strings.  When we add a new service, we update
ONE file and the entire pipeline (scorer → pitch → SDR → optimizer)
picks it up automatically.
"""
from __future__ import annotations

AGENCY_CONFIG: dict = {
    "agency_name": "Postmaster Digital",
    "services": {
        "website_modernization": {
            "label": "Website Modernization",
            "price_range": "$2,500 – $8,000",
            "signals": [
                "pagespeed < 50",
                "no mobile-responsive design",
                "site built > 5 years ago",
                "uses outdated CMS (Joomla, Drupal 7, raw HTML)",
            ],
            "pitch_angle": "Your website loads in {pagespeed}s — 53 % of visitors leave after 3 s.",
        },
        "ai_automation": {
            "label": "AI Chatbot & Automation",
            "price_range": "$1,500 – $5,000",
            "signals": [
                "no live-chat widget detected",
                "high Google-review volume (customers want instant answers)",
                "staff < 20 (automation saves FTEs)",
            ],
            "pitch_angle": "You have {reviews} Google reviews asking the same 5 questions — an AI chatbot answers 24/7.",
        },
        "online_booking": {
            "label": "Online Booking System",
            "price_range": "$1,000 – $3,500",
            "signals": [
                "service-based business (dental, HVAC, salon, etc.)",
                "no online scheduling link found",
                "phone-only booking mentioned on site",
            ],
            "pitch_angle": "Patients/customers can't book online — practices that add booking see 25 % more new inquiries.",
        },
        "seo_local": {
            "label": "Local SEO & Google Business",
            "price_range": "$800 – $2,000 /mo",
            "signals": [
                "GBP listing incomplete or unverified",
                "< 20 Google reviews",
                "no schema markup on site",
                "not ranking page 1 for primary keyword + city",
            ],
            "pitch_angle": "You're invisible on Google Maps for '{keyword} {city}' — here's a 90-day plan to fix that.",
        },
        "paid_ads": {
            "label": "Google / Meta Ads Management",
            "price_range": "$1,200 – $3,000 /mo",
            "signals": [
                "competitor is running ads (SpyFu / SimilarWeb)",
                "high commercial-intent niche",
                "no Google Ads tag detected on site",
            ],
            "pitch_angle": "Your competitor {competitor} is buying your branded keywords — you're paying for their clicks.",
        },
    },
    "icp": {
        "employee_range": "1-200",
        "industries": [
            "HVAC", "Plumbing", "Electrical", "Roofing",
            "Dental", "Chiropractic", "Med Spa", "Veterinary",
            "Legal", "Accounting", "Insurance",
            "Landscaping", "Pest Control", "Cleaning",
            "Auto Repair", "Real Estate", "Restaurant",
            "IT Consulting", "Marketing Agency",
        ],
        "regions": ["US"],
        "decision_maker_titles": [
            "Owner", "CEO", "President", "Managing Partner",
            "Practice Manager", "Office Manager", "Director of Marketing",
        ],
        "disqualifiers": [
            "Government / .gov",
            "Non-profit / .org (unless revenue > $2M)",
            "Franchise HQ (we target individual locations)",
            "Company dissolved / inactive",
            "Competitor (same service offering as us)",
        ],
    },
}


def agency_prompt_snippet() -> str:
    """Return a Markdown block that any LLM prompt can include to stay in sync
    with the services and ICP we actually sell."""
    svc_lines: list[str] = []
    for key, svc in AGENCY_CONFIG["services"].items():
        svc_lines.append(
            f"- **{svc['label']}** ({svc['price_range']}): "
            f"signals = {', '.join(svc['signals'][:2])}…"
        )
    icp = AGENCY_CONFIG["icp"]
    return (
        "## Agency Context — Postmaster Digital\n"
        "### Services we sell\n"
        + "\n".join(svc_lines)
        + "\n\n### Ideal Customer Profile (ICP)\n"
        f"- Employees: {icp['employee_range']}\n"
        f"- Industries: {', '.join(icp['industries'][:6])}…\n"
        f"- Regions: {', '.join(icp['regions'])}\n"
        f"- Decision-makers: {', '.join(icp['decision_maker_titles'][:4])}…\n"
        f"- Disqualifiers: {', '.join(icp['disqualifiers'][:3])}…\n"
    )
