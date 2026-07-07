import { useEffect, useState } from "react";
import { PersonaCard } from "../../components/PersonaCard";
import type { Persona } from "../../personas";

type PseudoLoginPageProps = {
  personas: Persona[];
  onSelect: (id: string) => void;
  onBack?: () => void;
};

export function PseudoLoginPage({ personas, onSelect, onBack }: PseudoLoginPageProps) {
  const [logoVisible, setLogoVisible] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setLogoVisible(true), 80);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div className="min-h-screen bg-[#f5f5f3] flex flex-col items-center px-4 py-12">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          aria-label="Back"
          className="self-start mb-4 h-9 w-9 rounded-full border border-gray-200 bg-white hover:bg-gray-50 flex items-center justify-center cursor-pointer transition-colors flex-shrink-0"
        >
          <span className="nav-arrow nav-arrow-dark nav-arrow-back" aria-hidden="true" />
        </button>
      )}
      <div
        className="flex flex-col items-center gap-2 mb-10 transition-all duration-500"
        style={{ opacity: logoVisible ? 1 : 0, transform: logoVisible ? "translateY(0)" : "translateY(-8px)" }}
      >
        <div className="bg-brand-red rounded-lg flex items-center justify-center" style={{ width: 72, height: 52 }}>
          <object className="w-full h-full" data="/assets/db-logo.svg" type="image/svg+xml">
            <span className="text-white font-bold">DB</span>
          </object>
        </div>
        <h1 className="text-xl font-semibold text-[#1f1f1f] mt-4 m-0">Select a profile to continue</h1>
        <p className="text-sm text-gray-500 m-0">Demo mode — no real authentication</p>
      </div>

      <div className="w-full max-w-md flex flex-col gap-3">
        {personas.map((persona) => (
          <PersonaCard key={persona.id} persona={persona} onSelect={onSelect} />
        ))}

        <button
          type="button"
          onClick={() => onSelect("new")}
          className="w-full text-left bg-white rounded-2xl border-2 border-dashed border-gray-300 p-5 flex items-center gap-4 hover:border-brand-red transition-colors cursor-pointer group"
        >
          <div className="w-14 h-14 rounded-full flex items-center justify-center bg-gray-100 text-gray-400 text-2xl font-light flex-shrink-0">
            +
          </div>
          <div>
            <p className="font-semibold text-gray-500 m-0">Add new profile</p>
            <p className="text-sm text-gray-400 m-0 mt-0.5">Start fresh with empty data</p>
          </div>
        </button>
      </div>

      <p className="text-xs text-gray-400 mt-12 text-center max-w-xs">
        BCG × Deutsche Bahn university project prototype. No data is stored outside your browser.
      </p>
    </div>
  );
}
