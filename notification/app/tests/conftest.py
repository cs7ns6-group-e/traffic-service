import pytest

from shared.auth import CurrentUser


@pytest.fixture
def mock_current_user():
    return CurrentUser(id="user-1", email="driver@test.com", name="Test Driver", roles=["driver"])


@pytest.fixture
def mock_settings():
    class FakeSettings:
        smtp_user = "test@gmail.com"
        smtp_pass = "secret"
        smtp_host = "smtp.gmail.com"
        smtp_port = 587
        telegram_bot_token = "fake_token"
        telegram_chat_id = "12345"
        rabbitmq_url = "amqp://guest:guest@localhost:5672/"

    return FakeSettings()
