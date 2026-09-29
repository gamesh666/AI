#!/usr/bin/env python3
"""Regenerate shared/schemas/*.json from the Pydantic contracts in shared/python/aivms_shared.

    pip install -e shared/python && python scripts/gen_schemas.py
"""

from __future__ import annotations

import json
from pathlib import Path

from aivms_shared.payloads import ALL_PAYLOADS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "shared" / "schemas"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, model in ALL_PAYLOADS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path = OUT / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2) + "\n")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
