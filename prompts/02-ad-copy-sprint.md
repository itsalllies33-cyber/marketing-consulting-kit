# Prompt: Ad Copy Sprint

**Profile:** `auto:ad-copy`  
**Service price:** $500–1,500 one-time  
**Deliverable:** 50+ ad variants + landing page copy

---

## Variables

| Variable | Example |
|----------|---------|
| `{{CLIENT_NAME}}` | FitLife Gym |
| `{{PRODUCT_OR_SERVICE}}` | 30-day fitness trial membership |
| `{{TARGET_AUDIENCE}}` | busy professionals 30–50 in Denver |
| `{{UNIQUE_VALUE}}` | no contracts, personal trainers included, open 5am–11pm |
| `{{PAIN_POINT}}` | can't stick to a gym routine |
| `{{PRICE_OR_OFFER}}` | $29 for first month |
| `{{LANDING_PAGE_URL}}` | fitlifegym.com/trial |

---

## Step 1: Google Search Ads

**System prompt:**
```
You are a direct-response copywriter who has managed $1M+ in Google Ads spend. You write tight, benefit-driven copy that respects character limits. Every headline must earn the click.
```

**User prompt:**
```
Create Google Search ad copy for {{CLIENT_NAME}}.

Product/service: {{PRODUCT_OR_SERVICE}}
Audience: {{TARGET_AUDIENCE}}
Key differentiator: {{UNIQUE_VALUE}}
Pain point: {{PAIN_POINT}}
Offer: {{PRICE_OR_OFFER}}

Generate:
- 15 headlines (max 30 characters each — count carefully)
- 4 descriptions (max 90 characters each)
- 3 callout extensions (max 25 chars)
- 3 sitelink extensions (title max 25 chars + description max 35 chars)

Group headlines into 3 themes:
1. Pain/agitation
2. Solution/benefit
3. Offer/urgency

Format as tables. Flag any headline over 30 chars with ⚠️.
```

---

## Step 2: Meta (Facebook/Instagram) Ads

**Profile:** `auto:ad-copy` · `temperature: 0.9`

**User prompt:**
```
Create Meta ad copy for {{CLIENT_NAME}} — same product/audience as above.

Generate:
- 5 primary text variants (125 chars recommended, max 3 lines feel)
- 5 headline variants (40 chars max)
- 5 description variants (30 chars max)
- 3 hook lines for Reels/Stories (first 3 seconds — pattern interrupt style)

Tone: conversational, scroll-stopping, not corporate.
Include 1 emoji per primary text max. No hashtag spam.
```

---

## Step 3: LinkedIn Ads (if B2B client)

**User prompt:**
```
Create LinkedIn ad copy for {{CLIENT_NAME}} targeting {{TARGET_AUDIENCE}}.

Generate:
- 3 intro text variants (150 chars — above the fold)
- 3 headline variants (70 chars max)
- 1 longer thought-leadership style post (300 words) that could run as sponsored content

Tone: professional but not stiff. Lead with insight, not features.
```

---

## Step 4: Landing page copy

**Profile:** `auto:ad-copy`

**User prompt:**
```
Write landing page copy for {{CLIENT_NAME}} — {{PRODUCT_OR_SERVICE}}.

URL: {{LANDING_PAGE_URL}}
Audience: {{TARGET_AUDIENCE}}
Offer: {{PRICE_OR_OFFER}}
Differentiator: {{UNIQUE_VALUE}}

Structure:
1. Hero: headline (8 words max) + subheadline (20 words) + CTA button text
2. Problem section: 3 pain bullets (their words, not ours)
3. Solution section: 3 benefit bullets with proof points
4. Social proof placeholder: [TESTIMONIAL SLOT]
5. Offer section: what's included, price, guarantee
6. FAQ: 4 objections handled
7. Final CTA: headline + button text + urgency line

Keep total page under 800 words. Scannable. No lorem ipsum.
```

---

## Step 5: A/B test matrix

**Profile:** `auto:bulk-copy`

**User prompt:**
```
For {{CLIENT_NAME}}, create an A/B test plan for the ad copy above.

Format as a table:
| Test # | Element | Variant A | Variant B | Hypothesis | Primary metric |

Include 5 tests covering: headline angle, CTA wording, offer framing, social proof, urgency.
```

---

## Quality checklist

- [ ] All Google headlines ≤ 30 characters (verify manually)
- [ ] Claims are truthful and client-approved
- [ ] Offer/price matches what client actually sells
- [ ] Landing page CTA matches ad promise (message match)
- [ ] No trademark violations or competitor bashing
