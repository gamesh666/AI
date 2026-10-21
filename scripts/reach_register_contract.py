#!/usr/bin/env python3
"""REACH AI BOX <-> AIVMS /edge/register 契約驗證。

用法：
  AIVMS_API_URL=http://127.0.0.1:8000 \
  REACH_TEST_TOKEN=<有效 token> \
  REACH_OTHER_TOKEN=<另一業主的 token，選填> \
  python scripts/reach_register_contract.py
token 只從環境變數讀，絕不印出。
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = os.environ["AIVMS_API_URL"].rstrip("/").removesuffix("/api/v1")
TOKEN = os.environ["REACH_TEST_TOKEN"]
OTHER = os.environ.get("REACH_OTHER_TOKEN", "")
KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{16,128}$")
PHONE_RE = re.compile(r"^[0-9+()#\- ]{0,32}$")
PROFILES = {"office", "construction", "factory", "security"}
SITE_KEYS = {
    "site_name", "profile", "site_code", "host_code", "license_code", "license_until",
    "contract_no", "term_years", "transaction_type", "company_name", "company_address",
    "company_phone", "tax_id", "contact_name", "contact_phone",
}
results: list[tuple[str, bool, str]] = []


def call(method: str, path: str, headers: dict, body: dict | None = None) -> tuple[int, dict, float]:
    data = json.dumps(body).encode() if body is not None else None
    req = Request(f"{API}{path}", data=data, method=method,
                  headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
    start = time.monotonic()
    try:
        with urlopen(req, timeout=6) as resp:
            return resp.status, json.loads(resp.read() or b"{}"), time.monotonic() - start
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read() or b"{}")
        except ValueError:
            payload = {}
        return exc.code, payload, time.monotonic() - start


def check(name: str, ok: bool, note: str = "") -> None:
    results.append((name, ok, note))


def random_mac() -> str:
    first = (secrets.randbits(8) & 0xFC) | 0x02  # 本地管理、unicast，不會撞到實體網卡
    rest = [secrets.randbits(8) for _ in range(5)]
    return ":".join(f"{b:02x}" for b in [first, *rest])


def uuid_of(mac: str) -> str:
    return "REACH-" + re.sub(r"[:\-.]", "", mac).upper()


def register(mac: str, token: str, device_uuid: str | None = None):
    headers = {"X-Provisioning-Token": token} if token else {}
    return call("POST", "/api/v1/edge/register", headers,
                {"device_uuid": device_uuid or uuid_of(mac), "mac_address": mac})


def validate_site_profile(sp) -> str:
    """回傳錯誤說明；空字串代表通過。規則同 BOX 端 app/site_settings.py。"""
    if sp is None:
        return ""
    if not isinstance(sp, dict):
        return "site_profile 不是 object"
    extra = set(sp) - SITE_KEYS
    if extra:
        return f"多餘鍵 {sorted(extra)}"
    v = {k: x for k, x in sp.items() if x is not None}
    if "term_years" in v and (isinstance(v["term_years"], bool) or not isinstance(v["term_years"], int)
                              or not 0 <= v["term_years"] <= 99):
        return "term_years 必須是 0~99 的整數"
    for k in SITE_KEYS - {"term_years"}:
        if k in v and not isinstance(v[k], str):
            return f"{k} 必須是字串"
        limit = 256 if k == "company_address" else 128
        if len(v.get(k, "")) > limit:
            return f"{k} 超過 {limit} 字"
    if "profile" in v and v["profile"] not in PROFILES:
        return "profile 不合法"
    if v.get("license_until") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v["license_until"]):
        return "license_until 必須是 YYYY-MM-DD"
    if v.get("transaction_type", "") not in ("", "buyout", "lease"):
        return "transaction_type 不合法"
    if v.get("tax_id") and not re.fullmatch(r"\d{8}", v["tax_id"]):
        return "tax_id 必須是 8 位數字"
    for k in ("company_phone", "contact_phone"):
        if k in v and not PHONE_RE.fullmatch(v[k]):
            return f"{k} 格式錯"
    return ""


def main() -> int:
    mac = random_mac()

    status, body, elapsed = register(mac, TOKEN)
    check("1 新 MAC 註冊 200", status == 200, f"HTTP {status}")
    check("14 回應 < 6 秒", elapsed < 6, f"{elapsed:.2f}s")
    key1 = str(body.get("api_key", ""))
    dev1 = str(body.get("device_uuid", ""))
    check("1 api_key 格式", bool(KEY_RE.fullmatch(key1)))
    check("1 device_uuid 不為空", bool(dev1))
    err = validate_site_profile(body.get("site_profile"))
    check("10 register site_profile 規則", not err, err)

    status, cfg, _ = call("GET", "/api/v1/edge/config", {"X-Device-Key": key1})
    check("9 api_key 可打 /edge/config", status == 200, f"HTTP {status}")
    check("9 device_uuid 一致", cfg.get("device_uuid") == dev1)
    check("9 /edge/config 有 site_profile 鍵", "site_profile" in cfg)
    err = validate_site_profile(cfg.get("site_profile"))
    check("9 /edge/config site_profile 規則", not err, err)

    status, body2, _ = register(mac.upper().replace(":", "-"), TOKEN, uuid_of(mac))
    check("2/12 重新註冊（大寫、- 分隔）200", status == 200, f"HTTP {status}")
    check("2 device_uuid 不變", body2.get("device_uuid") == dev1)
    key2 = str(body2.get("api_key", ""))
    if key2 and key2 != key1:
        status, _, _ = call("GET", "/api/v1/edge/config", {"X-Device-Key": key1})
        check("2 舊 key 失效", status == 401, f"HTTP {status}")

    if OTHER:
        status, _, _ = register(mac, OTHER)
        check("3 他業主 token -> 409", status == 409, f"HTTP {status}")

    check("4 缺 token -> 401", register(random_mac(), "")[0] == 401)
    check("4 錯 token -> 401", register(random_mac(), "invalid-" + secrets.token_hex(8))[0] == 401)
    check("5 全 0 MAC -> 422", register("00:00:00:00:00:00", TOKEN)[0] == 422)
    check("5 multicast MAC -> 422", register("01:00:5e:00:00:01", TOKEN)[0] == 422)
    check("5 MAC 格式錯 -> 422", register("not-a-mac", TOKEN, "REACH-XYZ")[0] == 422)
    check("6 device_uuid 不一致 -> 422", register(random_mac(), TOKEN, "REACH-000000000001")[0] == 422)

    raw = json.dumps([body, body2, cfg], ensure_ascii=False)
    check("13 回應不含 token", TOKEN not in raw)

    width = max(len(n) for n, _, _ in results)
    failed = 0
    for name, ok, note in results:
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else note}")
    print(f"\n{len(results) - failed}/{len(results)} passed  (測試裝置 device_uuid={dev1}，請在後台除役)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
