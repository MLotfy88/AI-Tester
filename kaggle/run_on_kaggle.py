"""يشغّل امتحان الـ 21 سؤال على Kaggle GPU من أمر واحد:

    python kaggle/run_on_kaggle.py --models Qwen/Qwen3.5-4B-GGUF --owner myuser

الخطوات: بناء الـ kernel ← `kaggle kernels push` ← انتظار ← `kaggle kernels output`.

المتطلبات:
  · مكتبة kaggle: `pip install "kaggle>=1.6.17" six` (من غير six بيفشل الـ CLI)
  · التوكن: KAGGLE_USERNAME و KAGGLE_KEY كمتغيرات بيئة (أو ~/.kaggle/kaggle.json)

تحذيرات من تقارير المستخدمين (لم نتحقق منها):
  · اسم الـ accelerator ممكن يتغيّر بين نسخ Kaggle CLI — لو الـ push رفض، شيل
    حقول الـ accelerator من `kernel-metadata.json` واختار الكارت يدوياً من واجهة Kaggle.
  · Kaggle Secrets بتتشال مع `kernels push` بالـ CLI ⇒ النماذج لازم تكون **عامة**.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_kernel  # noqa: E402

TERMINAL_OK = ("complete",)
TERMINAL_FAIL = ("error", "cancel", "failed")


def run_cli(args: list[str], *, check: bool = False, timeout: int = 300) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["kaggle", *args], capture_output=True, text=True, timeout=timeout, env=dict(os.environ)
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if check and proc.returncode != 0:
        raise SystemExit(f"❌ فشل الأمر: kaggle {' '.join(args)}\n{output[-3000:]}")
    return proc


def ensure_kaggle_cli() -> None:
    """يتأكد إن Kaggle CLI شغّال، ويشرح الإصلاح لو ناقص six."""
    if not shutil.which("kaggle"):
        raise SystemExit(
            "❌ أمر `kaggle` مش موجود. ثبّته بـ:\n"
            '   pip install "kaggle>=1.6.17" six'
        )
    try:
        proc = run_cli(["--version"], timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"❌ تعذّر تشغيل Kaggle CLI: {exc}") from exc
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        if "No module named 'six'" in output:
            raise SystemExit(
                "❌ Kaggle CLI محتاج مكتبة `six` (ModuleNotFoundError).\n"
                "   الحل: pip install six\n"
                f"   تفاصيل: {output[-800:]}"
            )
        raise SystemExit(f"❌ Kaggle CLI مش شغّال:\n{output[-1200:]}")
    print(f"✅ Kaggle CLI: {output.splitlines()[0] if output else 'OK'}")


def ensure_credentials(username: str | None, key: str | None, kaggle_json: Path | None = None) -> str:
    """يجهّز التوكن للـ CLI ويرجع اسم المستخدم."""
    user = username or os.environ.get("KAGGLE_USERNAME") or ""
    token = key or os.environ.get("KAGGLE_KEY") or ""
    if user and token:
        os.environ["KAGGLE_USERNAME"] = user
        os.environ["KAGGLE_KEY"] = token
        print(f"🔑 التوكن من متغيرات البيئة — المستخدم: {user}")
        return user
    json_path = kaggle_json
    if json_path is None:
        json_path = Path.home() / ".kaggle" / "kaggle.json"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        user = data.get("username") or user
        os.environ.setdefault("KAGGLE_USERNAME", str(user))
        os.environ.setdefault("KAGGLE_KEY", str(data.get("key") or ""))
        print(f"🔑 التوكن من {json_path} — المستخدم: {user}")
        return str(user)
    raise SystemExit(
        "❌ مفيش توكن Kaggle. في GitHub Actions: أضف Secrets باسم "
        "KAGGLE_USERNAME و KAGGLE_KEY (من kaggle.com → Settings → API). "
        "محلياً: export KAGGLE_USERNAME=... && export KAGGLE_KEY=... "
        "(أو حط kaggle.json في ~/.kaggle/)."
    )


def wait_for_kernel(kernel_id: str, *, timeout_min: int, poll_s: int) -> str:
    """يستنى لحد ما الـ kernel يخلص ويرجع الحالة النهائية."""
    deadline = time.time() + timeout_min * 60
    last = ""
    while True:
        proc = run_cli(["kernels", "status", kernel_id])
        text = ((proc.stdout or "") + (proc.stderr or "")).strip()
        low = text.lower()
        if text != last:
            print(f"⏳ الحالة: {text or '(مفيش رد)'}")
            last = text
        if any(k in low for k in TERMINAL_OK):
            return "complete"
        if any(k in low for k in TERMINAL_FAIL):
            return "failed"
        if time.time() > deadline:
            return "timeout"
        time.sleep(poll_s)


def main() -> int:
    ap = argparse.ArgumentParser(description="تشغيل امتحان الورقة على Kaggle GPU")
    ap.add_argument("--models", required=True, help="repo ids على HF مفصولة بفاصلة (نماذج عامة)")
    ap.add_argument("--kernel-name", default="", help="اسم الـ kernel (افتراضي: exam-<تاريخ>)")
    ap.add_argument("--owner", default="", help="اسم مستخدم Kaggle (افتراضي: من التوكن)")
    ap.add_argument("--quant", default="Q4_K_M")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--policy", default="paper", choices=["paper", "baseline"])
    ap.add_argument("--accelerator", default="t4x2", choices=sorted(build_kernel.ACCELERATORS))
    ap.add_argument("--vram-gib", type=float, default=3.4)
    ap.add_argument("--ram-gib", type=float, default=15.9)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--llama-tag", default="latest")
    ap.add_argument("--kv", default="f16")
    ap.add_argument("--template-mode", default="auto", choices=["auto", "exam", "model"])
    ap.add_argument("--max-gib", type=float, default=20.0)
    ap.add_argument("--model-timeout", type=int, default=300)
    ap.add_argument("--total-timeout", type=int, default=600)
    ap.add_argument("--build-dir", default="", help="مجلد البناء (افتراضي kaggle/_build/<slug>)")
    ap.add_argument("--out", default="", help="مجلد تنزيل المخرجات (افتراضي out_kaggle/<slug>)")
    ap.add_argument("--timeout-min", type=int, default=350, help="أقصى انتظار للـ kernel (دقائق)")
    ap.add_argument("--poll", type=int, default=60, help="كل قد إيه نسأل على الحالة (ثواني)")
    ap.add_argument("--build-only", action="store_true", help="بناء المجلد بس من غير رفع")
    ap.add_argument("--push-only", action="store_true", help="رفع واستنى من غير تنزيل مخرجات")
    args = ap.parse_args()

    ensure_kaggle_cli()
    user = ensure_credentials(args.owner or None, None)
    kernel_name = args.kernel_name or f"exam-{time.strftime('%Y%m%d-%H%M')}"

    print("📦 بناء مجلد الـ kernel…")
    info = build_kernel.build(
        owner=user,
        kernel_name=kernel_name,
        models=args.models,
        quant=args.quant,
        ctx=args.ctx,
        policy=args.policy,
        accelerator=args.accelerator,
        vram_gib=args.vram_gib,
        ram_gib=args.ram_gib,
        threads=args.threads,
        llama_tag=args.llama_tag,
        kv=args.kv,
        template_mode=args.template_mode,
        max_gib=args.max_gib,
        model_timeout=args.model_timeout,
        total_timeout=args.total_timeout,
        out_dir=args.build_dir or None,
    )
    print(f"   dir={info['dir']} · files={info['project_files']} · cells={info['cells']}")

    if args.build_only:
        print("✅ خلص البناء (--build-only). ارفع يدوياً لو حبيت:")
        print(f"   kaggle kernels push -p {info['dir']}")
        return 0

    print(f"🚀 رفع الـ kernel {info['kernel_id']} (GPU + Internet)…")
    proc = run_cli(["kernels", "push", "-p", info["dir"]], timeout=600)
    output = (proc.stdout or "") + (proc.stderr or "")
    print(output[-2500:])
    if proc.returncode != 0:
        raise SystemExit(
            "❌ فشل الرفع. لو الرسالة عن `six` نفّذ: pip install six. "
            "ولو الرسالة عن الـ accelerator: شيله من kernel-metadata.json "
            "واختار الكارت من واجهة Kaggle ثم أعد المحاولة.\n" + output[-1200:]
        )

    print(f"⏳ الانتظار (حد أقصى {args.timeout_min} دقيقة)…")
    state = wait_for_kernel(info["kernel_id"], timeout_min=args.timeout_min, poll_s=args.poll)
    if state != "complete":
        print(f"⚠ انتهى الانتظار بحالة: {state} — جرّب تنزّل المخرجات الجزئية:")
        print(f"   kaggle kernels output {info['kernel_id']} -p out_kaggle/{info['slug']}")
        return 2

    if args.push_only:
        print("✅ الـ kernel خلص (--push-only).")
        return 0

    out_dir = Path(args.out) if args.out else Path("out_kaggle") / info["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"⬇️ تنزيل المخرجات إلى {out_dir}…")
    proc = run_cli(
        ["kernels", "output", info["kernel_id"], "-p", str(out_dir)],
        timeout=900,
    )
    print((proc.stdout or "")[-2500:])
    if proc.stderr:
        print(proc.stderr[-1000:])

    files = sorted(p for p in out_dir.rglob("*") if p.is_file())
    print(f"\n✅ المخرجات ({len(files)} ملف):")
    for path in files[:40]:
        print(f"   {path} ({path.stat().st_size / 1024:.1f} KiB)")
    if len(files) > 40:
        print(f"   … و{len(files) - 40} ملف كمان")
    summary = next((p for p in files if p.name == "summary.md"), None)
    if summary:
        print("\n===== summary.md =====\n")
        print(summary.read_text(encoding="utf-8", errors="replace")[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
