// Deliberately has no <LanguageSwitcher> — this is a ~2.6s auto-advancing splash
// (see App.tsx's onboardingStep === 0 handling) with no header of its own, and every other
// onboarding/login/main screen already carries the switcher, so a language choice made just
// before or after this splash is never more than one screen away.
export function LogoIntroPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      <div
        className="logo-animation bg-brand-red rounded-lg flex items-center justify-center overflow-hidden"
        style={{ width: 160, height: 120 }}
        aria-label="DB Mobility Advisor"
      >
        <object
          className="w-full h-full"
          data="/assets/db-logo.svg"
          type="image/svg+xml"
        >
          <span>DB</span>
        </object>
      </div>
    </div>
  );
}
