from unittest.mock import MagicMock

from src.notifications.gmail_auth import get_gmail_service


def test_get_gmail_service_reuses_valid_cached_token_without_interactive_flow(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    token_path.write_text('{"fake": "token"}')

    fake_creds = MagicMock(valid=True)
    monkeypatch.setattr(
        "src.notifications.gmail_auth.Credentials.from_authorized_user_file",
        lambda *args, **kwargs: fake_creds,
    )
    build_mock = MagicMock(return_value="fake-service")
    monkeypatch.setattr("src.notifications.gmail_auth.build", build_mock)
    flow_mock = MagicMock()
    monkeypatch.setattr("src.notifications.gmail_auth.InstalledAppFlow", flow_mock)

    service = get_gmail_service(tmp_path / "client_secret.json", token_path)

    assert service == "fake-service"
    flow_mock.from_client_secrets_file.assert_not_called()
    build_mock.assert_called_once_with("gmail", "v1", credentials=fake_creds)


def test_get_gmail_service_runs_interactive_flow_when_no_cached_token(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"

    fake_creds = MagicMock(valid=True)
    fake_creds.to_json.return_value = "{}"
    flow_instance = MagicMock()
    flow_instance.run_local_server.return_value = fake_creds
    flow_mock = MagicMock()
    flow_mock.from_client_secrets_file.return_value = flow_instance
    monkeypatch.setattr("src.notifications.gmail_auth.InstalledAppFlow", flow_mock)
    monkeypatch.setattr("src.notifications.gmail_auth.build", MagicMock(return_value="fake-service"))

    service = get_gmail_service(tmp_path / "client_secret.json", token_path)

    assert service == "fake-service"
    flow_mock.from_client_secrets_file.assert_called_once()
    assert token_path.exists()
