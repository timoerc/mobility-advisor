import type { Persona } from "../personas";

type PersonaCardProps = {
  persona: Persona;
  onSelect: (id: string) => void;
};

export function PersonaCard({ persona, onSelect }: PersonaCardProps) {
  const isNew = persona.id === "new";

  return (
    <button
      type="button"
      onClick={() => onSelect(persona.id)}
      className="w-full text-left bg-white rounded-2xl border-2 border-gray-200 p-5 flex items-center gap-4 hover:border-brand-red transition-colors cursor-pointer group"
    >
      <div
        className="w-14 h-14 rounded-full flex items-center justify-center text-white font-bold text-lg flex-shrink-0 transition-opacity group-hover:opacity-90"
        style={{ backgroundColor: isNew ? "#e5e7eb" : persona.avatarBg }}
      >
        <span style={{ color: isNew ? "#9ca3af" : "white" }}>{persona.avatar}</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-[#1f1f1f] m-0 leading-snug">{persona.name}</p>
        <p className="text-sm text-gray-500 m-0 mt-0.5 leading-snug">{persona.tagline}</p>
        {persona.onboardingComplete && (
          <span className="inline-block mt-1.5 text-xs bg-green-50 text-green-700 border border-green-200 rounded-full px-2 py-0.5 font-medium">
            Profile complete
          </span>
        )}
      </div>
      <span className="nav-arrow nav-arrow-dark opacity-30 group-hover:opacity-70 transition-opacity flex-shrink-0" aria-hidden="true" />
    </button>
  );
}
