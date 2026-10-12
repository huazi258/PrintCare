import type { QueryHistoryItem, QueryRequest } from "@/types/api";
import type { QaMessage } from "@/types/qa";

export const QA_SESSION_STORAGE_KEY = "printcare.qa.session_id";

export function buildQaRequest(query: string, sessionId?: string): QueryRequest {
  return {
    query,
    session_id: sessionId,
    is_stream: true,
    device_id: "creality-k1",
    mode: "qa",
  };
}

export function historyToQaMessages(items: QueryHistoryItem[]): QaMessage[] {
  return items.flatMap((item, index) => {
    if ((item.role !== "user" && item.role !== "assistant") || !item.text.trim()) {
      return [];
    }

    return [{
      id: item._id || `history-${index}`,
      role: item.role,
      content: item.text,
    }];
  });
}

export function appendAssistantDelta(
  messages: QaMessage[],
  assistantMessageId: string,
  delta: string,
): QaMessage[] {
  if (!delta) return messages;
  return messages.map((message) => (
    message.id === assistantMessageId
      ? { ...message, content: `${message.content}${delta}` }
      : message
  ));
}

export function replaceAssistantAnswer(
  messages: QaMessage[],
  assistantMessageId: string,
  answer: string,
): QaMessage[] {
  return messages.map((message) => (
    message.id === assistantMessageId ? { ...message, content: answer } : message
  ));
}
