import { ProfileDropdown } from "./ProfileDropdown";

type AppShellProps = {
  personaName: string;
  personaTagline: string;
  avatarBg: string;
  onBack?: () => void;
  onChatOpen: () => void;
  onEditPreferences: () => void;
  onEditProfile: () => void;
  onMobilityModes: () => void;
  onEditConnections: () => void;
  onRedoOnboarding: () => void;
  onSwitchProfile: () => void;
  children: React.ReactNode;
};

export function AppShell({
  personaName,
  personaTagline,
  avatarBg,
  onBack,
  onChatOpen,
  onEditPreferences,
  onEditProfile,
  onMobilityModes,
  onEditConnections,
  onRedoOnboarding,
  onSwitchProfile,
  children,
}: AppShellProps) {
  return (
    <div className="min-h-screen flex flex-col bg-[#f5f5f3]">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              aria-label="Back"
              className="h-8 w-8 rounded-full border border-gray-200 bg-white hover:bg-gray-50 flex items-center justify-center cursor-pointer flex-shrink-0 transition-colors"
            >
              <span className="nav-arrow nav-arrow-dark nav-arrow-back" aria-hidden="true" />
            </button>
          ) : (
            <img src="/assets/db-logo.svg" className="h-5 w-8 object-contain block flex-shrink-0" alt="" />
          )}
          <span className="font-bold text-sm">Mobility Advisor</span>
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={onChatOpen}
              title="Open chat"
              className="h-8 w-8 rounded-full border border-gray-200 bg-white hover:bg-gray-50 flex items-center justify-center cursor-pointer text-gray-500 transition-colors"
              aria-label="Open chat"
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

      <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-6">
        {children}
      </main>
    </div>
  );
}
