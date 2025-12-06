/**
 * Gateway API service for connecting to Solace Agent Mesh WebUI Gateway.
 * Uses JSON-RPC 2.0 format for message sending and SSE for streaming responses.
 */

const API_BASE = '/api/v1';

interface SendMessageResponse {
  id: string;
  jsonrpc: string;
  result: {
    id: string;  // task_id
    contextId?: string;
    status?: {
      state: string;
    };
  };
}

class GatewayAPI {
  private requestId = 0;

  /**
   * Generate unique request ID
   */
  private getNextId(): string {
    return `req-${Date.now()}-${++this.requestId}`;
  }

  /**
   * Check if the gateway is available
   */
  async checkHealth(): Promise<boolean> {
    try {
      const response = await fetch('/health', { method: 'GET' });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Send a message to the orchestrator and stream the response
   */
  async sendMessage(
    content: string,
    onChunk: (text: string) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): Promise<void> {
    try {
      // Check gateway health first
      const isHealthy = await this.checkHealth();
      if (!isHealthy) {
        throw new Error(
          'Gateway is not available. Please ensure the WebUI gateway is running:\n' +
          'sam run configs/gateways/webui.yaml'
        );
      }

      const requestId = this.getNextId();
      const messageId = `msg-${Date.now()}`;

      // Send the message using JSON-RPC 2.0 format
      const response = await fetch(`${API_BASE}/message:send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: requestId,
          jsonrpc: '2.0',
          method: 'message/send',
          params: {
            message: {
              messageId: messageId,
              role: 'user',
              parts: [{ kind: 'text', text: content }],
              metadata: {
                agent_name: 'HealthCounselorOrchestrator',
              },
            },
          },
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to send message: ${response.status} - ${errorText}`);
      }

      const result: SendMessageResponse = await response.json();

      // Extract task ID from the response
      const taskId = result.result?.id;
      if (!taskId) {
        throw new Error('No task ID returned from gateway');
      }

      // Connect to SSE stream for response
      await this.streamResponse(taskId, onChunk, onComplete, onError);
    } catch (error) {
      onError(error instanceof Error ? error : new Error(String(error)));
    }
  }

  /**
   * Stream response from task events via SSE
   */
  private async streamResponse(
    taskId: string,
    onChunk: (text: string) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): Promise<void> {
    const eventSource = new EventSource(`${API_BASE}/sse/subscribe/${taskId}`);
    let fullResponse = '';
    let completed = false;

    const cleanup = () => {
      if (!completed) {
        completed = true;
        eventSource.close();
      }
    };

    // Helper to extract text from message parts
    const extractText = (parts: Array<{ kind: string; text?: string }>) => {
      for (const part of parts) {
        if (part.kind === 'text' && part.text) {
          fullResponse = part.text; // Replace with full text (not streaming)
          onChunk(fullResponse);
        }
      }
    };

    // Handle the final_response event (primary event type from gateway)
    eventSource.addEventListener('final_response', (event) => {
      try {
        const data = JSON.parse(event.data);
        const state = data.result?.status?.state;

        if (state === 'completed') {
          // Extract response text from status.message.parts
          const messageParts = data.result?.status?.message?.parts;
          if (messageParts) {
            extractText(messageParts);
          }
          cleanup();
          onComplete();
        } else if (state === 'failed') {
          cleanup();
          const errorText = data.result?.status?.message?.parts?.[0]?.text || 'Task failed';
          onError(new Error(errorText));
        }
      } catch {
        // Ignore parse errors
      }
    });

    // Handle streaming artifact events (for longer responses)
    eventSource.addEventListener('task_artifact', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.artifact?.parts) {
          for (const part of data.artifact.parts) {
            if (part.kind === 'text' && part.text) {
              fullResponse += part.text;
              onChunk(fullResponse);
            }
          }
        }
      } catch {
        // Ignore parse errors
      }
    });

    // Handle task status updates
    eventSource.addEventListener('task_status', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status?.state === 'completed') {
          // If we already have response from artifacts, just complete
          if (fullResponse) {
            cleanup();
            onComplete();
          }
        } else if (data.status?.state === 'failed') {
          cleanup();
          onError(new Error(data.status?.message?.parts?.[0]?.text || 'Task failed'));
        }
      } catch {
        // Ignore parse errors
      }
    });

    // Generic message handler for any other event types
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle message parts in various locations
        if (data.result?.status?.message?.parts) {
          extractText(data.result.status.message.parts);
        } else if (data.message?.parts) {
          extractText(data.message.parts);
        }
      } catch {
        // Ignore JSON parse errors for non-JSON events
      }
    };

    eventSource.onerror = () => {
      cleanup();
      // Only call onComplete if we got some response
      if (fullResponse) {
        onComplete();
      } else {
        onError(new Error('Connection to gateway lost. Is the gateway running on port 8000?'));
      }
    };
  }
}

export const gatewayApi = new GatewayAPI();
