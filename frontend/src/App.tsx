import { useEffect, useState } from "react";
import "./App.css";
import { ProgressBar } from "./components/ProgressBar";
import { SkipButton } from "./components/SkipButton";
import { LogoIntroPage } from "./pages/0_LogoIntroPage";
import { AgentIntroPage } from "./pages/1_AgentIntroPage";
import { PersonalProfilePage } from "./pages/2_PersonalProfilePage";
import { LocationCommutePage } from "./pages/3_LocationCommutePage";
import { CarProfilePage } from "./pages/4_CarProfilePage";
import { MobilityStackPage } from "./pages/5_MobilityStackPage";
import { PrioritiesPage } from "./pages/7_PrioritiesPage";
import { IntegrationsPage } from "./pages/8_IntegrationsPage";
import { NotesPage } from "./pages/9_NotesPage";
import { FinalPage } from "./pages/10_FinalPage";
import type { OnboardingPreferences } from "./types";

const initialPreferences: OnboardingPreferences = {
  personal: {
    full_name: "",
    employment_status: "employed",
    profession: "",
    household_context: "",
  },
  location: { home_city: "" },
  commute: {
    wfh_days: ["mon", "fri"],
    office_days: ["tue", "wed", "thu"],
  },
  car: {
    owns_car: false,
    fuel_type: null,
    efficiency: null,
    efficiency_unit: null,
    monthly_km_estimate: null,
  },
  subscriptions: [],
  priorities: {
    cost: 1 / 3,
    time: 1 / 3,
    sustainability: 1 / 3,
  },
  integrations: {
    outlook_connected: false,
    gmail_connected: false,
    calendar_connected: false,
    db_connected: false,
    miles_connected: false,
    deutschlandticket_connected: false,
  },
  notes: "",
};

const stepSkipDefaults: Partial<Record<number, Partial<OnboardingPreferences>>> = {
  2: {
    personal: {
      full_name: "",
      employment_status: "employed",
      profession: "",
      household_context: "",
    },
  },
  3: {
    location: { home_city: "" },
    commute: { wfh_days: ["mon", "fri"], office_days: ["tue", "wed", "thu"] },
  },
  4: {
    car: {
      owns_car: false,
      fuel_type: null,
      efficiency: null,
      efficiency_unit: null,
      monthly_km_estimate: null,
    },
  },
  5: {
    integrations: {
      outlook_connected: false,
      gmail_connected: false,
      calendar_connected: false,
      db_connected: false,
      miles_connected: false,
      deutschlandticket_connected: false,
    },
  },
  6: { subscriptions: [] },
  7: {
    priorities: {
      cost: 1 / 3,
      time: 1 / 3,
      sustainability: 1 / 3,
    },
  },
  8: { notes: "" },
};

const totalSteps = 10;

function buildExportJson(p: OnboardingPreferences) {
  return {
    personal: p.personal,
    location: p.location,
    commute: p.commute,
    car: p.car,
    subscriptions: p.subscriptions,
    preferences: {
      priorities: p.priorities,
      notes: p.notes,
    },
    integrations: p.integrations,
  };
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function App() {
  const [step, setStep] = useState(0);
  const [preferences, setPreferences] =
    useState<OnboardingPreferences>(initialPreferences);

  const goBack = () => setStep((s) => Math.max(s - 1, 0));
  const goNext = () => setStep((s) => Math.min(s + 1, totalSteps - 1));

  const handleSkip = () => {
    const defaults = stepSkipDefaults[step];
    if (defaults) {
      setPreferences((current) => ({ ...current, ...defaults }));
    }
    goNext();
  };

  useEffect(() => {
    if (step !== 0) return;
    const timer = window.setTimeout(() => setStep(1), 2600);
    return () => window.clearTimeout(timer);
  }, [step]);

  if (step === 0) {
    return <LogoIntroPage />;
  }

  const showSkipButton = step >= 2 && step <= 8;

  return (
    <div className="min-h-screen flex flex-col bg-[#f5f5f3]">
      <ProgressBar step={step} total={totalSteps} />

      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          <img
            src="/assets/db-logo.svg"
            className="h-5 w-8 object-contain block"
            alt=""
          />
          <span className="font-bold text-sm">Mobility Advisor</span>
          <span className="ml-auto text-xs text-gray-400">
            {step} / {totalSteps - 1}
          </span>
        </div>
      </header>

      <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-8 flex flex-col gap-4">
        {showSkipButton && <SkipButton onSkip={handleSkip} />}

        {step === 1 && <AgentIntroPage />}

        {step === 2 && (
          <PersonalProfilePage
            profile={preferences.personal}
            onChange={(personal) =>
              setPreferences((c) => ({ ...c, personal }))
            }
          />
        )}

        {step === 3 && (
          <LocationCommutePage
            homeCity={preferences.location.home_city}
            commute={preferences.commute}
            onCityChange={(home_city) =>
              setPreferences((c) => ({
                ...c,
                location: { home_city },
              }))
            }
            onCommuteChange={(commute) =>
              setPreferences((c) => ({ ...c, commute }))
            }
          />
        )}

        {step === 4 && (
          <CarProfilePage
            car={preferences.car}
            onChange={(car) => setPreferences((c) => ({ ...c, car }))}
          />
        )}

        {step === 5 && (
          <IntegrationsPage
            integrations={preferences.integrations}
            onChange={(integrations) =>
              setPreferences((c) => ({ ...c, integrations }))
            }
          />
        )}

        {step === 6 && (
          <MobilityStackPage
            subscriptions={preferences.subscriptions}
            onChange={(subscriptions) =>
              setPreferences((c) => ({ ...c, subscriptions }))
            }
          />
        )}

        {step === 7 && (
          <PrioritiesPage
            priorities={preferences.priorities}
            onChange={(priorities) =>
              setPreferences((c) => ({ ...c, priorities }))
            }
          />
        )}

        {step === 8 && (
          <NotesPage
            notes={preferences.notes}
            onChange={(notes) => setPreferences((c) => ({ ...c, notes }))}
          />
        )}

        {step === 9 && (
          <FinalPage
            onDownload={() =>
              downloadJson("user_profile.json", buildExportJson(preferences))
            }
          />
        )}
      </main>

      <footer
        className={`max-w-2xl mx-auto w-full px-4 pb-8 flex gap-3 ${
          step > 1 ? "justify-between" : "justify-end"
        }`}
      >
        {step > 1 && (
          <button
            type="button"
            onClick={goBack}
            aria-label="Back"
            className="h-[52px] w-[52px] rounded-full bg-white border border-gray-200 flex items-center justify-center hover:bg-gray-50 cursor-pointer flex-shrink-0"
          >
            <span className="nav-arrow nav-arrow-dark nav-arrow-back" aria-hidden="true" />
          </button>
        )}
        {step < totalSteps - 1 && (
          <button
            type="button"
            onClick={goNext}
            aria-label="Continue"
            className="h-[52px] w-[52px] rounded-full bg-brand-red flex items-center justify-center hover:opacity-90 cursor-pointer border-0 flex-shrink-0"
          >
            <span className="nav-arrow nav-arrow-white" aria-hidden="true" />
          </button>
        )}
      </footer>
    </div>
  );
}

export default App;
