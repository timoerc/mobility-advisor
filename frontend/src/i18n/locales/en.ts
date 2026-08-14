// Source of truth for every user-facing string in the frontend. Flat, dotted keys (not nested)
// so `keyof typeof en` is a plain string-literal union — greppable straight from a screenshot,
// no recursive type gymnastics for de.ts's Record<TranslationKey, string> to satisfy.
//
// Key scheme: "<domain>.<screen-or-component>.<element>". Plurals follow the `_one`/`_other`
// convention (see translatePlural() in ../translate.ts) — both suffixed keys are declared
// directly below their base, so both are type-checked like any other key.
//
// ── Protected families — do NOT wire these to backend enum/id values ─────────────────────────
// `mode.*`, `confidence.*`, `outcome.*`, `metric.direction.*`, and `car.type.*`/`car.size.*` are
// DISPLAY LABELS for values the backend must keep in English (see models.py's Literal fields and
// CLAUDE.md's i18n notes). Never call t() on the raw backend value itself — always look it up
// through one of these families instead, so the underlying value stays an untranslated enum.
//
// `8_IntegrationsPage.tsx`'s PROVIDER_FULL_NAMES (brand names) are intentionally NOT here — see
// the comment on that Record.

export const en = {
  // ── common ───────────────────────────────────────────────────────────────────────────────
  "common.back": "Back",
  "common.cancel": "Cancel",
  "common.save": "Save",
  "common.next": "Next →",
  "common.continue": "Continue",
  "common.tryAgain": "Try again",
  "common.reset": "Reset",
  "common.backToDashboard": "Back to dashboard",
  "common.skip": "Skip →",
  "common.selectPlaceholder": "— select —",

  // ── onboarding step 2: personal profile ──────────────────────────────────────────────────
  "onboarding.personalProfile.heading": "Tell us about yourself",
  "onboarding.personalProfile.subheading": "This helps the advisor tailor recommendations to your lifestyle.",
  "onboarding.personalProfile.fullName": "Full name",
  "onboarding.personalProfile.fullName.placeholder": "e.g. Maja Hoffmann",
  "onboarding.personalProfile.age": "Age",
  "onboarding.personalProfile.age.placeholder": "e.g. 32",
  "onboarding.personalProfile.employmentStatus": "Employment status",
  "onboarding.personalProfile.employmentStatus.employed": "Employed",
  "onboarding.personalProfile.employmentStatus.selfEmployed": "Self-employed",
  "onboarding.personalProfile.employmentStatus.student": "Student",
  "onboarding.personalProfile.employmentStatus.other": "Other",
  "onboarding.personalProfile.profession": "Profession",
  "onboarding.personalProfile.optional": "(optional)",
  "onboarding.personalProfile.profession.placeholder": "e.g. Product Manager",
  "onboarding.personalProfile.household": "Household",
  "onboarding.personalProfile.household.single": "Single",
  "onboarding.personalProfile.household.partner": "With partner",
  "onboarding.personalProfile.household.family": "Family",

  // ── onboarding step 3: location & commute ────────────────────────────────────────────────
  "onboarding.locationCommute.heading": "Where are you based?",
  "onboarding.locationCommute.subheading": "Your home city and commute pattern help estimate your regular travel needs.",
  "onboarding.locationCommute.homeCity": "Home city",
  "onboarding.locationCommute.homeCity.placeholder": "e.g. Frankfurt",
  "onboarding.locationCommute.weeklyPattern": "Weekly commute pattern",
  "onboarding.locationCommute.clickToToggle": "Click a day to toggle between Office and WFH.",
  "onboarding.locationCommute.wfh": "WFH",
  "onboarding.locationCommute.office": "Office",
  "day.mon": "Mon",
  "day.tue": "Tue",
  "day.wed": "Wed",
  "day.thu": "Thu",
  "day.fri": "Fri",

  // ── onboarding step 4: car profile ───────────────────────────────────────────────────────
  "onboarding.carProfile.heading": "Do you own a car?",
  "onboarding.carProfile.subheading": "If you drive regularly, we can factor your car into the cost and emissions comparison.",
  "onboarding.carProfile.yes": "Yes",
  "onboarding.carProfile.no": "No",
  "onboarding.carProfile.fuelType": "Fuel type",
  "onboarding.carProfile.carSize": "Car size",
  "onboarding.carProfile.estimatedMonthlyKm": "Estimated monthly km",
  "onboarding.carProfile.estimatedMonthlyKm.placeholder": "e.g. 800",
  "car.type.Petrol": "Petrol",
  "car.type.Diesel": "Diesel",
  "car.type.Hybrid": "Hybrid",
  "car.type.Plug-in Hybrid": "Plug-in Hybrid",
  "car.type.Electric": "Electric",
  "car.size.Small car": "Small car",
  "car.size.Medium car": "Medium car",
  "car.size.Large car": "Large car",

  // ── onboarding step 1: agent intro ───────────────────────────────────────────────────────
  "onboarding.agentIntro.headline": "Hi, I am your mobility advisor.",
  "onboarding.agentIntro.paragraph1": "I will help you understand your mobility portfolio and find travel options that fit your preferences.",
  "onboarding.agentIntro.paragraph2": "Let us get you started!",

  // ── onboarding step 9: notes ─────────────────────────────────────────────────────────────
  "onboarding.notes.heading": "Anything else?",
  "onboarding.notes.subheading": "Add optional details such as comfort needs, accessibility, luggage, or preferred travel times.",
  "onboarding.notes.label": "Notes",
  "onboarding.notes.placeholder": "For example: I prefer direct trains and need space for luggage.",

  // ── onboarding step 10: final ────────────────────────────────────────────────────────────
  "onboarding.final.heading": "Thank you!",
  "onboarding.final.body": "I will now analyze your mobility portfolio and prepare personalized recommendations for your next trips.",
  "onboarding.final.goHome": "Go to homepage →",

  // ── onboarding step 5(6): mobility stack ─────────────────────────────────────────────────
  "onboarding.mobilityStack.heading": "Current mobility stack",
  "onboarding.mobilityStack.scanning": "Scanning your connected accounts for active subscriptions…",
  "onboarding.mobilityStack.detected": "We've detected your active subscriptions from your connected accounts. Review, edit, or add more.",
  "onboarding.mobilityStack.noneDetected": "No services detected — skip to continue with an empty stack.",
  "onboarding.mobilityStack.addService": "Add service",
  "onboarding.mobilityStack.provider": "Provider",
  "onboarding.mobilityStack.provider.placeholder": "Search provider…",
  "onboarding.mobilityStack.product": "Product",
  "onboarding.mobilityStack.product.placeholder": "Search product…",
  "onboarding.mobilityStack.product.selectProviderFirst": "Select a provider first",
  "onboarding.mobilityStack.validFrom": "Valid from",
  "onboarding.mobilityStack.nextRenewal": "Next renewal / expiry",
  "onboarding.mobilityStack.add": "Add",

  // ── onboarding step 8: integrations. Service/provider NAMES (Deutsche Bahn, MILES Mobility,
  // Outlook, BVG, ...) are brand names and are intentionally NOT translated anywhere on this
  // page — see PROVIDER_FULL_NAMES in the source, left as a plain untranslated Record. ────────
  "onboarding.integrations.heading": "Connect your accounts",
  "onboarding.integrations.subheading": "Connect your mobility and email accounts so we can detect your active subscriptions and travel history automatically.",
  "onboarding.integrations.mobilityAccounts": "Mobility accounts",
  "onboarding.integrations.connectedCount_one": "{count} connected",
  "onboarding.integrations.connectedCount_other": "{count} connected",
  "onboarding.integrations.moreProviders": "More providers",
  "onboarding.integrations.emailCalendar": "Email & calendar",
  "onboarding.integrations.connect": "Connect",
  "onboarding.integrations.connected": "Connected ✓",
  "onboarding.integrations.confirmTitle": "Connect {provider}?",
  "onboarding.integrations.confirmBody": "Link your {provider} account to import ticket and trip data.",
  "onboarding.integrations.confirmConnect": "Connect ✓",
  "onboarding.integrations.db.description": "Import BahnCard, Sparpreise and trip history from your DB account",
  "onboarding.integrations.miles.description": "Import your MILES membership tier and trip history",
  "onboarding.integrations.dTicket.description": "Confirm your active D-Ticket subscription and renewal date",
  "onboarding.integrations.outlook.description": "Scan booking confirmations and subscription receipts",
  "onboarding.integrations.gmail.description": "Scan booking confirmations and subscription receipts",
  "onboarding.integrations.calendar.description": "Detect commute patterns and upcoming travel demand",

  // ── main: dashboard (decision screen) ────────────────────────────────────────────────────
  "dashboard.whyRecommendation": "Why this recommendation?",
  "dashboard.hideAssumptions": "Hide assumptions",
  "dashboard.showAssumptions": "Show assumptions",
  "dashboard.dataQualityNotes": "Data quality notes",
  "dashboard.yourMobilityProfile": "Your mobility profile",
  "dashboard.portfolioImplications": "Portfolio implications",
  "dashboard.source": "Source: {source}",
  "dashboard.alternatives": "Alternatives",
  "dashboard.confirmKeepCurrent": "Confirm: keep my current setup →",
  "dashboard.continue": "Continue →",

  // ── main: approval ────────────────────────────────────────────────────────────────────────
  "approval.proposedAction": "Proposed action",
  "approval.whatThisMeans": "What this means",
  "approval.whatChangesIfConfirm": "What changes if you confirm",
  "approval.prototypeNote.label": "Prototype note:",
  "approval.prototypeNote.body": "Confirming applies this change to your saved profile data for this prototype — it does not contact Deutsche Bahn or any real provider.",
  "approval.yesProceed": "Yes, proceed",
  "approval.notNow": "Not now",

  // ── main: chat ───────────────────────────────────────────────────────────────────────────
  "chat.initialMessage": "Hi! I'm your mobility advisor. Ask me anything about your travel costs, subscriptions, CO₂ footprint, or upcoming trips.",
  "chat.error": "I couldn't reach the advisor right now. Please try again.",
  "chat.example.subscriptions": "What are my current mobility subscriptions?",
  "chat.example.optimal": "Is my mobility setup optimal right now?",
  "chat.example.co2": "How much CO₂ have I emitted this year?",
  "chat.example.renewal": "When does my BahnCard renew?",

  // ── main: annual report ──────────────────────────────────────────────────────────────────
  "annualReport.status.1": "Reviewing your year of travel…",
  "annualReport.status.2": "Calculating subscription ROI…",
  "annualReport.status.3": "Adding up CO₂ savings…",
  "annualReport.status.4": "Building your forward outlook…",
  "annualReport.status.5": "Finalizing your report…",
  "annualReport.error": "Couldn't generate your annual report right now. Please try again.",
  "annualReport.building": "Building your annual report…",
  "annualReport.iframeTitle": "Your Annual Mobility Review",

  // ── main: analysis (loading) ─────────────────────────────────────────────────────────────
  "analysis.status.1": "Loading your travel history…",
  "analysis.status.2": "Checking subscription costs…",
  "analysis.status.3": "Forecasting upcoming travel…",
  "analysis.status.4": "Comparing contract alternatives…",
  "analysis.status.5": "Computing CO₂ impact…",
  "analysis.status.6": "Preparing your recommendation…",
  "analysis.status.7": "Almost there…",
  "analysis.failed": "Analysis failed",
  "analysis.heading": "Analysing your setup…",
  "analysis.fallbackError": "The analysis pipeline failed. Please try again.",

  // ── main: executing ──────────────────────────────────────────────────────────────────────
  "executing.status.1": "Confirming with the execution agent…",
  "executing.status.2": "Updating your subscriptions…",
  "executing.couldntApply": "Couldn't apply this change",
  "executing.heading": "Applying your change…",
  "executing.fallbackError": "The execution agent could not apply this change.",
  "executing.fallbackErrorRetry": "The execution agent failed. Please try again.",

  // ── main: home ───────────────────────────────────────────────────────────────────────────
  "home.greeting.morning": "Good morning",
  "home.greeting.afternoon": "Good afternoon",
  "home.greeting.evening": "Good evening",
  "home.subheading": "Here's your mobility at a glance.",
  "home.loadingDashboard": "Loading your dashboard…",
  "home.openRecommendation": "You have an open recommendation",
  "home.saveUpTo": "Save up to {amount}/yr",
  "home.review": "Review",
  "home.rangeAsOf": "as of {date}",
  "home.modesByUsage": "Modes by usage",
  "home.modesByUsage.subtitle": "Ranked by number of trips",
  "home.noTripsInRange": "No trips in this range.",
  "home.spend.title": "Mobility spend",
  "home.spend.subtitle": "Trip costs plus subscriptions, assumed active since they started",
  "home.spend.empty": "No spend in this range.",
  "spendChart.legend.trips": "Trips",
  "spendChart.legend.subscriptions": "Subscriptions",
  "spendChart.tooltip": "{label} · Trips {trip} · Subscriptions {sub} · Total {total}",
  "spendChart.summary": "{total} across {count} {unit} · {trip} trips + {sub} subscriptions",
  "spendChart.unit.week_one": "week",
  "spendChart.unit.week_other": "weeks",
  "spendChart.unit.month_one": "month",
  "spendChart.unit.month_other": "months",
  "spendChart.unit.quarter_one": "quarter",
  "spendChart.unit.quarter_other": "quarters",
  "home.co2ByMode": "CO₂ by mode",
  "home.co2ByMode.subtitle": "Which modes drive your footprint",
  "home.noEmissionsInRange": "No emissions data in this range.",
  "home.recentActivity": "Recent activity",
  "home.recentActivity.subtitle": "Your latest trips in this range",
  "home.yourSubscriptions": "Your subscriptions",
  "home.noActiveSubscriptions": "No active subscriptions.",
  "home.free": "Free",
  "home.total": "Total",
  "home.nextRenewal": "Next renewal: {provider} — {product} in {days} {dayWord} ({date})",
  "home.day_one": "day",
  "home.day_other": "days",
  "home.quickActions": "Quick actions",
  "home.action.chat.title": "Chat",
  "home.action.chat.subtitle": "Ask me anything about your trips, costs, and subscriptions.",
  "home.action.analysis.title": "Start Analysis",
  "home.action.analysis.subtitle": "Run a full analysis of your mobility portfolio.",
  "home.action.annualReport.title": "Generate Annual Report",
  "home.action.annualReport.subtitle": "Get your full year-in-review: spend, CO₂, and subscription ROI.",
  "home.action.history.title": "History",
  "home.action.history.subtitle": "Review past analyses and the decisions you made.",
  "home.kpi.co2Footprint": "CO₂ footprint",
  "home.kpi.travelSpend": "Travel spend",
  "home.kpi.distance": "Distance",
  "home.kpi.trip_one": "Trip",
  "home.kpi.trip_other": "Trips",
  "home.trip_one": "trip",
  "home.trip_other": "trips",

  // ── main: history ────────────────────────────────────────────────────────────────────────
  "history.heading": "History",
  "history.subheading": "Past analyses and the decisions you made.",
  "history.loading": "Loading your analysis history…",
  "history.fallbackError": "Could not load your analysis history.",
  "history.noAnalysesYet": "No analyses yet",
  "history.noAnalysesYet.body": "Run your first analysis from Home and it'll show up here.",
  "history.latest": "Latest",
  "history.superseded": "Superseded — no decision",
  "history.assumptions": "Assumptions",
  "history.optionsConsidered": "Options considered",
  "history.reconsider": "Reconsider this decision",
  "history.reviewAndDecide": "Review & decide",
  "history.revertThisChange": "Revert this change",
  "history.revertConfirm": "Revert this change? Your previous mobility setup will be restored.",
  "history.reverting": "Reverting…",
  "history.revert": "Revert",
  "history.revertFailed": "Couldn't revert right now. Please try again.",
  "home.travelInsights": "Travel insights",
  "home.travelDataLoadError": "Couldn't load travel data right now.",

  // ── mobility archetypes (mobility-archetypes.ts). `source` fields are bibliographic
  // citations and are intentionally NOT translated anywhere — same reasoning as
  // PROVIDER_FULL_NAMES; a citation reads the same regardless of UI language. ─────────────────
  "archetype.committed_driver.name": "Committed Driver",
  "archetype.committed_driver.tagline": "Car-first mobility — high ownership cost, low transit use",
  "archetype.committed_driver.description": "You rely primarily on your car for daily transport. With 57% of Germans choosing the car as their main mode (MiD 2017), you're in the largest segment — but also the one with the highest hidden costs.",
  "archetype.committed_driver.insight1": "Total cost of car ownership (loan, insurance, fuel, parking) frequently exceeds €500/month — often invisible because costs are spread across multiple bills.",
  "archetype.committed_driver.insight2": "A BahnCard 25 can pay off even at low rail frequency: it breaks even after just 2–3 long-distance business trips per year.",
  "archetype.committed_driver.insight3": "Carsharing becomes cost-competitive once actual driving drops below ~800 km/month, which is common when office attendance is hybrid.",

  "archetype.rail_commuter.name": "Rail Commuter",
  "archetype.rail_commuter.tagline": "Train as primary mode — subscription choices drive most savings",
  "archetype.rail_commuter.description": "You use Deutsche Bahn regularly and rely on rail subscriptions to manage costs. BahnCard holders make up DB's most loyal and savings-sensitive segment, where small tier decisions have outsized financial impact.",
  "archetype.rail_commuter.insight1": "BahnCard 50 break-even requires roughly €488 in annual full-price ticket spend (2nd class, 2024 pricing). Below that, BahnCard 25 or pay-per-use is cheaper.",
  "archetype.rail_commuter.insight2": "Flex Price caps (Sparpreis, Super Sparpreis) can save 30–60% on long-distance routes even without a BahnCard — stacking them with a BahnCard 25 is the typical optimal combination.",
  "archetype.rail_commuter.insight3": "Combining a Deutschlandticket (€49/month) with a BahnCard 25 is optimal for hybrid commuters who travel long-distance 1–2 times per month.",

  "archetype.multimodal.name": "Multimodal Explorer",
  "archetype.multimodal.tagline": "Mixes modes flexibly — highest satisfaction, highest overlap risk",
  "archetype.multimodal.description": "You switch between transport modes depending on the trip. Multimodal users make up 18% of all German trips (MiD 2017) and report the highest satisfaction — but also carry the highest risk of redundant subscriptions.",
  "archetype.multimodal.insight1": "Subscription stacking is the biggest cost risk: Deutschlandticket + BahnCard + carsharing membership can overlap significantly for urban short trips.",
  "archetype.multimodal.insight2": "MaaS (Mobility as a Service) bundles like DB Connect or regional ÖPNV-Flatrates can replace 2–3 individual subscriptions at lower combined cost.",
  "archetype.multimodal.insight3": "Review each subscription against actual monthly usage — paying for 3 services but only using each 30% of the time means 70% of spend is wasted.",

  "archetype.eco_pioneer.name": "Eco Pioneer",
  "archetype.eco_pioneer.tagline": "Sustainability-first — CO₂ is a decision variable, not a footnote",
  "archetype.eco_pioneer.description": "Environmental impact is your primary mobility criterion. You're part of a fast-growing segment: 23% of Germans now cite climate as a top concern when choosing how to travel (ADAC 2023).",
  "archetype.eco_pioneer.insight1": "Rail travel emits ~32 g CO₂/pkm vs. 147 g CO₂/pkm by car — a single Munich–Hamburg return trip by train instead of car saves ~38 kg CO₂.",
  "archetype.eco_pioneer.insight2": "Deutschlandticket + e-bike subscription covers >90% of trips for urban/suburban users at under €100/month total cost.",
  "archetype.eco_pioneer.insight3": "Carbon savings have a monetary value: at the German shadow carbon price of €200/tonne, every tonne avoided is worth €200 in avoided social cost — a legitimate factor in ROI calculations.",

  "archetype.budget_optimizer.name": "Budget Optimizer",
  "archetype.budget_optimizer.tagline": "Cost is the primary lens — every subscription must justify itself",
  "archetype.budget_optimizer.description": "You evaluate every mobility subscription against its real-world return. Cost is the #1 factor for 68% of public transit users in Germany (VDV-Erhebung 2022) — and subscription math is often more complex than it looks.",
  "archetype.budget_optimizer.insight1": "Annual subscriptions should be stress-tested: if usage drops by 20% (holiday, illness, remote periods), break-even often tips negative.",
  "archetype.budget_optimizer.insight2": "Pay-per-use outperforms fixed subscriptions when monthly trip count varies by more than ±30% — avoid locking in annual fees for variable needs.",
  "archetype.budget_optimizer.insight3": "Deutschlandticket at €49/month has the lowest break-even of any German transit pass: it pays off after just 2 return ÖPNV journeys per month in most major cities.",

  "archetype.remote_native.name": "Remote Native",
  "archetype.remote_native.tagline": "Hybrid worker — occasional bursts, not daily commuting",
  "archetype.remote_native.description": "You work from home most days and travel only occasionally. Post-pandemic, 24% of German employees are in hybrid arrangements (IFO Institut 2023), which fundamentally changes the economics of fixed mobility subscriptions.",
  "archetype.remote_native.insight1": "Annual subscriptions built around a 5-day commute lose 30–60% of their value for hybrid workers — BahnCard 25 or month-to-month Deutschlandticket is usually the better fit.",
  "archetype.remote_native.insight2": "Carsharing is significantly cheaper than ownership for under ~600 km/month of actual driving — a threshold most hybrid workers fall below on remote days.",
  "archetype.remote_native.insight3": "Cluster your travel: grouping trips into multi-day blocks rather than spreading them thin increases the per-trip value extracted from any fixed subscription you do hold.",

  // ── dashboard-stats.ts range presets. 1M/6M/1Y/5Y/YTD are conventional compact abbreviations
  // kept as-is in German too (a translated "YTD" would either lose the recognizable shorthand
  // or not fit the pill) — only "All" is translated.
  "range.1m": "1M",
  "range.6m": "6M",
  "range.1y": "1Y",
  "range.ytd": "YTD",
  "range.5y": "5Y",
  "range.all": "All",

  // ── App.tsx shell chrome ──────────────────────────────────────────────────────────────────
  "onboarding.backToApp": "Back to app",
  "onboarding.saveAndReturn": "Save & return →",
  // The one place the frontend authors recommendation-adjacent prose itself (rather than
  // receiving it from the backend) — see App.tsx's handleProceedToApproval().
  "confirmation.keptCurrentMessage": "You chose to keep your current mobility setup. No changes have been made.",

  // ── login screen ─────────────────────────────────────────────────────────────────────────
  "login.selectProfile": "Select a profile to continue",
  "login.demoMode": "Demo mode — no real authentication",
  "login.addNewProfile": "Add new profile",
  "login.startFresh": "Start fresh with empty data",
  "login.disclaimer": "BCG × Deutsche Bahn university project prototype. No data is stored outside your browser.",

  // ── nav / language switcher ─────────────────────────────────────────────────────────────
  "nav.appName": "Mobility Advisor",
  "nav.language": "Language",
  "nav.home": "Home",
  "nav.openChat": "Open chat",

  // ── mode.* — display labels for the backend's mobility-mode enum. Never translate `mode`
  // itself; only look it up through this family (see labels.ts's modeLabel()). ──────────────
  "mode.rail": "Rail",
  "mode.car_share": "Carsharing",
  "mode.car_rental": "Car Rental",
  "mode.flight": "Flight",
  "mode.bus": "Bus",

  // ── shared small components ──────────────────────────────────────────────────────────────
  "subscriptionCard.detected": "Detected",
  "subscriptionCard.edit": "Edit",
  "subscriptionCard.remove": "Remove",
  "progressBar.stepOf": "Step {step} of {total}",
  "chatInput.placeholder": "Ask anything about your mobility…",
  "chatInput.send": "Send",
  "personaCard.profileComplete": "Profile complete",
  "profileDropdown.profileAndSettings": "Profile and settings",
  "profileDropdown.editPreferences.label": "Edit preferences",
  "profileDropdown.editPreferences.sublabel": "Cost · Time · CO₂ weights",
  "profileDropdown.editProfile.label": "Edit profile",
  "profileDropdown.editProfile.sublabel": "Name, location, commute",
  "profileDropdown.mobilityModes.label": "Mobility modes",
  "profileDropdown.mobilityModes.sublabel": "Car, subscriptions, modes",
  "profileDropdown.connections.label": "Connections",
  "profileDropdown.connections.sublabel": "Linked accounts & services",
  "profileDropdown.redoOnboarding.label": "Re-do full onboarding",
  "profileDropdown.redoOnboarding.sublabel": "Start the setup wizard again",
  "profileDropdown.switchProfile": "Switch profile",

  // ── AlternativeRow ───────────────────────────────────────────────────────────────────────
  "alternativeRow.recommended": "Recommended",
  "alternativeRow.selected": "Selected",
  "alternativeRow.executed": "Executed",
  "alternativeRow.vsStatusQuo": "vs. status quo",
  "alternativeRow.vsCurrentSetup": "vs. your current setup",
  "alternativeRow.noChange": "no change",
  "alternativeRow.cost": "cost",
  "alternativeRow.co2": "CO₂",
  "alternativeRow.travelTime": "travel time",

  // ── confidence.* — display labels for the backend's confidence enum (high/medium/low).
  // Never translate the enum value itself; only look it up through this family. ─────────────
  "confidence.high": "High confidence",
  "confidence.medium": "Medium confidence",
  "confidence.low": "Low confidence",

  // ── outcome.* — display labels for AnalysisHistoryEntry.outcome (pending/kept_current/executed) ──
  "outcome.pending": "Pending decision",
  "outcome.kept_current": "Kept current setup",
  "outcome.executed": "Executed",

  // ── confirmation page ────────────────────────────────────────────────────────────────────
  "confirmation.heading.executed": "Done!",
  "confirmation.heading.no_change": "Got it — no changes made",
  "confirmation.footnote.executed":
    "This updated your saved profile data for this prototype only — no real provider (e.g. Deutsche Bahn) was contacted.",
  "confirmation.footnote.no_change": "No changes were made to your subscriptions or saved profile data.",

  // ── onboarding: priorities (step 7) ──────────────────────────────────────────────────────
  "priorities.heading": "What matters most to you?",
  "priorities.subheading": "Answer three short comparisons and we'll calculate your priorities.",
  "priorities.likert.1": "Strongly disagree",
  "priorities.likert.2": "Disagree",
  "priorities.likert.3": "Somewhat disagree",
  "priorities.likert.4": "Balanced",
  "priorities.likert.5": "Somewhat agree",
  "priorities.likert.6": "Agree",
  "priorities.likert.7": "Strongly agree",
  "priorities.q1.statement": "Getting to my destination quickly matters more to me than a low price.",
  "priorities.q1.leftLabel": "Low price",
  "priorities.q1.rightLabel": "Fast travel",
  "priorities.q2.statement": "A low CO₂ footprint matters more to me than a low price.",
  "priorities.q2.leftLabel": "Low price",
  "priorities.q2.rightLabel": "Low CO₂",
  "priorities.q3.statement": "Getting to my destination quickly matters more to me than a low CO₂ footprint.",
  "priorities.q3.leftLabel": "Low CO₂",
  "priorities.q3.rightLabel": "Fast travel",
  "priorities.consistencyWarning":
    "Your answers are slightly inconsistent (CR = {cr}). This can happen when, for example, you say Time > Price, Price > CO₂, but also CO₂ > Time. Would you like to review your answers?",
  "priorities.yourPriorities": "Your priorities",
  "priorities.weight.cost": "Cost",
  "priorities.weight.time": "Time",
  "priorities.weight.co2": "CO₂",
} as const;
