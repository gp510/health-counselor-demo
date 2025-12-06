import { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage as ChatMessageType } from '../../types/health';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { gatewayApi } from '../../services/gatewayApi';

interface ChatPanelProps {
  className?: string;
}

// Suggested prompts for quick access
const suggestedPrompts = [
  "How's my sleep this week?",
  "Summarize my fitness trends",
  "Am I meeting nutrition goals?",
  "How's my stress level?",
];

export function ChatPanel({ className = '' }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(async (content: string) => {
    // Add user message
    const userMessage: ChatMessageType = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    // Create placeholder for assistant message that will be updated as chunks arrive
    const assistantMessageId = `assistant-${Date.now()}`;

    try {
      // Add initial empty assistant message
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString(),
        },
      ]);

      // Send message and stream response from gateway
      await gatewayApi.sendMessage(
        content,
        // onChunk - update the assistant message with streaming content
        (text: string) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId ? { ...msg, content: text } : msg
            )
          );
        },
        // onComplete
        () => {
          setIsLoading(false);
        },
        // onError
        (error: Error) => {
          console.error('Failed to send message:', error);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
                  }
                : msg
            )
          );
          setIsLoading(false);
        }
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: 'Sorry, I encountered an error processing your request. Please try again.',
              }
            : msg
        )
      );
      setIsLoading(false);
    }
  }, []);

  return (
    <div className={`flex flex-col bg-bg-card ${className}`}>
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-bg-hover">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-domain-mental/20 rounded-lg flex items-center justify-center">
            <span>💬</span>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Health Assistant</h3>
            <p className="text-xs text-text-muted">Ask about your health data</p>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <span className="text-4xl mb-3">🏥</span>
            <h4 className="text-sm font-medium text-text-primary mb-1">
              Health Counselor
            </h4>
            <p className="text-xs text-text-muted mb-4">
              Ask questions about your biomarkers, fitness, diet, or mental wellness
            </p>

            {/* Suggested Prompts */}
            <div className="space-y-2 w-full">
              {suggestedPrompts.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(prompt)}
                  className="w-full text-left px-3 py-2 bg-bg-hover hover:bg-bg-secondary rounded-lg text-xs text-text-secondary hover:text-text-primary transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isLoading && (
              <div className="flex items-center gap-2 text-text-muted text-sm">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-domain-mental rounded-full animate-bounce" />
                  <span
                    className="w-2 h-2 bg-domain-mental rounded-full animate-bounce"
                    style={{ animationDelay: '0.1s' }}
                  />
                  <span
                    className="w-2 h-2 bg-domain-mental rounded-full animate-bounce"
                    style={{ animationDelay: '0.2s' }}
                  />
                </div>
                <span>Analyzing...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
