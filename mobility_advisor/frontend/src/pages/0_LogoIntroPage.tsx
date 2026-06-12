type LogoIntroPageProps = {
  onSkip: () => void;
};

export function LogoIntroPage({ onSkip }: LogoIntroPageProps) {
  return (
    <div className="page-content logo-intro-page">
      <button className="skip-button" type="button" onClick={onSkip}>
        Skip
      </button>

      <div className="logo-animation" aria-label="DB Mobility Advisor">
        <object
          className="logo-image"
          data="/assets/db-logo.svg"
          type="image/svg+xml"
        >
          <span>DB</span>
        </object>
      </div>
    </div>
  );
}
