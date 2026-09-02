# Prompt: SEO Content Package

**Profile:** `auto:seo-research`  
**Service price:** $800–2,500/mo  
**Deliverable:** Content brief + full blog post + meta tags

---

## Variables

| Variable | Example |
|----------|---------|
| `{{CLIENT_NAME}}` | Austin Pro Plumbing |
| `{{INDUSTRY}}` | residential plumbing |
| `{{TARGET_KEYWORD}}` | emergency plumber austin |
| `{{TARGET_MARKET}}` | Austin, TX |
| `{{BRAND_VOICE}}` | professional, trustworthy, local, no jargon |
| `{{WORD_COUNT}}` | 1,500 |
| `{{COMPETITOR_URL_1}}` | https://competitor1.com/emergency-plumber |
| `{{COMPETITOR_URL_2}}` | https://competitor2.com/austin-plumber |

---

## Step 1: Content brief (run first)

**System prompt:**
```
You are a senior SEO content strategist with 10+ years of experience in local service businesses. You write actionable briefs, not fluff. Always cite search intent, competitor gaps, and specific H2 recommendations.
```

**User prompt:**
```
Create a detailed SEO content brief for {{CLIENT_NAME}}, a {{INDUSTRY}} company in {{TARGET_MARKET}}.

Target keyword: "{{TARGET_KEYWORD}}"
Brand voice: {{BRAND_VOICE}}
Target word count: {{WORD_COUNT}}

Include:
1. Search intent analysis (informational / navigational / transactional / commercial)
2. SERP analysis — what top-ranking pages cover and what's missing
3. Recommended title tag (under 60 chars) and meta description (under 155 chars)
4. H1 and full H2/H3 outline with keyword placement notes
5. Internal linking suggestions (3–5 anchor text ideas)
6. FAQ section (5 questions people actually search)
7. Schema markup recommendation (Article, FAQ, LocalBusiness, etc.)
8. Content differentiation — how this piece beats competitors
9. CTA recommendation aligned to buyer stage

Competitor pages to analyze:
- {{COMPETITOR_URL_1}}
- {{COMPETITOR_URL_2}}

Format as a structured brief I can hand to a writer. Be specific, not generic.
```

**Grounding tip:** Add Google Search tool when calling Gemini directly:
```python
tools=[{"type": "function", "function": {"name": "google_search", "parameters": {}}}]
```

---

## Step 2: Full blog post (run after brief approval)

**System prompt:**
```
You are an expert content writer for {{INDUSTRY}} businesses. Write in {{BRAND_VOICE}} voice. Never use filler phrases like "in today's digital landscape" or "look no further." Write for humans first, search engines second. Use short paragraphs, bullet points where helpful, and natural keyword placement.
```

**User prompt:**
```
Write a complete {{WORD_COUNT}}-word blog post for {{CLIENT_NAME}} based on this brief:

[PASTE APPROVED BRIEF FROM STEP 1]

Requirements:
- Target keyword: "{{TARGET_KEYWORD}}" — use in H1, first 100 words, one H2, and naturally 3–5 more times
- Include the FAQ section from the brief with concise answers
- End with a clear CTA for {{CLIENT_NAME}} in {{TARGET_MARKET}}
- Add [INTERNAL LINK: anchor text] placeholders where internal links should go
- Do NOT include the meta title/description in the body — those are separate deliverables
- Reading level: 8th grade
```

---

## Step 3: Meta tags batch (same keyword cluster)

**Profile:** `auto:bulk-copy`

**User prompt:**
```
Generate 5 meta title and meta description pairs for {{CLIENT_NAME}} ({{INDUSTRY}}, {{TARGET_MARKET}}).

Primary keyword: "{{TARGET_KEYWORD}}"
Related keywords: [list 3–5 from brief]

Rules:
- Titles: 50–60 characters, keyword near front, include location where natural
- Descriptions: 140–155 characters, include CTA, unique per variant
- No duplicate phrasing across variants
- Format as a table: Variant | Title | Chars | Description | Chars
```

---

## Quality checklist (you do this — not the AI)

- [ ] Facts about {{CLIENT_NAME}} are accurate (services, areas, phone)
- [ ] No competitor names mentioned negatively
- [ ] Keyword doesn't feel stuffed
- [ ] CTA matches client's actual offer
- [ ] Read aloud — does it sound human?
