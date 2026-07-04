import { useState } from "react";
import type { Integrations } from "../types";

type IntegrationsPageProps = {
  integrations: Integrations;
  onChange: (integrations: Integrations) => void;
};

const MOBILITY_SERVICES: {
  key: keyof Integrations;
  label: string;
  description: string;
}[] = [
  {
    key: "db_connected",
    label: "Deutsche Bahn",
    description: "Import BahnCard, Sparpreise and trip history from your DB account",
  },
  {
    key: "miles_connected",
    label: "MILES Mobility",
    description: "Import your MILES membership tier and trip history",
  },
  {
    key: "deutschlandticket_connected",
    label: "Deutschlandticket",
    description: "Confirm your active D-Ticket subscription and renewal date",
  },
];

const EMAIL_SERVICES: {
  key: keyof Integrations;
  label: string;
  description: string;
}[] = [
  {
    key: "outlook_connected",
    label: "Outlook",
    description: "Scan booking confirmations and subscription receipts",
  },
  {
    key: "gmail_connected",
    label: "Gmail",
    description: "Scan booking confirmations and subscription receipts",
  },
  {
    key: "calendar_connected",
    label: "Google Calendar",
    description: "Detect commute patterns and upcoming travel demand",
  },
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
        {connected ? "Connected ✓" : "Connect"}
      </button>
    </div>
  );
}

export function IntegrationsPage({
  integrations,
  onChange,
}: IntegrationsPageProps) {
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
          Connect your accounts
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          Connect your mobility and email accounts so we can detect your active
          subscriptions and travel history automatically.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">
            Mobility accounts
          </h2>
          {mobilityCount > 0 && (
            <span className="text-xs text-brand-red font-semibold">
              {mobilityCount} connected
            </span>
          )}
        </div>
        <div className="flex flex-col gap-3">
          {MOBILITY_SERVICES.map(({ key, label, description }) => (
            <ServiceRow
              key={key}
              label={label}
              description={description}
              connected={!!integrations[key]}
              onToggle={() => toggle(key)}
            />
          ))}
        </div>

        {/* More providers — interactive pills */}
        <div className="mt-1 p-3 rounded-lg border border-dashed border-gray-200 bg-white">
          <p className="text-xs text-gray-500 mb-2 font-medium">More providers</p>
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
          Email & calendar
        </h2>
        <div className="flex flex-col gap-3">
          {EMAIL_SERVICES.map(({ key, label, description }) => (
            <ServiceRow
              key={key}
              label={label}
              description={description}
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
                Connect {PROVIDER_FULL_NAMES[confirmingProvider] ?? confirmingProvider}?
              </p>
              <p className="text-sm text-gray-500 mt-1 m-0">
                Link your {PROVIDER_FULL_NAMES[confirmingProvider] ?? confirmingProvider} account to import ticket and trip data.
              </p>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setConfirmingProvider(null)}
                className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 bg-transparent border border-gray-200 rounded-full cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => connectProvider(confirmingProvider)}
                className="px-4 py-2 text-sm font-semibold bg-brand-red text-white rounded-full border-0 cursor-pointer hover:opacity-90"
              >
                Connect ✓
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
