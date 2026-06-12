import { useEffect, useState } from "react";
import "./App.css";
import { ProgressDots } from "./components/ProgressDots";
import { LogoIntroPage } from "./pages/0_LogoIntroPage";
import { AgentIntroPage } from "./pages/1_AgentIntroPage";
import { PrioritiesPage } from "./pages/2_PrioritiesPage";
import { MobilityOptionsPage } from "./pages/3_MobilityOptionsPage";
import { FlexibilityPage } from "./pages/4_FlexibilityPage";
import { NotesPage } from "./pages/5_NotesPage";
import { FinalPage } from "./pages/6_FinalPage";
import type { OnboardingPreferences } from "./types";

const initialPreferences: OnboardingPreferences = {
  priorities: {
    money: 0.5,
    time: 0.5,
    sustainability: 0.5,
  },
  flexibility: 0.5,
  mobility_options: {
    owns_bike: false,
    owns_car: false,
  },
  notes: "",
};

const totalSteps = 7;

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
      <section className="onboarding-panel">
        <header className={step === 0 ? "app-header hidden-header" : "app-header"}>
          <p className="eyebrow">DB Mobility Advisor</p>
          <ProgressDots currentStep={step} totalSteps={totalSteps} />
        </header>

        {step === 0 && <LogoIntroPage onSkip={goNext} />}

        {step === 1 && <AgentIntroPage />}

        {step === 2 && (
          <PrioritiesPage
            priorities={preferences.priorities}
            onChange={(priorities) =>
              setPreferences((current) => ({ ...current, priorities }))
            }
          />
        )}

        {step === 3 && (
          <MobilityOptionsPage
            mobilityOptions={preferences.mobility_options}
            onChange={(mobility_options) =>
              setPreferences((current) => ({ ...current, mobility_options }))
            }
          />
        )}

        {step === 4 && (
          <FlexibilityPage
            flexibility={preferences.flexibility}
            onChange={(flexibility) =>
              setPreferences((current) => ({ ...current, flexibility }))
            }
          />
        )}

        {step === 5 && (
          <NotesPage
            notes={preferences.notes}
            onChange={(notes) =>
              setPreferences((current) => ({ ...current, notes }))
            }
          />
        )}

        {step === 6 && <FinalPage />}

        <footer className={step === 0 ? "button-row hidden-footer" : "button-row"}>
          <button
            className="secondary-button"
            type="button"
            onClick={goBack}
            disabled={step <= 1}
          >
            Back
          </button>
          {step < totalSteps - 1 ? (
            <button className="primary-button" type="button" onClick={goNext}>
              Continue
            </button>
          ) : (
            <button className="primary-button" type="button">
              Finish
            </button>
          )}
        </footer>
      </section>
    </main>
  );
}

export default App;
