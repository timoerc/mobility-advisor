import { useEffect, useState } from "react";
import "./App.css";
import { ProgressDots } from "./components/ProgressDots";
import { LogoIntroPage } from "./pages/0_LogoIntroPage";
import { AgentIntroPage } from "./pages/1_AgentIntroPage";
import { BudgetPage } from "./pages/2_BudgetPage";
import { RankedPrioritiesPage } from "./pages/3_RankedPrioritiesPage";
import { MobilityOptionsPage } from "./pages/4_MobilityOptionsPage";
import { FlexibilityPage } from "./pages/5_FlexibilityPage";
import { NotesPage } from "./pages/6_NotesPage";
import { FinalPage } from "./pages/7_FinalPage";
import type { OnboardingPreferences } from "./types";

const initialPreferences: OnboardingPreferences = {
  monthly_budget_eur: 100,
  priorities: {
    money: 0.333,
    time: 0.333,
    sustainability: 0.334,
  },
  flexibility: 0.5,
  mobility_options: {
    owns_bike: false,
    owns_car: false,
  },
  notes: "",
};

const totalSteps = 8;

function App() {
  const [step, setStep] = useState(0);
  const [preferences, setPreferences] =
    useState<OnboardingPreferences>(initialPreferences);

  const goBack = () => setStep((currentStep) => Math.max(currentStep - 1, 0));
  const goNext = () =>
    setStep((currentStep) => Math.min(currentStep + 1, totalSteps - 1));

  useEffect(() => {
    if (step !== 0) {
      return;
    }

    const introTimer = window.setTimeout(() => {
      setStep(1);
    }, 2600);

    return () => window.clearTimeout(introTimer);
  }, [step]);

  return (
    <main className="app-shell">
      <div className="phone-frame">
        <div className="phone-speaker" aria-hidden="true" />
        <section className="onboarding-panel">
          <header className={step === 0 ? "app-header hidden-header" : "app-header"}>
            <div className="brand-mark" aria-label="DB Mobility Advisor">
              <img src="/assets/db-logo.svg" alt="" />
              <span>Mobility Advisor</span>
            </div>
            <ProgressDots currentStep={step} totalSteps={totalSteps} />
          </header>

          {step === 0 && <LogoIntroPage />}

          {step === 1 && <AgentIntroPage />}

          {step === 2 && (
            <BudgetPage
              monthlyBudgetEur={preferences.monthly_budget_eur}
              onChange={(monthly_budget_eur) =>
                setPreferences((current) => ({ ...current, monthly_budget_eur }))
              }
            />
          )}

          {step === 3 && <RankedPrioritiesPage />}

          {step === 4 && (
            <MobilityOptionsPage
              mobilityOptions={preferences.mobility_options}
              onChange={(mobility_options) =>
                setPreferences((current) => ({ ...current, mobility_options }))
              }
            />
          )}

          {step === 5 && (
            <FlexibilityPage
              flexibility={preferences.flexibility}
              onChange={(flexibility) =>
                setPreferences((current) => ({ ...current, flexibility }))
              }
            />
          )}

          {step === 6 && (
            <NotesPage
              notes={preferences.notes}
              onChange={(notes) =>
                setPreferences((current) => ({ ...current, notes }))
              }
            />
          )}

          {step === 7 && <FinalPage />}

          <footer className={step <= 1 ? "button-row single-button-row" : "button-row"}>
            {step > 1 && (
              <button
                className="secondary-button"
                type="button"
                onClick={goBack}
                aria-label="Back"
              >
                <span className="nav-arrow nav-arrow-left" aria-hidden="true" />
              </button>
            )}
            {step < totalSteps - 1 ? (
              <button
                className="primary-button"
                type="button"
                onClick={goNext}
                aria-label="Continue"
              >
                <span className="nav-arrow" aria-hidden="true" />
              </button>
            ) : (
              <button className="primary-button" type="button" aria-label="Finish">
                <span className="nav-arrow" aria-hidden="true" />
              </button>
            )}
          </footer>
        </section>
      </div>
    </main>
  );
}

export default App;
