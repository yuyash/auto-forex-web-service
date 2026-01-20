/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class NotificationsService {
  /**
   * GET /api/accounts/notifications
   * Retrieve list of notifications for the authenticated user. Supports filtering by read status and limiting results.
   * @param limit Maximum number of notifications to return (1-200, default: 50)
   * @param unreadOnly Filter to show only unread notifications
   * @returns any Notifications retrieved successfully
   * @throws ApiError
   */
  public static accountsNotificationsRetrieve(
    limit?: number,
    unreadOnly?: boolean
  ): CancelablePromise<
    Array<{
      id?: number;
      title?: string;
      message?: string;
      severity?: 'info' | 'warning' | 'error' | 'critical';
      timestamp?: string;
      read?: boolean;
      notification_type?: string;
      extra_data?: Record<string, any>;
    }>
  > {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/accounts/notifications',
      query: {
        limit: limit,
        unread_only: unreadOnly,
      },
      errors: {
        401: `Authentication required`,
        500: `Failed to retrieve notifications`,
      },
    });
  }
  /**
   * POST /api/accounts/notifications/{notification_id}/read
   * Mark a single notification as read for the authenticated user.
   * @param notificationId ID of the notification to mark as read
   * @returns any Notification marked as read
   * @throws ApiError
   */
  public static accountsNotificationsReadCreate(
    notificationId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/notifications/{notification_id}/read',
      path: {
        notification_id: notificationId,
      },
      errors: {
        401: `Authentication required`,
        404: `Notification not found`,
        500: `Failed to mark notification as read`,
      },
    });
  }
  /**
   * POST /api/accounts/notifications/read-all
   * Mark all unread notifications as read for the authenticated user.
   * @returns any All notifications marked as read
   * @throws ApiError
   */
  public static accountsNotificationsReadAllCreate(): CancelablePromise<{
    message?: string;
    count?: number;
  }> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/notifications/read-all',
      errors: {
        401: `Authentication required`,
        500: `Failed to mark all notifications as read`,
      },
    });
  }
}
