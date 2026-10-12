import type { QueryHistoryItem, QueryRequest } from "@/types/api";
import type { QaMessage } from "@/types/qa";

export const QA_SESSION_STORAGE_KEY = "printcare.qa.session_id";
export const QA_SESSION_INDEX_STORAGE_KEY = "printcare.qa.session_index";

export type QaSessionIndexEntry = {
  sessionId: string;
  createdAt: number;
  updatedAt: number;
};

export function parseQaSessionIndex(value: string | null): QaSessionIndexEntry[] {
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.flatMap((entry) => {
      if (
        typeof entry !== "object" || entry === null
        || !("sessionId" in entry) || typeof entry.sessionId !== "string" || !entry.sessionId.trim()
        || !("createdAt" in entry) || typeof entry.createdAt !== "number"
        || !("updatedAt" in entry) || typeof entry.updatedAt !== "number"
      ) return [];
      return [{ sessionId: entry.sessionId, createdAt: entry.createdAt, updatedAt: entry.updatedAt }];
    });
  } catch {
    return [];
  }
}

export function upsertQaSessionIndex(
  entries: QaSessionIndexEntry[],
  sessionId: string,
  now = Date.now(),
): QaSessionIndexEntry[] {
  const existing = entries.find((entry) => entry.sessionId === sessionId);
  const next = existing
    ? { ...existing, updatedAt: now }
    : { sessionId, createdAt: now, updatedAt: now };
  return [next, ...entries.filter((entry) => entry.sessionId !== sessionId)];
}

export function removeQaSessionIndex(entries: QaSessionIndexEntry[], sessionId: string): QaSessionIndexEntry[] {
  return entries.filter((entry) => entry.sessionId !== sessionId);
}

export function registerQaSession(sessionId: string): void {
  if (!sessionId.trim()) return;
  const entries = upsertQaSessionIndex(
    parseQaSessionIndex(window.localStorage.getItem(QA_SESSION_INDEX_STORAGE_KEY)),
    sessionId,
  );
  window.localStorage.setItem(QA_SESSION_INDEX_STORAGE_KEY, JSON.stringify(entries));
}

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
