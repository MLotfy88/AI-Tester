"""اختيار وتنزيل ملف GGUF المطلوب من Hugging Face.

- يقرأ شجرة الملفات من HF API (بدون تنزيل الريبو كله).
- يختار ملف الـ quant المطابق، ويفهم الملفات المقسّمة (-00001-of-0000N).
- يمنع التحميل لو الحجم أكبر من الحد أو مساحة القرص غير كافية.
- لا يكتب أي JSON وسيط؛ يعيد manifest كـ dict في الذاكرة.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from common import GIB, human_bytes, slugify


class HFError(RuntimeError):
    pass


@dataclass
class QuantGroup:
    base: str
    files: list[dict] = field(default_factory=list)
    total_bytes: int = 0
    split: bool = False
    score: int = 0

    @property
    def first_path(self) -> str:
        return sorted(f["path"] for f in self.files)[0]


def _api_headers(token: str | None) -> dict:
    headers = {"User-Agent": "exam-runner/1.0 (+github-actions)"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str, token: str | None, timeout: int = 60):
    req = urllib.request.Request(url, headers=_api_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        if exc.code in (401, 403):
            raise HFError(
                f"الريبو مقيّد أو غير متاح ({exc.code}). أضف HF_TOKEN كـ secret. {body}"
            ) from exc
        if exc.code == 404:
            raise HFError(f"الريبو أو الـ revision غير موجود: {url}") from exc
        raise HFError(f"HF API {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise HFError(f"تعذّر الاتصال بـ Hugging Face: {exc}") from exc


def generation_config(repo: str, revision: str = "main", token: str | None = None) -> dict:
    """generation_config.json من Hugging Face — توصيات Sampling الرسمية للمطوّر.

    لو الملف مش موجود (أغلب موديلات GGUF) بيرجع {} من غير خطأ.
    """
    url = (
        f"https://huggingface.co/{urllib.parse.quote(repo, safe='/')}/resolve/"
        f"{urllib.parse.quote(revision or 'main', safe='')}/generation_config.json"
    )
    try:
        data = _get_json(url, token, timeout=30)
    except HFError:
        return {}
    return data if isinstance(data, dict) else {}


def model_info(repo: str, revision: str, token: str | None) -> dict:
    url = f"https://huggingface.co/api/models/{urllib.parse.quote(repo, safe='/')}"
    if revision:
        url += f"/revision/{urllib.parse.quote(revision, safe='')}"
    try:
        return _get_json(url, token)
    except HFError:
        # المعلومات الاختيارية (license/sha) لا يجب أن تُسقط التشغيل.
        return {}


def list_repo_files(repo: str, revision: str, token: str | None) -> list[dict]:
    """يرجع كل الملفات مع أحجامها. يدعم pagination لو موجود."""
    base = f"https://huggingface.co/api/models/{urllib.parse.quote(repo, safe='/')}/tree/"
    base += f"{urllib.parse.quote(revision or 'main', safe='')}?recursive=true&expand=true"
    out: list[dict] = []
    url = base
    for _ in range(20):
        req = urllib.request.Request(url, headers=_api_headers(token))
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                link = resp.headers.get("Link", "")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code in (401, 403):
                raise HFError(
                    f"الريبو مقيّد أو غير متاح ({exc.code}). أضف HF_TOKEN كـ secret. {body}"
                ) from exc
            raise HFError(f"HF tree API {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise HFError(f"تعذّر الاتصال بـ Hugging Face: {exc}") from exc

        if not isinstance(data, list):
            raise HFError(f"استجابة HF غير متوقعة: {str(data)[:300]}")
        out.extend(x for x in data if isinstance(x, dict))

        nxt = None
        for part in link.split(","):
            m = re.search(r'<([^>]+)>;\s*rel="next"', part)
            if m:
                nxt = m.group(1)
                break
        if not nxt:
            break
        url = nxt
    return out


def _split_parts(path: str) -> tuple[str, int, int] | None:
    m = re.match(r"^(.*)-(\d{5})-of-(\d{5})\.gguf$", path, re.I)
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


AUTO_QUANT_PREFERENCE = (
    ("q4_k_m", 100),
    ("q4_k_s", 92),
    ("iq4_xs", 88),
    ("iq4_nl", 84),
    ("q5_k_m", 80),
    ("q5_k_s", 74),
    ("q4_0", 70),
    ("q6_k", 58),
    ("q8_0", 48),
    ("q3_k_m", 38),
    ("q3_k_s", 32),
    ("q2_k", 10),
    ("f16", 5),
    ("bf16", 5),
)


def _auto_quant_score(low: str) -> int:
    """درجة تفضيل quant لما المستخدم يختار `auto`.

    الترتيب: Q4_K_M أولاً (أفضل توازن جودة/حجم ومعظم الموديلات بتوفّره)،
    وبعده Q4_K_S و IQ4_XS، ثم الأحجام الأكبر/الأصغر. الملفات الغريبة
    (mmproj/vision) بتتعامل معاها `_quant_score` بعقوبة كبيرة.
    """
    for token, score in AUTO_QUANT_PREFERENCE:
        if token in low:
            return score
    return 20


def _quant_score(path: str, pattern: str) -> int:
    name = Path(path).name
    low = name.lower()
    pat = pattern.lower().strip()
    if pat == "auto":
        score = _auto_quant_score(low)
    else:
        score = 0
        if pat and pat in low:
            score += 60
            # مطابقة حدّية أفضل من مجرد substring
            if re.search(r"(^|[-_.])" + re.escape(pat) + r"($|[-_.])", low):
                score += 45
    if re.search(r"mmproj|projector|vision|image|embed|clip", low):
        score -= 120
    if "imatrix" in low and "imatrix" not in pat:
        score -= 15
    if "q4_k_m" in low and pat == "q4_k_m":
        score += 5
    return score


def select_quant(files: Iterable[dict], pattern: str) -> list[QuantGroup]:
    """يبني مجموعات (single/split) للملفات المطابقة ويعيدها مرتبة بالأفضل.

    `pattern="auto"` ⇒ يختار أفضل quant متاح تلقائياً (Q4_K_M أولاً) بدل ما
    يرفض لو النمط مش موجود. ده اللي بيخلي الأداة تدعم أي موديل GGUF من غير
    تعديل يدوي.
    """
    ggufs = [f for f in files if str(f.get("path", "")).lower().endswith(".gguf")]
    if not ggufs:
        raise HFError("مفيش أي ملفات GGUF في الريبو.")

    pat = (pattern or "").strip()
    auto = pat.lower() == "auto"
    matched = ggufs if auto else [f for f in ggufs if not pat or pat.lower() in str(f["path"]).lower()]
    if not matched:
        available = "\n".join(f"  - {f['path']}" for f in ggufs[:80])
        raise HFError(
            f"مفيش ملف GGUF يطابق النمط «{pattern}».\nالملفات المتاحة:\n{available}"
        )

    by_key: dict[tuple[str, int], QuantGroup] = {}
    singles: list[QuantGroup] = []
    for f in matched:
        path = str(f["path"])
        size = int(f.get("size") or (f.get("lfs") or {}).get("size") or 0)
        rec = {"path": path, "size": size}
        parts = _split_parts(path)
        if parts:
            base, idx, total = parts
            key = (base, total)
            grp = by_key.setdefault(key, QuantGroup(base=base, split=True))
            grp.files.append({**rec, "index": idx, "total": total})
        else:
            singles.append(QuantGroup(base=path, files=[rec], split=False))

    groups = list(by_key.values()) + singles
    complete: list[QuantGroup] = []
    for grp in groups:
        if grp.split:
            total = grp.files[0]["total"]
            indexes = {f["index"] for f in grp.files}
            if len(indexes) != total:
                continue
            grp.files.sort(key=lambda x: x["index"])
        grp.total_bytes = sum(f["size"] for f in grp.files)
        grp.score = sum(_quant_score(f["path"], pat) for f in grp.files) // len(grp.files)
        complete.append(grp)

    if not complete:
        raise HFError(f"لقيت ملفات مطابقة للنمط «{pattern}» لكن أجزاء الملف المقسّم ناقصة.")

    # عند تساوي درجة الـ quant: نفضّل الملف المقسّم المكتمل (كل أجزائه موجودة)
    # لأنه أوضح وأأمن من الاعتماد على ملف single ممكن يكون ناقصًا، وبعدها
    # الأصغر حجمًا ثم المسار لضمان ترتيب حتمي ثابت.
    complete.sort(
        key=lambda g: (-g.score, 0 if g.split else 1, g.total_bytes, g.first_path)
    )
    return complete


def _disk_free(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def resolve_and_download(
    repo: str,
    pattern: str,
    *,
    revision: str = "main",
    token: str | None = None,
    out_dir: str | Path = "models",
    max_gib: float = 10.0,
    min_free_gib: float = 1.0,
) -> dict:
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    files = list_repo_files(repo, revision, token)
    groups = select_quant(files, pattern)
    chosen = groups[0]
    size = chosen.total_bytes

    if size <= 0:
        raise HFError("HF API رجّع حجم صفر للملف المختار؛ جرّب revision مختلف.")
    if size > max_gib * GIB:
        raise HFError(
            f"الملف المختار حجمه {human_bytes(size)} وأكبر من الحد {max_gib:.1f} GiB. "
            "ارفع max_download_gib أو اختر quant أصغر."
        )
    free = _disk_free(out_root)
    needed = size + min_free_gib * GIB
    if free < needed:
        raise HFError(
            f"مساحة القرص غير كافية: متاح {human_bytes(free)} ومطلوب {human_bytes(needed)}."
        )

    info = model_info(repo, revision, token)
    sha = info.get("sha") or ""
    license_name = ""
    card = info.get("cardData") or {}
    if isinstance(card, dict):
        lic = card.get("license")
        if isinstance(lic, list):
            license_name = ", ".join(map(str, lic))
        elif lic:
            license_name = str(lic)

    local_dir = out_root / slugify(repo.replace("/", "__"))
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import hf_hub_download
    except Exception as exc:  # pragma: no cover
        raise HFError(f"مكتبة huggingface_hub غير مثبتة: {exc}") from exc

    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    downloaded = []
    for f in chosen.files:
        path = hf_hub_download(
            repo_id=repo,
            filename=f["path"],
            revision=revision or "main",
            token=token or None,
            local_dir=str(local_dir),
        )
        p = Path(path)
        got = p.stat().st_size
        expected = int(f["size"] or 0)
        if expected and got != expected:
            raise HFError(
                f"حجم الملف بعد التنزيل مختلف: {p.name} ({got} != {expected})."
            )
        downloaded.append({"path": f["path"], "local_path": str(p), "bytes": got})

    first = sorted(downloaded, key=lambda x: x["path"])[0]["local_path"]
    manifest = {
        "repo": repo,
        "revision": revision or "main",
        "sha": sha,
        "license": license_name or "unknown",
        "quant_pattern": pattern,
        "quant_chosen": chosen.first_path,
        "files": downloaded,
        "primary_path": first,
        "total_bytes": sum(x["bytes"] for x in downloaded),
        "local_dir": str(local_dir),
        "url": f"https://huggingface.co/{repo}",
    }
    return manifest


def cleanup_model(manifest: dict | None) -> None:
    """يحذف ملفات النموذج بعد الانتهاء لتوفير مساحة الـ runner."""
    if not manifest:
        return
    folder = manifest.get("local_dir")
    if not folder:
        return
    p = Path(folder)
    try:
        if p.exists() and p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass
