import { useState, type KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Ask about your health...',
}: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    const trimmed = input.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex items-end gap-2 p-3 border-t border-bg-hover bg-bg-secondary">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className="flex-1 bg-bg-card border border-bg-hover rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder-text-muted resize-none focus:outline-none focus:border-domain-mental transition-colors disabled:opacity-50"
        style={{ minHeight: '44px', maxHeight: '120px' }}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !input.trim()}
        className="flex-shrink-0 w-11 h-11 bg-domain-mental hover:bg-domain-mental/80 disabled:bg-bg-hover disabled:text-text-muted text-white rounded-xl flex items-center justify-center transition-colors"
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
            d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
          />
        </svg>
      </button>
    </div>
  );
}
