# Prompt: Local SEO Pages

**Profile:** `auto:bulk-copy`  
**Service price:** $100–300/page  
**Deliverable:** Unique city/service landing pages at scale

---

## Variables

| Variable | Example |
|----------|---------|
| `{{CLIENT_NAME}}` | Summit HVAC |
| `{{SERVICE}}` | AC repair |
| `{{PRIMARY_CITY}}` | Dallas |
| `{{SERVICE_AREA_CITIES}}` | Plano, Frisco, McKinney, Allen, Richardson |
| `{{UNIQUE_LOCAL_DETAILS}}` | family-owned since 2008, 24/7 emergency, licensed #TACLA12345 |
| `{{PHONE}}` | (214) 555-0199 |
| `{{WORD_COUNT}}` | 800 |

---

## Step 1: Master template (run once per service)

**System prompt:**
```
You are a local SEO copywriter. Every page must be unique — no copy-paste city swaps. Reference real local context (climate, neighborhoods, common problems) without making up fake statistics.
```

**User prompt:**
```
Create a local SEO page template for {{CLIENT_NAME}} offering {{SERVICE}} in {{PRIMARY_CITY}}.

Include these sections with {{WORD_COUNT}} total words:
1. H1: {{SERVICE}} in {{PRIMARY_CITY}}, TX
2. Opening paragraph: local problem + {{CLIENT_NAME}} as solution
3. "Why {{PRIMARY_CITY}} homeowners choose us" — 3 bullets using: {{UNIQUE_LOCAL_DETAILS}}
4. Services included in {{SERVICE}} — detailed list
5. Service area: {{PRIMARY_CITY}} + neighborhoods/areas served
6. FAQ: 4 questions specific to {{SERVICE}} in {{PRIMARY_CITY}}
7. CTA: call {{PHONE}} + urgency line

Also provide:
- Meta title (under 60 chars)
- Meta description (under 155 chars)
- 3 schema FAQ questions for JSON-LD

Make it read naturally. No keyword stuffing. Mention {{PRIMARY_CITY}} 4–6 times naturally.
```

---

## Step 2: Bulk city variants

**Profile:** `auto:bulk-copy` · Run once per city in `{{SERVICE_AREA_CITIES}}`

**User prompt:**
```
Rewrite the {{SERVICE}} landing page for {{CLIENT_NAME}} for {{CURRENT_CITY}}, TX (not {{PRIMARY_CITY}}).

Base page structure: [PASTE PRIMARY CITY PAGE]

Requirements:
- At least 40% unique wording vs. the primary city page
- Reference {{CURRENT_CITY}}-specific context (neighborhoods, local climate factors, commute patterns)
- Keep: {{UNIQUE_LOCAL_DETAILS}}, phone {{PHONE}}, same services
- New H1, meta title, meta description unique to {{CURRENT_CITY}}
- Same section structure
- {{WORD_COUNT}} words

Do NOT just find-replace the city name. Rewrite paragraphs.
```

**Batch tip:** Loop through cities in a script:
```python
cities = ["Plano", "Frisco", "McKinney", "Allen", "Richardson"]
for city in cities:
    prompt = template.replace("{{CURRENT_CITY}}", city)
    # call API with model="auto:bulk-copy"
```

---

## Step 3: Meta tags for all cities (single batch)

**User prompt:**
```
Generate meta title + meta description for {{CLIENT_NAME}} {{SERVICE}} pages in these cities:

{{SERVICE_AREA_CITIES}}

Rules:
- Title format: "{{SERVICE}} in [City], TX | {{CLIENT_NAME}}" (adjust to fit 60 chars)
- Description: include {{PHONE}}, mention 24/7 if applicable, unique per city
- Table format: City | Title | Chars | Description | Chars
```

---

## Step 4: Internal linking map

**Profile:** `auto:seo-research`

**User prompt:**
```
Create an internal linking plan for {{CLIENT_NAME}}'s {{SERVICE}} city pages:

Cities: {{PRIMARY_CITY}}, {{SERVICE_AREA_CITIES}}
Main service hub page: /services/{{SERVICE}}

For each city page, specify:
- 3 internal links TO this page (from which pages, what anchor text)
- 3 internal links FROM this page (to which pages, what anchor text)

Goal: build topical authority for {{SERVICE}} across the {{PRIMARY_CITY}} metro without orphan pages.
```

---

## Quality checklist

- [ ] Each city page is genuinely unique (run diff check between pages)
- [ ] License numbers, phone, service areas are accurate
- [ ] No fabricated reviews or statistics
- [ ] NAP (name, address, phone) consistent across all pages
- [ ] Google may penalize near-duplicate city pages — 40% uniqueness minimum
