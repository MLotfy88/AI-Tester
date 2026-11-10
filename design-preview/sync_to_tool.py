"""يحدّث `scripts/html_report.py` من تصميم `design-preview/`.

الاستخدام (بعد أي تعديل في التصميم):
    python design-preview/sync_to_tool.py

ليه مولّد؟ لأن نسخ المشروع بتوزّع ملفات `.py` فقط (من غير مجلد أصول)،
فلازم CSS/JS/HTML يتضمّنوا جوه `html_report.py` كـconstants.
المصدر الحقيقي للتصميم: `design-preview/assets/` + `design-preview/template.html`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design-preview"
ASSETS = DESIGN / "assets"
JS_DIR = ASSETS / "js"
MODULE_SRC = DESIGN / "report_module.py"
OUT = ROOT / "scripts" / "html_report.py"


def main() -> int:
    if not MODULE_SRC.exists():
        print(f"❌ مفيش مصدر الموديول: {MODULE_SRC}")
        return 1

    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    js_parts = sorted(JS_DIR.glob("*.js"))
    if not js_parts:
        print(f"❌ مفيش ملفات JS في {JS_DIR}")
        return 1
    js = "\n\n".join(p.read_text(encoding="utf-8") for p in js_parts)
    tpl = (DESIGN / "template.html").read_text(encoding="utf-8")
    module_src = MODULE_SRC.read_text(encoding="utf-8")

    # حماية: مفيش `\"\"\"` جوه الأصول (وإلا هنكسر الـ raw strings)
    for name, blob in (("CSS", css), ("JS", js), ("TEMPLATE", tpl)):
        if '"""' in blob:
            print(f"❌ {name} فيه `\"\"\"` — مش هينفع يتضمّن كـ raw string")
            return 1
        if blob.rstrip().endswith("\\"):
            print(f"❌ {name} بيخلص بـ backslash — مش هينفع يتضمّن كـ raw string")
            return 1

    out = (
        module_src.replace("@@CSS_ASSET@@", css)
        .replace("@@JS_ASSET@@", js)
        .replace("@@TEMPLATE_ASSET@@", tpl)
    )

    # ملاحظة: الـ template جوه الموديول لازم يفضل فيه `__CSS__`/`__JS__`/`__DATA__`
    # — دي بتتستبدل وقت بناء التقرير (build_html). اللي لازم يتأكد منه هنا
    # إن ثوابت الموديول نفسها اتعبّتت.
    for assignment in (
        'CSS = r"""@@CSS_ASSET@@"""',
        'JS = r"""@@JS_ASSET@@"""',
        'TEMPLATE = r"""@@TEMPLATE_ASSET@@"""',
    ):
        if assignment in out:
            print(f"❌ لسه فاضل: {assignment}")
            return 1

    OUT.write_text(out, encoding="utf-8")
    print(f"✅ {OUT}")
    print(f"   الحجم: {OUT.stat().st_size:,} bytes")
    print(f"   CSS: {len(css):,} · JS: {len(js):,} ({len(js_parts)} ملفات) · HTML: {len(tpl):,}")

    # ── تحقق: الموديول لازم يستورد ويبني صفحة ──
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib

    import html_report

    importlib.reload(html_report)
    if not html_report.CSS.strip() or not html_report.JS.strip() or not html_report.TEMPLATE.strip():
        print("❌ الأصول ما اتضمّنتش صح")
        return 1
    print("✅ استيراد الموديول تمام")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
