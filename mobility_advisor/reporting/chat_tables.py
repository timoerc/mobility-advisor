"""Deterministic Markdown table/section renderers for the annual report — pure data, no
LLM formatting involved, so they can't drift from what the report's narrative sections
say about the same subscriptions. Substituted into annual_communicator_agent's
<!-- ..._PLACEHOLDER --> markers by api/routes/analysis.py."""

_MODE_DISPLAY_NAMES = {
    "rail": "Rail",
    "flight": "Flight",
    "car_rental": "Car rental",
    "car_share": "Car share",
    "bus": "Bus",
    "unknown": "Unknown",
}


def render_glance_table(stats: dict) -> str:
    """Render annual_communicator_agent's "Year at a Glance" section (Section 1) as a
    fixed 5-row Markdown table from compute_annual_report_stats() — pure data, no LLM
    formatting involved, so it can't drift from what Section 4 says about the same
    subscriptions."""
    discount_total = sum(
        s["discount_value_eur"] for s in stats["subscriptions"] if s["discount_value_eur"] is not None
    )
    rows = [
        ("Total mobility spend", f"€{stats['total_spend_eur']:,.2f}"),
        ("Estimated savings from subscription discounts", f"€{discount_total:,.2f}"),
        ("Total CO₂ footprint (all modes)", f"{stats['total_co2_kg']:,.1f} kg"),
        ("CO₂ avoided on regional trips (rail vs. car-share)", f"{stats['rail_vs_car_saving_kg']:,.1f} kg"),
        ("Trips logged", str(stats["total_trips"])),
    ]
    lines = ["| Metric | Value |", "|--------|-------|"]
    lines += [f"| {label} | {value} |" for label, value in rows]
    return "\n".join(lines)


def render_by_mode_table(stats: dict) -> str:
    """Render Section 2 "Spend & Emissions by Mode" — an aggregated-by-mode table that
    replaces what used to be a raw per-trip dump. Still fully cross-checkable (every
    trip that fed compute_annual_report_stats() is accounted for in some row) but
    scannable, the way a professional annual report should be."""
    lines = [
        "| Mode | Trips | Distance | Spend | CO₂ |",
        "|------|-------|----------|-------|-----|",
    ]
    for row in stats["by_mode"]:
        is_total = row["mode"] == "Total"
        label = "**Total**" if is_total else _MODE_DISPLAY_NAMES.get(
            row["mode"], row["mode"].replace("_", " ").title()
        )
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
            header += f" — €{sub['monthly_cost_eur']:.2f}/mo (€{sub['annual_fee_eur']:.2f}/yr)"
            net = sub["net_eur"]
            if net >= 0:
                verdict = "✅ Paid off"
            elif net >= -0.1 * sub["annual_fee_eur"]:
                verdict = "⚠️ Borderline"
            else:
                verdict = "❌ Did not break even"
            sign = "+" if net >= 0 else "−"
            # Blank line between the header paragraph and the bullet list below is
            # required — python-markdown (unlike CommonMark) treats a list that
            # directly follows a paragraph with no blank line as a lazy continuation
            # of that paragraph, flattening the bullets into running prose.
            blocks.append(
                f"{header}\n\n"
                f"- Trips attributed: {sub['trips_attributed']} {sub['provider']} "
                f"{sub['mode'].replace('_', ' ')} trips\n"
                f"- Discount value delivered: €{sub['discount_value_eur']:.2f}\n"
                f"- Net vs. annual fee: {sign}€{abs(net):.2f}\n"
                f"- Verdict: {verdict}"
            )
        elif sub["is_paid_subscription"]:
            header += f" — €{sub['monthly_cost_eur']:.2f}/mo (€{sub['annual_fee_eur']:.2f}/yr, flat fee)"
            blocks.append(
                f"{header}\n\n"
                f"- Trips covered this year: {sub['trips_attributed']}\n"
                f"- Flat-fee unlimited-access pass — no per-trip discount to break even against."
            )
        else:
            header += " — no monthly fee (loyalty tier)"
            qa = sub["qualifying_activity"]
            activity_line = (
                f"- Activity this year: {qa['count']} of {qa['threshold']} needed to reach the next tier"
                if qa
                else f"- Trips attributed: {sub['trips_attributed']}"
            )
            blocks.append(
                f"{header}\n\n"
                f"{activity_line}\n"
                f"- No break-even applies — this membership has no fee to offset."
            )
    return "\n\n".join(blocks)
