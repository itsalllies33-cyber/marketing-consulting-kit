# Prompt: Email Sequence

**Profile:** `auto:ad-copy`  
**Service price:** $500–1,200 one-time  
**Deliverable:** 5–7 email nurture sequence

---

## Variables

| Variable | Example |
|----------|---------|
| `{{CLIENT_NAME}}` | ClearPath Accounting |
| `{{PRODUCT_OR_SERVICE}}` | free tax readiness checklist + consultation |
| `{{TARGET_AUDIENCE}}` | small business owners dreading tax season |
| `{{SEQUENCE_GOAL}}` | book a free 30-min consultation |
| `{{SEQUENCE_LENGTH}}` | 5 emails over 10 days |
| `{{BRAND_VOICE}}` | helpful expert, calm, no scare tactics |
| `{{LEAD_MAGNET}}` | "2026 Small Business Tax Checklist" PDF |
| `{{OBJECTIONS}}` | too expensive, already have a CPA, not ready yet |

---

## Step 1: Sequence architecture

**System prompt:**
```
You are an email marketing strategist specializing in nurture sequences for service businesses. You write emails people actually open — short, valuable, one CTA per email. No "just checking in" filler.
```

**User prompt:**
```
Design a {{SEQUENCE_LENGTH}} email nurture sequence for {{CLIENT_NAME}}.

Product/service: {{PRODUCT_OR_SERVICE}}
Audience: {{TARGET_AUDIENCE}}
Goal: {{SEQUENCE_GOAL}}
Lead magnet: {{LEAD_MAGNET}}
Brand voice: {{BRAND_VOICE}}
Common objections: {{OBJECTIONS}}

For each email provide:
| # | Day | Subject line | Preview text | Purpose | Key message | CTA | Objection addressed |

Sequence arc:
- Email 1: Deliver lead magnet + set expectations
- Email 2: Problem agitation (empathy, not fear)
- Email 3: Education / quick win they can use today
- Email 4: Social proof / case study framework
- Email 5: Direct offer + urgency (real, not fake)

Include 2 subject line A/B variants per email.
Subject lines: under 50 chars, no ALL CAPS, no spam triggers.
```

---

## Step 2: Full email copy

**Profile:** `auto:ad-copy`

**User prompt:**
```
Write the full copy for all {{SEQUENCE_LENGTH}} emails in the sequence below.

[PASTE SEQUENCE ARCHITECTURE FROM STEP 1]

For each email:
- Subject line (pick best of A/B)
- Preview text (40–90 chars)
- Body (150–250 words max)
- Single CTA button text + link placeholder [LINK]
- P.S. line (optional, use on emails 3 and 5 only)

Rules:
- Voice: {{BRAND_VOICE}}
- Write in second person ("you")
- One idea per email
- No "I hope this email finds you well"
- Mobile-friendly: short paragraphs, 1–3 sentences each
- Plain text feel (minimal formatting)
```

---

## Step 3: Subject line bank (bonus deliverable)

**Profile:** `auto:bulk-copy`

**User prompt:**
```
Generate 20 bonus subject lines for {{CLIENT_NAME}}'s email marketing.

Categories (4 each):
1. Curiosity
2. Benefit-driven
3. Question-based
4. Urgency (ethical, no fake deadlines)
5. Re-engagement (for cold subscribers)

Audience: {{TARGET_AUDIENCE}}
Max 50 characters each. No spam words (free!!!, act now, limited time).
```

---

## Step 4: Re-engagement email (for non-openers)

**User prompt:**
```
Write a re-engagement email for subscribers who didn't open emails 3–5 of the {{CLIENT_NAME}} sequence.

Tone: {{BRAND_VOICE}}, light, no guilt trip.
Length: 100 words max.
Include: acknowledgment, one valuable tip, soft CTA to {{SEQUENCE_GOAL}}.
Subject line: 3 variants.
```

---

## Step 5: Sequence metrics guide (client handoff)

**Profile:** `auto:seo-research`

**User prompt:**
```
Write a 1-page guide for {{CLIENT_NAME}} on how to measure this email sequence.

Include:
- KPIs to track (open rate, click rate, reply rate, booking rate)
- Benchmark ranges for {{INDUSTRY}} service businesses
- When to pause/fix (red flags)
- 3 optimization tests to run after first 100 sends
- Recommended ESP settings (send time, from name, reply-to)

Keep it non-technical. Assume they use Mailchimp or similar.
```

---

## Quality checklist

- [ ] CAN-SPAM compliant: physical address placeholder, unsubscribe mention
- [ ] CTA links match real landing pages
- [ ] No false urgency or fabricated scarcity
- [ ] Financial/health/legal: add disclaimer if giving advice
- [ ] Test all subject lines in a spam checker before client delivery
