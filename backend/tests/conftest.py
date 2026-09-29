import os

from cryptography.fernet import Fernet

# unit tests never touch real services; provide dummy settings
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-000")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("EDGE_PROVISIONING_TOKEN", "test-provisioning")
os.environ.setdefault("MQTT_PASSWORD", "test")
os.environ.setdefault("MINIO_ACCESS_KEY", "test")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret")
