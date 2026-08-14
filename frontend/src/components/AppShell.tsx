import { ProfileDropdown } from "./ProfileDropdown";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { useT } from "../i18n";
import { BTN_ICON } from "../ui";

type AppShellProps = {
  personaName: string;
  personaTagline: string;
  avatarBg: string;
  onBack?: () => void;
  onLogoClick?: () => void;
  onChatOpen: () => void;
  onEditPreferences: () => void;
  onEditProfile: () => void;
  onMobilityModes: () => void;
  onEditConnections: () => void;
  onRedoOnboarding: () => void;
  onSwitchProfile: () => void;
  // When true, the header + content use a wider max-width so a multi-column view (the home
  // dashboard) can spread horizontally. Other views keep the narrow single-column reading width.
  wide?: boolean;
  children: React.ReactNode;
};

export function AppShell({
  personaName,
  personaTagline,
  avatarBg,
  onBack,
  onLogoClick,
  onChatOpen,
  onEditPreferences,
  onEditProfile,
  onMobilityModes,
  onEditConnections,
  onRedoOnboarding,
  onSwitchProfile,
  wide = false,
  children,
}: AppShellProps) {
  const t = useT();
  const widthClass = wide ? "max-w-6xl" : "max-w-2xl";
  return (
    <div className="min-h-screen flex flex-col bg-canvas">
      <header className="bg-white/80 backdrop-blur-md border-b border-hairline sticky top-0 z-10">
        <div className={`${widthClass} mx-auto px-4 py-3 flex items-center gap-3`}>
          {onBack ? (
            <>
              <button
                type="button"
                onClick={onBack}
                aria-label={t("common.back")}
                className={BTN_ICON}
              >
                <span className="nav-arrow nav-arrow-dark nav-arrow-back" aria-hidden="true" />
              </button>
              <span className="font-bold text-sm">{t("nav.appName")}</span>
            </>
          ) : onLogoClick ? (
            <button
              type="button"
              onClick={onLogoClick}
              aria-label={t("nav.home")}
              className="flex items-center gap-3 border-0 bg-transparent cursor-pointer p-0"
            >
              <img src="/assets/db-logo.svg" className="h-5 w-8 object-contain block flex-shrink-0" alt="" />
              <span className="font-bold text-sm">{t("nav.appName")}</span>
            </button>
          ) : (
            <>
              <img src="/assets/db-logo.svg" className="h-5 w-8 object-contain block flex-shrink-0" alt="" />
              <span className="font-bold text-sm">{t("nav.appName")}</span>
            </>
          )}
          <div className="ml-auto flex items-center gap-2">
            <LanguageSwitcher />
            <button
              type="button"
              onClick={onChatOpen}
              title={t("nav.openChat")}
              className={BTN_ICON}
              aria-label={t("nav.openChat")}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </button>
            <ProfileDropdown
              name={personaName}
              tagline={personaTagline}
              avatarBg={avatarBg}
              onEditPreferences={onEditPreferences}
              onEditProfile={onEditProfile}
              onMobilityModes={onMobilityModes}
              onEditConnections={onEditConnections}
              onRedoOnboarding={onRedoOnboarding}
              onSwitchProfile={onSwitchProfile}
            />
          </div>
        </div>
      </header>

      <main className={`flex-1 ${widthClass} mx-auto w-full px-4 py-6`}>
        {children}
      </main>
    </div>
  );
}
