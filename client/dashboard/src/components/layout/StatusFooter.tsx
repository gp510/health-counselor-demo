import type { SystemStatus } from '../../types/health';

interface StatusFooterProps {
  status: SystemStatus | null;
  loading?: boolean;
}

export function StatusFooter({ status, loading }: StatusFooterProps) {
  const formatTime = (timestamp: string | null) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <footer className="flex-shrink-0 bg-bg-secondary border-t border-bg-hover px-6 py-3">
      <div className="flex items-center justify-between text-sm">
        {/* Left Side - Connection Status */}
        <div className="flex items-center gap-6">
          {/* Broker Status */}
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                status?.brokerConnected
                  ? 'bg-health-excellent animate-pulse'
                  : 'bg-health-critical'
              }`}
            />
            <span className="text-text-secondary">
              Broker: {status?.brokerConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Agents Online */}
          <div className="flex items-center gap-2">
            <span className="text-text-muted">🤖</span>
            <span className="text-text-secondary">
              {loading ? '--' : status?.agentsOnline ?? 0} Agents Online
            </span>
          </div>
        </div>

        {/* Right Side - Last Sync */}
        <div className="flex items-center gap-2 text-text-muted">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>Last sync: {loading ? '--' : formatTime(status?.lastSyncTime ?? null)}</span>
        </div>
      </div>
    </footer>
  );
}
