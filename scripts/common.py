"""أدوات مشتركة: مسارات، إعدادات، بصمات SHA، وتشغيل أوامر بأمان."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
SCRIPTS_DIR = ROOT / "scripts"

GIB = 1024 ** 3


# --------------------------------------------------------------------------- إعدادات
def load_yaml(path: str | Path) -> dict:
    import yaml

    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_exam() -> dict:
    return load_yaml(CONFIG_DIR / "exam.yaml")


def load_device_profile(path: str | Path | None = None) -> dict:
    return load_yaml(path or (CONFIG_DIR / "device_profile.yaml"))


def repo_path(value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (ROOT / p)


# --------------------------------------------------------------------------- بصمات
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def short_sha(value: str | None, n: int = 12) -> str:
    return (value or "")[:n]


# --------------------------------------------------------------------------- تسمية
def slugify(value: str, max_len: int = 80) -> str:
    value = value.strip().replace("\\", "/")
    value = re.sub(r"[^A-Za-z0-9._-]+", "__", value)
    value = re.sub(r"_{2,}", "__", value).strip("._-")
    return (value or "model")[:max_len]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def human_bytes(n: float | int | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024.0 or unit == "TiB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.2f} TiB"


def fmt_num(value: Any, digits: int = 2) -> str:
    try:
        if value is None or value == "":
            return "—"
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


# --------------------------------------------------------------------------- أوامر
def run_cmd(
    cmd: Iterable[str] | str,
    *,
    cwd: str | Path | None = None,
    env: dict | None = None,
    check: bool = True,
    timeout: int | None = None,
    log_path: str | Path | None = None,
    quiet: bool = False,
) -> subprocess.CompletedProcess:
    """يشغّل أمراً. لو log_path موجود يكتب stdout+stderr فيه أيضاً."""
    if isinstance(cmd, str):
        shell = True
        printable = cmd
    else:
        cmd = [str(x) for x in cmd]
        shell = False
        printable = " ".join(shlex.quote(x) for x in cmd)

    if not quiet:
        print(f"$ {printable}", flush=True)

    merged_env = dict(os.environ)
    if env:
        merged_env.update({str(k): str(v) for k, v in env.items()})

    if log_path:
        log = Path(log_path)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(f"\n$ {printable}\n")
            fh.flush()
            proc = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=merged_env,
                shell=shell,
                text=True,
                stdout=fh,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        if proc.returncode != 0 and check:
            raise SystemExit(f"فشل الأمر ({proc.returncode}): {printable}\nراجع: {log}")
        return proc

    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        shell=shell,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if not quiet:
        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.stderr:
            print(proc.stderr.rstrip(), file=sys.stderr)
    if proc.returncode != 0 and check:
        raise SystemExit(
            f"فشل الأمر ({proc.returncode}): {printable}\n"
            f"stdout:\n{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-3000:]}"
        )
    return proc


def tail_text(path: str | Path, max_chars: int = 4000) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def write_text(path: str | Path, text: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def dump_json_for_html(data: Any) -> str:
    """JSON آمن للتضمين داخل <script> (يمنع أي وسم HTML خام).

    بنهرّب كل علامة ``<`` إلى ``\\u003c``، وده JSON صالح ويرجع لنفس القيمة
    عند ``json.loads``. النتيجة إن الـ payload مستحيل يفتح أو يقفل وسم
    ``script`` حتى لو اسم الموديل نفسه فيه HTML.
    """
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return raw.replace("<", "\\u003c")
