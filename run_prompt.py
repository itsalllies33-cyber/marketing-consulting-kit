"""
Marketing Consulting Kit — prompt runner for FreeLLMAPI.

Usage:
  python run_prompt.py --profile seo-research --prompt-file prompts/01-seo-content-package.md
  python run_prompt.py --profile ad-copy --text "Write 10 headlines for..."
  python run_prompt.py --list-profiles

Set FREELLMAPI_KEY env var or pass --api-key.
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from openai import OpenAI
except ImportError:
    print("Install: pip install openai")
    sys.exit(1)

BASE_URL = os.environ.get("FREELLMAPI_URL", "http://localhost:3001/v1")
API_KEY = os.environ.get("FREELLMAPI_KEY", "freellmapi-your-unified-key")

PROFILES = {
    "seo-research": "Strategy, audits, SERP research, brand voice",
    "ad-copy": "Ads, emails, landing pages, creative variants",
    "bulk-copy": "Meta tags, local pages, social at scale",
}

DEFAULT_SYSTEM = {
    "seo-research": (
        "You are a senior SEO and content strategist. "
        "Be specific, actionable, and industry-aware. No generic filler."
    ),
    "ad-copy": (
        "You are a direct-response copywriter. "
        "Tight copy, clear CTAs, respect character limits."
    ),
    "bulk-copy": (
        "You are a high-volume content producer. "
        "Consistent quality, scannable output, follow format instructions exactly."
    ),
}


def load_prompt_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # If file has ## Step sections, user should paste the specific step;
    # for quick runs, use everything after the first ## Step 1 block's user prompt fence.
    if "## Step 1" in content and "**User prompt:**" in content:
        start = content.index("**User prompt:**", content.index("## Step 1"))
        block = content[start:]
        if "```" in block:
            inner = block.split("```", 2)
            if len(inner) >= 2:
                return inner[1].strip()
    return content


def run(profile: str, user_prompt: str, system: str | None, temperature: float) -> None:
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    model = f"auto:{profile}"

    messages = []
    sys_msg = system or DEFAULT_SYSTEM.get(profile, DEFAULT_SYSTEM["seo-research"])
    messages.append({"role": "system", "content": sys_msg})
    messages.append({"role": "user", "content": user_prompt})

    print(f"Model: {model}")
    print(f"Base URL: {BASE_URL}")
    print("-" * 60)

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    print(resp.choices[0].message.content)
    routed = getattr(resp, "headers", None)
    if routed:
        via = routed.get("x-routed-via") or routed.get("X-Routed-Via")
        if via:
            print("-" * 60)
            print(f"Routed via: {via}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run marketing prompts via FreeLLMAPI")
    parser.add_argument(
        "--profile",
        choices=list(PROFILES),
        default="seo-research",
        help="Routing profile (see routing-profiles.md)",
    )
    parser.add_argument("--prompt-file", help="Path to a prompt markdown file")
    parser.add_argument("--text", help="Raw user prompt text")
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--api-key", default=API_KEY, help="FreeLLMAPI unified key")
    parser.add_argument("--base-url", default=BASE_URL, help="FreeLLMAPI base URL")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--list-profiles", action="store_true")
    args = parser.parse_args()

    if args.list_profiles:
        for name, desc in PROFILES.items():
            print(f"  {name:15} — {desc}")
        return

    global API_KEY, BASE_URL
    API_KEY = args.api_key
    BASE_URL = args.base_url

    if args.text:
        user_prompt = args.text
    elif args.prompt_file:
        user_prompt = load_prompt_file(args.prompt_file)
    else:
        parser.error("Provide --text or --prompt-file")

    run(args.profile, user_prompt, args.system, args.temperature)


if __name__ == "__main__":
    main()
