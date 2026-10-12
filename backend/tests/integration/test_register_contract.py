"""REACH AI BOX register contract — full test matrix (docs/reach-edge-register/CLAUDE.md §8) against a running stack.

Skipped unless AIVMS_IT_URL is set, e.g.:

    AIVMS_IT_URL=http://127.0.0.1:8000 AIVMS_IT_ADMIN_USER=admin AIVMS_IT_ADMIN_PASSWORD=... \
    AIVMS_IT_LOG_CMD="docker compose logs backend" AIVMS_IT_RESET_CMD="<flush aivms:reg:* in Redis>" \
    pytest tests/integration -q

It creates owners / sites / tokens / test devices (local-admin MACs) and does not clean them up.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

URL = os.environ.get("AIVMS_IT_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="AIVMS_IT_URL not set (integration test against a running stack)")

KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{16,128}$")
SITE_KEYS = {"site_name", "profile", "site_code", "host_code", "license_code", "license_until", "contract_no",
             "term_years", "transaction_type", "company_name", "company_address", "company_phone", "tax_id",
             "contact_name", "contact_phone"}


def call(method: str, path: str, headers: dict | None = None, body=None) -> tuple[int, dict, dict]:
    req = Request(f"{URL}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                  headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=6) as resp:
            return resp.status, json.loads(resp.read() or b"{}"), {k.lower(): v for k, v in resp.headers.items()}
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read() or b"{}")
        except ValueError:
            payload = {}
        return exc.code, payload, {k.lower(): v for k, v in exc.headers.items()}


def reset_limits() -> None:
    if cmd := os.environ.get("AIVMS_IT_RESET_CMD"):
        subprocess.run(cmd, shell=True, check=False, capture_output=True)


def random_mac() -> str:
    first = (secrets.randbits(8) & 0xFC) | 0x02
    return ":".join(f"{b:02x}" for b in [first, *(secrets.randbits(8) for _ in range(5))])


def uuid_of(mac: str) -> str:
    return "REACH-" + re.sub(r"[:\-.]", "", mac).upper()


def register(token: str | None, mac: str, device_uuid: str | None = None):
    headers = {"X-Provisioning-Token": token} if token else {}
    return call("POST", "/api/v1/edge/register", headers, {"device_uuid": device_uuid or uuid_of(mac),
                                                           "mac_address": mac})


@pytest.fixture(scope="module")
def admin() -> dict:
    status, body, _ = call("POST", "/api/v1/auth/login", body={
        "username": os.environ.get("AIVMS_IT_ADMIN_USER", "admin"), "password": os.environ["AIVMS_IT_ADMIN_PASSWORD"]})
    assert status == 200
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture(scope="module")
def world(admin) -> dict:
    """owner A (full contract data, site, token), owner B (token), owner C (no data), quota token."""
    run = secrets.token_hex(3)
    _, a, _ = call("POST", "/api/v1/owners", admin, {
        "name": f"IT owner A {run}", "company_name": "範例科技股份有限公司", "company_address": "台北市範例路 1 號",
        "company_phone": "02-0000-0000", "tax_id": "12345678", "contact_name": "王小明",
        "contact_phone": "0900-000-000"})
    _, site, _ = call("POST", "/api/v1/sites", admin, {
        "name": f"IT site {run}", "code": f"it-{run}", "owner_id": a["id"], "profile": "office",
        "license_code": "LIC-1", "license_until": "2027-10-31", "contract_no": "CT-1", "term_years": 3,
        "transaction_type": "lease"})
    _, ta, _ = call("POST", f"/api/v1/owners/{a['id']}/tokens", admin, {"site_id": site["id"]})
    _, b, _ = call("POST", "/api/v1/owners", admin, {"name": f"IT owner B {run}"})
    _, tb, _ = call("POST", f"/api/v1/owners/{b['id']}/tokens", admin, {})
    _, c, _ = call("POST", "/api/v1/owners", admin, {"name": f"IT owner C {run}"})
    _, tc, _ = call("POST", f"/api/v1/owners/{c['id']}/tokens", admin, {})
    _, tq, _ = call("POST", f"/api/v1/owners/{a['id']}/tokens", admin, {"max_devices": 1})
    _, tr, _ = call("POST", f"/api/v1/owners/{a['id']}/tokens", admin, {})
    _, te, _ = call("POST", f"/api/v1/owners/{a['id']}/tokens", admin, {"expires_at": "2020-01-01T00:00:00Z"})
    call("POST", f"/api/v1/provisioning-tokens/{tr['id']}/revoke", admin)
    return {"site": site, "a": ta["token"], "b": tb["token"], "c": tc["token"], "quota": tq["token"],
            "revoked": tr["token"], "expired": te["token"]}


@pytest.fixture(autouse=True)
def _limits():
    reset_limits()
    yield


def test_01_new_mac_and_09_config(world):
    mac = random_mac()
    started = time.monotonic()
    status, body, headers = register(world["a"], mac)
    assert status == 200 and time.monotonic() - started < 6  # 14
    assert KEY_RE.fullmatch(body["api_key"]) and body["device_uuid"]
    assert headers.get("cache-control") == "no-store"
    assert body["site_id"] == world["site"]["code"]
    sp = body["site_profile"]
    assert set(sp) <= SITE_KEYS and sp["host_code"] == body["device_uuid"]  # 10
    assert sp["tax_id"] == "12345678" and sp["term_years"] == 3 and sp["license_until"] == "2027-10-31"
    status, cfg, headers = call("GET", "/api/v1/edge/config", {"X-Device-Key": body["api_key"]})
    assert status == 200 and cfg["device_uuid"] == body["device_uuid"] and cfg["site_profile"] == sp
    assert headers.get("cache-control") == "no-store"
    status, only, _ = call("GET", "/api/v1/edge/site-profile", {"X-Device-Key": body["api_key"]})
    assert status == 200 and only == {"site_profile": sp}


def test_02_12_reregister_same_id_new_key(world):
    mac = random_mac()
    _, first, _ = register(world["a"], mac)
    status, again, _ = register(world["a"], mac.upper().replace(":", "-"), uuid_of(mac))
    assert status == 200 and again["device_uuid"] == first["device_uuid"] and again["api_key"] != first["api_key"]
    assert call("GET", "/api/v1/edge/config", {"X-Device-Key": first["api_key"]})[0] == 401
    assert call("GET", "/api/v1/edge/config", {"X-Device-Key": again["api_key"]})[0] == 200


def test_03_other_owner_conflict(world):
    mac = random_mac()
    register(world["a"], mac)
    status, body, _ = register(world["b"], mac)
    assert status == 409 and "IT owner" not in body["detail"]


@pytest.mark.parametrize("which", [None, "wrong", "revoked", "expired"])
def test_04_bad_tokens(world, which):
    token = {"wrong": "invalid-" + secrets.token_hex(8)}.get(which, world.get(which) if which else None)
    status, body, _ = register(token, random_mac())
    assert status == 401 and isinstance(body["detail"], str)


@pytest.mark.parametrize("mac", ["00:00:00:00:00:00", "01:00:5e:00:00:01", "ff:ff:ff:ff:ff:ff", "not-a-mac"])
def test_05_bad_macs(world, mac):
    status, body, _ = register(world["a"], mac, "REACH-000000000000")
    assert status == 422 and isinstance(body["detail"], str)


def test_06_uuid_mismatch(world):
    assert register(world["a"], random_mac(), "REACH-000000000001")[0] == 422


def test_07_disabled_device(world, admin):
    mac = random_mac()
    _, reg, _ = register(world["a"], mac)
    _, devices, _ = call("GET", "/api/v1/devices", admin)
    device = next(d for d in devices["items"] if d["device_uuid"] == reg["device_uuid"])
    assert call("PATCH", f"/api/v1/devices/{device['id']}", admin, {"admin_state": "disabled"})[0] == 200
    assert register(world["a"], mac)[0] == 403
    assert call("GET", "/api/v1/edge/config", {"X-Device-Key": reg["api_key"]})[0] == 403
    status, audit, _ = call("GET", f"/api/v1/devices/{device['id']}/audit", admin)
    assert {"registered", "rejected_403"} <= {a["action"] for a in audit}


def test_08_quota(world):
    assert register(world["quota"], random_mac())[0] == 200
    status, body, _ = register(world["quota"], random_mac())
    assert status == 403 and "quota" in body["detail"]


def test_11_owner_without_contract_data_omits_fields(world):
    status, body, _ = register(world["c"], random_mac())
    assert status == 200 and body["site_id"] == ""
    sp = body["site_profile"]
    assert sp is not None and "" not in sp.values()
    assert set(sp) == {"host_code", "site_name"}  # only what exists; nothing sent as ""


def test_prebound_device_is_claimed_by_mac(world, admin):
    """An admin-created device with its MAC filled in keeps its ID when the box auto-registers."""
    mac = random_mac()
    run = secrets.token_hex(3)
    status, created, _ = call("POST", "/api/v1/devices", admin, {"device_uuid": f"PREBOUND{run}", "name": "pre",
                                                                 "mac_address": mac.upper()})
    assert status == 201
    status, body, _ = register(world["a"], mac)
    assert status == 200 and body["device_uuid"] == f"PREBOUND{run}"


def test_rate_limit_and_ip_block(world):
    for _ in range(5):
        register("invalid-" + secrets.token_hex(4), random_mac())
    status, body, _ = register(world["a"], random_mac())
    assert status == 429 and isinstance(body["detail"], str)


def test_13_no_secrets_in_logs(world):
    cmd = os.environ.get("AIVMS_IT_LOG_CMD")
    if not cmd:
        pytest.skip("AIVMS_IT_LOG_CMD not set")
    logs = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
    for secret in (world["a"], world["b"], world["quota"], "12345678", "0900-000-000", "02-0000-0000"):
        assert secret not in logs
