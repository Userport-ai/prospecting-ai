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
}

export const USERPORT_TENANT_ID = "34410fcc-83bf-4006-b7d3-fedfe0472afb";
