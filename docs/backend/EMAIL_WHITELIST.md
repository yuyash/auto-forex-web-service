# Email Whitelist Feature

## Overview

The email whitelist feature allows administrators to restrict user registration and login to specific email addresses or domains. When enabled, only users with whitelisted email addresses can register new accounts or login to existing accounts.

## Features

- **Exact Email Matching**: Whitelist specific email addresses (e.g., `user@example.com`)
- **Domain Wildcards**: Whitelist entire domains (e.g., `*@example.com` or `@example.com`)
- **Enable/Disable Control**: Toggle whitelist enforcement without deleting entries
- **Individual Entry Control**: Activate/deactivate specific whitelist entries
- **Admin Management**: Full CRUD operations for administrators

## Configuration

### Enable Email Whitelist

Administrators can enable/disable the email whitelist through the system settings:

**Endpoint**: `PUT /api/admin/system/settings`

**Request Body**:

```json
{
  "email_whitelist_enabled": true
}
```

**Response**:

```json
{
  "registration_enabled": true,
  "login_enabled": true,
  "email_whitelist_enabled": true,
  "updated_at": "2025-11-03T10:30:00.000Z"
}
```

### Check Whitelist Status (Public)

Anyone can check if the whitelist is enabled:

**Endpoint**: `GET /api/system/settings/public`

**Response**:

```json
{
  "registration_enabled": true,
  "login_enabled": true,
  "email_whitelist_enabled": true
}
```

## Managing Whitelisted Emails

### List All Whitelisted Emails

**Endpoint**: `GET /api/admin/whitelist/emails`

**Query Parameters**:

- `is_active` (optional): Filter by active status (`true` or `false`)

**Response**:

```json
[
  {
    "id": 1,
    "email_pattern": "admin@example.com",
    "description": "Admin email",
    "is_active": true,
    "created_at": "2025-11-03T10:00:00.000Z",
    "updated_at": "2025-11-03T10:00:00.000Z"
  },
  {
    "id": 2,
    "email_pattern": "*@company.com",
    "description": "All company employees",
    "is_active": true,
    "created_at": "2025-11-03T10:05:00.000Z",
    "updated_at": "2025-11-03T10:05:00.000Z"
  }
]
```

### Add Whitelisted Email

**Endpoint**: `POST /api/admin/whitelist/emails`

**Request Body**:

```json
{
  "email_pattern": "user@example.com",
  "description": "Specific user",
  "is_active": true
}
```

**Email Pattern Formats**:

- Exact email: `user@example.com`
- Domain wildcard: `*@example.com` or `@example.com`

**Response**:

```json
{
  "id": 3,
  "email_pattern": "user@example.com",
  "description": "Specific user",
  "is_active": true,
  "created_at": "2025-11-03T10:15:00.000Z",
  "updated_at": "2025-11-03T10:15:00.000Z"
}
```

### Get Whitelisted Email Details

**Endpoint**: `GET /api/admin/whitelist/emails/{id}`

**Response**:

```json
{
  "id": 1,
  "email_pattern": "admin@example.com",
  "description": "Admin email",
  "is_active": true,
  "created_at": "2025-11-03T10:00:00.000Z",
  "updated_at": "2025-11-03T10:00:00.000Z"
}
```

### Update Whitelisted Email

**Endpoint**: `PUT /api/admin/whitelist/emails/{id}`

**Request Body** (all fields optional):

```json
{
  "email_pattern": "newuser@example.com",
  "description": "Updated description",
  "is_active": false
}
```

**Response**:

```json
{
  "id": 1,
  "email_pattern": "newuser@example.com",
  "description": "Updated description",
  "is_active": false,
  "created_at": "2025-11-03T10:00:00.000Z",
  "updated_at": "2025-11-03T10:20:00.000Z"
}
```

### Delete Whitelisted Email

**Endpoint**: `DELETE /api/admin/whitelist/emails/{id}`

**Response**:

```json
{
  "message": "Whitelisted email deleted successfully."
}
```

## How It Works

### Registration Flow

1. User submits registration form with email address
2. System checks if `email_whitelist_enabled` is `true`
3. If enabled, system validates email against whitelist:
   - Checks for exact email match
   - Checks for domain wildcard match
4. If email is not whitelisted, registration is rejected with error:
   ```json
   {
     "email": [
       "This email address is not authorized to register. Please contact the administrator."
     ]
   }
   ```

### Login Flow

1. User submits login credentials
2. System checks if `email_whitelist_enabled` is `true`
3. If enabled, system validates email against whitelist before authentication
4. If email is not whitelisted, login is rejected with error:
   ```json
   {
     "non_field_errors": [
       "This email address is not authorized to login. Please contact the administrator."
     ]
   }
   ```

## Whitelist Matching Logic

The system supports two types of patterns:

### 1. Exact Email Match

- Pattern: `user@example.com`
- Matches: `user@example.com` only
- Case-insensitive

### 2. Domain Wildcard

- Pattern: `*@example.com` or `@example.com`
- Matches: Any email with `@example.com` domain
- Examples: `john@example.com`, `jane@example.com`, `admin@example.com`
- Case-insensitive

## Best Practices

1. **Start with Domain Wildcards**: Use `*@company.com` to allow all company employees
2. **Add Specific Emails**: Add individual emails for external partners or contractors
3. **Use Descriptions**: Add clear descriptions to track why each entry was added
4. **Deactivate Instead of Delete**: Use `is_active: false` to temporarily disable entries
5. **Test Before Enabling**: Add whitelist entries first, then enable the feature
6. **Monitor Logs**: Check logs for rejected registration/login attempts

## Security Considerations

- Only administrators can manage the whitelist
- Whitelist checks happen before authentication to prevent information disclosure
- All whitelist operations are logged for audit purposes
- Email patterns are case-insensitive and trimmed of whitespace
- Invalid patterns are rejected during creation/update

## Example Use Cases

### 1. Company-Only Access

```json
{
  "email_pattern": "*@company.com",
  "description": "All company employees",
  "is_active": true
}
```

### 2. Multiple Domains

```json
[
  {
    "email_pattern": "*@company.com",
    "description": "Main company domain"
  },
  {
    "email_pattern": "*@subsidiary.com",
    "description": "Subsidiary company"
  }
]
```

### 3. Specific Users + Domain

```json
[
  {
    "email_pattern": "*@company.com",
    "description": "All employees"
  },
  {
    "email_pattern": "partner@external.com",
    "description": "External partner"
  },
  {
    "email_pattern": "consultant@freelance.com",
    "description": "Consultant"
  }
]
```

## Troubleshooting

### Users Can't Register/Login

1. Check if whitelist is enabled:

   ```bash
   GET /api/system/settings/public
   ```

2. Verify email is whitelisted:

   ```bash
   GET /api/admin/whitelist/emails
   ```

3. Check if entry is active:

   - Ensure `is_active: true` for the matching entry

4. Verify pattern format:
   - Exact: `user@example.com`
   - Domain: `*@example.com` or `@example.com`

### Whitelist Not Working

1. Ensure `email_whitelist_enabled: true` in system settings
2. Check that at least one active whitelist entry exists
3. Verify email pattern matches the format (case-insensitive)
4. Check application logs for validation errors

## Database Schema

### SystemSettings Table

```sql
ALTER TABLE system_settings
ADD COLUMN email_whitelist_enabled BOOLEAN DEFAULT FALSE;
```

### WhitelistedEmail Table

```sql
CREATE TABLE whitelisted_emails (
    id BIGSERIAL PRIMARY KEY,
    email_pattern VARCHAR(255) UNIQUE NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE,
    created_by_id BIGINT REFERENCES users(id),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_whitelisted_emails_pattern ON whitelisted_emails(email_pattern);
CREATE INDEX idx_whitelisted_emails_active ON whitelisted_emails(is_active);
```

## API Permissions

All whitelist management endpoints require:

- Authentication: Valid JWT token
- Authorization: Admin user (`is_staff: true`)

Public endpoints:

- `GET /api/system/settings/public` - No authentication required
