from __future__ import annotations

from hashlib import sha256

from django.db import migrations


def is_sha256_digest(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def hash_existing_refresh_tokens(apps, schema_editor) -> None:
    RefreshToken = apps.get_model("accounts", "RefreshToken")

    for token_row in RefreshToken.objects.all().iterator():
        token_value = (token_row.token or "").strip()
        if not token_value or is_sha256_digest(token_value):
            continue

        token_row.token = sha256(token_value.encode("utf-8")).hexdigest()
        token_row.save(update_fields=["token"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_remove_usersession_last_activity"),
    ]

    operations = [
        migrations.RunPython(hash_existing_refresh_tokens, migrations.RunPython.noop),
    ]
