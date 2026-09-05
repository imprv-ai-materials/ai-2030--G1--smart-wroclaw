/**
 * Typed client for citizen issue reports and the specialist HITL review queue.
 *
 * Citizens submit reports (`POST /reports`); triage runs asynchronously and
 * moves a report to `PENDING_REVIEW`. A city specialist then reviews the AI
 * triage and APPROVE/REJECTs it (`/specialist/reports/{id}/review`).
 */

import { api } from "@/lib/api-client";

export type ReportCategory =
  | "WATER"
  | "ROADS"
  | "WASTE"
  | "GREENERY"
  | "LIGHTING"
  | "PUBLIC_TRANSPORT"
  | "OTHER";

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ReportStatus =
  | "SUBMITTED"
  | "TRIAGING"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "PUBLISHED"
  | "FAILED";

export type ReviewDecision = "APPROVE" | "REJECT";

/** AI triage attached to a report once triage has run. */
export type Triage = {
  category: ReportCategory;
  severity: Severity;
  department: string;
  summary: string;
  suggested_response: string;
  is_duplicate: boolean;
  confidence: number;
};

export type IssueReport = {
  id: number;
  citizen_id: number;
  title: string;
  description: string;
  category: ReportCategory | null;
  location_text: string | null;
  lat: number | null;
  lng: number | null;
  status: ReportStatus;
  severity: Severity | null;
  department: string | null;
  triage: Triage | null;
  public_response: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateReportInput = {
  title: string;
  description: string;
  category?: ReportCategory;
  location_text?: string;
  lat?: number;
  lng?: number;
};

export type ReviewInput = {
  decision: ReviewDecision;
  edited_category?: ReportCategory;
  edited_severity?: Severity;
  edited_department?: string;
  public_response?: string;
  comment?: string;
};

// -- Polish display labels ---------------------------------------------------

export const CATEGORY_LABELS: Record<ReportCategory, string> = {
  WATER: "Woda i kanalizacja",
  ROADS: "Drogi i chodniki",
  WASTE: "Odpady i czystość",
  GREENERY: "Zieleń miejska",
  LIGHTING: "Oświetlenie",
  PUBLIC_TRANSPORT: "Transport publiczny",
  OTHER: "Inne",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  LOW: "Niski",
  MEDIUM: "Średni",
  HIGH: "Wysoki",
  CRITICAL: "Krytyczny",
};

export const STATUS_LABELS: Record<ReportStatus, string> = {
  SUBMITTED: "Przyjęte",
  TRIAGING: "Analiza AI",
  PENDING_REVIEW: "Oczekuje na weryfikację",
  APPROVED: "Zatwierdzone",
  REJECTED: "Odrzucone",
  PUBLISHED: "Opublikowane",
  FAILED: "Błąd",
};

export const CATEGORY_OPTIONS = Object.keys(CATEGORY_LABELS) as ReportCategory[];
export const SEVERITY_OPTIONS = Object.keys(SEVERITY_LABELS) as Severity[];

export const reportsApi = {
  // -- Citizen ---------------------------------------------------------------
  createReport: (body: CreateReportInput) => api.post<IssueReport>("/reports", body),
  listReports: () => api.get<{ reports: IssueReport[] }>("/reports"),
  getReport: (id: number) => api.get<IssueReport>(`/reports/${id}`),

  // -- Specialist (HITL) -----------------------------------------------------
  listPendingReports: (status: ReportStatus = "PENDING_REVIEW") =>
    api.get<{ reports: IssueReport[] }>(`/specialist/reports?status=${status}`, {
      specialist: true,
    }),
  getSpecialistReport: (id: number) =>
    api.get<IssueReport>(`/specialist/reports/${id}`, { specialist: true }),
  reviewReport: (id: number, body: ReviewInput) =>
    api.post<IssueReport>(`/specialist/reports/${id}/review`, body, {
      specialist: true,
    }),
};
