"""يتحقق إن كل ملف في مجلد المرجع مطابق لبصمة SHA-256 في `MANIFEST.md`.

الاستخدام:
    python scripts/verify_manifest.py            # من جذر مجلد المرجع
    python scripts/verify_manifest.py <مجلد>

خروج بالرمز 0 = كله سليم · 1 = فيه ملف ناقص أو متغيّر.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROW = re.compile(r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|.*?`([0-9a-f]{16})…`\s*\|")


def sha256_prefix(path: Path, length: int = 16) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def verify(root: Path) -> int:
    manifest = root / "MANIFEST.md"
    if not manifest.exists():
        print(f"❌ مفيش MANIFEST.md في {root}")
        return 1
    ok = 0
    changed: list[str] = []
    missing: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if not m:
            continue
        rel, prefix = m.group(1), m.group(2)
        path = root / rel
        if not path.exists():
            missing.append(rel)
            continue
        if sha256_prefix(path) != prefix:
            changed.append(rel)
        else:
            ok += 1
    for rel in missing:
        print(f"❌ ناقص: {rel}")
    for rel in changed:
        print(f"⚠️  متغيّر: {rel}")
    print(f"✅ مطابق: {ok} · متغيّر: {len(changed)} · ناقص: {len(missing)}")
    return 1 if (changed or missing) else 0


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    return verify(target.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
