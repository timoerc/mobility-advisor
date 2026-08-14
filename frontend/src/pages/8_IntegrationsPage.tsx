import { useState } from "react";
import { useI18n } from "../i18n";
import type { TranslationKey } from "../i18n";
import type { Integrations } from "../types";

type IntegrationsPageProps = {
  integrations: Integrations;
  onChange: (integrations: Integrations) => void;
};

// `label` is a brand name (Deutsche Bahn, MILES Mobility, ...) and is intentionally NOT
// translated — same reasoning as PROVIDER_FULL_NAMES below. Only `descriptionKey` is localized.
const MOBILITY_SERVICES: {
  key: keyof Integrations;
  label: string;
  descriptionKey: TranslationKey;
}[] = [
  { key: "db_connected", label: "Deutsche Bahn", descriptionKey: "onboarding.integrations.db.description" },
  { key: "miles_connected", label: "MILES Mobility", descriptionKey: "onboarding.integrations.miles.description" },
  { key: "deutschlandticket_connected", label: "Deutschlandticket", descriptionKey: "onboarding.integrations.dTicket.description" },
];

const EMAIL_SERVICES: {
  key: keyof Integrations;
  label: string;
  descriptionKey: TranslationKey;
}[] = [
  { key: "outlook_connected", label: "Outlook", descriptionKey: "onboarding.integrations.outlook.description" },
  { key: "gmail_connected", label: "Gmail", descriptionKey: "onboarding.integrations.gmail.description" },
  { key: "calendar_connected", label: "Google Calendar", descriptionKey: "onboarding.integrations.calendar.description" },
];

const MORE_PROVIDERS = [
  "BVG", "MVV", "HVV", "RMV", "KVB", "VVS",
  "Flinkster", "Stadtmobil", "ShareNow",
  "Nextbike", "Tier", "Lime", "Bolt", "FreeNow",
];

const PROVIDER_FULL_NAMES: Record<string, string> = {
  BVG: "Berliner Verkehrsbetriebe (BVG)",
  MVV: "Münchner Verkehrsgesellschaft (MVV)",
  HVV: "Hamburger Verkehrsverbund (HVV)",
  RMV: "Rhein-Main-Verkehrsverbund (RMV)",
  KVB: "Kölner Verkehrs-Betriebe (KVB)",
  VVS: "Verkehrs- und Tarifverbund Stuttgart (VVS)",
  Flinkster: "Flinkster",
  Stadtmobil: "Stadtmobil",
  ShareNow: "ShareNow",
  Nextbike: "Nextbike",
  Tier: "TIER Mobility",
  Lime: "Lime",
  Bolt: "Bolt",
  FreeNow: "FREE NOW",
};

function ServiceRow({
  label,
  description,
  connected,
  onToggle,
}: {
  label: string;
  description: string;
  connected: boolean;
  onToggle: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-4 p-4 bg-white rounded-lg border border-gray-200">
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm m-0">{label}</p>
        <p className="text-xs text-gray-400 m-0 leading-relaxed">{description}</p>
      </div>
      <button
        type="button"
        onClick={onToggle}
        className={`px-4 py-2 rounded-full text-sm font-semibold border-2 cursor-pointer transition-colors flex-shrink-0 ${
          connected
            ? "bg-brand-red border-brand-red text-white"
            : "bg-white border-gray-300 text-gray-600 hover:border-gray-400"
        }`}
      >
        {connected ? t("onboarding.integrations.connected") : t("onboarding.integrations.connect")}
      </button>
    </div>
  );
}

export function IntegrationsPage({
  integrations,
  onChange,
}: IntegrationsPageProps) {
  const { t, tPlural } = useI18n();
  const [confirmingProvider, setConfirmingProvider] = useState<string | null>(null);

  const toggle = (key: keyof Integrations) =>
    onChange({ ...integrations, [key]: !integrations[key] });

  const additionalConnections = integrations.additional_connections ?? [];

  const connectProvider = (name: string) => {
    onChange({
      ...integrations,
      additional_connections: [...additionalConnections, name],
    });
    setConfirmingProvider(null);
  };

  const disconnectProvider = (name: string) => {
    onChange({
      ...integrations,
      additional_connections: additionalConnections.filter((n) => n !== name),
    });
  };

  const mobilityCount = MOBILITY_SERVICES.filter(
    (s) => integrations[s.key]
  ).length;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          {t("onboarding.integrations.heading")}
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          {t("onboarding.integrations.subheading")}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">
            {t("onboarding.integrations.mobilityAccounts")}
          </h2>
          {mobilityCount > 0 && (
            <span className="text-xs text-brand-red font-semibold">
              {tPlural("onboarding.integrations.connectedCount", mobilityCount)}
            </span>
          )}
        </div>
        <div className="flex flex-col gap-3">
          {MOBILITY_SERVICES.map(({ key, label, descriptionKey }) => (
            <ServiceRow
              key={key}
              label={label}
              description={t(descriptionKey)}
              connected={!!integrations[key]}
              onToggle={() => toggle(key)}
            />
          ))}
        </div>

        {/* More providers — interactive pills */}
        <div className="mt-1 p-3 rounded-lg border border-dashed border-gray-200 bg-white">
          <p className="text-xs text-gray-500 mb-2 font-medium">{t("onboarding.integrations.moreProviders")}</p>
          <div className="flex flex-wrap gap-1.5">
            {MORE_PROVIDERS.map((name) => {
              const connected = additionalConnections.includes(name);
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() =>
                    connected ? disconnectProvider(name) : setConfirmingProvider(name)
                  }
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border cursor-pointer transition-colors ${
                    connected
                      ? "bg-brand-red border-brand-red text-white"
                      : "bg-gray-50 border-gray-200 text-gray-500 hover:border-gray-400 hover:text-gray-700"
                  }`}
                >
                  {connected ? `${name} ✓` : name}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">
          {t("onboarding.integrations.emailCalendar")}
        </h2>
        <div className="flex flex-col gap-3">
          {EMAIL_SERVICES.map(({ key, label, descriptionKey }) => (
            <ServiceRow
              key={key}
              label={label}
              description={t(descriptionKey)}
              connected={!!integrations[key]}
              onToggle={() => toggle(key)}
            />
          ))}
        </div>
      </div>

      {/* Connect confirmation dialog */}
      {confirmingProvider !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.25)" }}
          onClick={() => setConfirmingProvider(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-xs flex flex-col gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <p className="font-bold text-base m-0">
                {t("onboarding.integrations.confirmTitle", { provider: PROVIDER_FULL_NAMES[confirmingProvider] ?? confirmingProvider })}
              </p>
              <p className="text-sm text-gray-500 mt-1 m-0">
                {t("onboarding.integrations.confirmBody", { provider: PROVIDER_FULL_NAMES[confirmingProvider] ?? confirmingProvider })}
              </p>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setConfirmingProvider(null)}
                className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 bg-transparent border border-gray-200 rounded-full cursor-pointer"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={() => connectProvider(confirmingProvider)}
                className="px-4 py-2 text-sm font-semibold bg-brand-red text-white rounded-full border-0 cursor-pointer hover:opacity-90"
              >
                {t("onboarding.integrations.confirmConnect")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
