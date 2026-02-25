"""Merge conflicting trading migration branches.

This merge resolves the split graph between:
- 0003_fix_trading_task_status_check_constraint
- 0005_merge_20260225_0608
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0003_fix_trading_task_status_check_constraint"),
        ("trading", "0005_merge_20260225_0608"),
    ]

    operations = []
