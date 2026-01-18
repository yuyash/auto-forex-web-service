# Generated migration for renaming OandaAccount to OandaAccounts

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0013_rename_oanda_api_h_account_fbf8a3_idx_oanda_api_h_account_b788ad_idx_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='OandaAccount',
            new_name='OandaAccounts',
        ),
    ]
