"""
AI-powered API endpoints for the dealflow engine.

All routes degrade gracefully when ANTHROPIC_API_KEY is not set.
The deterministic engine always runs first; AI adds interpretation on top.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..engine.models import DealInput, DealOutput
from ..engine.startup_models import StartupInput, StartupValuationOutput
from ..services.ai_service import (
    ask_claude,
    ask_claude_with_history,
    stream_claude,
    is_ai_available,
    get_token_usage,
    deal_parser_system_prompt,
    narrative_system_prompt,
    startup_narrative_system_prompt,
    chat_system_prompt,
    field_help_system_prompt,
    scenario_system_prompt,
    MAX_TOKENS_NARRATIVE,
    MAX_TOKENS_CHAT,
    MAX_TOKENS_HELP,
    MAX_TOKENS_PARSE,
    MAX_TOKENS_SCENARIO,
    _cache_key,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    deal_input: DealInput | None = None
    deal_output: DealOutput | None = None


class ParseDealRequest(BaseModel):
    messages: list[ChatMessage]


class ParseDealResponse(BaseModel):
    status: str                         # "need_more_info" | "ready_to_model"
    follow_up_question: str | None
    extracted: dict[str, Any]
    confidence: dict[str, float]
    summary: str
    ai_available: bool


class NarrativeRequest(BaseModel):
    deal_input: DealInput
    deal_output: DealOutput


class NarrativeResponse(BaseModel):
    verdict_narrative: str | None
    risk_narratives: dict[str, str]
    executive_summary: str | None
    ai_available: bool
    cached: bool = False


class FieldHelpRequest(BaseModel):
    field_name: str
    field_label: str
    industry: str
    current_value: str | None = None
    deal_context_summary: str | None = None


class FieldHelpResponse(BaseModel):
    explanation: str
    ai_available: bool
    cached: bool = False


class ScenarioNarrativeRequest(BaseModel):
    base_deal_input: DealInput
    base_deal_output: DealOutput
    scenario_row_label: str
    scenario_col_label: str
    scenario_row_value: float
    scenario_col_value: float
    scenario_accretion_pct: float


class StartupNarrativeRequest(BaseModel):
    startup_input: StartupInput
    startup_output: StartupValuationOutput


class StartupNarrativeResponse(BaseModel):
    verdict_narrative: str | None
    scorecard_commentary: dict[str, str]
    executive_summary: str | None
    ai_available: bool
    cached: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deal_context_dict(deal_input: DealInput, deal_output: DealOutput) -> dict[str, Any]:
    """Build a compact deal context dict for system prompts."""
    y1 = deal_output.pro_forma_income_statement[0] if deal_output.pro_forma_income_statement else None
    return {
        "deal_summary": {
            "acquirer": deal_input.acquirer.company_name,
            "target": deal_input.target.company_name,
            "acquisition_price_m": round(deal_input.target.acquisition_price / 1e6, 1),
            "acquirer_revenue_m": round(deal_input.acquirer.revenue / 1e6, 1),
            "target_revenue_m": round(deal_input.target.revenue / 1e6, 1),
            "acquirer_ebitda_m": round(deal_input.acquirer.ebitda / 1e6, 1),
            "target_ebitda_m": round(deal_input.target.ebitda / 1e6, 1),
            "target_industry": deal_input.target.industry.value,
            "financing": {
                "cash_pct": round(deal_input.structure.cash_percentage * 100, 0),
                "stock_pct": round(deal_input.structure.stock_percentage * 100, 0),
                "debt_pct": round(deal_input.structure.debt_percentage * 100, 0),
            },
            "entry_multiple": round(deal_output.returns_analysis.entry_multiple, 1),
            "mode": deal_input.mode.value,
        },
        "year1_results": {
            "accretion_dilution_pct": round(y1.accretion_dilution_pct, 2) if y1 else None,
            "pro_forma_eps": round(y1.pro_forma_eps, 2) if y1 else None,
            "standalone_eps": round(y1.acquirer_standalone_eps, 2) if y1 else None,
            "net_income_m": round(y1.net_income / 1e6, 1) if y1 else None,
            "interest_expense_m": round(y1.interest_expense / 1e6, 1) if y1 else None,
            "ebitda_m": round(y1.ebitda / 1e6, 1) if y1 else None,
        },
        "verdict": deal_output.deal_verdict.value,
        "risks": [
            {
                "metric": r.metric_name,
                "severity": r.severity.value,
                "current": round(r.current_value, 2),
                "threshold": round(r.threshold_value, 2),
                "band": r.tolerance_band,
            }
            for r in deal_output.risk_assessment
        ],
        "scorecard": [
            {"name": m.name, "value": m.formatted_value, "health": m.health_status.value}
            for m in deal_output.deal_scorecard
        ],
        "synergies": {
            "cost_synergies_m": round(
                sum(s.annual_amount for s in deal_input.synergies.cost_synergies) / 1e6, 2
            ),
            "revenue_synergies_m": round(
                sum(s.annual_amount for s in deal_input.synergies.revenue_synergies) / 1e6, 2
            ),
        },
    }


def _fallback_narrative(deal_output: DealOutput) -> NarrativeResponse:
    """Return template-based narrative when AI is unavailable."""
    y1 = deal_output.pro_forma_income_statement[0] if deal_output.pro_forma_income_statement else None
    ad = y1.accretion_dilution_pct if y1 else 0
    verdict = (
        f"This deal is {'accretive' if ad > 0 else 'dilutive'} by {abs(ad):.1f}% in Year 1."
        if y1 else deal_output.deal_verdict_headline
    )
    return NarrativeResponse(
        verdict_narrative=None,
        risk_narratives={r.metric_name: r.plain_english for r in deal_output.risk_assessment},
        executive_summary=None,
        ai_available=False,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", summary="Check AI availability")
async def ai_status() -> dict[str, Any]:
    """Return AI availability and cumulative usage stats."""
    return {
        "ai_available": is_ai_available(),
        "model": "claude-sonnet-4-20250514",
        "token_usage": get_token_usage(),
    }


@router.post("/parse-deal", response_model=ParseDealResponse, summary="Parse natural language deal description")
async def parse_deal(request: ParseDealRequest) -> ParseDealResponse:
    """
    Parse a natural language deal description and extract structured fields.
    Returns either a follow-up question or a ready-to-model PartialDealInput.
    """
    if not is_ai_available():
        return ParseDealResponse(
            status="ai_unavailable",
            follow_up_question=None,
            extracted={},
            confidence={},
            summary="AI parsing not available. Please use the guided form below.",
            ai_available=False,
        )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    system = deal_parser_system_prompt()

    response = ask_claude_with_history(
        system_prompt=system,
        messages=messages,
        max_tokens=MAX_TOKENS_PARSE,
    )

    if not response:
        return ParseDealResponse(
            status="ai_unavailable",
            follow_up_question=None,
            extracted={},
            confidence={},
            summary="AI temporarily unavailable. Please use the guided form.",
            ai_available=False,
        )

    try:
        # Strip markdown code blocks if present
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        parsed = json.loads(clean)
        return ParseDealResponse(
            status=parsed.get("status", "need_more_info"),
            follow_up_question=parsed.get("follow_up_question"),
            extracted=parsed.get("extracted", {}),
            confidence=parsed.get("confidence", {}),
            summary=parsed.get("summary", ""),
            ai_available=True,
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse Claude deal extraction response: %s\nRaw: %s", e, response)
        return ParseDealResponse(
            status="need_more_info",
            follow_up_question="Could you tell me more about the companies involved and the deal size?",
            extracted={},
            confidence={},
            summary=response[:300],
            ai_available=True,
        )


@router.post("/generate-narrative", response_model=NarrativeResponse, summary="Generate AI deal narrative")
async def generate_narrative(request: NarrativeRequest) -> NarrativeResponse:
    """
    Generate three narrative sections using Claude:
    - Verdict narrative (punchy banker assessment)
    - Per-risk plain-English explanations
    - Executive summary (board-ready)

    Batches all three into one API call. Results are cached by deal fingerprint.
    """
    if not is_ai_available():
        return _fallback_narrative(request.deal_output)

    # Cache key: hash of key deal parameters
    deal_fingerprint = _cache_key(
        str(round(request.deal_input.target.acquisition_price, -3)),
        str(round(request.deal_input.acquirer.ebitda, -3)),
        str(round(request.deal_input.target.ebitda, -3)),
        str(len(request.deal_output.risk_assessment)),
        request.deal_input.mode.value,
    )
    ck = f"narrative:{deal_fingerprint}"

    system = narrative_system_prompt(request.deal_input.mode.value)
    context = _deal_context_dict(request.deal_input, request.deal_output)

    user_msg = f"""Generate a deal assessment for this transaction:

{json.dumps(context, indent=2)}

Verdict headline from engine: {request.deal_output.deal_verdict_headline}
Risks identified: {[r.metric_name for r in request.deal_output.risk_assessment]}

Generate the verdict_narrative, risk_narratives (one per identified risk by metric_name), and executive_summary."""

    from ..services.ai_service import _get_cached, _set_cached
    cached_raw = _get_cached(ck)
    if cached_raw:
        try:
            data = json.loads(cached_raw)
            return NarrativeResponse(
                verdict_narrative=data.get("verdict_narrative"),
                risk_narratives=data.get("risk_narratives", {}),
                executive_summary=data.get("executive_summary"),
                ai_available=True,
                cached=True,
            )
        except Exception:
            pass

    response = ask_claude(
        system_prompt=system,
        user_message=user_msg,
        max_tokens=MAX_TOKENS_NARRATIVE,
        cache_key=None,  # We handle caching ourselves here
    )

    if not response:
        return _fallback_narrative(request.deal_output)

    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean)
        _set_cached(ck, json.dumps(data))
        return NarrativeResponse(
            verdict_narrative=data.get("verdict_narrative"),
            risk_narratives=data.get("risk_narratives", {}),
            executive_summary=data.get("executive_summary"),
            ai_available=True,
            cached=False,
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse narrative response: %s", e)
        # Try to extract verdict narrative from raw text as fallback
        return NarrativeResponse(
            verdict_narrative=response[:600] if response else None,
            risk_narratives={r.metric_name: r.plain_english for r in request.deal_output.risk_assessment},
            executive_summary=None,
            ai_available=True,
        )


@router.post("/explain-field", response_model=FieldHelpResponse, summary="Get contextual field help")
async def explain_field(request: FieldHelpRequest) -> FieldHelpResponse:
    """
    Return a contextual AI explanation of a specific input field.
    Cached per field+industry combination.
    """
    ck = _cache_key(request.field_name, request.industry, request.current_value or "")

    if not is_ai_available():
        return FieldHelpResponse(
            explanation="",
            ai_available=False,
        )

    from ..services.ai_service import _get_cached
    cached = _get_cached(ck)
    if cached:
        return FieldHelpResponse(explanation=cached, ai_available=True, cached=True)

    system = field_help_system_prompt(request.industry)
    context_note = ""
    if request.current_value:
        context_note = f" The current value is {request.current_value}."
    if request.deal_context_summary:
        context_note += f" Deal context: {request.deal_context_summary}"

    user_msg = (
        f"Explain the '{request.field_label}' input field for an M&A model.{context_note} "
        f"Focus on what a {request.industry} company typically looks like for this metric, "
        "and what range to expect."
    )

    response = ask_claude(
        system_prompt=system,
        user_message=user_msg,
        max_tokens=MAX_TOKENS_HELP,
        cache_key=ck,
    )

    return FieldHelpResponse(
        explanation=response or "",
        ai_available=True,
        cached=False,
    )


@router.post("/chat", summary="AI co-pilot chat (streaming)")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    Stream a Claude response for the AI co-pilot chat panel.

    Keeps up to 20 messages of history. Has full deal context in system prompt.
    Returns Server-Sent Events (text/event-stream).
    """
    async def generate():
        if not is_ai_available():
            yield "data: [AI_UNAVAILABLE]\n\n"
            return

        context = {}
        if request.deal_input and request.deal_output:
            context = _deal_context_dict(request.deal_input, request.deal_output)

        system = chat_system_prompt(context)

        # Trim to last 20 messages to stay within context
        recent = request.messages[-20:]
        messages = [{"role": m.role, "content": m.content} for m in recent]

        try:
            async for chunk in stream_claude(system, messages, MAX_TOKENS_CHAT):
                # SSE format: data: <chunk>\n\n
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.warning("Chat stream error: %s", e)
            yield "data: [STREAM_ERROR]\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/scenario-narrative", summary="Generate scenario story (streaming)")
async def scenario_narrative(request: ScenarioNarrativeRequest) -> StreamingResponse:
    """
    Stream a one-paragraph scenario narrative when a user clicks a sensitivity cell.
    """
    async def generate():
        if not is_ai_available():
            yield "data: [AI_UNAVAILABLE]\n\n"
            return

        y1_base = request.base_deal_output.pro_forma_income_statement[0] if request.base_deal_output.pro_forma_income_statement else None
        base_ad = y1_base.accretion_dilution_pct if y1_base else 0
        base_price = request.base_deal_input.target.acquisition_price
        entry_mult = request.base_deal_output.returns_analysis.entry_multiple

        user_msg = f"""Describe this specific deal scenario in one paragraph.

BASE CASE:
- Acquisition price: ${base_price/1e6:.1f}M ({entry_mult:.1f}× EBITDA)
- Year 1 accretion/dilution: {base_ad:+.1f}%
- Acquirer: {request.base_deal_input.acquirer.company_name}
- Target: {request.base_deal_input.target.company_name}

THIS SCENARIO:
- {request.scenario_row_label}: {request.scenario_row_value}
- {request.scenario_col_label}: {request.scenario_col_value}
- Resulting Year 1 accretion/dilution: {request.scenario_accretion_pct:+.1f}%

Tell the story of what this scenario means for the deal. Would you still do it at these terms?"""

        try:
            async for chunk in stream_claude(
                scenario_system_prompt(),
                [{"role": "user", "content": user_msg}],
                MAX_TOKENS_SCENARIO,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.warning("Scenario narrative stream error: %s", e)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/startup-narrative", response_model=StartupNarrativeResponse, summary="Generate AI startup valuation narrative")
async def startup_narrative(request: StartupNarrativeRequest) -> StartupNarrativeResponse:
    """
    Generate three narrative sections for a startup valuation using Claude:
    - Verdict narrative (VC advisor's take on the valuation)
    - Per-scorecard-flag commentary
    - Executive summary (IC-ready)

    Results are cached by startup fingerprint.
    """
    if not is_ai_available():
        return StartupNarrativeResponse(
            verdict_narrative=None,
            scorecard_commentary={},
            executive_summary=None,
            ai_available=False,
        )

    inp = request.startup_input
    out = request.startup_output

    fingerprint = _cache_key(
        inp.fundraise.vertical,
        inp.fundraise.stage,
        str(round(out.blended_valuation, 1)),
        str(round(out.benchmark_p50, 1)),
        out.verdict,
    )
    ck = f"startup_narrative:{fingerprint}"

    from ..services.ai_service import _get_cached, _set_cached
    cached_raw = _get_cached(ck)
    if cached_raw:
        try:
            data = json.loads(cached_raw)
            return StartupNarrativeResponse(
                verdict_narrative=data.get("verdict_narrative"),
                scorecard_commentary=data.get("scorecard_commentary", {}),
                executive_summary=data.get("executive_summary"),
                ai_available=True,
                cached=True,
            )
        except Exception:
            pass

    # Build compact context for the prompt
    context = {
        "company": inp.company_name,
        "vertical": inp.fundraise.vertical,
        "stage": inp.fundraise.stage,
        "geography": inp.fundraise.geography,
        "blended_valuation_m": round(out.blended_valuation, 2),
        "valuation_range": f"{round(out.valuation_range_low, 2)}M – {round(out.valuation_range_high, 2)}M",
        "benchmark_p50_m": round(out.benchmark_p50, 2),
        "percentile_in_market": out.percentile_in_market,
        "verdict": out.verdict,
        "verdict_headline": out.verdict_headline,
        "raise_amount_m": inp.fundraise.raise_amount,
        "pre_money_ask_m": inp.fundraise.pre_money_valuation_ask,
        "implied_dilution_pct": round(out.implied_dilution * 100, 1),
        "traction_bar": out.traction_bar,
        "arr_m": round(inp.traction.annual_recurring_revenue, 3) if inp.traction.annual_recurring_revenue else 0,
        "mrr_m": round(inp.traction.monthly_recurring_revenue, 3) if inp.traction.monthly_recurring_revenue else 0,
        "mom_growth_pct": round(inp.traction.mom_growth_rate * 100, 1),
        "gross_margin_pct": round(inp.traction.gross_margin * 100, 1),
        "method_results": [
            {
                "method": m.method_label,
                "value_m": round(m.indicated_value, 2) if m.indicated_value is not None else None,
                "applicable": m.applicable,
            }
            for m in out.method_results
        ],
        "scorecard_flags": [
            {
                "metric": f.metric,
                "value": f.value,
                "signal": f.signal,
                "benchmark": f.benchmark,
            }
            for f in out.investor_scorecard
        ],
        "warnings": out.warnings,
    }

    user_msg = f"""Generate a startup valuation assessment for this company:

{json.dumps(context, indent=2)}

Generate the verdict_narrative, scorecard_commentary (one entry per scorecard flag metric), and executive_summary."""

    system = startup_narrative_system_prompt()
    response = ask_claude(
        system_prompt=system,
        user_message=user_msg,
        max_tokens=MAX_TOKENS_NARRATIVE,
        cache_key=None,
    )

    if not response:
        return StartupNarrativeResponse(
            verdict_narrative=None,
            scorecard_commentary={},
            executive_summary=None,
            ai_available=True,
        )

    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean)
        _set_cached(ck, json.dumps(data))
        return StartupNarrativeResponse(
            verdict_narrative=data.get("verdict_narrative"),
            scorecard_commentary=data.get("scorecard_commentary", {}),
            executive_summary=data.get("executive_summary"),
            ai_available=True,
            cached=False,
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse startup narrative response: %s", e)
        return StartupNarrativeResponse(
            verdict_narrative=response[:600] if response else None,
            scorecard_commentary={},
            executive_summary=None,
            ai_available=True,
        )
