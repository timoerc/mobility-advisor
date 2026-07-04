import { useCallback, useEffect, useState } from "react";
import "./App.css";
import { AppShell } from "./components/AppShell";
import { ProgressBar } from "./components/ProgressBar";
import { SkipButton } from "./components/SkipButton";
import { DEFAULT_PERSONAS, type Persona } from "./personas";
import { saveProfile, activatePersona, fetchPersonas } from "./api";
import type { Recommendation } from "./types/recommendation";
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
import { BudgetPage } from "./pages/6_BudgetPage";
import { NotesPage } from "./pages/9_NotesPage";
import { FinalPage } from "./pages/10_FinalPage";
import { AnalysisPage } from "./pages/main/AnalysisPage";
import { DashboardPage } from "./pages/main/DashboardPage";
import { ApprovalPage } from "./pages/main/ApprovalPage";
import { ConfirmationPage } from "./pages/main/ConfirmationPage";
import { ChatPage } from "./pages/main/ChatPage";
import { HomePage } from "./pages/main/HomePage";
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
  personal: { full_name: "", employment_status: "employed", profession: "", household_context: "" },
  location: { home_city: "" },
  commute: { wfh_days: ["mon", "fri"], office_days: ["tue", "wed", "thu"] },
  car: { owns_car: false, fuel_type: null, car_size: null, efficiency: null, efficiency_unit: null, monthly_km_estimate: null },
  subscriptions: [],
  priorities: { cost: 1 / 3, time: 1 / 3, sustainability: 1 / 3 },
  integrations: { outlook_connected: false, gmail_connected: false, calendar_connected: false, db_connected: false, miles_connected: false, deutschlandticket_connected: false },
  monthlyBudgetEur: 0,
  notes: "",
};

// ── Onboarding skip defaults ─────────────────────────────────────────────────

const STEP_SKIP_DEFAULTS: Partial<Record<number, Partial<OnboardingPreferences>>> = {
  4: { car: { owns_car: false, fuel_type: null, car_size: null, efficiency: null, efficiency_unit: null, monthly_km_estimate: null } },
  5: { integrations: { outlook_connected: false, gmail_connected: false, calendar_connected: false, db_connected: false, miles_connected: false, deutschlandticket_connected: false } },
  6: { subscriptions: [] },
  9: { notes: "" },
};

// Step count: 0 (logo) → 10 (final), totalSteps = 11
const TOTAL_ONBOARDING_STEPS = 11;

function buildExportJson(p: OnboardingPreferences) {
  return { personal: p.personal, location: p.location, commute: p.commute, car: p.car, subscriptions: p.subscriptions, priorities: p.priorities, integrations: p.integrations, monthlyBudgetEur: p.monthlyBudgetEur, notes: p.notes };
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

type Phase = "login" | "onboarding" | "main";
type MainView = "home" | "analysis" | "dashboard" | "approval" | "confirmation" | "chat";

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
  const [sessionId] = useState(getOrCreateSessionId);
  // When deep-linking from the dropdown, store the view to return to after saving
  const [returnToMain, setReturnToMain] = useState<MainView | null>(null);

  const activePersona = personas.find((p) => p.id === activePersonaId) ?? DEFAULT_PERSONAS[0];

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
              mockRecommendation: local?.mockRecommendation ?? (bp as any).mockRecommendation,
            };
          })
        );
      })
      .catch(console.warn);
  }, []);

  // ── Login ──────────────────────────────────────────────────────────────────

  const handlePersonaSelect = (id: string) => {
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
      const profile = saved.profileData ?? persona?.profileData ?? EMPTY_PROFILE;
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
    saveProfile(activePersonaId ?? "current", preferences).catch(console.warn);
    setMainView("home");
    setPhase("main");
  };

  // ── Main app navigation ───────────────────────────────────────────────────

  const handleAnalysisComplete = useCallback((rec?: Recommendation) => {
    if (rec) setLiveRecommendation(rec);
    setMainView("dashboard");
  }, []);
  const handleProceedToApproval = () => setMainView("approval");
  const handleConfirm = () => setMainView("confirmation");
  const handleBackToDashboard = () => setMainView("dashboard");
  const handleRunAnalysis = () => {
    setLiveRecommendation(null);
    setMainView("analysis");
  };

  // Deep-link from dropdown → a specific onboarding step, then return to main
  const deepLinkToStep = (step: number) => {
    setReturnToMain(mainView);
    setOnboardingStep(step);
    setPhase("onboarding");
  };

  const handleSaveAndReturn = () => {
    const target = returnToMain ?? "dashboard";
    setReturnToMain(null);
    if (activePersonaId && activePersonaId !== "new") {
      savePersistedPersona(activePersonaId, { onboardingComplete: true, profileData: preferences });
    }
    setActiveArchetypeId(classifyArchetype(preferences));
    saveProfile(activePersonaId ?? "current", preferences).catch(console.warn);
    setMainView(target);
    setPhase("main");
  };

  const handleRedoOnboarding = () => {
    setReturnToMain(null);
    if (activePersonaId) {
      savePersistedPersona(activePersonaId, { onboardingComplete: false });
      setPersonas((ps) => ps.map((p) => p.id === activePersonaId ? { ...p, onboardingComplete: false } : p));
    }
    setOnboardingStep(0);
    setPhase("onboarding");
  };

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

    const showSkip = onboardingStep >= 4 && onboardingStep <= 9 && onboardingStep !== 7 && onboardingStep !== 8;

    return (
      <div className="min-h-screen flex flex-col bg-[#f5f5f3]">
        <ProgressBar step={onboardingStep} total={TOTAL_ONBOARDING_STEPS} />

        <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
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

          {onboardingStep === 1 && <AgentIntroPage />}

          {onboardingStep === 2 && (
            <PersonalProfilePage
              profile={preferences.personal}
              onChange={(personal) => setPreferences((c) => ({ ...c, personal }))}
            />
          )}

          {onboardingStep === 3 && (
            <LocationCommutePage
              homeCity={preferences.location.home_city}
              commute={preferences.commute}
              onCityChange={(home_city) => setPreferences((c) => ({ ...c, location: { home_city } }))}
              onCommuteChange={(commute) => setPreferences((c) => ({ ...c, commute }))}
            />
          )}

          {onboardingStep === 4 && (
            <CarProfilePage
              car={preferences.car}
              onChange={(car) => setPreferences((c) => ({ ...c, car }))}
            />
          )}

          {onboardingStep === 5 && (
            <IntegrationsPage
              integrations={preferences.integrations}
              onChange={(integrations) => setPreferences((c) => ({ ...c, integrations }))}
            />
          )}

          {onboardingStep === 6 && (
            <MobilityStackPage
              subscriptions={preferences.subscriptions}
              onChange={(subscriptions) => setPreferences((c) => ({ ...c, subscriptions }))}
            />
          )}

          {onboardingStep === 7 && (
            <PrioritiesPage
              priorities={preferences.priorities}
              onChange={(priorities) => setPreferences((c) => ({ ...c, priorities }))}
            />
          )}

          {onboardingStep === 8 && (
            <BudgetPage
              monthlyBudgetEur={preferences.monthlyBudgetEur}
              onChange={(monthlyBudgetEur) => setPreferences((c) => ({ ...c, monthlyBudgetEur }))}
            />
          )}

          {onboardingStep === 9 && (
            <NotesPage
              notes={preferences.notes}
              onChange={(notes) => setPreferences((c) => ({ ...c, notes }))}
            />
          )}

          {onboardingStep === 10 && (
            <FinalPage
              onGoHome={handleOnboardingComplete}
            />
          )}
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
              className="h-[52px] w-[52px] rounded-full bg-white border border-gray-200 flex items-center justify-center hover:bg-gray-50 cursor-pointer flex-shrink-0"
            >
              <span className="nav-arrow nav-arrow-dark nav-arrow-back" aria-hidden="true" />
            </button>
          )}
          {returnToMain !== null ? (
            <button
              type="button"
              onClick={handleSaveAndReturn}
              className="flex-1 bg-brand-red text-white rounded-full px-8 py-3 font-semibold hover:opacity-90 cursor-pointer border-0 text-sm"
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
                  className="h-[52px] w-[52px] rounded-full bg-brand-red flex items-center justify-center hover:opacity-90 cursor-pointer border-0 flex-shrink-0"
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

  // ── Phase: main ───────────────────────────────────────────────────────────

  return (
    <AppShell
      personaName={activePersona.profileData.personal.full_name || activePersona.name}
      personaTagline={activePersona.tagline}
      onBack={mainView === "chat" ? () => setMainView("home") : undefined}
      onChatOpen={() => setMainView("chat")}
      onEditPreferences={() => deepLinkToStep(7)}
      onEditProfile={() => deepLinkToStep(2)}
      onMobilityModes={() => deepLinkToStep(4)}
      onRedoOnboarding={handleRedoOnboarding}
      onSwitchProfile={handleSwitchProfile}
    >
      {mainView === "home" && (
        <HomePage onChat={() => setMainView("chat")} onAnalysis={handleRunAnalysis} />
      )}

      {mainView === "analysis" && (
        <AnalysisPage sessionId={sessionId} onComplete={handleAnalysisComplete} />
      )}

      {mainView === "dashboard" && (
        <DashboardPage
          recommendation={liveRecommendation ?? activePersona.mockRecommendation}
          mobilityArchetype={activeArchetypeId ? MOBILITY_ARCHETYPES[activeArchetypeId] : undefined}
          onProceed={handleProceedToApproval}
        />
      )}

      {mainView === "approval" && (
        <ApprovalPage
          recommendation={liveRecommendation ?? activePersona.mockRecommendation}
          onConfirm={handleConfirm}
          onCancel={handleBackToDashboard}
        />
      )}

      {mainView === "confirmation" && (
        <ConfirmationPage
          actionTitle={(liveRecommendation ?? activePersona.mockRecommendation).proposedAction.title}
          onBackToDashboard={handleBackToDashboard}
        />
      )}

      {mainView === "chat" && (
        <ChatPage
          sessionId={sessionId}
          recommendation={liveRecommendation ?? activePersona.mockRecommendation}
          onRunAnalysis={handleRunAnalysis}
        />
      )}
    </AppShell>
  );
}
