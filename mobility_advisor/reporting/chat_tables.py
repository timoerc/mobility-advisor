"""Deterministic Markdown table/section renderers for the annual report — pure data, no
LLM formatting involved, so they can't drift from what the report's narrative sections
say about the same subscriptions. Substituted into annual_communicator_agent's
<!-- ..._PLACEHOLDER --> markers by api/routes/analysis.py."""
from ..i18n import t

_MODE_DISPLAY_KEYS = {
    "rail": "mode.rail",
    "flight": "mode.flight",
    "car_rental": "mode.carRental",
    "car_share": "mode.carShare",
    "bus": "mode.bus",
    "unknown": "mode.unknown",
}


def _mode_display_label(mode: str) -> str:
    key = _MODE_DISPLAY_KEYS.get(mode)
    return t(key) if key else mode.replace("_", " ").title()


def render_glance_table(stats: dict) -> str:
    """Render annual_communicator_agent's "Year at a Glance" section (Section 1) as a
    fixed 5-row Markdown table from compute_annual_report_stats() — pure data, no LLM
    formatting involved, so it can't drift from what Section 4 says about the same
    subscriptions."""
    discount_total = sum(
        s["discount_value_eur"] for s in stats["subscriptions"] if s["discount_value_eur"] is not None
    )
    rows = [
        (t("report.glance.totalSpend"), f"€{stats['total_spend_eur']:,.2f}"),
        (t("report.glance.savings"), f"€{discount_total:,.2f}"),
        (t("report.glance.totalCo2"), f"{stats['total_co2_kg']:,.1f} kg"),
        (t("report.glance.co2Avoided"), f"{stats['rail_vs_car_saving_kg']:,.1f} kg"),
        (t("report.glance.tripsLogged"), str(stats["total_trips"])),
    ]
    lines = [f"| {t('report.glance.header.metric')} | {t('report.glance.header.value')} |", "|--------|-------|"]
    lines += [f"| {label} | {value} |" for label, value in rows]
    return "\n".join(lines)


def render_by_mode_table(stats: dict) -> str:
    """Render Section 2 "Spend & Emissions by Mode" — an aggregated-by-mode table that
    replaces what used to be a raw per-trip dump. Still fully cross-checkable (every
    trip that fed compute_annual_report_stats() is accounted for in some row) but
    scannable, the way a professional annual report should be."""
    lines = [
        f"| {t('report.byMode.header.mode')} | {t('report.byMode.header.trips')} | "
        f"{t('report.byMode.header.distance')} | {t('report.byMode.header.spend')} | "
        f"{t('report.byMode.header.co2')} |",
        "|------|-------|----------|-------|-----|",
    ]
    for row in stats["by_mode"]:
        # "Total" is an internal sentinel written by engine/stats.py's
        # compute_annual_report_stats() and matched by exact string equality here — it is
        # never itself displayed, so it must stay untranslated (see that function's comment
        # on the same value).
        is_total = row["mode"] == "Total"
        label = t("report.byMode.total") if is_total else _mode_display_label(row["mode"])
        lines.append(
            f"| {label} | {row['trips']} | {row['distance_km']:,.0f} km | "
            f"€{row['spend_eur']:,.2f} | {row['co2_kg']:,.1f} kg |"
        )
    return "\n".join(lines)


def render_subscription_value(stats: dict) -> str:
    """Render Section 4 "Subscription Value" — one block per active subscription.

    Three cases, keyed off compute_annual_report_stats()'s has_discount_value /
    is_paid_subscription flags:
      - has_discount_value: a paid subscription with a real per-trip discount (e.g.
        BahnCard) — gets a discount-vs-fee net figure and a break-even verdict.
      - is_paid_subscription but not has_discount_value: a paid flat-fee
        unlimited-access pass (e.g. Deutschlandticket, BahnCard 100) — there's no
        discrete per-trip fare to discount, so it gets a usage line instead of a
        fabricated €0.00 "discount value" / break-even verdict.
      - neither: a €0 loyalty/status tier (e.g. a car-rental loyalty program) — gets
        a plain activity status line; there is no fee to break even against, so a
        break-even verdict for it would be meaningless (the bug this replaces).
    """
    blocks = []
    for sub in stats["subscriptions"]:
        header = f"**{sub['product']}**"
        if sub["has_discount_value"]:
            header += t("report.subValue.header.discount", monthly=f"{sub['monthly_cost_eur']:.2f}", annual=f"{sub['annual_fee_eur']:.2f}")
            net = sub["net_eur"]
            if net >= 0:
                verdict = t("report.subValue.paidOff")
            elif net >= -0.1 * sub["annual_fee_eur"]:
                verdict = t("report.subValue.borderline")
            else:
                verdict = t("report.subValue.didNotBreakEven")
            sign = "+" if net >= 0 else "−"
            # Blank line between the header paragraph and the bullet list below is
            # required — python-markdown (unlike CommonMark) treats a list that
            # directly follows a paragraph with no blank line as a lazy continuation
            # of that paragraph, flattening the bullets into running prose.
            blocks.append(
                f"{header}\n\n"
                + t("report.subValue.tripsAttributedWithMode", count=sub["trips_attributed"], provider=sub["provider"], mode=sub["mode"].replace("_", " ")) + "\n"
                + t("report.subValue.discountValue", amount=f"{sub['discount_value_eur']:.2f}") + "\n"
                + t("report.subValue.netVsFee", sign=sign, amount=f"{abs(net):.2f}") + "\n"
                + t("report.subValue.verdict", verdict=verdict)
            )
        elif sub["is_paid_subscription"]:
            header += t("report.subValue.header.flatFee", monthly=f"{sub['monthly_cost_eur']:.2f}", annual=f"{sub['annual_fee_eur']:.2f}")
            blocks.append(
                f"{header}\n\n"
                + t("report.subValue.tripsCoveredThisYear", count=sub["trips_attributed"]) + "\n"
                + t("report.subValue.flatFeeNoBreakEven")
            )
        else:
            header += t("report.subValue.header.loyalty")
            qa = sub["qualifying_activity"]
            activity_line = (
                t("report.subValue.activityThisYear", count=qa["count"], threshold=qa["threshold"])
                if qa
                else t("report.subValue.tripsAttributedSimple", count=sub["trips_attributed"])
            )
            blocks.append(
                f"{header}\n\n"
                f"{activity_line}\n"
                + t("report.subValue.loyaltyNoBreakEven")
            )
    return "\n\n".join(blocks)
