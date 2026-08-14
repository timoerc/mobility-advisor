import { useEffect, useState } from "react";
import { PersonaCard } from "../../components/PersonaCard";
import { LanguageSwitcher } from "../../components/LanguageSwitcher";
import { useT } from "../../i18n";
import type { Persona } from "../../personas";

type PseudoLoginPageProps = {
  personas: Persona[];
  onSelect: (id: string) => void;
  onBack?: () => void;
};

export function PseudoLoginPage({ personas, onSelect, onBack }: PseudoLoginPageProps) {
  const t = useT();
  const [logoVisible, setLogoVisible] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setLogoVisible(true), 80);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div className="relative min-h-screen bg-canvas flex flex-col items-center px-4 py-12">
      {/* This page has no shared header (see AppShell/App.tsx's onboarding+editing headers), so
          the switcher is positioned independently rather than folded into one. */}
      <LanguageSwitcher className="absolute top-4 right-4 z-10" />
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          aria-label={t("common.back")}
          className="self-start mb-4 h-9 w-9 rounded-full border border-gray-200 bg-white hover:bg-gray-50 hover:border-gray-300 hover:shadow-card active:scale-95 flex items-center justify-center cursor-pointer flex-shrink-0 transition-[background-color,border-color,box-shadow,transform] duration-150 ease-soft"
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
        <h1 className="text-xl font-semibold text-ink mt-4 m-0">{t("login.selectProfile")}</h1>
        <p className="text-sm text-gray-500 m-0">{t("login.demoMode")}</p>
      </div>

      <div className="w-full max-w-md flex flex-col gap-3">
        {personas.map((persona) => (
          <PersonaCard key={persona.id} persona={persona} onSelect={onSelect} />
        ))}

        <button
          type="button"
          onClick={() => onSelect("new")}
          className="w-full text-left bg-white rounded-2xl border-2 border-dashed border-gray-300 p-5 flex items-center gap-4 hover:border-brand-red hover:shadow-lift hover:-translate-y-0.5 active:translate-y-0 transition-[border-color,box-shadow,transform] duration-200 ease-soft cursor-pointer group"
        >
          <div className="w-14 h-14 rounded-full flex items-center justify-center bg-gray-100 text-gray-400 text-2xl font-light flex-shrink-0">
            +
          </div>
          <div>
            <p className="font-semibold text-gray-500 m-0">{t("login.addNewProfile")}</p>
            <p className="text-sm text-gray-400 m-0 mt-0.5">{t("login.startFresh")}</p>
          </div>
        </button>
      </div>

      <p className="text-xs text-gray-400 mt-12 text-center max-w-xs">
        {t("login.disclaimer")}
      </p>
    </div>
  );
}
