export type QaMessageRole = "user" | "assistant";

export interface QaSource {
  sourceId: string;
  title?: string;
  sectionTitle?: string;
  type: "local" | "web";
  excerpt?: string;
  href?: string;
}

export interface QaMessage {
  id: string;
  role: QaMessageRole;
  content: string;
  sources?: QaSource[];
}
