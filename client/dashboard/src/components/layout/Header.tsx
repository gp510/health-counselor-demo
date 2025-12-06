interface HeaderProps {
  onRefresh?: () => void;
  refreshing?: boolean;
}

export function Header({ onRefresh, refreshing }: HeaderProps) {
  return (
    <header className="flex-shrink-0 bg-bg-secondary border-b border-bg-hover px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Logo & Title */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-domain-mental to-domain-fitness rounded-xl flex items-center justify-center">
            <span className="text-2xl">🏥</span>
          </div>
          <div>
            <h1 className="text-xl font-bold text-text-primary">Health Counselor</h1>
            <p className="text-xs text-text-muted">Holistic Health Dashboard</p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className={`p-2 rounded-lg hover:bg-bg-hover transition-colors text-text-secondary hover:text-text-primary ${
              refreshing ? 'animate-spin' : ''
            }`}
            title="Refresh data"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>

          {/* User Avatar */}
          <div className="w-9 h-9 bg-bg-hover rounded-full flex items-center justify-center text-text-secondary">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
          </div>
        </div>
      </div>
    </header>
  );
}
