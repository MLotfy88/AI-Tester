"""يبني مجلد «Final AI Test» — نسخة مرجعية مستقلة من الأداة (v3).

النسخة دي بتتعمل في **آخر** خطوة عشان تكون نهائية ومطابقة تماماً للأداة:
  · ملفات التوثيق الأساسية (README + HF-Model-Selection-Workflow + GRADING-ERRORS).
  · **ملف مواصفات الامتحان** `exam/exam_questions_v2.json` (المصدر الوحيد للحقيقة).
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
DEST = ROOT / "dist" / "Final AI Test"

DOCS = [
    "README.md",
    "HF-Model-Selection-Workflow.md",
    "GRADING-ERRORS-AND-FIXES.md",
]

TREES = [
    "scripts",
    "config",
    "exam",
    "templates",
    "tests",
    "kaggle",
]

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log"}


README_TEXT = """# Final AI Test — النسخة المرجعية المستقلة (v3)

مجلد مرجعي **مستقل** لاختبار الموديلات: فيه ورقة الامتحان (ملف المواصفات) + المصحّح + كل ما يتعلق بالامتحان
(أسئلة، rubric، محاور، حدود دنيا، قوالب، إعدادات، اختبارات).

> هدفه إن يبقى **مرجع أساسي** تقدر تقيس عليه أي موديل، **بصرف النظر عن الأداة** اللي بيشغّل
> الموديل (llama.cpp، LM Studio، Ollama، vLLM، API…).

## اللي جواه

| المسار | المحتوى |
|---|---|
| `exam/exam_questions_v2.json` | **المصدر الوحيد للح-truth**: 33 سؤال مصحّح + 14 استكشافي + 8 محاور بأوزان وحدود دنيا + الإعدادات الثابتة + الأدوات + `system_prompt_style`. |
| `exam/منهج الامتحان الجديد.md` | منهج الامتحان الجديد بالعربي. |
| `HF-Model-Selection-Workflow.md` | مرجع اختيار الموديل: fit، حدود VRAM/RAM، السرعة، ومحاكاة الجهاز على Kaggle. |
| `GRADING-ERRORS-AND-FIXES.md` | **سجل أخطاء التصحيح**: كل خطأ، سبب ظهوره، الكود قبل/بعد، والأثر بالأرقام. اقراه قبل تعديل أي مصحّح. |
| `config/references.yaml` | مراجع **العرض فقط** + حدود الحكم (85/70/55) — كل رقم مرجعي مكتوب مصدره. |
| `config/device_profile.yaml` | مواصفات الجهاز المستهدف + ميزانية VRAM (3.4 GiB). |
| `config/model_overrides.yaml` | توصيات per-model (قالب/KV/ngl/threads/device/Sampling موصى به). |
| `templates/qwen35_egyptian_nothink.jinja` | قالب المحادثة الثابت (مع منع thinking). |
| `scripts/exam/` | **المصحّح**: `spec.py` (تحميل المواصفات) · `grader.py` (التجميع + متوسط التكرار + الحكم) · `rubric_engine.py` (نسب المحاور + بوابات الحد الأدنى) · `rubric_lib.py` + `checks_*.py` (165 فحص) · `lib.py` (أدوات النص). |
| `scripts/exam_runner.py` · `scripts/run_exam.py` | تشغيل الموديل وتمرير الإجابات للمصحّح (في الذاكرة — بلا JSON وسيط). |
| `scripts/excel_report.py` · `scripts/html_report.py` · `scripts/html_charts.py` | التقارير: Excel (11 شيت) وHTML تفاعلي (كارت لكل موديل + الرسم السداسي + رسوم المقارنة + جدول السرعة + سجل الإجابات). |
| `scripts/references.py` | الطبقة المشتركة للمراجع: مرجع Gemini 2.5 Pro (**عرض فقط ⛔**) + حساب **المسافة** على المحاور الثمانية + وسم المصدر. |
| `scripts/fit_check.py` · `scripts/hf_resolver.py` · `scripts/model_settings.py` | fit والملاءمة، تنزيل GGUF، وطبقة الإعدادات لكل موديل. |
| `kaggle/` | مسار Kaggle GPU (فحص الكارت + ballast رام/VRAM + بناء CUDA + تشغيل + تنظيف Output). |
| `tests/test_smoke.py` | اختبارات المصحّح والإعدادات والتقارير (من غير شبكة). |
| `MANIFEST.md` | قائمة كل الملفات + SHA-256 + تاريخ النسخة (للتحقق إن النسخة سليمة). |

## استخدام النسخة دي مع أي أداة

1. **ثبّت القالب:** انسخ `templates/qwen35_egyptian_nothink.jinja` وفعّل
   `chat_template_kwargs: {"enable_thinking": false}` (من غيره الردود بتفضل فاضية).
2. **الإعدادات الثابتة:** `temperature=0.6` · `top_p=0.95` · `seed=1234` · `ctx_size=8192` ·
   `max_tokens=4000` · نفس الـ system prompt (من `system_prompt_style`) · نفس القالب.
   أي تغيير بيكسر المقارنة.
3. **الأسئلة:** 33 سؤال في `exam/exam_questions_v2.json` (المصدر الوحيد للحقيقة).
4. **التصحيح:** بعد ما تاخد الإجابات، شغّل المصحّح على نفس الإجابات:

   ```python
   import sys; sys.path.insert(0, "scripts")
   from common import load_exam
   from exam.grader import grade_exam

   exam = load_exam()
   graded = grade_exam({"EG1": "...", "LG1": [{"answer": "..."}, {"answer": "..."}]}, exam)
   print(graded["total"], graded["verdict"])
   ```

5. **التكرار:** محاور `LG` و `IF` و `TL` بتمرّ مرتين — ابعت قائمتين تحت المفتاح نفسه
   (أو `LG1__1` / `LG1__2`) والمصحّح هياخد المتوسط.
6. **اقرأ `GRADING-ERRORS-AND-FIXES.md`** قبل ما تظلم موديل بسبب false positive معروف.

## مقارنة أكثر من موديل + الأداء المقيس

- **تعدد الموديلات:** `run_exam.py --models "owner/a-GGUF,owner/b-GGUF"` — الموديلات بتشتغل
  **متسلسلة** على نفس الـ runner وبنفس الإعدادات الثابتة، وكل أقسام التقرير (كارت لكل
  موديل · البصمة السداسية · رسوم المقارنة · جدول السرعة لكل سؤال · شيت `SpeedDetail`)
  بتغطيهم جنب بعض. الحد العمقي ≈ 5 موديلات في 6 ساعات.
- **الأداء:** شيت `Performance` في الـ Excel وقسم «الأداء المقيس» في الـ HTML
  بيعرضوا أرقام **مقيسة فعلياً** (من `timings` الخاص بـ llama.cpp + أوقات الطلبات).
  أرقام «الملاءمة» (سقف tg/pp) **نظرية** — للمقارنة والتخطيط بس.
- **فحص منافسة الكارت:** الأداة بتفحص قبل كل موديل لو فيه `llama-server` / `ollama` تاني
  شغّال — لو لقى واحد بتنوّهك (وبتعرض بانر تحذير في التقرير). **اقفل LM Studio قبل القياس**،
  وإلا الكارت بينقسم والسرعة المقيسة تنزل للنص من غير ما تبان.

## ملاحظات

- التصحيح **حتمي 100%**: نفس الإجابات ⇒ نفس الدرجات دائماً (مفيش LLM-judge).
- **مرجع Gemini 2.5 Pro = عرض فقط ⛔**: مالوش أي تأثير في الدرجة ولا الحكم ولا بوابات الحد الأدنى.
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
        "python scripts/verify_manifest.py .",
        "```",
        "",
        "(أو من جذر المشروع: `python scripts/verify_manifest.py \"dist/Final AI Test\"`)",
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
