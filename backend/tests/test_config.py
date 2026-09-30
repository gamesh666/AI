import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(postgres_password="x", jwt_secret_key="k" * 32, edge_provisioning_token="t", mqtt_password="m",
                minio_access_key="a", minio_secret_key="s",
                credential_encryption_key="QnjTH6SV2urR9xD0aiKmKVubmJ8_Wq08VSW3JEqwFnE=")
    base.update(overrides)
    return Settings(**base)


def test_invalid_fernet_key_fails_at_startup_with_instructions():
    with pytest.raises(ValidationError, match="CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key"):
        _settings(credential_encryption_key="change-me-fernet-key")


def test_placeholders_warn_in_development_and_fail_in_production():
    dev = _settings(edge_provisioning_token="change-me-provisioning-token")
    assert dev.placeholder_secrets() == ["EDGE_PROVISIONING_TOKEN"]
    with pytest.raises(ValidationError, match="placeholder secrets are not allowed in production"):
        _settings(APP_ENV="production", edge_provisioning_token="change-me-provisioning-token")
