"""Data-store layer: loaders, history, the pending-decision gate, and the sole writer
of subscription/scenario mutations. Market-side (mobility_catalog.json) and user-side
(current_subscriptions.json) fixtures are always read through separate functions here —
see CLAUDE.md's data-modeling principles."""
