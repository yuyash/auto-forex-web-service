"""Add AccountSecurityEvent model.

Generated manually for this repo.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_notifications"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountSecurityEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        db_index=True,
                        help_text="Type of event (e.g., login_success, login_failed, logout)",
                        max_length=100,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        db_index=True,
                        default="security",
                        help_text="Event category; defaults to 'security' for auth/security events",
                        max_length=50,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("debug", "Debug"),
                            ("info", "Info"),
                            ("warning", "Warning"),
                            ("error", "Error"),
                            ("critical", "Critical"),
                        ],
                        db_index=True,
                        default="info",
                        help_text="Severity level",
                        max_length=20,
                    ),
                ),
                (
                    "description",
                    models.TextField(help_text="Human-readable event description"),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(
                        blank=True,
                        help_text="IP address associated with the event",
                        null=True,
                    ),
                ),
                (
                    "user_agent",
                    models.TextField(
                        blank=True,
                        help_text="User agent string (if available)",
                        null=True,
                    ),
                ),
                (
                    "details",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Additional structured event details",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        help_text="Timestamp when the event was created",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        help_text="Associated user (if known)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="security_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Account Security Event",
                "verbose_name_plural": "Account Security Events",
                "db_table": "account_security_events",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="accountsecurityevent",
            index=models.Index(
                fields=["event_type", "created_at"], name="account_secur_event_ty_6c54b1_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="accountsecurityevent",
            index=models.Index(
                fields=["category", "created_at"], name="account_secur_categor_582846_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="accountsecurityevent",
            index=models.Index(
                fields=["severity", "created_at"], name="account_secur_severit_04e69d_idx"
            ),
        ),
    ]
