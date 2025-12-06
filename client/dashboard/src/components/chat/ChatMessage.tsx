import type { ChatMessage as ChatMessageType } from '../../types/health';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
          isUser
            ? 'bg-domain-mental text-white rounded-br-md'
            : 'bg-bg-hover text-text-primary rounded-bl-md'
        }`}
      >
        {/* Avatar for assistant */}
        {!isUser && (
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm">🏥</span>
            <span className="text-xs font-medium text-text-secondary">Health Counselor</span>
          </div>
        )}

        {/* Message content */}
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>

        {/* Timestamp */}
        <p
          className={`text-xs mt-1 ${
            isUser ? 'text-white/60' : 'text-text-muted'
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </div>
  );
}
