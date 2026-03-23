from unittest.mock import MagicMock

from apps.market.services.accounts import (
    create_oanda_account,
    delete_oanda_account,
    update_oanda_account,
)


class TestMarketAccountService:
    def test_create_oanda_account_uses_serializer_save(self) -> None:
        serializer = MagicMock()
        account = MagicMock()
        serializer.save.return_value = account

        result = create_oanda_account(serializer)

        serializer.save.assert_called_once_with()
        assert result is account

    def test_update_oanda_account_uses_serializer_save(self) -> None:
        serializer = MagicMock()
        account = MagicMock()
        serializer.save.return_value = account

        result = update_oanda_account(serializer)

        serializer.save.assert_called_once_with()
        assert result is account

    def test_delete_oanda_account_uses_model_delete(self) -> None:
        account = MagicMock()

        delete_oanda_account(account)

        account.delete.assert_called_once_with()
