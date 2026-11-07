# %% [markdown]
# # امتحان المساعد المصري — تشغيل على Kaggle GPU
#
# ده الـ notebook اللي بيتولّد تلقائياً من `kaggle/build_kernel.py` ومش بيتعدّل بالإيد.
# بيعمل الآتي:
# 1. يتأكد إن الكارت T4 (وإلا يوقف فوراً — نتايج على كارت تاني مضللة).
# 2. يحجز **ballast** رام وVRAM علشان يبقي المتاح زي جهازك المستهدف بالظبط.
# 3. يبني llama.cpp بـ CUDA (أو ينزّل release جاهز).
# 4. ينزّل موديلات GGUF من Hugging Face (نماذج **عامة فقط** — Kaggle Secrets بتتشال مع CLI push).
# 5. يشغّل نفس الـ 21 سؤال بنفس الإعدادات ويكتب Excel + HTML + summary.md في Output.
#
# ⚠ لم يُختبر على Kaggle من قبلنا بعد — لو حصل خطأ، اقرأ رسالته وعدّل ثم أعد التشغيل.

# %% [markdown]
# ## Cell: المعاملات + فك ضغط المشروع

# %%
import base64
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import zipfile

PARAMS = json.loads(__PARAMS_JSON__)
PROJECT_B64 = "__PROJECT_B64__"

WORK = pathlib.Path("/kaggle/working")
EXAM = WORK / "exam"
OUT = WORK / "exam-out"

print("المعاملات:")
for key, value in PARAMS.items():
    print(f"  {key} = {value}")

# فك ضغط المشروع (scripts / config / prompts / templates) جوه الـ notebook
if EXAM.exists():
    shutil.rmtree(EXAM, ignore_errors=True)
EXAM.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PROJECT_B64))) as zf:
    zf.extractall(EXAM)
files_count = sum(1 for _ in EXAM.rglob("*") if _.is_file())
print(f"✅ فك ضغط المشروع: {files_count} ملف في {EXAM}")

# %% [markdown]
# ## Cell: فحص الكارت (يفشل لو مش P100/T4)

# %%
def sh(cmd, **kwargs):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kwargs)


gpu_csv = sh(
    "nvidia-smi --query-gpu=name,memory.total,memory.used,compute_cap --format=csv,noheader"
).stdout.strip()
print("nvidia-smi:")
print(gpu_csv or "— مفيش GPU —")
first_line = (gpu_csv.splitlines() or [""])[0]
gpu_name = first_line.split(",")[0].strip()
gpu_cap = first_line.split(",")[-1].strip()

expected = [str(x).lower() for x in (PARAMS.get("gpu_expect") or [])]
if expected and not any(key in gpu_name.lower() for key in expected):
    raise SystemExit(
        f"❌ الكارت {gpu_name!r} مش المتوقع {expected}. "
        "اختار Accelerator صح من إعدادات الـ notebook أو أوقف لتجنب نتايج مضللة."
    )
if not gpu_name:
    raise SystemExit("❌ مفيش GPU — فعّل Accelerator من إعدادات الـ notebook.")

# كارت واحد بس: الـ T4 x2 ذاكرتهم مش بتتجمع
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

cuda_arch = ""
if "t4" in gpu_name.lower() or gpu_cap.startswith("7."):
    cuda_arch = "75"
print(f"✅ GPU: {gpu_name} · compute {gpu_cap} · CUDA arch={cuda_arch or 'auto'}")

# %% [markdown]
# ## Cell: حجز RAM ballast (محاكاة 15.9 GiB متاحة)

# %%
import numpy as np  # noqa: E402

target_ram_gib = float(PARAMS.get("ram_gib") or 15.9)
# threads الفعلية على Kaggle (مش target) — تشغيل 8 threads على 4 vCPU بيعمل
# oversubscription ويبطّأ القياس. بنسجّل الفعلي في التقرير.
actual_threads = max(1, min(int(PARAMS.get("threads") or 8), os.cpu_count() or 8))
print(f"threads: target={PARAMS.get('threads')} · actual={actual_threads} (cpu_count={os.cpu_count()})")
meminfo = {}
with open("/proc/meminfo", encoding="utf-8") as fh:
    for line in fh:
        key, _, rest = line.partition(":")
        meminfo[key.strip()] = int(rest.strip().split()[0])
total_ram_gib = meminfo.get("MemTotal", 0) / 1024.0 / 1024.0
reserve_gib = 1.0  # هامش صغير للنظام
alloc_gib = max(0.0, total_ram_gib - target_ram_gib - reserve_gib)
print(f"RAM: total={total_ram_gib:.1f} GiB · target={target_ram_gib} GiB · ballast={alloc_gib:.1f} GiB")

ram_blocks = []
need = int(alloc_gib * 1024**3)
chunk = 256 * 1024**2
while need > 0:
    size = min(chunk, need)
    ram_blocks.append(np.ones(size, dtype=np.uint8))  # ones ⇒ صفحات فعلية مش lazy
    need -= size
print(f"✅ RAM ballast محجوز: {sum(b.nbytes for b in ram_blocks) / 1024**3:.1f} GiB")

# %% [markdown]
# ## Cell: حجز VRAM ballast (محاكاة ميزانية 3.4 GiB)

# %%
import torch  # noqa: E402

target_vram_gib = float(PARAMS.get("vram_gib") or 3.4)
free_b, total_b = torch.cuda.mem_get_info()
print(f"VRAM قبل الحجز: free={free_b / 1024**3:.2f} GiB / total={total_b / 1024**3:.2f} GiB")

vram_blocks = []
margin_b = 0.30 * 1024**3  # سياق CUDA للعملية الحالية
target_b = target_vram_gib * 1024**3
while True:
    free_b, _ = torch.cuda.mem_get_info()
    size = int(free_b - margin_b - target_b)
    if size < 32 * 1024**2:
        break
    vram_blocks.append(torch.empty(min(size, 256 * 1024**2), dtype=torch.uint8, device="cuda"))
free_b, _ = torch.cuda.mem_get_info()
print(
    f"✅ VRAM ballast: {sum(b.numel() for b in vram_blocks) / 1024**3:.1f} GiB محجوز · "
    f"المتاح الآن {free_b / 1024**3:.2f} GiB (المستهدف {target_vram_gib})"
)

# %% [markdown]
# ## Cell: تثبيت المتطلبات + بناء llama.cpp بـ CUDA

# %%
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pyyaml", "openpyxl"], check=False)

llama_dir = WORK / "llama"
install_cmd = [
    sys.executable,
    str(EXAM / "scripts" / "install_llamacpp.py"),
    "--dir",
    str(llama_dir),
    "--tag",
    str(PARAMS.get("llama_tag") or "latest"),
    "--backend",
    "cuda",
    "--cuda-arch",
    cuda_arch,
    "--jobs",
    "4",
]
print("$", " ".join(install_cmd))
proc = subprocess.run(install_cmd, capture_output=True, text=True)
print(proc.stdout[-4000:])
if proc.returncode != 0:
    print(proc.stderr[-4000:])
    raise SystemExit(f"❌ فشل تثبيت llama.cpp (exit={proc.returncode})")
server_bin = llama_dir / "bin" / "llama-server"
if not server_bin.exists():
    raise SystemExit(f"❌ llama-server مش موجود في {server_bin}")
print("✅ llama-server:", server_bin)

# %% [markdown]
# ## Cell: تشغيل الامتحان (21 سؤال — نفس ورقة الامتحان ونفس الإعدادات)

# %%
# ── ملف جهاز محاكاة: نفس مواصفات جهازك (Quadro M4000M / 15.9 GiB RAM)
#    مع ميزانيات الـ VRAM/RAM اللي اتحجزت فوق. الحسابات النظرية (fit) بتتم
#    على مواصفات جهازك، والقياس الفعلي على T4.
import yaml  # noqa: E402

profile_src = EXAM / "config" / "device_profile.yaml"
profile = yaml.safe_load(profile_src.read_text(encoding="utf-8")) or {}
budgets = profile.setdefault("budgets", {})
budgets["vram_budget_gib"] = target_vram_gib
budgets.setdefault("compute_buffer_gib", 0.3)
ram_cfg = profile.setdefault("ram", {})
ram_cfg["usable_gib"] = target_ram_gib
profile["name"] = "kaggle-t4-simulation"
profile["simulation"] = {
    "actual_gpu": gpu_name,
    "actual_gpu_memory_gib": round(total_b / 1024**3, 2),
    "actual_cpu_threads": actual_threads,
    "target_vram_budget_gib": target_vram_gib,
    "target_ram_gib": target_ram_gib,
    "note": "VRAM/RAM متقيدين بميزانية جهازك؛ الكارت نفسه T4 (أسرع من M4000M).",
}
profile_path = WORK / "device_profile.yaml"
profile_path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"✅ device_profile: {profile_path}")

runner_label = (
    f"Kaggle GPU T4×2 — {gpu_name} · محاكاة VRAM {target_vram_gib} GiB / "
    f"RAM {target_ram_gib} GiB · threads {actual_threads}"
)

exam_cmd = [
    sys.executable,
    str(EXAM / "scripts" / "run_exam.py"),
    "--models",
    str(PARAMS["models"]),
    "--quant",
    str(PARAMS.get("quant") or "Q4_K_M"),
    "--ctx",
    str(PARAMS.get("ctx") or 4096),
    "--kv",
    str(PARAMS.get("kv") or "f16"),
    "--threads",
    str(actual_threads),
    "--device",
    "CUDA0",
    "--runner-kind",
    "kaggle_gpu",
    "--runner-label",
    runner_label,
    "--runner-gpu",
    gpu_name,
    "--device-profile",
    str(profile_path),
    "--server",
    str(server_bin),
    "--out",
    str(OUT),
    "--policy",
    str(PARAMS.get("policy") or "paper"),
    "--max-gib",
    str(PARAMS.get("max_gib") or 20),
    "--model-timeout",
    str(PARAMS.get("model_timeout") or 300),
    "--total-timeout",
    str(PARAMS.get("total_timeout") or 600),
]
if PARAMS.get("template_mode"):
    exam_cmd += ["--template-mode", str(PARAMS["template_mode"])]
if PARAMS.get("flash_attn"):
    exam_cmd += ["--flash-attn", str(PARAMS["flash_attn"])]
env = {**os.environ, "PYTHONUNBUFFERED": "1", "HF_HUB_DISABLE_PROGRESS_BARS": "1"}
print("$", " ".join(exam_cmd))
started = time.time()
proc = subprocess.run(exam_cmd, cwd=str(EXAM), env=env, capture_output=True, text=True)
print(proc.stdout[-8000:])
if proc.stderr:
    print("stderr:", proc.stderr[-4000:])
print(f"exit={proc.returncode} · المدة {(time.time() - started) / 60:.1f} دقيقة")

# %% [markdown]
# ## Cell: تجميع المخرجات (Excel + HTML + logs) في Output

# %%
dest = WORK / "exam-out-final"
if dest.exists():
    shutil.rmtree(dest, ignore_errors=True)
shutil.copytree(OUT, dest, dirs_exist_ok=True)
(dest / "kaggle-gpu.txt").write_text(
    f"gpu={gpu_name}\ncompute_cap={gpu_cap}\ncuda_arch={cuda_arch}\n"
    f"vram_target_gib={target_vram_gib}\nram_target_gib={target_ram_gib}\n"
    f"actual_cpu_threads={actual_threads}\n"
    f"vram_free_after_ballast_gib={free_b / 1024**3:.2f}\n"
    f"runner_label={runner_label}\n"
    f"device_profile={profile_path}\n"
    f"exit_code={proc.returncode}\nseconds={(time.time() - started):.0f}\n",
    encoding="utf-8",
)

print("\n### الملفات في Output:")
for path in sorted(WORK.rglob("*")):
    if path.is_file():
        print(f"  {path} ({path.stat().st_size / 1024:.1f} KiB)")

summary = dest / "summary.md"
if summary.exists():
    print("\n===== summary.md =====\n")
    print(summary.read_text(encoding="utf-8")[:12000])

if proc.returncode != 0:
    raise SystemExit(f"❌ التشغيل خلص بفشل (exit={proc.returncode}) — راجع اللوج فوق.")
print("✅ خلص بنجاح — نزّل الملفات من تبويب Output.")
