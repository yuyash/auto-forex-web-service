/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for TradingEvent model.
 */
export type TradingEvent = {
  readonly id?: number;
  event_type: string;
  severity?: string;
  description: string;
  user?: number | null;
  account?: number | null;
  instrument?: string | null;
  task_type?: string;
  task_id?: string | null;
  /**
   * Celery task ID for tracking specific execution
   */
  celery_task_id?: string | null;
  details?: any;
  readonly created_at?: string;
};
