# Prompt: Social Media Management

**Profile:** `auto:bulk-copy`  
**Service price:** $500–1,500/mo  
**Deliverable:** 20–30 posts/month across platforms

---

## Variables

| Variable | Example |
|----------|---------|
| `{{CLIENT_NAME}}` | Bloom Bakery |
| `{{INDUSTRY}}` | artisan bakery / café |
| `{{BRAND_VOICE}}` | warm, playful, community-focused |
| `{{PLATFORMS}}` | Instagram, Facebook, LinkedIn |
| `{{POSTS_PER_MONTH}}` | 24 |
| `{{CONTENT_PILLARS}}` | behind-the-scenes, seasonal specials, customer stories, baking tips |
| `{{HASHTAG_STRATEGY}}` | 5 branded + 10 niche + 5 local |
| `{{LOCAL_HASHTAG}}` | #AustinEats |

---

## Step 1: Monthly content calendar

**System prompt:**
```
You are a social media manager for local businesses. You create calendars that balance promotion (20%), education (40%), engagement (25%), and brand personality (15%). Never sound like a corporate press release.
```

**User prompt:**
```
Create a {{POSTS_PER_MONTH}}-post social media calendar for {{CLIENT_NAME}} ({{INDUSTRY}}).

Platforms: {{PLATFORMS}}
Brand voice: {{BRAND_VOICE}}
Content pillars: {{CONTENT_PILLARS}}
Month: {{MONTH_YEAR}}

Format as a table:
| Date | Platform | Pillar | Post type | Caption draft | Visual idea | CTA | Hashtags |

Rules:
- Post 5–6 days/week, skip Sundays unless relevant
- Rotate pillars evenly
- Mix formats: carousel, reel hook, static image, story prompt, poll idea
- Captions: Instagram 150–300 chars, Facebook can be longer, LinkedIn more professional
- Include 1 engagement post/week (question, poll, "this or that")
- Include 1 user-generated content prompt/week
- Hashtags: {{HASHTAG_STRATEGY}}, always include {{LOCAL_HASHTAG}}
```

---

## Step 2: Full captions (batch by week)

**Profile:** `auto:bulk-copy`

**User prompt:**
```
Write full captions for Week {{WEEK_NUMBER}} of {{CLIENT_NAME}}'s social calendar:

[PASTE WEEK ROWS FROM CALENDAR]

For each post provide:
1. Full caption (platform-specific length)
2. First-line hook (must work without "see more")
3. CTA (specific action: visit, comment, share, DM)
4. Hashtag set (max 15 for IG, 3 for LinkedIn)
5. Reel/TikTok script if applicable (15–30 sec, with on-screen text notes)

Voice: {{BRAND_VOICE}}. No generic bakery clichés ("baked with love" unless it's on-brand).
```

---

## Step 3: Reel/short-form scripts (batch of 8)

**Profile:** `auto:ad-copy` · `temperature: 0.9`

**User prompt:**
```
Write 8 short-form video scripts (15–30 seconds) for {{CLIENT_NAME}} ({{INDUSTRY}}).

Mix:
- 2 behind-the-scenes
- 2 educational tips
- 2 product/showcase
- 2 trending format adaptations (e.g., "POV:", "Things I wish I knew", "Day in the life")

For each script:
| # | Hook (0–3 sec) | Body | CTA | On-screen text | Audio suggestion |

Keep hooks under 8 words. Write for sound-off viewing (text on screen).
```

---

## Step 4: Engagement templates (reusable)

**User prompt:**
```
Create 10 reusable engagement post templates for {{CLIENT_NAME}}:

- 3 question posts (comment-bait, on-brand)
- 2 "fill in the blank" posts
- 2 "this or that" polls
- 2 seasonal/timely prompt posts
- 1 "tag someone who..." post

Each template should have {{BRAND_VOICE}} placeholders like [PRODUCT], [SEASON], [LOCAL_EVENT].
```

---

## Step 5: Monthly performance narrative (for client report)

**Profile:** `auto:seo-research`

**User prompt:**
```
Write a 1-paragraph social media summary for {{CLIENT_NAME}}'s {{MONTH_YEAR}} report.

Posts published: {{POSTS_PUBLISHED}}
Top performing post: {{TOP_POST_DESCRIPTION}}
Engagement trend: {{UP/DOWN/FLAT}} vs last month
Next month focus: {{CONTENT_PILLARS}}

Tone: professional but friendly. Highlight 1 win, 1 learning, 1 plan for next month. 100 words max.
```

---

## Quality checklist

- [ ] No posts reference expired promotions or wrong dates
- [ ] Hashtags are relevant (not #love #instagood spam)
- [ ] Visual ideas are feasible for client (don't suggest studio shoots if they only have an iPhone)
- [ ] Compliance: no health claims for food/wellness clients without disclaimers
