# Final AI Test — Manifest النسخة المرجعية

- **تاريخ النسخة:** 2026-11-07 19:16 UTC
- **مصدر النسخ:** مجلد المشروع `AI Online Tester` (نسخة مطابقة للملفات وقت النسخ)
- **عدد الملفات:** 33

| # | الملف | الحجم (بايت) | SHA-256 |
|---|---|---|---|
| 1 | `config/device_profile.yaml` | 1266 | `d2c3b7a13faa89bb…` |
| 2 | `config/exam.yaml` | 8807 | `cfb435187d01dfab…` |
| 3 | `config/model_overrides.yaml` | 3285 | `a73514d321439907…` |
| 4 | `EXAM-PAPER-v1.md` | 57251 | `a0d8e9544732f3c1…` |
| 5 | `GRADING-ERRORS-AND-FIXES.md` | 55059 | `64462adc33490bea…` |
| 6 | `HF-Model-Selection-Workflow.md` | 93109 | `29267a76ca0fe6bb…` |
| 7 | `kaggle/build_kernel.py` | 8912 | `b6e55df7b55f6abe…` |
| 8 | `kaggle/kernel_main.py` | 8628 | `361c6088bae9b403…` |
| 9 | `kaggle/run_on_kaggle.py` | 8739 | `6a11dc25b151f403…` |
| 10 | `prompts/owner_system_prompt.txt` | 4296 | `0e885ad517ca9056…` |
| 11 | `README.md` | 7249 | `e2f1e20dda152d48…` |
| 12 | `scripts/build_exam_core.py` | 14988 | `e6bfb3547e099b1c…` |
| 13 | `scripts/build_final_reference.py` | 11483 | `534a7a369a8256f2…` |
| 14 | `scripts/common.py` | 5615 | `305070fdbcfaca91…` |
| 15 | `scripts/exam/__init__.py` | 87 | `dfca87523ccd5c11…` |
| 16 | `scripts/exam/axis1.py` | 12077 | `102fb487a4604441…` |
| 17 | `scripts/exam/axis2.py` | 11094 | `00b9607f8f247c30…` |
| 18 | `scripts/exam/axis34.py` | 15877 | `7f84755c57d0d5d0…` |
| 19 | `scripts/exam/grader.py` | 22989 | `7569b9e8ea5a2508…` |
| 20 | `scripts/exam/lib.py` | 10709 | `b11a42a60cf8f2a5…` |
| 21 | `scripts/exam_runner.py` | 31985 | `82d63c2ba33661e3…` |
| 22 | `scripts/excel_report.py` | 40793 | `2228cd3017727346…` |
| 23 | `scripts/fit_check.py` | 11714 | `fb464c1e1baa1c3b…` |
| 24 | `scripts/hf_resolver.py` | 11725 | `a34dbea3e697d24a…` |
| 25 | `scripts/html_charts.py` | 63986 | `f231c7b19d7fe717…` |
| 26 | `scripts/html_report.py` | 86925 | `0914264236337444…` |
| 27 | `scripts/install_llamacpp.py` | 8917 | `775bac5d9c408d4f…` |
| 28 | `scripts/model_settings.py` | 12794 | `bb8bad4ae6956fd9…` |
| 29 | `scripts/references.py` | 8864 | `dba23ae6e9581857…` |
| 30 | `scripts/run_exam.py` | 31182 | `32a0b6c0721ca79b…` |
| 31 | `scripts/verify_manifest.py` | 1888 | `62b37c32a629b349…` |
| 32 | `templates/qwen35_egyptian_nothink.jinja` | 7585 | `22e67fd2f9b2fc41…` |
| 33 | `tests/test_smoke.py` | 37107 | `d52cc9f167381d32…` |

## التحقق

```bash
# تحقق إن كل ملف في النسخة مطابق لبصمة SHA-256 في الـ MANIFEST
python scripts/verify_manifest.py
```

أو يدوياً:

```bash
python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('scripts/exam/grader.py').read_bytes()).hexdigest())"
```
