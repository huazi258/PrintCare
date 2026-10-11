import { apiClient, type RequestOptions } from "@/services/http";
import type {
  DiagnosisEndRequest,
  DiagnosisFeedbackRequest,
  DiagnosisListResponse,
  DiagnosisSession,
  ImportTaskStatus,
  QueryRequest,
  QueryResponse,
  StreamSubmitResponse,
  TaskStatus,
  UploadResponse,
} from "@/types/api";

export const printCareApi = {
  getCoreOpenApi: (options?: RequestOptions) =>
    apiClient.get<Record<string, unknown>>("core", "/openapi.json", options),
  getAdminOpenApi: (options?: RequestOptions) =>
    apiClient.get<Record<string, unknown>>("admin", "/openapi.json", options),

  submitQuery: (payload: QueryRequest, options?: RequestOptions) =>
    apiClient.post<QueryResponse | StreamSubmitResponse>("core", "/query", payload, options),
  getQueryStatus: (taskId: string, options?: RequestOptions) =>
    apiClient.get<TaskStatus>("core", `/status/${encodeURIComponent(taskId)}`, options),
  getQueryHistory: (sessionId: string, options?: RequestOptions) =>
    apiClient.get<{ session_id: string; items: unknown[] }>(
      "core",
      `/history/${encodeURIComponent(sessionId)}`,
      options,
    ),
  clearQueryHistory: (sessionId: string, options?: RequestOptions) =>
    apiClient.delete<{ message: string; deleted_count: number }>(
      "core",
      `/history/${encodeURIComponent(sessionId)}`,
      options,
    ),

  listDiagnoses: (options?: RequestOptions) =>
    apiClient.get<DiagnosisListResponse>("core", "/diagnoses", options),
  getDiagnosis: (diagnosisId: string, options?: RequestOptions) =>
    apiClient.get<DiagnosisSession>("core", `/diagnoses/${encodeURIComponent(diagnosisId)}`, options),
  submitDiagnosisFeedback: (
    diagnosisId: string,
    payload: DiagnosisFeedbackRequest,
    options?: RequestOptions,
  ) =>
    apiClient.post<DiagnosisSession>(
      "core",
      `/diagnoses/${encodeURIComponent(diagnosisId)}/feedback`,
      payload,
      options,
    ),
  endDiagnosis: (diagnosisId: string, payload: DiagnosisEndRequest, options?: RequestOptions) =>
    apiClient.post<DiagnosisSession>(
      "core",
      `/diagnoses/${encodeURIComponent(diagnosisId)}/end`,
      payload,
      options,
    ),
  deleteDiagnosis: (diagnosisId: string, options?: RequestOptions) =>
    apiClient.delete<{ message: string; diagnosis_id: string }>(
      "core",
      `/diagnoses/${encodeURIComponent(diagnosisId)}`,
      options,
    ),

  uploadDocument: (file: File, deviceId: string, options?: RequestOptions) => {
    const formData = new FormData();
    formData.set("device_id", deviceId);
    formData.set("file", file);
    return apiClient.post<UploadResponse>("admin", "/upload", formData, options);
  },
  getImportStatus: (taskId: string, options?: RequestOptions) =>
    apiClient.get<ImportTaskStatus>("admin", `/status/${encodeURIComponent(taskId)}`, options),
};
