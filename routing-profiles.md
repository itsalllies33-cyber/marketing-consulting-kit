# FreeLLMAPI Routing Profiles for Marketing Consulting

Create three named profiles in the dashboard: **Models → Profiles** (or Fallback Chain → Save as profile). Use these exact names so your prompts and scripts stay consistent.

---

## Profile 1: `seo-research`

**Purpose:** Strategy, audits, SERP-aware content, competitor analysis, brand voice.  
**Routing strategy:** `Smartest` (dashboard) or `auto:smart` per request.  
**Why:** Quality and reasoning matter more than speed. Pin Google models first for Search grounding.

### Fallback chain (top → bottom)

| Priority | Model | Provider | Use when |
|----------|-------|----------|----------|
| 1 | `gemini-2.5-flash` | Google AI Studio | Default — fast + grounding-capable |
| 2 | `gemini-2.5-pro` | Google AI Studio | Deep audits, strategy docs |
| 3 | `llama-3.3-70b-versatile` | Groq | Google rate-limited |
| 4 | `mistral-small-latest` | Mistral | Multilingual / EU clients |
| 5 | `@cf/google/gemma-4-26b-a4b-it` | Cloudflare | Last resort text |

### API call

```bash
curl http://localhost:3001/v1/chat/completions \
  -H "Authorization: Bearer freellmapi-YOUR-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto:seo-research",
    "messages": [{"role": "user", "content": "..."}]
  }'
```

### Enable Google Search grounding (SEO research)

Pin a Google model and add the grounding tool:

```python
resp = client.chat.completions.create(
    model="gemini-2.5-flash",
    messages=[{"role": "user", "content": "Analyze SERP for 'emergency plumber austin'"}],
    tools=[{"type": "function", "function": {"name": "google_search", "parameters": {}}}],
)
```

---

## Profile 2: `ad-copy`

**Purpose:** Headlines, ad variants, email subjects, CTAs, landing page hooks.  
**Routing strategy:** `Balanced` or `auto:balanced`.  
**Why:** Mix of creativity and speed; Groq first for rapid variant generation.

### Fallback chain (top → bottom)

| Priority | Model | Provider | Use when |
|----------|-------|----------|----------|
| 1 | `llama-3.3-70b-versatile` | Groq | Fast, strong marketing copy |
| 2 | `gemma2-9b-it` | Groq | High-volume lighter tasks |
| 3 | `gemini-2.5-flash` | Google AI Studio | When you need smarter hooks |
| 4 | `llama-3.1-8b-instant` | Groq | Burn through quota on simple variants |
| 5 | `mistral-small-latest` | Mistral | Multilingual ad sets |

### API call

```python
resp = client.chat.completions.create(
    model="auto:ad-copy",
    messages=[...],
    temperature=0.9,  # higher creativity for ads
)
```

---

## Profile 3: `bulk-copy`

**Purpose:** Meta tags, product descriptions, local pages, social posts at scale.  
**Routing strategy:** `Fastest` or `auto:fast`.  
**Why:** Volume over polish; speed preserves daily quota across many items.

### Fallback chain (top → bottom)

| Priority | Model | Provider | Use when |
|----------|-------|----------|----------|
| 1 | `llama-3.1-8b-instant` | Groq | Maximum throughput |
| 2 | `gemma2-9b-it` | Groq | Slightly better quality, still fast |
| 3 | `llama-3.3-70b-versatile` | Groq | When 8B quality isn't enough |
| 4 | `@cf/zai-org/glm-4.7-flash` | Cloudflare | Groq exhausted |
| 5 | `gemini-2.5-flash` | Google AI Studio | End of day fallback |

### API call

```python
resp = client.chat.completions.create(
    model="auto:bulk-copy",
    messages=[...],
    temperature=0.7,
)
```

---

## Embeddings profile (content audits)

Embeddings don't use named profiles — configure on **Models → Embeddings**.

| Setting | Value |
|---------|-------|
| Default family | `bge-m3` |
| Provider order | Cloudflare → HuggingFace |
| API model | `bge-m3` |

```python
resp = client.embeddings.create(
    model="bge-m3",
    input=["keyword cluster 1", "keyword cluster 2", "page title example"],
)
```

---

## Dashboard setup checklist

- [ ] Add Google AI Studio key
- [ ] Add Groq key
- [ ] Add Cloudflare key
- [ ] Create profile `seo-research` with chain above, strategy = Smartest
- [ ] Create profile `ad-copy` with chain above, strategy = Balanced
- [ ] Create profile `bulk-copy` with chain above, strategy = Fastest
- [ ] Set embeddings default to `bge-m3`
- [ ] Enable prompt compression (Settings) for bulk jobs — stretches quota
- [ ] Copy unified API key from Keys page

---

## Per-request overrides (no dashboard changes)

| Need | Model string |
|------|--------------|
| Best quality, one-off | `auto:smart` |
| Fastest possible | `auto:fast` |
| Use a specific profile | `auto:seo-research` |
| Pin exact model | `gemini-2.5-flash` |
| Multi-model synthesis | `fusion` |

---

## Daily workflow tip

Run bulk jobs (`bulk-copy`) in the morning when quotas are fresh. Save `seo-research` / `ad-copy` for afternoon client-facing strategy work when you need higher quality.
