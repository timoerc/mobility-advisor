import type { Integrations } from "../types";

type IntegrationsPageProps = {
  integrations: Integrations;
  onChange: (integrations: Integrations) => void;
};

const SERVICES: {
  key: keyof Integrations;
  label: string;
  description: string;
}[] = [
  {
    key: "outlook_connected",
    label: "Outlook",
    description: "Sync calendar events and travel bookings",
  },
  {
    key: "gmail_connected",
    label: "Gmail",
    description: "Read booking confirmations and receipts",
  },
  {
    key: "calendar_connected",
    label: "Google Calendar",
    description: "Detect commute patterns from calendar",
  },
];

export function IntegrationsPage({
  integrations,
  onChange,
}: IntegrationsPageProps) {
  // STUB — no real integration
  const toggle = (key: keyof Integrations) =>
    onChange({ ...integrations, [key]: !integrations[key] });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          Connect your accounts
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          Optional integrations let the advisor learn from your real travel
          patterns. You can skip this for now.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {SERVICES.map(({ key, label, description }) => {
          const connected = integrations[key];
          return (
            <div
              key={key}
              className="flex items-center gap-4 p-4 bg-white rounded-lg border border-gray-200"
            >
              <div className="flex-1">
                <p className="font-semibold text-sm m-0">{label}</p>
                <p className="text-xs text-gray-400 m-0">{description}</p>
              </div>
              <button
                type="button"
                onClick={() => toggle(key)}
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
        })}
      </div>

      <p className="text-xs text-gray-400 text-center">
        These are stubs — no data is actually sent anywhere.
      </p>
    </div>
  );
}
