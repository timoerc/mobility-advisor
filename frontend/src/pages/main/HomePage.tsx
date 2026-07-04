type HomePageProps = {
  onChat: () => void;
  onAnalysis: () => void;
};

type ActionCardProps = {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  onClick?: () => void;
  disabled?: boolean;
};

function ActionCard({ icon, title, subtitle, onClick, disabled }: ActionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`w-full flex items-center gap-4 bg-white border border-gray-200 rounded-xl px-5 py-5 text-left transition-all cursor-pointer
        ${disabled
          ? "opacity-40 cursor-not-allowed"
          : "hover:border-brand-red hover:shadow-sm active:scale-[0.99]"
        }`}
    >
      <div className="w-12 h-12 rounded-xl bg-[#f5f5f3] flex items-center justify-center flex-shrink-0 text-gray-700">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-base text-gray-900 m-0">{title}</p>
        <p className="text-sm text-gray-500 m-0 mt-0.5">{subtitle}</p>
      </div>
      {!disabled && (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gray-400 flex-shrink-0">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      )}
    </button>
  );
}

export function HomePage({ onChat, onAnalysis }: HomePageProps) {
  return (
    <div className="flex flex-col gap-6 py-4">
      <div>
        <h1 className="text-2xl font-bold leading-tight mb-1">Welcome back</h1>
        <p className="text-gray-500 text-sm m-0">What would you like to do today?</p>
      </div>

      <div className="flex flex-col gap-3">
        <ActionCard
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          }
          title="Chat"
          subtitle="Ask me anything about your trips, costs, and subscriptions."
          onClick={onChat}
        />

        <ActionCard
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          }
          title="Start Analysis"
          subtitle="Run a full analysis of your mobility portfolio."
          onClick={onAnalysis}
        />

        <ActionCard
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          }
          title="Generate Annual Report"
          subtitle="Coming soon"
          disabled
        />
      </div>
    </div>
  );
}
