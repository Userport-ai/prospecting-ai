export enum ParsingStatus {
  NOT_STARTED = 'not_started',
  FETCHED_ACTIVITY_BUTTONS = 'fetched_activity_buttons',
  COMPLETE = 'complete',
  FAILED = 'failed',
}

// State we are storing per Tab during activity parsing.
export interface ActivityData {
  status: ParsingStatus;
  url: string;
  last_status: ParsingStatus | null;
  error?: string;
}
