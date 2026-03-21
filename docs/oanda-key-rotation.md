# OANDA Token Key Rotation Runbook

This runbook covers safe rotation of `OANDA_TOKEN_ENCRYPTION_KEY` for stored OANDA API tokens.

## Preconditions

- Confirm the new key is a valid Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

- Ensure you can update backend, celery, and celery-beat environment variables in the same rollout window.
- Take a database backup before rotating keys.

## Standard Rotation

1. Generate a new Fernet key.
2. Set `OANDA_TOKEN_ENCRYPTION_KEY` to the new key.
3. Move the previous primary key into `OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS`.
4. Deploy backend, celery, and celery-beat together.
5. Verify that existing OANDA accounts can still be read and that newly saved tokens remain valid.

Example environment change:

```env
OANDA_TOKEN_ENCRYPTION_KEY=<new-primary-key>
OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS=<previous-primary-key>
```

## Re-encryption Pass

Fallback keys keep old ciphertext readable, but they do not rewrite existing rows. To complete the rotation:

1. Open each saved OANDA account in the application and resave the token, or run a one-off management command/script that loads and saves each encrypted token field.
2. Confirm the database no longer contains ciphertext encrypted with the fallback key.
3. Remove the fallback key from `OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS`.
4. Deploy the environment change again.

## Verification Checklist

- Existing OANDA account connections still authenticate successfully after deployment.
- Creating or updating an OANDA account stores a token that decrypts with the new primary key.
- No service is still running with the old environment after rollout.
- `OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS` is emptied after re-encryption completes.

## Rollback

If decryption failures appear after rollout:

1. Restore the previous value as `OANDA_TOKEN_ENCRYPTION_KEY`.
2. Move the failed new key into `OANDA_TOKEN_ENCRYPTION_FALLBACK_KEYS` only if rows may already have been rewritten with it.
3. Redeploy backend, celery, and celery-beat together.
4. Investigate the bad key material or partial rollout before attempting rotation again.
