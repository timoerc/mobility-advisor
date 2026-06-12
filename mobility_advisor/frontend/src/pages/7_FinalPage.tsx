import { TypewriterHeading } from "../components/TypewriterHeading";

export function FinalPage() {
  return (
    <div className="page-content final-page">
      <div className="success-mark" aria-hidden="true">
        ✓
      </div>

      <div>
        <TypewriterHeading text="Thank you!" />
        <p className="intro-text">
          I will now analyze your mobility portfolio and prepare personalized
          recommendations for your next trips.
        </p>
      </div>
    </div>
  );
}
