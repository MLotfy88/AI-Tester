# Final AI Test — Manifest النسخة المرجعية

- **تاريخ النسخة:** 2026-11-07 23:07 UTC
- **مصدر النسخ:** مجلد المشروع `AI Online Tester` (نسخة مطابقة للملفات وقت النسخ)
- **عدد الملفات:** 33

| # | الملف | الحجم (بايت) | SHA-256 |
|---|---|---|---|
| 1 | `config/device_profile.yaml` | 1266 | `d2c3b7a13faa89bb…` |
| 2 | `config/exam.yaml` | 9264 | `c4645f718ca9ced7…` |
| 3 | `config/model_overrides.yaml` | 3285 | `a73514d321439907…` |
| 4 | `EXAM-PAPER-v1.md` | 57251 | `a0d8e9544732f3c1…` |
| 5 | `GRADING-ERRORS-AND-FIXES.md` | 58978 | `b7269f4e459eba8e…` |
| 6 | `HF-Model-Selection-Workflow.md` | 93388 | `0726072494064391…` |
| 7 | `kaggle/build_kernel.py` | 8982 | `84594acb64f5e885…` |
| 8 | `kaggle/kernel_main.py` | 10618 | `6132f7599d8afc68…` |
| 9 | `kaggle/run_on_kaggle.py` | 9978 | `bf40bfefa80abd58…` |
| 10 | `prompts/owner_system_prompt.txt` | 4296 | `0e885ad517ca9056…` |
| 11 | `README.md` | 7249 | `e2f1e20dda152d48…` |
| 12 | `scripts/build_exam_core.py` | 15294 | `0785e12143cb537d…` |
| 13 | `scripts/build_final_reference.py` | 11698 | `388281f9118f505d…` |
| 14 | `scripts/common.py` | 5615 | `305070fdbcfaca91…` |
| 15 | `scripts/exam/__init__.py` | 87 | `dfca87523ccd5c11…` |
| 16 | `scripts/exam/axis1.py` | 12077 | `102fb487a4604441…` |
| 17 | `scripts/exam/axis2.py` | 11094 | `00b9607f8f247c30…` |
| 18 | `scripts/exam/axis34.py` | 15877 | `7f84755c57d0d5d0…` |
| 19 | `scripts/exam/grader.py` | 22989 | `7569b9e8ea5a2508…` |
| 20 | `scripts/exam/lib.py` | 10709 | `b11a42a60cf8f2a5…` |
| 21 | `scripts/exam_runner.py` | 31985 | `82d63c2ba33661e3…` |
| 22 | `scripts/excel_report.py` | 42507 | `f06e629729df955e…` |
| 23 | `scripts/fit_check.py` | 11714 | `fb464c1e1baa1c3b…` |
| 24 | `scripts/hf_resolver.py` | 13035 | `555c112ed3219512…` |
| 25 | `scripts/html_charts.py` | 63891 | `215d8148f6667778…` |
| 26 | `scripts/html_report.py` | 90682 | `f9d818ce9375c45b…` |
| 27 | `scripts/install_llamacpp.py` | 8917 | `775bac5d9c408d4f…` |
| 28 | `scripts/model_settings.py` | 14820 | `0854fd7576a56325…` |
| 29 | `scripts/references.py` | 13567 | `f9e725239d42f25d…` |
| 30 | `scripts/run_exam.py` | 33369 | `77e5deefa95b0646…` |
| 31 | `scripts/verify_manifest.py` | 1888 | `62b37c32a629b349…` |
| 32 | `templates/qwen35_egyptian_nothink.jinja` | 7585 | `22e67fd2f9b2fc41…` |
| 33 | `tests/test_smoke.py` | 39909 | `aeab40e75e5954de…` |

## التحقق

```bash
# تحقق إن كل ملف في النسخة مطابق لبصمة SHA-256 في الـ MANIFEST
python scripts/verify_manifest.py
```

أو يدوياً:

```bash
python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('scripts/exam/grader.py').read_bytes()).hexdigest())"
```
