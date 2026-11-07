"""يبني مجلد «Final AI Test» — نسخة مرجعية مستقلة من الأداة.

النسخة دي بتتعمل في **آخر** خطوة عشان تكون نهائية ومطابقة تماماً للأداة:
  · ملفَّي التوثيق الأساسية (EXAM-PAPER + HF-Model-Selection-Workflow).
  · ملف توثيق أخطاء التصحيح (GRADING-ERRORS-AND-FIXES).
  · نسخة كل سكربتات الامتحان والتصحيح والتقارير + الإعدادات + القوالب + الاختبارات.
  · MANIFEST.md: قائمة الملفات + SHA-256 + تاريخ النسخة (للتحقق من عدم التغيّر).

الأداة الأصلية ما بتتلمسش — النسخ فقط (read → write).
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "Final AI Test"

DOCS = [
    "EXAM-PAPER-v1.md",
    "HF-Model-Selection-Workflow.md",
    "GRADING-ERRORS-AND-FIXES.md",
]

TREES = [
    "scripts",
    "config",
    "prompts",
    "templates",
    "tests",
    "kaggle",
]

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log"}

README_TEXT = """# Final AI Test — النسخة المرجعية المستقلة

مجلد مرجعي **مستقل** لاختبار الموديلات: فيه ورقة الامتحان + المصحّح + كل ما يتعلق بالامتحان
(أسئلة، قواعد، بوابات، سلالم درجات، قوالب، prompts، إعدادات، اختبارات).

> هدفه إن يبقى **مرجع أساسي** تقدر تقيس عليه أي موديل، **بصرف النظر عن الأداة** اللي بيشغّل
> الموديل (llama.cpp، LM Studio، Ollama، vLLM، API…).

## اللي جواه

| المسار | المحتوى |
|---|---|
| `EXAM-PAPER-v1.md` | **ورقة الامتحان الأصلية**: الـ21 سؤال، المحاور الأربعة، سلالم الدرجات، البوابات G1–G8، خط الأساس 61.6 + شريط الهدف Gemini 2.5 Pro (77). |
| `HF-Model-Selection-Workflow.md` | مرجع اختيار الموديل: fit، حدود VRAM/RAM، السرعة، ومحاكاة الجهاز على Kaggle. |
| `GRADING-ERRORS-AND-FIXES.md` | **سجل أخطاء التصحيح**: كل خطأ، سبب ظهوره، الكود قبل/بعد، والأثر بالأرقام. اقراه قبل تعديل أي مصحّح. |
| `config/exam.yaml` | النسخة الآلية من الورقة: الأسئلة، المحاور، الإعدادات الثابتة (temp=0 · seed=20261106 · ctx=4096 · max_tokens=1200)، خط الأساس (مقاس آلياً) + شريط الهدف Gemini 2.5 Pro (معايرة يدوية). |
| `config/device_profile.yaml` | مواصفات الجهاز المستهدف + ميزانية VRAM (3.4 GiB). |
| `config/model_overrides.yaml` | توصيات per-model (قالب/KV/ngl/threads/device/Sampling موصى به). |
| `prompts/owner_system_prompt.txt` | الـ system prompt الثابت — لازم يتبعت مع كل سؤال. |
| `templates/qwen35_egyptian_nothink.jinja` | قالب المحادثة الثابت (مع منع thinking). |
| `scripts/exam/` | **المصحّح**: `grader.py` (سياستا `paper`/`baseline` + البوابات G1–G8 + الحكم) · `axis1/axis2/axis34.py` (فحوص المحاور) · `lib.py` (أدوات النص). |
| `scripts/exam_runner.py` · `scripts/run_exam.py` | تشغيل الموديل وتمرير الإجابات للمصحّح (في الذاكرة — بلا JSON وسيط). |
| `scripts/excel_report.py` · `scripts/html_report.py` · `scripts/html_charts.py` | التقارير: Excel (10 شيتات) وHTML (كارت لكل موديل + الرسم السداسي + رسوم المقارنة + جدول السرعة + سجل الإجابات الكامل) — **وكلهم بيعرضوا شريط الهدف (Gemini 2.5 Pro) في كل رسوم المقارنة**. |
| `scripts/references.py` | الطبقة المشتركة للمراجع: خط الأساس + **شريط الهدف (Gemini 2.5 Pro)** · حساب **«المسافة عن الهدف»** · وسم المصدر (مقاس / معايرة يدوية). |
| `scripts/fit_check.py` · `scripts/hf_resolver.py` · `scripts/model_settings.py` | fit والملاءمة، تنزيل GGUF، وطبقة الإعدادات لكل موديل. |
| `kaggle/` | مسار Kaggle GPU (فحص الكارت + ballast رام/VRAM + بناء CUDA + تشغيل). |
| `tests/test_smoke.py` | 38 اختباراً للمصحّح والإعدادات والتقارير (من غير شبكة). |
| `MANIFEST.md` | قائمة كل الملفات + SHA-256 + تاريخ النسخة (للتحقق إن النسخة سليمة). |

## استخدام النسخة دي مع أي أداة

1. **ثبّت الـ prompt والقالب:** انسخ `prompts/owner_system_prompt.txt` و
   `templates/qwen35_egyptian_nothink.jinja` وفعّل `chat_template_kwargs: {"enable_thinking": false}`
   (ورقة الامتحان §0.1 — من غيره الردود بتفضل فاضية).
2. **الإعدادات الثابتة:** `temperature=0` · `top_p=1` · `seed=20261106` · `ctx_size=4096` ·
   `max_tokens=1200` · نفس الـ system prompt · نفس القالب. أي تغيير بيكسر المقارنة.
3. **الأسئلة:** الـ21 سؤال في `EXAM-PAPER-v1.md` (ولها نسخة آلية في `config/exam.yaml`).
4. **التصحيح:** بعد ما تاخد الإجابات، شغّل المصحّح على نفس الإجابات:

   ```python
   import sys; sys.path.insert(0, "scripts")
   from common import load_yaml
   from exam.grader import grade_exam

   exam = load_yaml("config/exam.yaml")
   graded = grade_exam({"A1": "...", "A2": "..."}, exam, policy="paper")
   print(graded["total"], graded["verdict"])
   ```

5. **قارن كده:** `policy="paper"` (صارم حسب الورقة) أو `policy="baseline"` (مطابق للرقم
   المنشور 61.6). **لازم تقارن كل الموديلات بنفس السياسة.**
6. **اقرأ `GRADING-ERRORS-AND-FIXES.md`** قبل ما تظلم موديل بسبب false positive معروف.
7. **انتبه لقناة التفكير:** G5 (ورقة §52) بتتحسب على وسوم `<think>` **في الرد المرئي** فقط.
   لو أداتك ترجّع `reasoning_content` في حقل منفصل، سيبه كـ **ملاحظة** مش عقوبة
   (`settings.g5_reasoning_channel: visible` افتراضياً · `any` لو حبيت الأشد).

## مقارنة أكثر من موديل + الأداء المقيس

- **تعدد الموديلات:** `run_exam.py --models "owner/a-GGUF,owner/b-GGUF"` — الموديلات بتشتغل
  **متسلسلة** على نفس الـ runner وبنفس الإعدادات الثابتة، وكل أقسام التقرير (كارت لكل
  موديل · البصمة السداسية · رسوم المقارنة · جدول السرعة لكل سؤال · شيت `SpeedDetail`)
  بتغطيهم جنب بعض. الحد العمقي ≈ 5 موديلات في 6 ساعات.
- **الأداء:** شيت `Performance` في الـ Excel وقسم «⚡ الأداء الحقيقي المقيس» في الـ HTML
  بيعرضوا أرقام **مقيسة فعلياً** (من `timings` الخاص بـ llama.cpp + أوقات الطلبات).
  أرقام «الملاءمة» (سقف tg/pp) **نظرية** — للمقارنة والتخطيط بس.
- **فحص منافسة الكارت:** الأداة بتفحص قبل كل موديل لو فيه `llama-server` / `ollama` تاني
  شغّال — لو لقى واحد بتنوّهك (وبتعرض بانر تحذير في التقرير). **اقفل LM Studio قبل القياس**،
  وإلا الكارت بينقسم والسرعة المقيسة تنزل للنص من غير ما تبان.

## ملاحظات

- التصحيح **حتمي 100%**: نفس الإجابات ⇒ نفس الدرجات دائماً (مفيش LLM-judge).
- درجة المقارنة: `paper` هي المقياس الصارم · `baseline` هو المقياس المنشور (61.6).
- مجلد الأداة الأصلي بيفضل مكانه في المجلد الأب — النسخة دي **نسخة مرجعية** مش بديل.
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST, ignore_errors=True)
    DEST.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []

    # 1) ملفات التوثيق
    for name in DOCS:
        src = ROOT / name
        if not src.exists():
            print(f"⚠ ناقص: {name}")
            continue
        copy_file(src, DEST / name)
        copied.append(DEST / name)

    # 2) شجرات المشروع
    for top in TREES:
        base = ROOT / top
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in SKIP_SUFFIX:
                continue
            rel = path.relative_to(ROOT)
            copy_file(path, DEST / rel)
            copied.append(DEST / rel)

    # 3) README النسخة
    (DEST / "README.md").write_text(README_TEXT, encoding="utf-8")
    copied.append(DEST / "README.md")

    # 4) الـ manifest
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Final AI Test — Manifest النسخة المرجعية",
        "",
        f"- **تاريخ النسخة:** {stamp}",
        "- **مصدر النسخ:** مجلد المشروع `AI Online Tester` (نسخة مطابقة للملفات وقت النسخ)",
        f"- **عدد الملفات:** {len(copied)}",
        "",
        "| # | الملف | الحجم (بايت) | SHA-256 |",
        "|---|---|---|---|",
    ]
    for i, path in enumerate(sorted(copied, key=lambda p: str(p).lower()), 1):
        rel = path.relative_to(DEST).as_posix()
        digest = sha256(path)
        lines.append(f"| {i} | `{rel}` | {path.stat().st_size} | `{digest[:16]}…` |")
    lines += [
        "",
        "## التحقق",
        "",
        "```bash",
        "# تحقق إن كل ملف في النسخة مطابق لبصمة SHA-256 في الـ MANIFEST",
        "python scripts/verify_manifest.py",
        "```",
        "",
        "أو يدوياً:",
        "",
        "```bash",
        "python -c \"import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('scripts/exam/grader.py').read_bytes()).hexdigest())\"",
        "```",
        "",
    ]
    (DEST / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"✅ Final AI Test: {len(copied)} ملف + MANIFEST.md")
    for path in sorted(copied, key=lambda p: str(p).lower()):
        print(f"   {path.relative_to(DEST).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
