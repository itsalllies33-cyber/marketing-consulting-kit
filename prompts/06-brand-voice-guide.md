# Prompt: Brand Voice Guide

**Profile:** `auto:seo-research`  
**Service price:** $750–2,000 one-time  
**Deliverable:** Voice doc + 10 sample pieces in-brand

---

## Variables

| Variable | Example |
|----------|---------|
| `{{CLIENT_NAME}}` | Northline Financial |
| `{{INDUSTRY}}` | financial planning for small business owners |
| `{{TARGET_AUDIENCE}}` | business owners 35–55, $500K–$5M revenue |
| `{{BRAND_VALUES}}` | transparency, expertise, approachability |
| `{{COMPETITORS_TO_DIFFERENTIATE}}` | big banks, robo-advisors, generic CPA firms |
| `{{EXISTING_COPY_SAMPLES}}` | Paste website homepage, 2 emails, any marketing they've liked |
| `{{WORDS_TO_AVOID}}` | synergy, leverage, disrupt, game-changer |

---

## Step 1: Voice discovery

**System prompt:**
```
You are a brand strategist who creates voice guides that writers actually use — not 40-page decks. Every rule must have a before/after example.
```

**User prompt:**
```
Create a brand voice guide for {{CLIENT_NAME}} ({{INDUSTRY}}).

Target audience: {{TARGET_AUDIENCE}}
Brand values: {{BRAND_VALUES}}
Differentiate from: {{COMPETITORS_TO_DIFFERENTIATE}}
Words to never use: {{WORDS_TO_AVOID}}

Existing copy samples:
{{EXISTING_COPY_SAMPLES}}

Deliver:

## 1. Brand personality (4 traits)
For each trait: definition, what it sounds like, what it does NOT sound like

## 2. Voice spectrum
Rate {{CLIENT_NAME}} on these scales (1–10 with explanation):
- Formal ↔ Casual
- Serious ↔ Playful
- Expert ↔ Approachable
- Bold ↔ Understated

## 3. Tone by context
How voice shifts for: website, social media, email, proposals, crisis/support

## 4. Vocabulary
- Words we use (10)
- Words we avoid (10) with alternatives
- Industry jargon: which terms are OK vs. need plain-language translation

## 5. Grammar & style rules
- Sentence length preference
- Contractions (yes/no)
- First person (we/I) vs. third person
- Numbers, dates, currency formatting
- Oxford comma, em dash, exclamation marks

## 6. Before/after examples (5 pairs)
Rewrite generic corporate copy into {{CLIENT_NAME}}'s voice

## 7. Sample phrases
10 on-brand openers, 10 on-brand CTAs, 10 on-brand closers

Keep it under 1,500 words. Scannable. Writer-ready.
```

---

## Step 2: Sample content (prove the guide works)

**Profile:** `auto:ad-copy` for social/email · `auto:seo-research` for blog

**User prompt:**
```
Using the brand voice guide below, write 10 sample content pieces for {{CLIENT_NAME}}:

[PASTE VOICE GUIDE FROM STEP 1]

Write one of each:
1. Homepage hero (headline + subhead + CTA)
2. About us paragraph (100 words)
3. Service description (150 words)
4. Blog post opening paragraph
5. Welcome email (subject + body, 150 words)
6. LinkedIn post
7. Instagram caption
8. Client proposal opening paragraph
9. FAQ answer (addressing "why should I trust you?")
10. Error/404 page message (shows personality)

Label each piece. They should all feel like the same brand.
```

---

## Step 3: Voice QA checklist (for ongoing work)

**User prompt:**
```
Create a 10-point brand voice QA checklist for writers working on {{CLIENT_NAME}} content.

Each point: question to ask + red flag example + green flag example.

Include checks for: tone match, jargon level, CTA style, audience appropriateness, competitor differentiation, and {{WORDS_TO_AVOID}} compliance.

Format as a printable one-page checklist.
```

---

## Quality checklist

- [ ] Voice guide reflects client's actual personality (interview them first)
- [ ] Samples don't contradict real business facts
- [ ] Financial/legal/medical clients: flag compliance review needed
- [ ] Client signs off on voice guide before you use it for production work
