export enum EnrichmentType {
  COMPANY_INFO = "company_info",
  GENERATE_LEADS = "generate_leads",
}

export enum EnrichmentStatusEnum {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
}

// Recent company event.
export interface RecentCompanyEvent {
  date: string;
  title: string;
  source: string;
  description: string;
}

export interface EnrichmentStatusDetail {
  enrichment_type: EnrichmentType;
  status: EnrichmentStatusEnum;
  completion_percent: number | null;
}

// Account Enrichment status as set by the backend.
export interface EnrichmentStatus {
  total_enrichments: number;
  completed: number;
  failed: number;
  in_progress: number;
  pending: number;
  last_update: string; // ISO Date string.
  quality_score: number | null;
  avg_completion_percent: number | null;
  statuses: EnrichmentStatusDetail[] | null;
}

export const USERPORT_TENANT_ID = "34410fcc-83bf-4006-b7d3-fedfe0472afb";
