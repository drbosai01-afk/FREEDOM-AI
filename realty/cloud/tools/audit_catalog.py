#!/usr/bin/env python3
"""Read-only audit of an exported JSON catalog. Prints no record values."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

CANDIDATES = ("properties", "objects", "listings", "items", "catalog", "records", "flats")
SECRETS = ("password", "token", "secret", "key", "safe", "код", "сейф", "пароль", "access")

def audit(path):
    blob = Path(path).read_bytes()
    value = json.loads(blob)
    location = "root"
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = None
        for key in CANDIDATES:
            if isinstance(value.get(key), list):
                rows, location = value[key], key
                break
        if rows is None:
            for key, nested in value.items():
                if isinstance(nested, dict):
                    for subkey in CANDIDATES:
                        if isinstance(nested.get(subkey), list):
                            rows, location = nested[subkey], f"{key}.{subkey}"
                            break
                    if rows is not None:
                        break
        if rows is None:
            raise ValueError("Не найден массив объектов")
    else:
        raise ValueError("Некорректный формат экспорта")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("В массиве есть записи неподдерживаемого формата")
    ids = [str(row.get("record_id") or row.get("id") or row.get("externalId") or "") for row in rows]
    counted = Counter(x for x in ids if x)
    fields = sorted(set().union(*(set(row) for row in rows)))
    return {
      "file": Path(path).name,
      "sha256": hashlib.sha256(blob).hexdigest(),
      "records_path": location,
      "records_total": len(rows),
      "records_with_id": sum(bool(i) for i in ids),
      "duplicate_ids": sum(n - 1 for n in counted.values() if n > 1),
      "field_names": fields,
      "potential_sensitive_fields": [k for k in fields if any(s in k.lower() for s in SECRETS)],
      "changed_source": False
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    args = parser.parse_args()
    print(json.dumps(audit(args.backup), ensure_ascii=False, indent=2))
