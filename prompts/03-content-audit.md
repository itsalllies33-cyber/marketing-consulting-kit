# Prompt: Content Audit

**Profile:** `auto:seo-research` + embeddings (`bge-m3`)  
**Service price:** $1,000–3,000 one-time  
**Deliverable:** Gap analysis, keyword clusters, priority action list

---

## Variables

| Variable | Example |
|----------|---------|
| `{{CLIENT_NAME}}` | GreenLeaf Landscaping |
| `{{WEBSITE_URL}}` | greenleaflandscaping.com |
| `{{INDUSTRY}}` | residential landscaping |
| `{{TARGET_MARKET}}` | Portland, OR metro |
| `{{TOP_COMPETITORS}}` | competitor1.com, competitor2.com, competitor3.com |
| `{{CURRENT_PAGE_LIST}}` | Paste sitemap URLs or top 20 pages |
| `{{BUSINESS_GOALS}}` | increase spring booking inquiries by 40% |

---

## Step 1: Site content inventory

**System prompt:**
```
You are an SEO auditor who produces actionable reports, not 50-page PDFs nobody reads. Prioritize by impact. Be blunt about problems.
```

**User prompt:**
```
Conduct a content audit for {{CLIENT_NAME}} ({{WEBSITE_URL}}) in the {{INDUSTRY}} space, targeting {{TARGET_MARKET}}.

Current pages:
{{CURRENT_PAGE_LIST}}

Business goal: {{BUSINESS_GOALS}}

Analyze and report:

## 1. Content inventory summary
- Total pages assessed
- Content types (blog, service, location, product, thin/utility)
- Average estimated quality (High / Medium / Low / Thin)

## 2. Top 10 issues (ranked by SEO impact)
For each: issue, affected pages, why it matters, fix effort (Low/Med/High)

## 3. Thin content flags
List pages that should be merged, expanded, or noindexed

## 4. Missing content types
What content types competitors have that {{CLIENT_NAME}} lacks

## 5. On-page SEO gaps
- Missing/poor meta titles
- Missing meta descriptions
- H1 issues
- Missing internal links
- No FAQ/schema opportunities

## 6. Keyword gap analysis
10 high-intent keywords {{CLIENT_NAME}} should target but doesn't (with suggested page type)

## 7. Competitor comparison
Compare against: {{TOP_COMPETITORS}}
What are they doing better? Where can {{CLIENT_NAME}} win?

## 8. 90-day priority roadmap
Phase 1 (quick wins, 30 days), Phase 2 (content build, 60 days), Phase 3 (authority, 90 days)

Format as a client-ready report. Use tables. Be specific to {{INDUSTRY}}, not generic SEO advice.
```

**Tip:** Enable Google Search grounding for competitor/SERP research.

---

## Step 2: Keyword clustering (embeddings)

Use this when you have a list of 50–200 keywords from Ahrefs, GSC, or Step 1.

**Python workflow:**
```python
keywords = [
    "landscaping portland",
    "lawn care portland or",
    "yard cleanup portland",
  # ... paste full list
]

resp = client.embeddings.create(model="bge-m3", input=keywords)
# Cluster by cosine similarity in your spreadsheet or a simple script
```

**Then prompt:**
```
I have these keyword clusters for {{CLIENT_NAME}}:

Cluster 1 — Lawn maintenance: [keywords]
Cluster 2 — Hardscaping: [keywords]
Cluster 3 — Seasonal services: [keywords]
...

For each cluster:
1. Recommended pillar page title
2. 3 supporting blog post ideas
3. Suggested URL slug
4. Search intent (info/commercial/transactional)
5. Priority (P1/P2/P3) based on business goal: {{BUSINESS_GOALS}}

Format as a content map table.
```

---

## Step 3: Executive summary (client-facing, 1 page)

**Profile:** `auto:seo-research`

**User prompt:**
```
Write a 1-page executive summary of the content audit for {{CLIENT_NAME}}.

Audience: business owner, not technical. No jargon.

Include:
- Current state (2 sentences)
- Top 3 opportunities (with estimated impact: High/Med/Low)
- Top 3 risks if nothing changes
- Recommended package: what to fix first and why
- Expected timeline to see results: 30/60/90 days

Tone: confident, direct, helpful. End with a clear "recommended next step."
```

---

## Quality checklist

- [ ] URLs and page names match client's actual site
- [ ] Competitor claims are verifiable
- [ ] Recommendations match client's actual capacity (don't recommend 50 posts/mo to a solo operator)
- [ ] Executive summary has zero jargon (no "canonical," "crawl budget" unless explained)
