import { useCallback, useEffect, useState } from "react";
import "./App.css";
import { AppShell } from "./components/AppShell";
import { ProgressBar } from "./components/ProgressBar";
import { SkipButton } from "./components/SkipButton";
import { DEFAULT_PERSONAS, type Persona } from "./personas";
import { saveProfile, activatePersona, fetchCurrentSubscriptions, fetchPersonas, resolveAnalysis, revertAnalysis } from "./api";
import type { Alternative, AnalysisHistoryEntry, AnalysisRunResult, ExecutionResult, Recommendation } from "./types/recommendation";
import { BTN_PRIMARY_COMPACT } from "./ui";
import {
  classifyArchetype,
  MOBILITY_ARCHETYPES,
  type ArchetypeId,
} from "./mobility-archetypes";
import { PseudoLoginPage } from "./pages/login/PseudoLoginPage";
import { LogoIntroPage } from "./pages/0_LogoIntroPage";
import { AgentIntroPage } from "./pages/1_AgentIntroPage";
import { PersonalProfilePage } from "./pages/2_PersonalProfilePage";
import { LocationCommutePage } from "./pages/3_LocationCommutePage";
import { CarProfilePage } from "./pages/4_CarProfilePage";
import { IntegrationsPage } from "./pages/8_IntegrationsPage";
import { MobilityStackPage } from "./pages/5_MobilityStackPage";
import { PrioritiesPage } from "./pages/7_PrioritiesPage";
import { NotesPage } from "./pages/9_NotesPage";
import { FinalPage } from "./pages/10_FinalPage";
import { AnalysisPage } from "./pages/main/AnalysisPage";
import { DashboardPage } from "./pages/main/DashboardPage";
import { ApprovalPage } from "./pages/main/ApprovalPage";
import { ExecutingPage } from "./pages/main/ExecutingPage";
import { ConfirmationPage } from "./pages/main/ConfirmationPage";
import { ChatPage } from "./pages/main/ChatPage";
import { HomePage } from "./pages/main/HomePage";
import { AnnualReportPage } from "./pages/main/AnnualReportPage";
import { HistoryPage } from "./pages/main/HistoryPage";
import type { OnboardingPreferences } from "./types";

// ── Persistence helpers ──────────────────────────────────────────────────────

type PersistedPersona = { onboardingComplete: boolean; profileData?: OnboardingPreferences };

function loadPersistedPersona(id: string): PersistedPersona | null {
  try {
    const raw = localStorage.getItem(`persona:${id}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function savePersistedPersona(id: string, data: PersistedPersona) {
  localStorage.setItem(`persona:${id}`, JSON.stringify(data));
}

function loadPersonas(): Persona[] {
  return DEFAULT_PERSONAS.map((p) => {
    const saved = loadPersistedPersona(p.id);
    if (!saved) return p;
    return { ...p, onboardingComplete: saved.onboardingComplete };
  });
}

// ── Empty profile for "new" persona ─────────────────────────────────────────

const EMPTY_PROFILE: OnboardingPreferences = {
  personal: { full_name: "", age: null, employment_status: "employed", profession: "", household_context: "" },
  location: { home_city: "" },
  commute: { wfh_days: ["mon", "fri"], office_days: ["tue", "wed", "thu"] },
  car: { owns_car: false, mode: "car_private", type: null, size: null, monthly_km_estimate: null },
  subscriptions: [],
  priorities: { cost: 1 / 3, time: 1 / 3, sustainability: 1 / 3 },
  integrations: { outlook_connected: false, gmail_connected: false, calendar_connected: false, db_connected: false, miles_connected: false, deutschlandticket_connected: false, additional_connections: [] },
  notes: "",
};

// ── Onboarding skip defaults ─────────────────────────────────────────────────

const STEP_SKIP_DEFAULTS: Partial<Record<number, Partial<OnboardingPreferences>>> = {
  // Steps 4 (car), 5 (integrations), 6 (subscriptions) intentionally have no skip default:
  // skipping just advances without clearing pre-filled persona data.
  8: { notes: "" },
};

// Step count: 0 (logo) → 9 (final), totalSteps = 10
const TOTAL_ONBOARDING_STEPS = 10;

function buildExportJson(p: OnboardingPreferences) {
  return { personal: p.personal, location: p.location, commute: p.commute, car: p.car, subscriptions: p.subscriptions, priorities: p.priorities, integrations: p.integrations, notes: p.notes };
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ── App ──────────────────────────────────────────────────────────────────────

type Phase = "login" | "onboarding" | "editing" | "main";
type MainView = "home" | "analysis" | "dashboard" | "approval" | "executing" | "confirmation" | "chat" | "annual" | "history";
type EditConfig = { steps: number[]; currentIndex: number; label: string };

function getOrCreateSessionId(): string {
  const key = "mobility_advisor_session_id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const id = crypto.randomUUID();
  localStorage.setItem(key, id);
  return id;
}

export default function App() {
  const [phase, setPhase] = useState<Phase>("login");
  const [loginCanGoBack, setLoginCanGoBack] = useState(false);
  const [personas, setPersonas] = useState<Persona[]>(loadPersonas);
  const [activePersonaId, setActivePersonaId] = useState<string | null>(null);
  const [onboardingStep, setOnboardingStep] = useState(0);
  const [preferences, setPreferences] = useState<OnboardingPreferences>(EMPTY_PROFILE);
  const [mainView, setMainView] = useState<MainView>("home");
  const [activeArchetypeId, setActiveArchetypeId] = useState<ArchetypeId | null>(null);
  const [liveRecommendation, setLiveRecommendation] = useState<Recommendation | null>(null);
  const [currentAnalysisId, setCurrentAnalysisId] = useState<string | null>(null);
  const [selectedAlternative, setSelectedAlternative] = useState<Alternative | null>(null);
  const [confirmationVariant, setConfirmationVariant] = useState<"executed" | "no-change">("executed");
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [sessionId] = useState(getOrCreateSessionId);
  const [returnToMain, setReturnToMain] = useState<MainView | null>(null);
  // Where the decision screen (DashboardPage) was opened from, when it's a review of an existing
  // history entry rather than a fresh analysis. Drives an optional "back" affordance so a review can
  // be abandoned without a forced decision. `null` = fresh-analysis flow (no back — you must decide).
  const [decisionReturnView, setDecisionReturnView] = useState<MainView | null>(null);
  const [editConfig, setEditConfig] = useState<EditConfig | null>(null);
  // Keyed by persona id so each persona keeps its own generated report — switching
  // personas and back doesn't lose or regenerate one that's still valid.
  const [annualReports, setAnnualReports] = useState<Record<string, Blob>>({});

  const activePersona = personas.find((p) => p.id === activePersonaId) ?? DEFAULT_PERSONAS[0];
  const annualReportKey = activePersonaId ?? "current";

  const invalidateAnnualReport = (personaId: string | null) => {
    const key = personaId ?? "current";
    setAnnualReports((r) => {
      if (!(key in r)) return r;
      const { [key]: _removed, ...rest } = r;
      return rest;
    });
  };

  // Re-sync preferences.subscriptions with the backend's active mutable data after an
  // execution_agent change (dashboard/approval/execute flow, or a chat-driven action) — without
  // this, "Edit my mobility modes" keeps showing whatever was loaded at persona-select time,
  // including subscriptions that have since been cancelled/replaced.
  const refreshCurrentSubscriptions = useCallback(() => {
    fetchCurrentSubscriptions()
      .then((subscriptions) => {
        setPreferences((c) => {
          const next = { ...c, subscriptions };
          if (activePersonaId && activePersonaId !== "new") {
            savePersistedPersona(activePersonaId, { onboardingComplete: true, profileData: next });
          }
          return next;
        });
      })
      .catch(console.warn);
  }, [activePersonaId]);

  // ── Fetch personas from backend on mount ───────────────────────────────────

  useEffect(() => {
    fetchPersonas()
      .then((backendPersonas) => {
        setPersonas((current) =>
          backendPersonas.map((bp) => {
            const local = current.find((p) => p.id === bp.id);
            return {
              ...bp,
              onboardingComplete: local?.onboardingComplete ?? false,
            };
          })
        );
      })
      .catch(console.warn);
  }, []);

  // ── Step renderer (shared by onboarding and editing phases) ───────────────

  const renderStep = (step: number) => {
    switch (step) {
      case 1: return <AgentIntroPage />;
      case 2: return (
        <PersonalProfilePage
          profile={preferences.personal}
          onChange={(personal) => setPreferences((c) => ({ ...c, personal }))}
        />
      );
      case 3: return (
        <LocationCommutePage
          homeCity={preferences.location.home_city}
          commute={preferences.commute}
          onCityChange={(home_city) => setPreferences((c) => ({ ...c, location: { home_city } }))}
          onCommuteChange={(commute) => setPreferences((c) => ({ ...c, commute }))}
        />
      );
      case 4: return (
        <CarProfilePage
          car={preferences.car}
          onChange={(car) => setPreferences((c) => ({ ...c, car }))}
        />
      );
      case 5: return (
        <IntegrationsPage
          integrations={preferences.integrations}
          onChange={(integrations) => setPreferences((c) => ({ ...c, integrations }))}
        />
      );
      case 6: return (
        <MobilityStackPage
          subscriptions={preferences.subscriptions}
          onChange={(subscriptions) => setPreferences((c) => ({ ...c, subscriptions }))}
        />
      );
      case 7: return (
        <PrioritiesPage
          priorities={preferences.priorities}
          onChange={(priorities) => setPreferences((c) => ({ ...c, priorities }))}
        />
      );
      case 8: return (
        <NotesPage
          notes={preferences.notes}
          onChange={(notes) => setPreferences((c) => ({ ...c, notes }))}
        />
      );
      case 9: return <FinalPage onGoHome={handleOnboardingComplete} />;
      default: return null;
    }
  };

  // ── Login ──────────────────────────────────────────────────────────────────

  const handlePersonaSelect = (id: string) => {
    // annualReports is keyed per persona, so switching alone doesn't invalidate
    // anything — each persona's cached report (if any) is simply looked up by id.
    setActivePersonaId(id);

    if (id === "new") {
      setPreferences(EMPTY_PROFILE);
      setOnboardingStep(0);
      setPhase("onboarding");
      return;
    }

    // Always activate the backend scenario for pre-built personas
    activatePersona(id).catch(console.warn);

    const persona = personas.find((p) => p.id === id) ?? DEFAULT_PERSONAS.find((p) => p.id === id);
    const saved = loadPersistedPersona(id);

    if (saved?.onboardingComplete) {
      // Always use fresh persona profileData for pre-built personas so that
      // edit pages always reflect the current mock setup, never stale localStorage.
      const profile = persona?.profileData ?? EMPTY_PROFILE;
      setPreferences(profile);
      setActiveArchetypeId(classifyArchetype(profile));
      setMainView("home");
      setPhase("main");
    } else {
      setPreferences(persona?.profileData ?? EMPTY_PROFILE);
      setOnboardingStep(0);
      setPhase("onboarding");
    }
  };

  // ── Onboarding navigation ─────────────────────────────────────────────────

  const goNext = () => setOnboardingStep((s) => Math.min(s + 1, TOTAL_ONBOARDING_STEPS - 1));
  const goBack = () => setOnboardingStep((s) => Math.max(s - 1, 0));

  const handleSkip = () => {
    const defaults = STEP_SKIP_DEFAULTS[onboardingStep];
    if (defaults) setPreferences((c) => ({ ...c, ...defaults }));
    goNext();
  };

  useEffect(() => {
    if (phase !== "onboarding" || onboardingStep !== 0) return;
    const t = window.setTimeout(() => setOnboardingStep(1), 2600);
    return () => window.clearTimeout(t);
  }, [phase, onboardingStep]);

  const handleOnboardingComplete = () => {
    if (activePersonaId && activePersonaId !== "new") {
      savePersistedPersona(activePersonaId, { onboardingComplete: true, profileData: preferences });
      setPersonas((ps) => ps.map((p) => p.id === activePersonaId ? { ...p, onboardingComplete: true } : p));
    }
    setActiveArchetypeId(classifyArchetype(preferences));
    setLiveRecommendation(null);
    invalidateAnnualReport(activePersonaId);
    saveProfile(activePersonaId ?? "current", preferences, activePersona.avatarBg).catch(console.warn);
    setMainView("home");
    setPhase("main");
  };

  // ── Main app navigation ───────────────────────────────────────────────────

  const handleAnalysisComplete = useCallback((result: AnalysisRunResult) => {
    setLiveRecommendation(result.recommendation);
    setCurrentAnalysisId(result.id);
    setMainView((current) => (current === "analysis" ? "dashboard" : current));
  }, []);
  const handleExecutionComplete = useCallback((result: ExecutionResult) => {
    setExecutionResult(result);
    setMainView((current) => (current === "executing" ? "confirmation" : current));
    if (result.success) {
      refreshCurrentSubscriptions();
      invalidateAnnualReport(activePersonaId);
    }
  }, [refreshCurrentSubscriptions, activePersonaId]);
  // Undo the executed change on the newest analysis (restores the pre-change subscriptions server-side)
  // and re-sync the dependent views. Returns whether the revert succeeded so History can refetch.
  const handleRevertEntry = useCallback(
    async (entry: AnalysisHistoryEntry): Promise<boolean> => {
      try {
        const res = await revertAnalysis(entry.id);
        if (res.success) {
          refreshCurrentSubscriptions();
          invalidateAnnualReport(activePersonaId);
        }
        return res.success;
      } catch (e) {
        console.warn(e);
        return false;
      }
    },
    [refreshCurrentSubscriptions, activePersonaId]
  );
  const handleProceedToApproval = (alt: Alternative) => {
    setSelectedAlternative(alt);
    if (alt.action === null) {
      // "Keep current setup" — nothing to execute, skip Approval/Executing entirely.
      const message = "You chose to keep your current mobility setup. No changes have been made.";
      if (currentAnalysisId) {
        resolveAnalysis(currentAnalysisId, { outcome: "kept_current", alternativeId: alt.id, message }).catch(console.warn);
      }
      setConfirmationVariant("no-change");
      setExecutionResult({ success: true, message });
      setMainView("confirmation");
      return;
    }
    setConfirmationVariant("executed");
    setMainView("approval");
  };
  const handleConfirm = () => setMainView("executing");
  // Nothing was executed on this path (cancelled approval, or execution failed) — the
  // existing recommendation is still valid, so just show it again instead of going home.
  const handleCancelChange = () => setMainView("dashboard");
  // Both the executed and no-change confirmations return Home — treat "confirmed" as
  // the end of this review, whether or not anything was actually applied.
  const handleBackFromConfirmation = () => {
    setDecisionReturnView(null);
    setMainView("home");
  };
  const handleRunAnalysis = () => {
    setLiveRecommendation(null);
    setCurrentAnalysisId(null);
    setSelectedAlternative(null);
    setDecisionReturnView(null);
    setMainView("analysis");
  };
  // Re-open an existing analysis (from History or the Home nudge) in the same decision screen the
  // fresh flow uses. Seeding liveRecommendation + currentAnalysisId (= the entry id resolveAnalysis
  // expects) lets the whole Approval → Executing → resolveAnalysis chain run unchanged. Only the
  // newest, non-executed entry is ever passed here (enforced by the callers).
  const handleReviewEntry = (entry: AnalysisHistoryEntry, from: MainView) => {
    setLiveRecommendation(entry.recommendation);
    setCurrentAnalysisId(entry.id);
    setSelectedAlternative(null);
    setConfirmationVariant("executed");
    setDecisionReturnView(from);
    setMainView("dashboard");
  };
  const handleAnnualReport = () => {
    setMainView("annual");
  };
  const handleViewHistory = () => {
    setMainView("history");
  };

  // ── Deep-link editing (clean single-section edit pages) ──────────────────

  const startEditing = (steps: number[], label: string) => {
    setReturnToMain(mainView);
    setEditConfig({ steps, currentIndex: 0, label });
    setPhase("editing");
  };

  const handleEditCancel = () => {
    const target = returnToMain ?? "home";
    setReturnToMain(null);
    setEditConfig(null);
    setMainView(target);
    setPhase("main");
  };

  const handleEditSave = () => {
    const target = returnToMain ?? "home";
    setReturnToMain(null);
    setEditConfig(null);
    if (activePersonaId && activePersonaId !== "new") {
      savePersistedPersona(activePersonaId, { onboardingComplete: true, profileData: preferences });
    }
    setActiveArchetypeId(classifyArchetype(preferences));
    invalidateAnnualReport(activePersonaId);
    saveProfile(activePersonaId ?? "current", preferences, activePersona.avatarBg).catch(console.warn);
    setMainView(target);
    setPhase("main");
  };

  const handleEditNext = () => {
    if (!editConfig) return;
    if (editConfig.currentIndex < editConfig.steps.length - 1) {
      setEditConfig({ ...editConfig, currentIndex: editConfig.currentIndex + 1 });
    } else {
      handleEditSave();
    }
  };

  const handleSaveAndReturn = () => {
    const target = returnToMain ?? "dashboard";
    setReturnToMain(null);
    if (activePersonaId && activePersonaId !== "new") {
      savePersistedPersona(activePersonaId, { onboardingComplete: true, profileData: preferences });
    }
    setActiveArchetypeId(classifyArchetype(preferences));
    invalidateAnnualReport(activePersonaId);
    saveProfile(activePersonaId ?? "current", preferences, activePersona.avatarBg).catch(console.warn);
    setMainView(target);
    setPhase("main");
  };

  const handleRedoOnboarding = () => {
    setReturnToMain(null);
    if (activePersonaId) {
      savePersistedPersona(activePersonaId, { onboardingComplete: false });
      setPersonas((ps) => ps.map((p) => p.id === activePersonaId ? { ...p, onboardingComplete: false } : p));
      // Reset to fresh persona profile so all steps show correct pre-filled data
      const freshPersona = personas.find((p) => p.id === activePersonaId);
      if (freshPersona) setPreferences(freshPersona.profileData);
    }
    setOnboardingStep(0);
    setPhase("onboarding");
  };

  const handleEditConnections = () => startEditing([5], "Connections");

  const handleSwitchProfile = () => {
    setPhase("login");
    setLoginCanGoBack(true);
  };

  // ── Phase: login ──────────────────────────────────────────────────────────

  if (phase === "login") {
    return (
      <PseudoLoginPage
        personas={personas}
        onSelect={(id) => { setLoginCanGoBack(false); handlePersonaSelect(id); }}
        onBack={loginCanGoBack ? () => setPhase("main") : undefined}
      />
    );
  }

  // ── Phase: onboarding ─────────────────────────────────────────────────────

  if (phase === "onboarding") {
    if (onboardingStep === 0) {
      return <LogoIntroPage />;
    }

    const showSkip = onboardingStep >= 4 && onboardingStep <= 8 && onboardingStep !== 7;

    return (
      <div className="min-h-screen flex flex-col bg-canvas">
        <ProgressBar step={onboardingStep} total={TOTAL_ONBOARDING_STEPS} />

        <header className="bg-white/80 backdrop-blur-md border-b border-hairline sticky top-0 z-10">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
            <img src="/assets/db-logo.svg" className="h-5 w-8 object-contain block" alt="" />
            <span className="font-bold text-sm">Mobility Advisor</span>
            <span className="ml-auto text-xs text-gray-400">
              {onboardingStep} / {TOTAL_ONBOARDING_STEPS - 1}
            </span>
          </div>
        </header>

        <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-8 flex flex-col gap-4">
          {showSkip && <SkipButton onSkip={handleSkip} />}
          {renderStep(onboardingStep)}
        </main>

        <footer
          className={`max-w-2xl mx-auto w-full px-4 pb-8 flex gap-3 ${
            onboardingStep > 1 ? "justify-between" : "justify-end"
          }`}
        >
          {onboardingStep > 1 && (
            <button
              type="button"
              onClick={returnToMain !== null ? handleSaveAndReturn : goBack}
              aria-label={returnToMain !== null ? "Back to app" : "Back"}
              className="h-[52px] w-[52px] rounded-full bg-white border border-gray-200 flex items-center justify-center hover:bg-gray-50 hover:border-gray-300 hover:shadow-card active:scale-95 cursor-pointer flex-shrink-0 transition-[background-color,border-color,box-shadow,transform] duration-150 ease-soft"
            >
              <span className="nav-arrow nav-arrow-dark nav-arrow-back" aria-hidden="true" />
            </button>
          )}
          {returnToMain !== null ? (
            <button
              type="button"
              onClick={handleSaveAndReturn}
              className={`flex-1 ${BTN_PRIMARY_COMPACT}`}
            >
              Save & return →
            </button>
          ) : (
            <>
              {onboardingStep < TOTAL_ONBOARDING_STEPS - 1 && (
                <button
                  type="button"
                  onClick={goNext}
                  aria-label="Continue"
                  className="h-[52px] w-[52px] rounded-full bg-brand-red flex items-center justify-center hover:bg-brand-red-hover active:bg-brand-red-deep active:scale-95 cursor-pointer border-0 flex-shrink-0 shadow-[0_1px_2px_rgba(236,0,22,0.25)] hover:shadow-[0_5px_14px_-3px_rgba(236,0,22,0.4)] transition-[background-color,box-shadow,transform] duration-150 ease-soft"
                >
                  <span className="nav-arrow nav-arrow-white" aria-hidden="true" />
                </button>
              )}
            </>
          )}
        </footer>
      </div>
    );
  }

  // ── Phase: editing ────────────────────────────────────────────────────────

  if (phase === "editing" && editConfig) {
    const currentStep = editConfig.steps[editConfig.currentIndex];
    const isLast = editConfig.currentIndex === editConfig.steps.length - 1;

    return (
      <div className="min-h-screen flex flex-col bg-canvas">
        <header className="bg-white/80 backdrop-blur-md border-b border-hairline sticky top-0 z-10">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
            <img src="/assets/db-logo.svg" className="h-5 w-8 object-contain block" alt="" />
            <span className="font-bold text-sm">{editConfig.label}</span>
            <button
              type="button"
              onClick={handleEditCancel}
              className="ml-auto text-sm text-gray-500 hover:text-gray-900 cursor-pointer border-0 bg-transparent"
            >
              Cancel
            </button>
          </div>
        </header>

        <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-8 flex flex-col gap-4">
          {renderStep(currentStep)}
        </main>

        <footer className="max-w-2xl mx-auto w-full px-4 pb-8 flex gap-3">
          <button
            type="button"
            onClick={handleEditCancel}
            className="h-[52px] px-6 rounded-full bg-white border border-gray-200 text-sm font-semibold hover:bg-gray-50 hover:border-gray-300 active:scale-[0.98] cursor-pointer flex-shrink-0 transition-[background-color,border-color,transform] duration-150 ease-soft"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={isLast ? handleEditSave : handleEditNext}
            className={`flex-1 ${BTN_PRIMARY_COMPACT}`}
          >
            {isLast ? "Save" : "Next →"}
          </button>
        </footer>
      </div>
    );
  }

  // ── Phase: main ───────────────────────────────────────────────────────────

  return (
    <AppShell
      wide={mainView === "home" || mainView === "annual"}
      personaName={activePersona.profileData.personal.full_name || activePersona.name}
      personaTagline={activePersona.tagline}
      avatarBg={activePersona.avatarBg}
      onBack={
        mainView === "dashboard" && decisionReturnView
          ? () => {
              const target = decisionReturnView;
              setDecisionReturnView(null);
              setMainView(target);
            }
          : mainView === "chat" || mainView === "annual" || mainView === "analysis" || mainView === "history"
            ? () => setMainView("home")
            : undefined
      }
      onLogoClick={() => setMainView("home")}
      onChatOpen={() => setMainView("chat")}
      onEditPreferences={() => startEditing([7], "Edit preferences")}
      onEditProfile={() => startEditing([2, 3], "Edit profile")}
      onMobilityModes={() => startEditing([4, 6], "Mobility modes")}
      onEditConnections={handleEditConnections}
      onRedoOnboarding={handleRedoOnboarding}
      onSwitchProfile={handleSwitchProfile}
    >
      {mainView === "home" && (
        <HomePage
          personaName={activePersona.profileData.personal.full_name || activePersona.name}
          onChat={() => setMainView("chat")}
          onAnalysis={handleRunAnalysis}
          onAnnualReport={handleAnnualReport}
          onHistory={handleViewHistory}
          onReviewRecommendation={(entry) => handleReviewEntry(entry, "home")}
        />
      )}

      {mainView === "analysis" && (
        <AnalysisPage sessionId={sessionId} onComplete={handleAnalysisComplete} />
      )}

      {mainView === "dashboard" && liveRecommendation && (
        <DashboardPage
          recommendation={liveRecommendation}
          mobilityArchetype={activeArchetypeId ? MOBILITY_ARCHETYPES[activeArchetypeId] : undefined}
          onProceed={handleProceedToApproval}
        />
      )}

      {mainView === "approval" && selectedAlternative?.action && (
        <ApprovalPage
          action={selectedAlternative.action}
          onConfirm={handleConfirm}
          onCancel={handleCancelChange}
        />
      )}

      {mainView === "executing" && selectedAlternative?.action && (
        <ExecutingPage
          sessionId={sessionId}
          action={selectedAlternative.action}
          analysisId={currentAnalysisId}
          alternativeId={selectedAlternative.id}
          onComplete={handleExecutionComplete}
          onCancel={handleCancelChange}
        />
      )}

      {mainView === "confirmation" && executionResult && (
        <ConfirmationPage
          resultMessage={executionResult.message}
          variant={confirmationVariant}
          onBackToDashboard={handleBackFromConfirmation}
        />
      )}

      {mainView === "chat" && (
        <ChatPage
          sessionId={sessionId}
          onRunAnalysis={handleRunAnalysis}
          onDataChanged={() => {
            refreshCurrentSubscriptions();
            invalidateAnnualReport(activePersonaId);
          }}
        />
      )}

      {mainView === "annual" && (
        <AnnualReportPage
          sessionId={sessionId}
          cachedReport={annualReports[annualReportKey] ?? null}
          onReportReady={(report) =>
            setAnnualReports((r) => ({ ...r, [annualReportKey]: report }))
          }
        />
      )}

      {mainView === "history" && (
        <HistoryPage
          onReviewEntry={(entry) => handleReviewEntry(entry, "history")}
          onRevertEntry={handleRevertEntry}
        />
      )}
    </AppShell>
  );
}
