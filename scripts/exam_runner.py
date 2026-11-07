"""تشغيل الامتحان على llama-server وجمع الإجابات في الذاكرة.

لا يكتب أي JSON: يعيد dict فيه الإجابات + بيانات التشغيل، والـ orchestrator
هو اللي يمرّرها للمصحّح ثم لملفات Excel/HTML.

الوظائف الأساسية:
  · يبني أمر llama-server حسب الأعلام المدعومة فعلاً في النسخة المثبتة.
  · ينتظر /health لحد ما السيرفر يبقى جاهز.
  · يبعت الأسئلة واحداً واحداً على /v1/chat/completions.
  · يقيس peak RSS ووقت كل سؤال، ويوقف السيرفر وينضّف العمليات دايماً.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from common import human_bytes, load_exam, now_iso, sha256_file, slugify, tail_text, write_text

# نفس الـ logger اللي بيستخدمه run_exam.py ("exam") ⇒ التحذيرات بتوصل لـ run.log والطرفية.
log = logging.getLogger("exam")


# --------------------------------------------------------------------------- أدوات
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _server_help(server: Path) -> str:
    try:
        proc = subprocess.run(
            [str(server), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except Exception:
        return ""


def _has_flag(help_text: str, flag: str) -> bool:
    """لو الـ help فاضي نفترض إن الأعلام الأساسية موجودة."""
    if not help_text.strip():
        return True
    return flag in help_text


def _server_version(server: Path) -> str:
    for args in (["--version"], ["-v"]):
        try:
            proc = subprocess.run(
                [str(server), *args],
                capture_output=True,
                text=True,
                timeout=45,
            )
            out = ((proc.stdout or "") + (proc.stderr or "")).strip()
            if out:
                return out.splitlines()[0][:300]
        except Exception:
            continue
    return "unknown"


def _rss_mib(pid: int) -> int:
    """ذاكرة العملية + أبنائها. psutil أولاً ثم /proc كاحتياط."""
    try:
        import psutil

        proc = psutil.Process(pid)
        total = int(proc.memory_info().rss)
        for child in proc.children(recursive=True):
            try:
                total += int(child.memory_info().rss)
            except Exception:
                continue
        return int(total / (1024 * 1024))
    except Exception:
        pass
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="replace")
        for line in status.splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


class _RssMonitor:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.peak = 0
        self.peak_vram_mib = 0
        self.gpu_name = ""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(0.75):
            value = _rss_mib(self.pid)
            if value > self.peak:
                self.peak = value
            # ذروة VRAM الحقيقية من الكارت
            gpu = _gpu_memory_mib()
            if gpu:
                used = int(gpu.get("total_mib") or 0) - sum(
                    int(g.get("free_mib") or 0) for g in gpu.get("gpus") or []
                )
                if used > self.peak_vram_mib:
                    self.peak_vram_mib = used
                if not self.gpu_name and gpu.get("gpus"):
                    self.gpu_name = str((gpu.get("gpus") or [{}])[0].get("name") or "")

    def start(self) -> "_RssMonitor":
        self._thread.start()
        return self

    def stop(self) -> int:
        self._stop.set()
        self._thread.join(timeout=5)
        value = _rss_mib(self.pid)
        return max(self.peak, value)


def _other_inference_servers(own_pid: int | None = None) -> list[dict]:
    """يكشف عمليات استدلال تانية شغالة (llama-server / llama-cli / Ollama …).

    ده **مهم جداً** في أي benchmark: لو LM Studio (أو أي سيرفر تاني) فاتح نفس
    الموديل على نفس الكارت، السرعة المقيسة بتنزل للنص (15 → 5 tok/s) من غير ما
    حاجة في التقرير تقولك إن الرقم ده اتقاس في ظروف مزحومة.
    """
    found: list[dict] = []
    wanted = ("llama-server.exe", "llama-cli.exe", "ollama.exe")
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                pid = int(proc.info.get("pid") or 0)
                if not pid or pid == own_pid:
                    continue
                pname = str(proc.info.get("name") or "").lower()
                cmd = " ".join(proc.info.get("cmdline") or [])
                if pname in wanted:
                    found.append({"pid": pid, "name": pname, "cmd": cmd[:220]})
            except Exception:
                continue
        if found:
            return found
    except Exception:
        pass
    # بديل بدون psutil: tasklist
    try:
        proc = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=25,
        )
        for line in (proc.stdout or "").splitlines():
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) < 2:
                continue
            image = parts[0].lower()
            if image not in wanted:
                continue
            try:
                pid = int(parts[1])
            except ValueError:
                continue
            if pid == own_pid:
                continue
            found.append({"pid": pid, "name": parts[0], "cmd": ""})
    except Exception:
        pass
    return found


def _gpu_memory_mib() -> dict:
    """قراءة VRAM الحقيقية من nvidia-smi (لو كارت NVIDIA موجود).

    الأرقام دي **مقيسة فعلياً** من الكارت — مش محسوبة. بتتحقق إن الميزانية
    اللي في device_profile.yaml (3.4 GiB) كفاية ولا لأ.
    """
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return {}
    if proc.returncode != 0:
        return {}
    gpus: list[dict] = []
    for line in (proc.stdout or "").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            gpus.append(
                {
                    "name": parts[0],
                    "total_mib": int(float(parts[1])),
                    "used_mib": int(float(parts[2])),
                    "free_mib": int(float(parts[3])),
                    "utilization_pct": int(float(parts[4])) if len(parts) > 4 else None,
                }
            )
        except ValueError:
            continue
    if not gpus:
        return {}
    return {"gpus": gpus, "total_mib": sum(g["total_mib"] for g in gpus)}


def _gpu_memory_after_load(pid: int) -> dict:
    """VRAM بعد تحميل الموديل:_used = مجموع كل الكروت − الباقي."""
    return _gpu_memory_mib()


def _stats(values: list[float]) -> dict:
    """ملخص إحصائي بسيط لمجموعة قيم."""
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return {}
    n = len(vals)
    median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return {
        "n": n,
        "min": round(vals[0], 2),
        "max": round(vals[-1], 2),
        "avg": round(sum(vals) / n, 2),
        "median": round(median, 2),
        "p95": round(vals[min(n - 1, int(n * 0.95))], 2),
    }


def _perf_summary(
    requests_meta: list[dict], seconds_total: float, startup_seconds: float
) -> dict:
    """ملخص الأداء **المقيس فعلياً** على الكارت اللي اشتغل عليه.

    الأرقام دي مصدرها `timings` من llama.cpp نفسه (سرعة توليد/معالجة حقيقية)
    + أوقات الطلبات الفعلية. مفيش أي تقدير رياضي هنا.
    """
    tg = [r.get("tg_tps_real") for r in requests_meta if r.get("tg_tps_real")]
    pp = [r.get("pp_tps_real") for r in requests_meta if r.get("pp_tps_real")]
    secs = [r.get("seconds") for r in requests_meta if r.get("seconds")]
    prompt_ms = [r.get("prompt_ms") for r in requests_meta if r.get("prompt_ms")]
    predicted_ms = [r.get("predicted_ms") for r in requests_meta if r.get("predicted_ms")]
    chars = [r.get("chars") for r in requests_meta if r.get("chars")]
    tokens = [r.get("tokens") for r in requests_meta if r.get("tokens")]
    total_tokens = sum(int(t) for t in tokens) if tokens else 0

    # زمن أول استجابة تقريبي: زمن معالجة الـ prompt + أول جزء من التوليد.
    ttft = [
        (float(p) + float(g) / 1000.0)
        for p, g in zip(prompt_ms, predicted_ms)
        if p is not None and g is not None
    ]

    out: dict = {
        "measured": True,
        "source": "llama.cpp timings + أوقات الطلبات الفعلية",
        "startup_seconds": round(startup_seconds, 1),
        "seconds_total": round(seconds_total, 1),
        "requests_count": len(requests_meta),
        "total_generated_tokens": total_tokens,
    }
    if tg:
        out["tg_tps"] = _stats(tg)
    if pp:
        out["pp_tps"] = _stats(pp)
    if secs:
        out["request_seconds"] = _stats(secs)
    if prompt_ms:
        out["prompt_ms"] = _stats(prompt_ms)
    if predicted_ms:
        out["predicted_ms"] = _stats(predicted_ms)
    if ttft:
        out["ttft_ms"] = _stats(ttft)
    if chars:
        out["chars_total"] = sum(int(c) for c in chars)
        if seconds_total > 0:
            out["chars_per_second"] = round(sum(int(c) for c in chars) / seconds_total, 1)
    if total_tokens and seconds_total > 0:
        out["tokens_per_second_overall"] = round(total_tokens / seconds_total, 2)
    return out


def _stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    try:
        import psutil

        parent = psutil.Process(proc.pid)
        kids = parent.children(recursive=True)
        for child in kids:
            try:
                child.terminate()
            except Exception:
                pass
        parent.terminate()
        try:
            parent.wait(timeout=15)
        except Exception:
            for child in kids:
                try:
                    child.kill()
                except Exception:
                    pass
            try:
                parent.kill()
            except Exception:
                pass
    except Exception:
        try:
            proc.terminate()
            proc.wait(timeout=15)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _wait_health(proc: subprocess.Popen, port: int, timeout: float, log_path: Path) -> None:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"llama-server خرج أثناء التحميل (code={proc.returncode}).\n"
                f"{tail_text(log_path, 4000)}"
            )
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except Exception as exc:
            last = type(exc).__name__
        time.sleep(1.5)
    raise RuntimeError(
        f"llama-server مش جاهز بعد {int(timeout)} ثانية (آخر حالة: {last}).\n"
        f"{tail_text(log_path, 4000)}"
    )


def _post_chat(port: int, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _build_command(
    server: Path,
    gguf_path: Path,
    *,
    port: int,
    ctx: int,
    threads: int,
    ngl: int,
    kv: str,
    template_path: Path,
    help_text: str,
    device: str = "",
    flash_attn: str = "",
    extra_args: list[str] | None = None,
) -> list[str]:
    cmd = [
        str(server),
        "-m",
        str(gguf_path),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-c",
        str(ctx),
        "-t",
        str(threads),
        "-ngl",
        str(ngl),
        "--jinja",
    ]
    if _has_flag(help_text, "--no-webui"):
        cmd.append("--no-webui")
    if _has_flag(help_text, "-np"):
        cmd += ["-np", "1"]
    if _has_flag(help_text, "--chat-template-file"):
        cmd += ["--chat-template-file", str(template_path)]
    if _has_flag(help_text, "--chat-template-kwargs"):
        cmd += ["--chat-template-kwargs", '{"enable_thinking": false}']
    if device and _has_flag(help_text, "--device"):
        cmd += ["--device", device]
    flash = flash_attn or (kv if kv and kv.lower() != "f16" else "")
    if kv and kv.lower() != "f16":
        if _has_flag(help_text, "--cache-type-k"):
            cmd += ["--cache-type-k", kv]
        if _has_flag(help_text, "--cache-type-v"):
            cmd += ["--cache-type-v", kv]
    if flash and _has_flag(help_text, "--flash-attn"):
        cmd += ["--flash-attn", flash]
    for item in extra_args or []:
        if item:
            cmd.append(item)
    return cmd


# --------------------------------------------------------------------------- الواجهة
def run_exam(
    *,
    gguf_path: str | Path,
    server_bin: str | Path,
    template_path: str | Path,
    system_prompt_path: str | Path,
    questions: list[dict],
    settings: dict,
    out_dir: str | Path,
    slug: str | None = None,
    ctx: int = 4096,
    threads: int = 4,
    kv: str = "f16",
    ngl: int = 0,
    port: int | None = None,
    startup_timeout: float = 900.0,
    request_timeout: float = 900.0,
    model_timeout: float = 10800.0,
    limit: int = 0,
    device: str = "",
    flash_attn: str = "",
    extra_args: list[str] | None = None,
) -> dict:
    gguf_path = Path(gguf_path).resolve()
    server_bin = Path(server_bin).resolve()
    template_path = Path(template_path).resolve()
    system_prompt_path = Path(system_prompt_path).resolve()
    out_root = Path(out_dir).resolve()
    logs_dir = out_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(slug or gguf_path.stem)
    log_path = logs_dir / f"{slug}.server.log"

    for path, label in (
        (gguf_path, "ملف GGUF"),
        (server_bin, "llama-server"),
        (template_path, "القالب"),
        (system_prompt_path, "الـ system prompt"),
    ):
        if not path.exists():
            raise FileNotFoundError(f"{label} مش موجود: {path}")
    if not questions:
        raise ValueError("قائمة الأسئلة فاضية.")

    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    temperature = float(settings.get("temperature", 0.0))
    top_p = float(settings.get("top_p", 1.0))
    seed = int(settings.get("seed", 20261106))
    max_tokens = int(settings.get("max_tokens", 1200))
    # معاملات اختيارية (توصيات المطوّر) — بتفضل None في وضع الامتحان القياسي
    top_k = settings.get("top_k")
    min_p = settings.get("min_p")
    repeat_penalty = settings.get("repeat_penalty")

    help_text = _server_help(server_bin)
    version = _server_version(server_bin)
    use_port = int(port or 0) or _free_port()
    cmd = _build_command(
        server_bin,
        gguf_path,
        port=use_port,
        ctx=ctx,
        threads=threads,
        ngl=ngl,
        kv=kv,
        template_path=template_path,
        help_text=help_text,
        device=device,
        flash_attn=flash_attn,
        extra_args=extra_args,
    )

    started_at = now_iso()
    t_start = time.monotonic()
    # الموعد النهائي للموديل يشمل تحميل الموديل نفسه، عشان ما يتجاوزش
    # مهلة التشغيل الكلي في الـ workflow (330 دقيقة) أو حد الـ job.
    deadline = t_start + model_timeout
    proc: subprocess.Popen | None = None
    monitor: _RssMonitor | None = None
    answers: dict[str, dict] = {}
    requests_meta: list[dict] = []
    fatal_error = ""
    startup_seconds = 0.0

    # ── فحص مسبق: هل فيه عملية استدلال تانية شغالة على نفس الكارت؟
    #    لو فيه، السرعة والزمن المقيسين هيكونوا مضلّلين (الكارت بينقسم).
    #    بنعيد الفحص مرة ثانية بعد مهلة قصيرة عشان نتجنّب تحذير كاذب بسبب
    #    سيرفر الموديل السابق اللي لسه بيخرج.
    competing = _other_inference_servers(os.getpid())
    if competing:
        time.sleep(3.0)
        competing = _other_inference_servers(os.getpid())
    gpu_before = _gpu_memory_mib()
    if competing:
        names = "، ".join(f"{c.get('name')} (pid {c.get('pid')})" for c in competing)
        log.warning(
            "⚠ فيه عمليات استدلال تانية شغالة: %s — "
            "السرعة والزمن المقيسين هيكونوا مضلّلين لو هي شاركت في نفس الكارت. "
            "أوقفها قبل ما تاخد الأرقام على محمل الجد.",
            names,
        )
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as log_fh:
            log_fh.write("$ " + " ".join(cmd) + "\n")
            log_fh.flush()
            proc = subprocess.Popen(
                cmd,
                cwd=str(server_bin.parent),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=dict(os.environ),
            )
        monitor = _RssMonitor(proc.pid).start()
        startup_wait = max(1.0, min(startup_timeout, model_timeout))
        _wait_health(proc, use_port, startup_wait, log_path)
        # زمن تجهيز الموديل (تحميله على الكارت) — رقم حقيقي ومهم للتجربة.
        startup_seconds = time.monotonic() - t_start

        consecutive_errors = 0
        selected = questions[:limit] if limit and limit > 0 else questions

        for index, question in enumerate(selected, 1):
            qid = str(question["id"])
            prompt = str(question["prompt"])
            t0 = time.monotonic()

            if fatal_error:
                answers[qid] = {
                    "answer": "",
                    "reasoning": "",
                    "finish": "ERROR",
                    "usage": {},
                    "seconds": 0.0,
                    "error": fatal_error,
                }
                continue
            if time.monotonic() > deadline:
                fatal_error = f"تجاوز وقت الموديل ({int(model_timeout / 60)} دقيقة)"
                answers[qid] = {
                    "answer": "",
                    "reasoning": "",
                    "finish": "TIMEOUT",
                    "usage": {},
                    "seconds": 0.0,
                    "error": fatal_error,
                }
                continue
            if proc.poll() is not None:
                fatal_error = f"llama-server وقف فجأة (code={proc.returncode})"
                answers[qid] = {
                    "answer": "",
                    "reasoning": "",
                    "finish": "ERROR",
                    "usage": {},
                    "seconds": 0.0,
                    "error": fatal_error,
                }
                continue

            payload = {
                "model": "local",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "top_p": top_p,
                "seed": seed,
                "max_tokens": max_tokens,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            if top_k is not None:
                payload["top_k"] = int(top_k)
            if min_p is not None:
                payload["min_p"] = float(min_p)
            if repeat_penalty is not None:
                payload["repeat_penalty"] = float(repeat_penalty)

            text = ""
            reasoning = ""
            finish = "ERROR"
            usage: dict = {}
            timings: dict = {}
            error = ""
            # مهلة الطلب ما تتجاوزش الموعد النهائي للموديل — عشان طلب واحد
            # بطيء ما يخرقش حدود الـ workflow (6 ساعات) ولا مهلة الموديل.
            left = deadline - time.monotonic()
            if left <= 1.0:
                fatal_error = f"تجاوز وقت الموديل ({int(model_timeout / 60)} دقيقة)"
                answers[qid] = {
                    "answer": "",
                    "reasoning": "",
                    "finish": "TIMEOUT",
                    "usage": {},
                    "seconds": 0.0,
                    "error": fatal_error,
                }
                continue
            req_timeout = max(1.0, min(request_timeout, left))
            try:
                resp = _post_chat(use_port, payload, req_timeout)
                choice = (resp.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = str(message.get("content") or "")
                reasoning = str(
                    message.get("reasoning_content")
                    or message.get("reasoning")
                    or ""
                )
                finish = str(choice.get("finish_reason") or "")
                usage = resp.get("usage") or {}
                timings = resp.get("timings") or {}
                consecutive_errors = 0
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:400]
                error = f"HTTP {exc.code}: {body}"
                finish = "ERROR"
                consecutive_errors += 1
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                finish = "ERROR"
                consecutive_errors += 1

            seconds = round(time.monotonic() - t0, 2)
            answers[qid] = {
                "answer": text,
                "reasoning": reasoning,
                "finish": finish,
                "usage": usage,
                "timings": timings,
                "seconds": seconds,
                "error": error,
            }
            tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            tps = None
            if tokens and seconds > 0:
                tps = round(float(tokens) / seconds, 2)
            # ── الأرقام الحقيقية من محرّك llama.cpp نفسه (timings):
            #    predicted_per_second = سرعة التوليد الفعلية على الكارت
            #    prompt_per_second    = سرعة معالجة الـ prompt (prompt eval)
            #    predicted_ms/prompt_ms = زمن التوليد/المعالجة
            timings = timings or {}
            tg_real = timings.get("predicted_per_second")
            pp_real = timings.get("prompt_per_second")
            requests_meta.append(
                {
                    "id": qid,
                    "index": index,
                    "seconds": seconds,
                    "tokens": tokens,
                    "tps": tps,
                    "tg_tps_real": round(float(tg_real), 2) if isinstance(tg_real, (int, float)) else None,
                    "pp_tps_real": round(float(pp_real), 2) if isinstance(pp_real, (int, float)) else None,
                    "prompt_ms": timings.get("prompt_ms"),
                    "predicted_ms": timings.get("predicted_ms"),
                    "prompt_n": timings.get("prompt_n"),
                    "predicted_n": timings.get("predicted_n"),
                    "finish": finish,
                    "chars": len(text),
                    "error": error,
                }
            )

            print(
                f"[{index:02d}/{len(selected)}] {qid:<3} {finish:<9} "
                f"{seconds:6.1f}s  {len(text):4d} حرف  {error[:80]}",
                flush=True,
            )

            if consecutive_errors >= 3 and not fatal_error:
                fatal_error = f"{consecutive_errors} طلبات فاشلة متتالية: {error[:160]}"

    finally:
        peak = monitor.stop() if monitor else 0
        peak_vram = monitor.peak_vram_mib if monitor else 0
        gpu_name = monitor.gpu_name if monitor else ""
        _stop_process(proc)

    finished_at = now_iso()
    seconds_total = round(time.monotonic() - t_start, 1)
    runtime = {
        "started_at": started_at,
        "finished_at": finished_at,
        "seconds_total": seconds_total,
        "peak_rss_mib": int(peak),
        "peak_vram_mib": int(peak_vram),
        "gpu_name": gpu_name,
        "port": use_port,
        "cmd": cmd,
        "server_log": str(log_path),
        "llama_version": version,
        "template_sha256": sha256_file(template_path),
        "system_prompt_sha256": sha256_file(system_prompt_path),
        "system_prompt_chars": len(system_prompt),
        "ctx": ctx,
        "threads": threads,
        "kv": kv,
        "ngl": ngl,
        "device": device,
        "flash_attn": flash_attn,
        "extra_args": list(extra_args or []),
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "repeat_penalty": repeat_penalty,
        "seed": seed,
        "max_tokens": max_tokens,
        "request_timeout": request_timeout,
        "model_timeout": model_timeout,
        "gguf_bytes": gguf_path.stat().st_size,
        "gguf_size_human": human_bytes(gguf_path.stat().st_size),
        "requests": requests_meta,
        "perf": _perf_summary(requests_meta, seconds_total, startup_seconds),
        "memory": {
            "peak_rss_mib": int(peak),
            "peak_vram_mib": int(peak_vram),
            "gpu_name": gpu_name,
            "source": "nvidia-smi (ذروة VRAM) + RSS (ذاكرة العملية)",
        },
        "gpu_contention": {
            "competing_processes": competing,
            "gpu_before": gpu_before,
            "note": (
                "فيه عمليات استدلال تانية كانت شغالة وقت القياس — السرعة والزمن "
                "المقيسين ممكن يكونوا أقل من الحقيقي."
                if competing
                else ""
            ),
        },
        "fatal_error": fatal_error,
    }
    return {"answers": answers, "runtime": runtime}


# --------------------------------------------------------------------------- CLI
def main() -> int:
    ap = argparse.ArgumentParser(description="تشغيل أسئلة الامتحان على llama-server")
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--server", default=".llama/bin/llama-server")
    ap.add_argument("--template", default="templates/qwen35_egyptian_nothink.jinja")
    ap.add_argument("--system-prompt", default="prompts/owner_system_prompt.txt")
    ap.add_argument("--exam", default="config/exam.yaml")
    ap.add_argument("--out", default="out")
    ap.add_argument("--slug", default="")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--kv", default="f16")
    ap.add_argument("--ngl", type=int, default=0)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--startup-timeout", type=float, default=900)
    ap.add_argument("--request-timeout", type=float, default=900)
    ap.add_argument("--model-timeout", type=float, default=10800)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="", help="device للـ offload (مثال: Vulkan0، CUDA0)")
    ap.add_argument("--flash-attn", default="", choices=["", "on", "off", "auto"])
    ap.add_argument("--extra-server-args", default="", help="أعلام llama-server إضافية مفصولة بمسافات")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    exam = load_exam()
    questions = exam["questions"]
    extra_args = args.extra_server_args.split() if args.extra_server_args else []
    if args.dry_run:
        work = _build_command(
            Path(args.server),
            Path(args.gguf),
            port=args.port or _free_port(),
            ctx=args.ctx,
            threads=args.threads,
            ngl=args.ngl,
            kv=args.kv,
            template_path=Path(args.template),
            help_text=_server_help(Path(args.server)) if Path(args.server).exists() else "",
            device=args.device,
            flash_attn=args.flash_attn,
            extra_args=extra_args,
        )
        print("$ " + " ".join(work))
        print(f"questions={len(questions)} ctx={args.ctx} temp=0 seed=20261106")
        return 0

    result = run_exam(
        gguf_path=args.gguf,
        server_bin=args.server,
        template_path=args.template,
        system_prompt_path=args.system_prompt,
        questions=questions,
        settings=exam.get("settings") or {},
        out_dir=args.out,
        slug=args.slug or Path(args.gguf).stem,
        ctx=args.ctx,
        threads=args.threads,
        kv=args.kv,
        ngl=args.ngl,
        port=args.port or None,
        startup_timeout=args.startup_timeout,
        request_timeout=args.request_timeout,
        model_timeout=args.model_timeout,
        limit=args.limit,
        device=args.device,
        flash_attn=args.flash_attn,
        extra_args=extra_args,
    )
    rt = result["runtime"]
    print(
        f"خلص: {len(result['answers'])} إجابة · {rt['seconds_total']}s · "
        f"peak RSS {rt['peak_rss_mib']} MiB · log {rt['server_log']}"
    )
    if rt["fatal_error"]:
        print("⚠ " + rt["fatal_error"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
