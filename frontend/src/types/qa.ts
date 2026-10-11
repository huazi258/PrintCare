export type QaMessageRole = "user" | "assistant";

export interface QaSource {
  title: string;
  type: "local" | "web";
  detail?: string;
  href?: string;
}

export interface QaMessage {
  id: string;
  role: QaMessageRole;
  content: string;
  sources?: QaSource[];
}
