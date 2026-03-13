"""
Shared Claude AI service for the dealflow engine.

All Anthropic API interactions go through this module. Features:
- Centralized API key management
- Graceful fallback when API key is missing or calls fail
- Streaming support via async generators
- Simple in-process cache (field explanations, per-deal narratives)
- Token usage tracking

IMPORTANT: The deterministic financial engine is the source of truth for all numbers.
Claude is used only for interpretation, narrative, and natural language — never for math.
"""
from __future__ import annotations

import json
import logging
import os
import hashlib
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AI_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-4-20250514")
AI_ENABLED = os.environ.get("AI_ENABLED", "true").lower() == "true"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Token budget per feature (configurable via env)
MAX_TOKENS_NARRATIVE = int(os.environ.get("AI_MAX_TOKENS_NARRATIVE", "1500"))
MAX_TOKENS_CHAT = int(os.environ.get("AI_MAX_TOKENS_CHAT", "2000"))
MAX_TOKENS_HELP = int(os.environ.get("AI_MAX_TOKENS_HELP", "300"))
MAX_TOKENS_PARSE = int(os.environ.get("AI_MAX_TOKENS_PARSE", "800"))
MAX_TOKENS_SCENARIO = int(os.environ.get("AI_MAX_TOKENS_SCENARIO", "400"))

# ---------------------------------------------------------------------------
# In-process TTL + LRU cache (no Redis needed for V1)
# ---------------------------------------------------------------------------

import threading
import time
from collections import OrderedDict

_CACHE_MAX_SIZE = 500
_CACHE_TTL_SECONDS = 3600  # 1 hour TTL
_CACHE_MAX_ENTRY_BYTES = 1_000_000  # 1MB per entry

_cache: OrderedDict[str, tuple[str, float]] = OrderedDict()  # key → (value, expiry_timestamp)
_cache_lock = threading.Lock()
_token_usage: dict[str, int] = {"input": 0, "output": 0, "calls": 0}


def _cache_key(*parts: str) -> str:
    combined = "|".join(parts)
    return hashlib.md5(combined.encode()).hexdigest()


def _get_cached(key: str) -> str | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            # Expired — remove and return miss
            del _cache[key]
            return None
        # Move to end (most recently used)
        _cache.move_to_end(key)
        return value


def _set_cached(key: str, value: str) -> None:
    # Reject oversized entries
    if len(value.encode("utf-8", errors="replace")) > _CACHE_MAX_ENTRY_BYTES:
        return
    with _cache_lock:
        # If key exists, update it
        if key in _cache:
            _cache.move_to_end(key)
        _cache[key] = (value, time.monotonic() + _CACHE_TTL_SECONDS)
        # Evict oldest (LRU) entries when over capacity
        while len(_cache) > _CACHE_MAX_SIZE:
            _cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

def _get_client():
    """Get Anthropic client, returning None if not configured."""
    if not AI_ENABLED:
        return None
    if not ANTHROPIC_API_KEY:
        logger.debug("ANTHROPIC_API_KEY not set — AI features disabled")
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        logger.warning("anthropic package not installed — AI features disabled")
        return None
    except Exception as e:
        logger.warning("Failed to initialize Anthropic client: %s", e)
        return None


def _get_async_client():
    """Get async Anthropic client."""
    if not AI_ENABLED:
        return None
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        return anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        return None
    except Exception as e:
        logger.warning("Failed to initialize async Anthropic client: %s", e)
        return None


def is_ai_available() -> bool:
    """Check whether AI features are available (key set + package installed)."""
    if not AI_ENABLED or not ANTHROPIC_API_KEY:
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Core ask functions
# ---------------------------------------------------------------------------

async def ask_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1000,
    cache_key: str | None = None,
) -> str | None:
    """
    Make an async Claude API call (non-blocking for the FastAPI event loop).

    Args:
        system_prompt: The system prompt that sets Claude's role and context.
        user_message: The user's message or query.
        max_tokens: Maximum tokens in the response.
        cache_key: If provided, cache the result under this key.

    Returns:
        Claude's response text, or None if AI is unavailable or call fails.
        Never raises — always degrades gracefully.
    """
    if cache_key:
        cached = _get_cached(cache_key)
        if cached:
            return cached

    client = _get_async_client()
    if client is None:
        return None

    try:
        response = await client.messages.create(
            model=AI_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text if response.content else ""

        # Track usage
        if hasattr(response, "usage"):
            _token_usage["input"] += response.usage.input_tokens
            _token_usage["output"] += response.usage.output_tokens
            _token_usage["calls"] += 1

        if cache_key and text:
            _set_cached(cache_key, text)

        return text

    except Exception as e:
        logger.warning("Claude API call failed: %s", e)
        return None


async def ask_claude_with_history(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
) -> str | None:
    """
    Make an async Claude API call with a conversation history.

    Args:
        system_prompt: System prompt.
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
        max_tokens: Max response tokens.

    Returns:
        Claude's response text, or None on failure.
    """
    client = _get_async_client()
    if client is None:
        return None

    try:
        response = await client.messages.create(
            model=AI_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        text = response.content[0].text if response.content else ""
        if hasattr(response, "usage"):
            _token_usage["input"] += response.usage.input_tokens
            _token_usage["output"] += response.usage.output_tokens
            _token_usage["calls"] += 1
        return text
    except Exception as e:
        logger.warning("Claude API call failed: %s", e)
        return None


async def stream_claude(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
) -> AsyncGenerator[str, None]:
    """
    Stream a Claude response as an async generator of text chunks.

    Used for chat, narrative generation, and scenario stories.
    Yields text chunks as they arrive. Yields nothing if AI unavailable.

    Usage:
        async for chunk in stream_claude(system, messages, max_tokens):
            # send chunk to client via SSE
    """
    client = _get_async_client()
    if client is None:
        return

    try:
        async with client.messages.stream(
            model=AI_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

            # Track final usage
            final_msg = await stream.get_final_message()
            if hasattr(final_msg, "usage"):
                _token_usage["input"] += final_msg.usage.input_tokens
                _token_usage["output"] += final_msg.usage.output_tokens
                _token_usage["calls"] += 1

    except Exception as e:
        logger.warning("Claude streaming failed: %s", e)
        return


def get_token_usage() -> dict[str, int]:
    """Return cumulative token usage statistics (for dev monitoring)."""
    return dict(_token_usage)


# ---------------------------------------------------------------------------
# System prompt builders
# ---------------------------------------------------------------------------

def deal_parser_system_prompt() -> str:
    """System prompt for the conversational deal entry parser."""
    return """You are a senior M&A advisor helping a user model a potential acquisition.
Your job is to extract deal parameters from natural language and ask smart follow-up questions.

EXTRACTION RULES:
1. Extract any financial figures mentioned: revenue, EBITDA, margins, deal size, industry, company names
2. If the user mentions a margin (e.g., "18% EBITDA margin"), compute the dollar amount if you know revenue
3. For any fields the user doesn't mention, use industry benchmarks — don't ask about them
4. Ask ONE follow-up question at a time. Never interrogate with multiple questions.
5. If you have enough for a Quick Model (revenue, EBITDA, deal size, industry for both parties), confirm and stop asking

RESPONSE FORMAT:
Always respond with valid JSON in exactly this structure:
{
  "status": "need_more_info" | "ready_to_model",
  "follow_up_question": "string (only when status=need_more_info)",
  "extracted": {
    "acquirer_name": null | "string",
    "acquirer_revenue": null | number,
    "acquirer_ebitda": null | number,
    "acquirer_industry": null | "string",
    "target_name": null | "string",
    "target_revenue": null | number,
    "target_ebitda": null | number,
    "target_ebitda_margin": null | number,
    "target_industry": null | "string",
    "acquisition_price": null | number,
    "cash_percentage": null | number,
    "debt_percentage": null | number,
    "synergy_description": null | "string"
  },
  "confidence": {
    "acquirer_revenue": 0.0-1.0,
    "target_revenue": 0.0-1.0,
    "acquisition_price": 0.0-1.0
  },
  "summary": "string — brief confirmation of what you understood, shown to user"
}

TONE: Conversational, professional but not stuffy. Like a smart advisor at a coffee meeting."""


def narrative_system_prompt(mode: str) -> str:
    """System prompt for deal narrative generation."""
    language_note = (
        "Write in plain English that a business owner can understand. Avoid jargon."
        if mode == "quick"
        else "You can use standard finance terminology — the user is finance-literate."
    )
    return f"""You are a senior M&A advisor writing a deal assessment. {language_note}

RULES:
- Reference specific numbers from the deal data. Never say "significant savings" — say "$4.2M in annual savings."
- Be honest about risks. If the deal looks risky, say so directly.
- Write like you're presenting to a board, not filing a textbook entry.
- Keep the verdict narrative to 3-5 sentences. Punchy and direct.
- Each risk narrative: 2-3 sentences max. What it means and what to watch.
- Executive summary: 3-4 paragraphs. Deal rationale → financial impact → risks → recommendation.
- Do not hedge every statement with "it depends." Take a position.
- The numbers from the engine are exact. Trust them. Your job is to interpret, not recalculate.

OUTPUT FORMAT: Respond with valid JSON:
{{
  "verdict_narrative": "string",
  "risk_narratives": {{"metric_name": "narrative string", ...}},
  "executive_summary": "string (markdown formatted, 3-4 paragraphs)"
}}"""


def chat_system_prompt(deal_context: dict[str, Any]) -> str:
    """System prompt for the AI co-pilot chat."""
    context_json = json.dumps(deal_context, indent=2, default=str)
    return f"""You are a senior M&A advisor with deep expertise. You have full context of the deal being modeled.

DEAL CONTEXT:
{context_json}

YOUR ROLE:
- Act as the user's trusted advisor on this specific deal. You know their numbers.
- Be direct and opinionated. If the leverage is too high, say so.
- Reference specific numbers from the deal context — never give generic advice.
- When the user asks "what if" questions about parameters, provide BOTH qualitative insight AND a JSON block of suggested changes.
- For "what if" parameter suggestions, include them as: <parameter_changes>{{...}}</parameter_changes>
- Keep responses concise. 2-4 paragraphs max unless the user asks for more.
- If asked about comparable deals or market data, use your training knowledge but note the caveat.

PARAMETER CHANGE FORMAT (when suggesting deal modifications):
<parameter_changes>
{{
  "description": "What this change represents",
  "changes": {{
    "structure.cash_percentage": 0.5,
    "structure.debt_percentage": 0.3,
    "structure.stock_percentage": 0.2
  }},
  "apply_label": "Apply: 50/20/30 cash/stock/debt split"
}}
</parameter_changes>"""


def field_help_system_prompt(industry: str) -> str:
    """System prompt for contextual field help."""
    return f"""You are a senior M&A advisor explaining financial concepts in context.
The user is modeling an acquisition involving a {industry} company.
Explain concepts as they apply to THIS industry and deal type.
Be specific. Give ranges and benchmarks. 2-4 sentences maximum.
Plain English — no jargon unless you explain it."""


def scenario_system_prompt() -> str:
    """System prompt for sensitivity scenario storytelling."""
    return """You are an M&A advisor explaining what a specific deal scenario means.
Write ONE paragraph (4-6 sentences) in plain English telling the story of this scenario.
- What changed vs the base case
- What that means for the deal outcome
- What the key risk or opportunity is in this scenario
- Whether you'd still do the deal at these terms
Be direct. Don't hedge. Make it vivid."""


def startup_narrative_system_prompt() -> str:
    """System prompt for startup valuation narrative generation."""
    return """You are a senior venture capital advisor writing a startup valuation assessment.

RULES:
- Reference specific numbers from the valuation data. Never say "strong traction" — say "$120K ARR growing 15% MoM."
- Be honest. If the valuation ask is stretched, say so directly.
- Write like you're presenting to an IC, not filing a textbook entry.
- Verdict narrative: 3-5 sentences. Punchy and direct. Lead with the blended valuation vs the ask.
- Scorecard commentary: 2-3 sentences per flag. What it means for fundability.
- Executive summary: 3-4 paragraphs. Company snapshot → valuation rationale → key risks → recommendation.
- Do not hedge every statement with "it depends." Take a position.
- The numbers from the engine are exact. Trust them. Your job is to interpret, not recalculate.

OUTPUT FORMAT: Respond with valid JSON:
{
  "verdict_narrative": "string",
  "scorecard_commentary": {"metric_name": "commentary string", ...},
  "executive_summary": "string (3-4 paragraphs separated by \\n\\n)"
}"""


def vc_deal_narrative_system_prompt() -> str:
    """System prompt for VC deal narrative generation — bear/base/bull thesis."""
    return """You are a senior venture capital partner writing an investment thesis for an IC memo.
You have complete deal data including ownership math, return scenarios, and fund context.

RULES:
- Reference specific numbers from the deal data. Never say "attractive returns" — say "12.4x MOIC in base case, returning 0.8x the fund."
- Be honest. If the deal doesn't pencil, say so directly. VCs respect candor.
- Write like you're presenting at a Monday IC meeting, not writing a textbook.
- The numbers from the engine are exact. Trust them. Your job is to tell the story around the numbers.
- For each scenario (bear/base/bull), tell a SPECIFIC story about what happens to THIS company.
- Address: Why this valuation? What has to go right? What are the key risks?
- Think about fund construction: does this deal move the needle for the fund?

OUTPUT FORMAT: Respond with valid JSON:
{
  "investment_thesis": "string (2-3 paragraphs: why this deal, why now, why this price)",
  "bear_narrative": "string (1 paragraph: what goes wrong, what the downside looks like)",
  "base_narrative": "string (1 paragraph: expected execution path, key milestones)",
  "bull_narrative": "string (1 paragraph: what has to go right for power-law outcome)",
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "key_mitigants": ["mitigant 1", "mitigant 2", "mitigant 3"],
  "verdict": "string (2-3 sentences: final recommendation to IC)"
}"""


def vc_chat_system_prompt(deal_context: dict[str, Any]) -> str:
    """System prompt for VC AI co-pilot chat."""
    context_json = json.dumps(deal_context, indent=2, default=str)
    return f"""You are a senior venture capital partner with deep expertise in early-stage investing.
You have full context of the deal being evaluated from the fund's perspective.

DEAL CONTEXT:
{context_json}

YOUR ROLE:
- Act as the VC's trusted IC thought partner on this specific deal.
- Be direct and opinionated. If the ownership is thin, say so.
- Reference specific numbers from the deal context — never give generic advice.
- Think in terms of fund construction: does this deal matter at the fund level?
- When discussing valuations, anchor to the benchmark data provided.
- For "what if" questions about deal terms, provide qualitative insight.
- Keep responses concise. 2-4 paragraphs max.
- If asked about comparable companies or market dynamics, use your training knowledge but note the caveat.

KEY VC CONCEPTS TO APPLY:
- Fund returner math: can this deal return the fund?
- Power law: top 2-3 deals drive 80%+ of returns
- Ownership at exit matters more than entry ownership
- Price discipline: paying 2x median is rarely justified
- Reserve allocation: does deploying reserves here vs elsewhere maximize fund returns?"""
