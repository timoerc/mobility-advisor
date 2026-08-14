"""The core review endpoints: /api/analyze (deterministic-first recommendation), the
annual report PDF, and the analysis-history log (list/resolve/revert)."""
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from google.adk.runners import InMemoryRunner
from google.genai import types as gtypes

from ... import clock, paths
from ...agents.pipelines import annual_report_pipeline, optimization_pipeline
from ...engine.stats import compute_annual_report_stats
from ...i18n import get_language, t
from ...models import AnalysisHistoryEntry, AnalysisRunResult, CurrentSubscriptions, Recommendation
from ...reporting.chat_tables import render_by_mode_table, render_glance_table, render_subscription_value
from ...reporting.pdf import render_annual_report_pdf
from ...store.decisions import detect_pending_portfolio_decision
from ...store.history import load_history, save_history
from ..deps import history_lock
from ..recommendation.builder import build_alternatives_from_optimization, load_optimization_warnings
from ..recommendation.extraction import extract_recommendation_json, extract_verdict
from ..recommendation.finalize import build_headline_metrics, finalize_recommendation
from ..schemas import AnalyzeRequest, ResolveAnalysisRequest
from .chat import _collect_text, _has_function_call

router = APIRouter()

_MAX_PIPELINE_ATTEMPTS = 2


def _resolve_recommendation_language(rec: Recommendation) -> Recommendation:
    """Swap in the German sibling fields (verdict_de, summaryText_de, ...) seeded on scenario
    analysis_history.json entries, when the active request is German — see models/api.py's _de
    fields and CLAUDE.md's i18n notes. A live /api/analyze run never populates these siblings
    (its LLM output already comes back in the request's language via the agent-prompt
    directive), so this is always a no-op for freshly-generated recommendations; it only
    matters for seeded scenario history read back through GET /api/analysis-history."""
    if get_language() != "de":
        return rec
    if rec.verdict_de:
        rec.verdict = rec.verdict_de
    if rec.summaryText_de:
        rec.summaryText = rec.summaryText_de
    if rec.reasoning_de:
        rec.reasoning = rec.reasoning_de
    if rec.assumptions_de:
        rec.assumptions = rec.assumptions_de
    for metric in rec.metrics:
        if metric.label_de:
            metric.label = metric.label_de
        if metric.value_de:
            metric.value = metric.value_de
    for alt in rec.alternatives:
        if alt.name_de:
            alt.name = alt.name_de
        if alt.tradeoff_de:
            alt.tradeoff = alt.tradeoff_de
        if alt.action is not None:
            if alt.action.title_de:
                alt.action.title = alt.action.title_de
            if alt.action.description_de:
                alt.action.description = alt.action.description_de
            if alt.action.consequence_de:
                alt.action.consequence = alt.action.consequence_de
    return rec


def _resolve_history_entry_language(entry: AnalysisHistoryEntry) -> AnalysisHistoryEntry:
    _resolve_recommendation_language(entry.recommendation)
    if get_language() == "de" and entry.resolvedMessage_de:
        entry.resolvedMessage = entry.resolvedMessage_de
    return entry


async def _with_pipeline_retry(attempt_fn, max_attempts: int = _MAX_PIPELINE_ATTEMPTS):
    """Retry attempt_fn() up to max_attempts times when it raises KeyError.

    attempt_fn should run one full pipeline invocation (its own fresh session)
    and raise KeyError if a stage produced an empty response — either because a
    downstream stage's {analysis}/{forecast}/{recommendation} template referenced
    session state an earlier stage never wrote, or because the final stage's own
    output came back empty. Confirmed via direct testing against this backend
    (KIConnect / GPT-OSS-120B): this happens intermittently even for prompts well
    within a sane context budget, so it is NOT a reliable sign of an oversized
    prompt — it's flaky-upstream-call behavior, which a retry is the standard fix
    for. Every attempt must use its own fresh session so a failed run's partial
    state is never reused by the next attempt.
    """
    last_error: KeyError | None = None
    for _ in range(max_attempts):
        try:
            return await attempt_fn()
        except KeyError as exc:
            last_error = exc
    raise HTTPException(
        status_code=500,
        detail=t("error.pipelineRetryExhausted", attempts=max_attempts, lastError=str(last_error)),
    ) from last_error


@router.post("/api/analyze", response_model=AnalysisRunResult)
async def analyze(req: AnalyzeRequest):
    paths.clear_scratch_files()
    runner = InMemoryRunner(agent=optimization_pipeline, app_name="mobility_advisor_analyze")

    async def attempt() -> str:
        sid = f"analysis_{uuid4().hex[:12]}"
        await runner.session_service.create_session(
            app_name="mobility_advisor_analyze",
            user_id="user",
            session_id=sid,
        )

        last_text = ""
        fallback_text = ""
        async for event in runner.run_async(
            user_id="user",
            session_id=sid,
            new_message=gtypes.Content(
                role="user",
                parts=[gtypes.Part(text="Analyse my current mobility setup and subscriptions.")],
            ),
        ):
            # `text`, not `t` — `t` is also this module's i18n translate function (imported
            # from mobility_advisor.i18n), and a bare assignment to `t` here would shadow it
            # for the rest of this handler, including the t(...) calls later in this function.
            if event.is_final_response():
                text = _collect_text(event)
                if text.strip():
                    last_text = text
            else:
                text = _collect_text(event)
                if text.strip() and not _has_function_call(event):
                    fallback_text = text

        # communicator_agent (the pipeline's last stage) has no output_key, so its
        # actual final report is only available from the event stream above — NOT
        # from session.state["recommendation"], which is optimizer_agent's
        # pre-Communicator draft (see its output_key in agents/optimization.py) and is
        # not what adk web/chat show.
        report_text = last_text or fallback_text
        if not report_text:
            raise KeyError("communicator produced an empty response")
        return report_text

    try:
        report_text = await _with_pipeline_retry(attempt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=t("error.pipelineNoReport", error=str(exc)),
        ) from exc

    try:
        det_alts = build_alternatives_from_optimization()
        if det_alts is not None:
            try:
                verdict = await extract_verdict(report_text)
            except Exception as exc:
                # The deterministic alternatives (det_alts) are the load-bearing artifact
                # here — already fully computed and persisted to _optimization_results.json.
                # The verdict is decorative narration on top of them, and every field below
                # already has a sensible fallback (rec_alt.name, "medium", ""/[]). A parse
                # hiccup on this one call must not throw away an entire completed
                # four-stage pipeline run — see extraction._parse_json_response's
                # docstring for how often this backend needs the tolerance this is
                # guarding against.
                # Greppable prefix + active language: a parse failure specifically on German
                # requests (e.g. from a translated section marker like **Urteil:** the
                # extractor doesn't recognize) would otherwise degrade silently into a
                # plausible-looking but empty-summary, medium-confidence result with no signal
                # anywhere that anything went wrong — this line is the only trace of it.
                print(
                    f"VERDICT_EXTRACTION_FALLBACK: language={get_language()!r} "
                    f"verdict extraction failed, using deterministic fallbacks: {exc}"
                )
                verdict = {}
            rec_alt = next((a for a in det_alts if a.isRecommended), det_alts[0])
            metrics = build_headline_metrics(det_alts, detect_pending_portfolio_decision())
            rec = Recommendation(
                verdict=verdict.get("verdict", rec_alt.name),
                confidence=verdict.get("confidence", "medium"),
                summaryText=verdict.get("summaryText", ""),
                metrics=metrics,
                reasoning=verdict.get("reasoning", []),
                assumptions=verdict.get("assumptions", []),
                alternatives=det_alts,
                dataQualityWarnings=load_optimization_warnings(),
            )
            rec = finalize_recommendation(rec)
        else:
            rec = await extract_recommendation_json(report_text)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=t("error.jsonExtractionFailed", error=str(exc))
        ) from exc

    entry_id = f"hist_{uuid4().hex[:10]}"
    try:
        async with history_lock:
            hist = load_history()
            hist.entries.append(
                AnalysisHistoryEntry(id=entry_id, date=clock.MOCK_TODAY.isoformat(), recommendation=rec)
            )
            save_history(hist)
    except Exception as exc:
        # Losing the history-log write is far cheaper than failing the whole call
        # after an already-completed pipeline run — log and continue regardless.
        print(f"Warning: failed to append analysis history entry: {exc}")

    return AnalysisRunResult(id=entry_id, recommendation=rec)


@router.post("/api/annual-report")
async def annual_report(req: AnalyzeRequest):
    """Run annual_report_pipeline directly (no coordinator routing), then convert the
    annual_communicator's Markdown report into a styled PDF and return it as
    application/pdf. Unlike /api/analyze, this pipeline's final agent has no
    output_key, so its report only exists on the last event, not in session state."""
    runner = InMemoryRunner(agent=annual_report_pipeline, app_name="mobility_advisor_annual")

    async def attempt() -> tuple[str, str]:
        sid = f"annual_{uuid4().hex[:12]}"
        await runner.session_service.create_session(
            app_name="mobility_advisor_annual",
            user_id="user",
            session_id=sid,
        )

        report_text = ""
        async for event in runner.run_async(
            user_id="user",
            session_id=sid,
            new_message=gtypes.Content(
                role="user",
                parts=[gtypes.Part(text="Generate my full annual mobility report.")],
            ),
        ):
            if event.is_final_response():
                report_text = _collect_text(event)

        if not report_text:
            raise KeyError("annual_communicator produced an empty response")
        return report_text, sid

    try:
        report_text, _sid = await _with_pipeline_retry(attempt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=t("error.annualPipelineNoReport", error=str(exc)),
        ) from exc

    # The three data-heavy sections (Year at a Glance, Spend & Emissions by Mode,
    # Subscription Value) are rendered here in Python from the same deterministic
    # compute_annual_report_stats() the communicator's prompt was built from, and
    # substituted for the placeholder markers the communicator was instructed to
    # emit verbatim — the LLM never formats these numbers itself, so they can't
    # drift from what the report's narrative sections say about them.
    stats = compute_annual_report_stats()
    report_text = (
        report_text
        .replace("<!-- GLANCE_TABLE -->", render_glance_table(stats))
        .replace("<!-- BY_MODE_TABLE -->", render_by_mode_table(stats))
        .replace("<!-- SUBSCRIPTION_VALUE -->", render_subscription_value(stats))
    )

    try:
        pdf_bytes = render_annual_report_pdf(report_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=t("error.pdfRenderingFailed", error=str(exc))) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="annual-mobility-review.pdf"'},
    )


@router.get("/api/analysis-history", response_model=list[AnalysisHistoryEntry])
async def get_analysis_history():
    """Return this persona's analysis history, newest first. Entries are stored
    oldest-first on disk (mocked ones authored in narrative order, live ones
    appended as they occur), and reversed here for display."""
    hist = load_history()
    return [_resolve_history_entry_language(e) for e in reversed(hist.entries)]


@router.post("/api/analysis-history/{entry_id}/resolve")
async def resolve_analysis(entry_id: str, req: ResolveAnalysisRequest):
    """Record that the user kept their current setup for the newest analysis.

    Executed changes are recorded by /api/execute itself; this endpoint only handles the
    kept-current decision, which changes nothing on disk.

    Only the newest, not-yet-executed entry can be resolved — older analyses are a read-only ledger,
    and an already-executed one must be reverted before it can be decided again.
    """
    async with history_lock:
        hist = load_history()
        if not hist.entries:
            raise HTTPException(status_code=404, detail=t("error.noAnalysisHistoryEntry", entryId=entry_id))
        newest = hist.entries[-1]
        if newest.id != entry_id:
            raise HTTPException(
                status_code=409,
                detail=t("error.onlyNewestCanBeResolved"),
            )
        if newest.outcome == "executed":
            raise HTTPException(
                status_code=409,
                detail=t("error.alreadyExecutedMustRevertFirst"),
            )
        newest.outcome = req.outcome
        newest.resolvedAlternativeId = req.alternative_id
        newest.resolvedMessage = req.message
        newest.resolvedAt = clock.MOCK_TODAY.isoformat()
        # A kept-current decision changed nothing, so there is nothing to undo.
        newest.revertSnapshot = None
        save_history(hist)
    return {"ok": True}


@router.post("/api/analysis-history/{entry_id}/revert")
async def revert_analysis(entry_id: str):
    """Undo an executed change on the newest analysis: restore the subscription stack captured just
    before the change and reset the entry to 'kept_current' (net effect: no change) so it can be
    decided again. Only the newest, executed entry that still has a stored snapshot can be reverted.
    """
    async with history_lock:
        hist = load_history()
        if not hist.entries:
            raise HTTPException(status_code=404, detail=t("error.noAnalysisHistoryEntry", entryId=entry_id))
        newest = hist.entries[-1]
        if newest.id != entry_id:
            raise HTTPException(status_code=409, detail=t("error.onlyNewestCanBeReverted"))
        if newest.outcome != "executed" or newest.revertSnapshot is None:
            raise HTTPException(status_code=409, detail=t("error.noExecutedChangeToRevert"))
        restored = CurrentSubscriptions.model_validate(newest.revertSnapshot)
        paths.atomic_write_json(paths.DATA_DIR / "current_subscriptions.json", restored.model_dump())
        newest.outcome = "kept_current"
        newest.resolvedAlternativeId = None
        newest.resolvedMessage = t("revert.resolvedMessage")
        newest.resolvedAt = clock.MOCK_TODAY.isoformat()
        newest.revertSnapshot = None
        save_history(hist)
    return {"success": True, "message": t("revert.message")}
