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
