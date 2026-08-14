import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";

type ProfileDropdownProps = {
  name: string;
  tagline: string;
  avatarBg: string;
  onEditPreferences: () => void;
  onEditProfile: () => void;
  onMobilityModes: () => void;
  onEditConnections: () => void;
  onRedoOnboarding: () => void;
  onSwitchProfile: () => void;
};

function DropdownItem({
  label,
  sublabel,
  onClick,
}: {
  label: string;
  sublabel?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left hover:bg-gray-50 cursor-pointer border-0 bg-transparent transition-colors text-ink"
    >
      <span className="flex-1">
        <span className="block font-medium leading-snug">{label}</span>
        {sublabel && <span className="block text-xs text-gray-400 mt-0.5">{sublabel}</span>}
      </span>
    </button>
  );
}

export function ProfileDropdown({
  name,
  tagline,
  avatarBg,
  onEditPreferences,
  onEditProfile,
  onMobilityModes,
  onEditConnections,
  onRedoOnboarding,
  onSwitchProfile,
}: ProfileDropdownProps) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const wrap = (fn: () => void) => () => { setOpen(false); fn(); };

  const initials = name
    .split(" ")
    .map((n) => n[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={t("profileDropdown.profileAndSettings")}
        aria-label={t("profileDropdown.profileAndSettings")}
        aria-expanded={open}
        aria-haspopup="true"
        className="h-8 w-8 rounded-full text-white text-xs font-bold flex items-center justify-center cursor-pointer hover:brightness-110 active:scale-95 transition-[filter,transform] duration-150"
        style={{ backgroundColor: avatarBg }}
      >
        {initials}
      </button>

      {open && (
        <div className="pop-in absolute right-0 top-10 w-60 bg-white rounded-xl shadow-pop border border-gray-100 z-50 overflow-hidden">
          {/* Persona header — non-interactive */}
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="font-semibold text-sm text-ink m-0 truncate">{name}</p>
            <p className="text-xs text-gray-500 m-0 mt-0.5 truncate">{tagline}</p>
          </div>

          {/* Preference & profile actions */}
          <div className="py-1">
            <DropdownItem
              label={t("profileDropdown.editPreferences.label")}
              sublabel={t("profileDropdown.editPreferences.sublabel")}
              onClick={wrap(onEditPreferences)}
            />
            <DropdownItem
              label={t("profileDropdown.editProfile.label")}
              sublabel={t("profileDropdown.editProfile.sublabel")}
              onClick={wrap(onEditProfile)}
            />
            <DropdownItem
              label={t("profileDropdown.mobilityModes.label")}
              sublabel={t("profileDropdown.mobilityModes.sublabel")}
              onClick={wrap(onMobilityModes)}
            />
            <DropdownItem
              label={t("profileDropdown.connections.label")}
              sublabel={t("profileDropdown.connections.sublabel")}
              onClick={wrap(onEditConnections)}
            />
            <DropdownItem
              label={t("profileDropdown.redoOnboarding.label")}
              sublabel={t("profileDropdown.redoOnboarding.sublabel")}
              onClick={wrap(onRedoOnboarding)}
            />
          </div>

          {/* Switch profile */}
          <div className="border-t border-gray-100 py-1">
            <button
              type="button"
              onClick={wrap(onSwitchProfile)}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left hover:bg-gray-50 cursor-pointer border-0 bg-transparent transition-colors text-gray-500"
            >
              {t("profileDropdown.switchProfile")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
