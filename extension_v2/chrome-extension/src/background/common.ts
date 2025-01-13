export enum ActivityParsingStatus {
  IN_PROGRESS = 'in_progress',
  COMPLETE = 'complete',
  FAILED = 'failed',
}

// State we are storing per Tab during activity parsing.
export interface ActivityData {
  status: ActivityParsingStatus;
  url: string;
  last_status: ActivityParsingStatus | null;
  error?: string;
  parsed_data?: {
    posts_html?: string | null;
    comments_html?: string | null;
    reactions_html?: string | null;
  };
}
