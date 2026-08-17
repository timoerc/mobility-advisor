"""German message catalog. Must have exactly the same keys (and per-key `{placeholder}` sets) as
en.py — enforced by test_i18n_catalog.py, which is the completeness gate for this side of the
i18n system (Python has no `keyof` to do it at the type level, unlike the frontend's de.ts)."""

MESSAGES: dict[str, str] = {
    "alt.keep.name": "Aktuelles Setup beibehalten",
    "alt.keep.tradeoff": "Keine Änderung bei Kosten oder Emissionen",
    "alt.co2.neutral": "Neutral",
    "alt.action.replace.title": "{removed} durch {added} ersetzen",
    "alt.action.replace.name": "Wechsel zu {label}",
    "alt.action.replace.consequence": "Ihr {removed} wird gekündigt und {added} tritt an dessen Stelle.",
    "alt.action.add.title": "{added} hinzufügen",
    "alt.action.add.name": "{label} hinzufügen",
    "alt.action.add.consequence": "{added} wird zu Ihrem Portfolio hinzugefügt.",
    "alt.action.cancel.title": "{removed} kündigen",
    "alt.action.cancel.name": "{removed} kündigen",
    "alt.action.cancel.consequence": "{removed} wird gekündigt.",
    "alt.action.noChange.consequence": "Keine Änderung.",
    "alt.action.description": "{title}. Dies verändert Ihr Mobilitätsportfolio.",
    "alt.tradeoff.moreExpensive": "€{amount} mehr pro Jahr",
    "alt.tradeoff.cheaper": "€{amount} günstiger pro Jahr",
    "alt.tradeoff.moreTime": "+{minutes} Min. Reisezeit pro Jahr",
    "alt.tradeoff.lessTime": "{minutes} Min. Reisezeit pro Jahr",
    "alt.tradeoff.moreCo2": "+{kg} kg CO₂ pro Jahr",
    "alt.tradeoff.lessCo2": "{kg} kg CO₂ pro Jahr",
    "alt.tradeoff.sameAsCurrent": "Gleiche Kosten, Reisezeit und CO₂ wie Ihr aktuelles Setup",
    "alt.breakEven.breaksEven": "amortisiert sich",
    "alt.breakEven.netLoss": "führt zu einem Nettoverlust",
    "alt.breakEven.line": "{label} {verb}: €{discount} Rabattwert ggü. €{fee} Gebühr",
    "alt.co2Impact.value": "{delta:+d} kg CO₂/Jahr",
    "alt.hold.name": "Entscheidung zurückstellen",

    "metric.potentialSaving": "Mögliche Ersparnis",
    "metric.extraCost": "Mehrkosten",
    "metric.noChange": "Keine Änderung",
    "metric.co2Reduction": "CO₂-Reduktion",
    "metric.co2Increase": "CO₂-Zunahme",
    "metric.noCo2Change": "Keine CO₂-Änderung",
    "metric.timeSaved": "Zeitersparnis",
    "metric.extraTravelTime": "Zusätzliche Reisezeit",
    "metric.noTimeChange": "Keine Zeitänderung",
    "metric.unit.minPerYear": "Min./Jahr",
    "metric.unit.hPerYear": "Std./Jahr",
    "metric.unit.eurPerYear": "€/Jahr",
    "metric.unit.kgCo2PerYear": "kg CO₂/Jahr",
    "metric.unit.kgCo2": "kg CO₂",
    "metric.unit.flexDiscountPct": "% Flex-Rabatt",
    "metric.unit.trips": "Fahrten",
    "metric.unit.decision": "Entscheidung",
    "metric.pendingDecision.revisitBy": "Erneut prüfen bis",
    "metric.pendingDecision.valueOnHold": "Wert zurückgestellt",
    "metric.pendingDecision.decisionPending": "Entscheidung ausstehend",
    "metric.pendingDecision.lifeEvent": "Lebensereignis",
    "lifeEvent.category.relocation": "Umzug",
    "lifeEvent.category.job_change": "Jobwechsel",
    "lifeEvent.category.subscription_change": "Abo-Änderung",
    "lifeEvent.category.household_change": "Änderung des Haushalts",
    "lifeEvent.category.other": "Sonstiges",

    "assumption.co2Methodology": (
        "Ein Abonnement verändert, was jedes Verkehrsmittel kostet; die prognostizierte "
        "Verkehrsmittelnutzung passt sich entsprechend an (eine graduelle Verschiebung, kein "
        "harter Wechsel), und Reisezeit sowie CO₂ folgen daraus. Für diese Person wird Zeit mit "
        "€{valueOfTime}/Stunde und CO₂ mit €{co2Price}/kg bewertet, abgeleitet aus den "
        "angegebenen Kosten-/Zeit-/Nachhaltigkeitspräferenzen."
    ),

    "pending.reason": (
        "Ein ausstehendes Ereignis ({categories}) wird voraussichtlich bis {date} wirksam, was "
        "das aktuelle, pendelbasierte Portfolio zurücksetzen würde — jetzt zu handeln riskiert "
        "eine Änderung, die durch die Entscheidung sofort wieder rückgängig gemacht werden "
        "könnte."
    ),
    "verdict.holdUntilResolved": "Behalten Sie Ihr aktuelles Setup bei, bis die ausstehende Entscheidung geklärt ist ({revisit})",

    "mode.rail": "Bahn",
    "mode.flight": "Flug",
    "mode.carRental": "Mietwagen",
    "mode.carShare": "Carsharing",
    "mode.bus": "Bus",
    "mode.unknown": "Unbekannt",
    "report.glance.totalSpend": "Gesamte Mobilitätsausgaben",
    "report.glance.savings": "Geschätzte Einsparungen durch Abo-Rabatte",
    "report.glance.totalCo2": "Gesamter CO₂-Fußabdruck (alle Verkehrsmittel)",
    "report.glance.co2Avoided": "Vermiedenes CO₂ bei Regionalfahrten (Bahn ggü. Carsharing)",
    "report.glance.tripsLogged": "Erfasste Fahrten",
    "report.glance.header.metric": "Kennzahl",
    "report.glance.header.value": "Wert",
    "report.byMode.header.mode": "Verkehrsmittel",
    "report.byMode.header.trips": "Fahrten",
    "report.byMode.header.distance": "Distanz",
    "report.byMode.header.spend": "Ausgaben",
    "report.byMode.header.co2": "CO₂",
    "report.byMode.total": "**Gesamt**",
    "report.subValue.paidOff": "✅ Amortisiert",
    "report.subValue.borderline": "⚠️ Grenzwertig",
    "report.subValue.didNotBreakEven": "❌ Nicht amortisiert",
    "report.subValue.header.discount": " — €{monthly}/Monat (€{annual}/Jahr)",
    "report.subValue.header.flatFee": " — €{monthly}/Monat (€{annual}/Jahr, Pauschalgebühr)",
    "report.subValue.header.loyalty": " — keine monatliche Gebühr (Bonusstufe)",
    "report.subValue.tripsAttributedWithMode": "- Zugeordnete Fahrten: {count} {provider}-{mode}-Fahrten",
    "report.subValue.discountValue": "- Erzielter Rabattwert: €{amount}",
    "report.subValue.netVsFee": "- Netto ggü. Jahresgebühr: {sign}€{amount}",
    "report.subValue.verdict": "- Urteil: {verdict}",
    "report.subValue.tripsCoveredThisYear": "- Abgedeckte Fahrten dieses Jahr: {count}",
    "report.subValue.flatFeeNoBreakEven": "- Pauschaltarif mit unbegrenztem Zugang — kein Pro-Fahrt-Rabatt, gegen den sich eine Amortisation berechnen ließe.",
    "report.subValue.tripsAttributedSimple": "- Zugeordnete Fahrten: {count}",
    "report.subValue.activityThisYear": "- Aktivität dieses Jahr: {count} von {threshold} für die nächste Stufe benötigt",
    "report.subValue.loyaltyNoBreakEven": "- Keine Amortisation anwendbar — diese Mitgliedschaft hat keine Gebühr, die sich ausgleichen ließe.",

    "error.pipelineRetryExhausted": (
        "Die Pipeline hat nach {attempts} Versuchen kein Ergebnis geliefert (letztes Problem: "
        "fehlende Eingabe {lastError}). Das kann passieren, wenn die Antwort einer Stufe leer "
        "zurückkommt — entweder durch einen zu großen Prompt oder eine sporadische Störung im "
        "Backend. Bitte versuchen Sie es erneut."
    ),
    "error.pipelineNoReport": "Die Empfehlungs-Pipeline ist fehlgeschlagen, bevor ein Bericht erstellt wurde: {error}",
    "error.annualPipelineNoReport": "Die Jahresbericht-Pipeline ist fehlgeschlagen, bevor ein Bericht erstellt wurde: {error}",
    "error.pdfRenderingFailed": "PDF-Erstellung fehlgeschlagen: {error}",
    "error.jsonExtractionFailed": "JSON-Extraktion fehlgeschlagen: {error}",
    "error.executionAgentNoResponse": "Der Ausführungs-Agent hat keine Antwort geliefert.",
    "error.agentNoResponse": "Der Agent hat keine Antwort geliefert.",
    "error.unlinkedExecutionNote": (
        "(Hinweis: Diese Änderung wurde angewendet, konnte aber nicht mit der ursprünglichen "
        "Analyse verknüpft werden — vermutlich weil in der Zwischenzeit eine neuere Analyse "
        "gelaufen ist. Sie erscheint daher nicht als rückgängig machbar in Ihrem Verlauf.)"
    ),
    "error.noAnalysisHistoryEntry": "Kein Analyseverlaufseintrag '{entryId}'.",
    "error.onlyNewestCanBeResolved": "Nur die neueste Analyse kann abgeschlossen werden; ältere Analysen sind schreibgeschützt.",
    "error.alreadyExecutedMustRevertFirst": "Diese Analyse wurde bereits umgesetzt; machen Sie sie rückgängig, bevor Sie erneut entscheiden.",
    "error.onlyNewestCanBeReverted": "Nur die neueste Analyse kann rückgängig gemacht werden.",
    "error.noExecutedChangeToRevert": "Diese Analyse hat keine umgesetzte Änderung zum Rückgängigmachen.",
    "error.invalidSubscriptions": "Ungültige Abonnements: {error}",
    "error.noScenarioForPersona": "Kein Szenario für Persona '{personaId}'.",
    "error.noScenarioDirectoryForPersona": "Kein Szenario-Verzeichnis für Persona '{personaId}'.",
    "revert.resolvedMessage": "Rückgängig gemacht — Ihr vorheriges Mobilitäts-Setup wurde wiederhergestellt.",
    "revert.message": "Zu Ihrem vorherigen Mobilitäts-Setup zurückgesetzt.",

    "warn.drivingRouteFailed": "{mode}: Routen-API für Autofahrten fehlgeschlagen, Heuristik wird verwendet",
    "warn.railCalibrationSkipped": (
        "Bahnpreis-Kalibrierung übersprungen ({n} nutzbare DB-Fahrt(en) mit Kosten- und "
        "Distanzdaten; benötigt werden >= {minTrips}) — prognostizierte Bahnpreise verwenden "
        "die unkalibrierte synthetische Preiskurve statt beobachteter Tarife."
    ),
    "warn.railCalibrationClamped": (
        "Der Bahnpreis-Kalibrierungsfaktor {ratio}x (aus {n} beobachteten DB-Fahrten) wirkte "
        "wie ein Ausreißer und wurde auf [{lo}, {hi}] begrenzt."
    ),
    "warn.railCalibrationApplied": (
        "Bahnpreise an beobachtete Tarife kalibriert: synthetische Preiskurve um den Faktor "
        "{ratio}x aus {n} beobachteten DB-Sparpreis-/Flexpreis-Fahrt(en) skaliert, bis zu "
        "{maxDist}km; Strecken darüber hinaus verwenden die unkalibrierte Kurve."
    ),
    "warn.travelReductionDetected": (
        "Signal für reduziertes Reiseaufkommen erkannt (Ereignisdatum {date}) — prognostizierte "
        "Fahrtenhäufigkeiten um den Faktor {factor} gedämpft, um weniger Reisen nach diesem "
        "Datum widerzuspiegeln, statt die Historie unverändert fortzuschreiben."
    ),
    "route.localRegional": "Lokale/regionale Fahrten ({count} Route(n), zusammengefasst)",
    "route.intraCityCar": "Innerstädtische Autofahrten ({count} Fahrt(en) beobachtet, zusammengefasst)",
    "route.homeCommute": "Pendelstrecke ({n}x/Woche Büro, ~{km}km einfache Strecke)",
    "route.carUsage": "Autonutzung ({name}, ~{km}km)",
    "warn.aggregatedIntraCityCar": (
        "{count} innerstädtische Carsharing-/Mietwagenfahrt(en) (durchschnittlich ~{avgDist}km) "
        "zu einer prognostizierten Innerstadt-Fahrt ({freq}/Jahr) zusammengefasst, statt sie zu "
        "verwerfen — dies ist die Nachfrage, an der sich eine Carsharing-Mitgliedschaft "
        "tatsächlich bemisst. Für diese Fahrt wird keine Bahnalternative angeboten (siehe "
        "Docstring dieser Funktion)."
    ),
    "warn.aggregatedRegionalRoutes": (
        "{count} Regionalroute(n) mit jeweils unter 2x/Jahr ({totalFreq}/Jahr zusammen, "
        "~{avgDist}km durchschnittlich) zu einer prognostizierten Nahreise-Fahrt zusammengefasst, "
        "statt sie zu verwerfen — dies ist die Nachfrage, an der sich ein Deutschlandticket oder "
        "ein Regionalabo tatsächlich bemisst."
    ),
    "warn.modelledCommute": (
        "{n} Bürotag(e)/Woche als wiederkehrenden Pendelweg innerhalb der Heimatstadt mit "
        "~{km}km einfacher Strecke modelliert (typische Pendeldistanz im städtischen Raum, nicht "
        "aus den tatsächlichen Daten — die Reisehistorie erfasst nur Fernfahrten) — {freq} "
        "Fahrten/Jahr. Dies ist die Nachfrage, an der sich ein Deutschlandticket oder ein "
        "Regionalabo tatsächlich bemisst."
    ),
    "warn.dedupCalendarWins": (
        "Dedup: {a} ↔ {b} — Kalender-Routendaten verwendet, Häufigkeit aber beim höheren Wert "
        "der Historie von {merged}/Jahr belassen statt bei {calFreq}/Jahr aus dem Kalender"
    ),
    "warn.dedupCalendarReplaces": "Dedup: {a} ↔ {b} — Kalender ({calFreq}/Jahr) ersetzt Historie ({histFreq}/Jahr)",
    "warn.uncorroboratedCalendarDemand": (
        "Unbestätigter Kalenderbedarf: {route} wurde allein aus Kalenderereignissen mit "
        "{freq}/Jahr prognostiziert, ohne unterstützende Fahrt in der Reisehistorie — auf "
        "{cap}/Jahr begrenzt."
    ),
    "data.tripExcludedNullCost": "{label}: cost_eur ist null — von Ausgabensummen ausgeschlossen",
    "data.tripExcludedEmptyMode": "{label}: mode ist leer — von CO₂- und Verkehrsmittel-Auswertung ausgeschlossen",
    "data.tripExcludedUnknownMode": "{label}: unbekanntes mode '{mode}' — von CO₂- und Verkehrsmittel-Auswertung ausgeschlossen",
    "catalog.noSubscriptions": "Keine Abonnements",
    "table.total": "Gesamt",

    "report.pdf.title": "Ihr Mobility Jahresrückblick",
    "report.pdf.filename": "jahresrueckblick-mobilitaet.pdf",
    "report.pdf.mastheadLeft": "Mobility Advisor",
    "report.pdf.mastheadRight": "Jahresrückblick Mobilität",
    "report.pdf.pageLabel": "Seite ",
    "report.pdf.ofLabel": " von ",

    "report.periodCovered": "**Berichtszeitraum:** 1. Januar – 31. Dezember {year}",
    "report.section1": "1. Jahresüberblick",
    "report.section2": "2. Ausgaben & Emissionen nach Verkehrsmittel",
    "report.section3": "3. Nachhaltigkeit",
    "report.section4": "4. Abo-Wert",
    "report.section5": "5. Empfehlungen & Maßnahmen",
    "report.section6": "6. Ausblick",
    "report.section7": "7. Methodik & Annahmen",
    "report.actionsTakenNoneLine": "> **Maßnahmen in diesem Jahr:** Keine.",
    "report.pendingProposalLine": "> **Ausstehender Vorschlag:** wartet auf Ihre Zustimmung (siehe unten).",
    "report.actionsTakenLabel": "Maßnahmen in diesem Jahr",
    "report.pendingProposalLabel": "Ausstehender Vorschlag",
    "report.footerDisclaimer": "⚠️ **Dieser Bericht dient nur zur Information. An Ihren Abonnements wurden keine Änderungen vorgenommen.**",
    "report.dataQualityNotesNone": "Keine.",

    "report.optimizer.proposedChange": "**Vorgeschlagene Änderung:**",
    "report.optimizer.currentMonthlyCost": "**Aktuelle monatliche Kosten:**",
    "report.optimizer.proposedMonthlyCost": "**Vorgeschlagene monatliche Kosten:**",
    "report.optimizer.monthlySaving": "**Monatliche Ersparnis:**",
    "report.optimizer.co2Impact": "**CO₂-Auswirkung:**",
    "report.optimizer.actionDeadline": "**Frist für Maßnahme:**",
    "report.optimizer.cancelChangeBefore": "Vor dem {date} kündigen/ändern, um die automatische Verlängerung zu vermeiden.",
    "report.optimizer.whatStaysAndWhy": "**Was bleibt und warum:**",
    "report.optimizer.whyThisChange": "**Warum diese Änderung:**",

    "error.noMatchFor": "keine Übereinstimmung für '{query}'",
    "error.ambiguousMatchFor": "mehrdeutige Übereinstimmung für '{query}': {count} Einträge gefunden ({matches})",

    "subscriptionChange.error.targetRequired": "target_subscription ist erforderlich für action={action}",
    "subscriptionChange.error.newProductRequired": "new_product ist erforderlich für action={action}",
    "subscriptionChange.error.newEntryInvalid": "neuer Abonnement-Eintrag hat die Validierung nicht bestanden: {error}",
    "subscriptionChange.error.resultInvalid": "resultierende Abonnements haben die Validierung nicht bestanden: {error}",
    "co2Impact.explanation.pureAdd": (
        "Neutral — 0 kg CO2/Jahr. Dies fügt ein Abonnement hinzu, ohne ein anderes zu "
        "entfernen — es ändert also nicht, welches Verkehrsmittel Sie derzeit für welche Fahrt "
        "nutzen."
    ),
    "co2Impact.explanation.priceOnly": (
        "Neutral — 0 kg CO2/Jahr. Dies ändert nur Preis/Stufe; es hat keinen Einfluss darauf, "
        "welches Verkehrsmittel Sie nutzen (Sie können {mode} mit oder ohne dieses Abonnement "
        "weiterhin nutzen)."
    ),
    "co2Impact.explanation.stillCovered": (
        "Neutral — 0 kg CO2/Jahr. Sie behalten ein weiteres Abonnement, das {mode} abdeckt, "
        "der Zugang zu diesem Verkehrsmittel bleibt also unverändert."
    ),
    "co2Impact.period.scoped": "im betrachteten Zeitraum",
    "co2Impact.period.pastYear": "aus den letzten 12 Monaten",
    "co2Impact.explanation.saved": (
        "{delta} kg CO2/Jahr eingespart. Ohne Ihr einziges {mode}-Abonnement würden Ihre "
        "{tripCount} {mode}-Fahrt(en) {period} auf das Auto umsteigen (bei {gramsPerKm} g/km), "
        "was tatsächlich weniger Emissionen sind als diese Fahrten derzeit verursachen "
        "({before} kg → {after} kg)."
    ),
    "co2Impact.explanation.moreEmissions": (
        "{delta} kg CO2/Jahr mehr Emissionen. Ohne Ihr einziges {mode}-Abonnement würden Ihre "
        "{tripCount} {mode}-Fahrt(en) {period} auf das Auto umsteigen (bei {gramsPerKm} g/km), "
        "was die Emissionen von {before} kg auf {after} kg/Jahr erhöht."
    ),

    "subscriptionChange.warn.replaceIsNoOp": (
        "Ersetzungsziel und new_product lösten beide zu '{product}' auf — dies setzt nur den "
        "Verlängerungszyklus eines unveränderten Produkts zurück, kein echter Wechsel."
    ),

    "persona.newUser": "Neuer Nutzer",
}
