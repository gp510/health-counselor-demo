import { useState } from 'react';
import Markdown from 'react-markdown';
import type { HealthInsight } from '../../types/health';
import { healthApi } from '../../services/healthApi';

interface ExecutiveSummaryCardProps {
  className?: string;
}

export function ExecutiveSummaryCard({ className = '' }: ExecutiveSummaryCardProps) {
  const [insight, setInsight] = useState<HealthInsight | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await healthApi.getExecutiveSummary();
      setInsight(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate summary');
    } finally {
      setLoading(false);
    }
  };

  const formatTimestamp = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  return (
    <div className={`bg-bg-card rounded-xl p-5 border border-accent-primary/20 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🩺</span>
          <h3 className="text-lg font-semibold text-text-primary">Health Counselor Summary</h3>
        </div>
        {!loading && (
          <button
            onClick={generateSummary}
            className="px-3 py-1.5 text-sm font-medium bg-accent-primary/20 hover:bg-accent-primary/30 text-accent-primary rounded-lg transition-colors"
          >
            {insight ? 'Refresh' : 'Generate Summary'}
          </button>
        )}
      </div>

      {/* Content Area */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-10">
          {/* Pulsing Health Orb */}
          <div className="relative mb-6">
            {/* Outer pulse rings */}
            <div className="absolute inset-0 w-20 h-20 -m-4 rounded-full bg-accent-primary/20 animate-ping" style={{ animationDuration: '2s' }}></div>
            <div className="absolute inset-0 w-20 h-20 -m-4 rounded-full bg-accent-primary/10 animate-ping" style={{ animationDuration: '2s', animationDelay: '0.5s' }}></div>

            {/* Core orb with heartbeat */}
            <div className="relative w-12 h-12 rounded-full bg-gradient-to-br from-accent-primary to-accent-primary/60 flex items-center justify-center shadow-lg shadow-accent-primary/30 animate-pulse">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
              </svg>
            </div>
          </div>

          {/* Animated Domain Icons */}
          <div className="flex items-center gap-4 mb-5">
            {[
              { icon: '🧬', label: 'Biomarkers', delay: '0s' },
              { icon: '🏃', label: 'Fitness', delay: '0.3s' },
              { icon: '🥗', label: 'Nutrition', delay: '0.6s' },
              { icon: '🧘', label: 'Wellness', delay: '0.9s' },
            ].map((domain, i) => (
              <div
                key={i}
                className="flex flex-col items-center animate-pulse"
                style={{ animationDelay: domain.delay, animationDuration: '1.5s' }}
              >
                <span className="text-2xl mb-1">{domain.icon}</span>
                <span className="text-[10px] text-text-muted">{domain.label}</span>
              </div>
            ))}
          </div>

          {/* Status Text */}
          <p className="text-text-secondary text-sm font-medium">Consulting health agents...</p>
          <p className="text-text-muted text-xs mt-1">Synthesizing insights from all domains</p>

          {/* Progress bar shimmer */}
          <div className="w-48 h-1 mt-4 rounded-full bg-bg-hover overflow-hidden">
            <div className="h-full w-1/3 rounded-full bg-gradient-to-r from-transparent via-accent-primary to-transparent animate-shimmer"></div>
          </div>
        </div>
      ) : error ? (
        <div className="bg-health-critical/10 border border-health-critical/30 rounded-lg p-4">
          <p className="text-health-critical font-medium">Unable to generate summary</p>
          <p className="text-sm text-text-secondary mt-1">{error}</p>
          <button
            onClick={generateSummary}
            className="mt-3 px-3 py-1 text-sm bg-health-critical/20 hover:bg-health-critical/30 rounded transition-colors"
          >
            Try Again
          </button>
        </div>
      ) : insight ? (
        <div>
          {/* Timestamp */}
          <div className="flex items-center gap-2 mb-4 text-xs text-text-muted">
            <span>Generated {formatTimestamp(insight.generated_at)}</span>
          </div>

          {/* Markdown Content */}
          <div className="prose prose-invert prose-sm max-w-none">
            <Markdown
              components={{
                h2: ({ children }) => (
                  <h2 className="text-base font-semibold text-text-primary mt-4 mb-2 first:mt-0">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm font-medium text-text-primary mt-3 mb-1">
                    {children}
                  </h3>
                ),
                p: ({ children }) => (
                  <p className="text-sm text-text-secondary mb-2 leading-relaxed">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside space-y-1 text-sm text-text-secondary mb-3">
                    {children}
                  </ul>
                ),
                li: ({ children }) => (
                  <li className="text-sm text-text-secondary">{children}</li>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-text-primary">{children}</strong>
                ),
              }}
            >
              {insight.content}
            </Markdown>
          </div>
        </div>
      ) : (
        <div className="text-center py-8">
          <p className="text-text-secondary text-sm">
            Get an AI-powered analysis of your health trends across all domains.
          </p>
          <p className="text-text-muted text-xs mt-2">
            The Health Counselor will analyze your biomarkers, fitness, nutrition, and mental wellness data.
          </p>
        </div>
      )}
    </div>
  );
}
