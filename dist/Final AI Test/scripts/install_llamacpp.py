"""تثبيت llama.cpp (CPU) على GitHub runner.

الترتيب:
  1) لو LLAMA_SERVER_BIN موجود أو .llama/bin/llama-server موجود ⇒ استخدمه.
  2) جرّب release جاهز Ubuntu x64 من GitHub (أسرع).
  3) لو فشل ⇒ ابنِ من المصدر بـ CMake (مضمون أكثر).

كل الملفات بتتكتب في مجلد واحد (bin) علشان الـ shared libraries تتلاقى.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from common import run_cmd, tail_text, write_text


def _gh_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "exam-runner/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "exam-runner/1.0"})
    with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as fh:
        shutil.copyfileobj(resp, fh, length=1024 * 1024)


def _find_server(root: Path) -> Path | None:
    names = ("llama-server", "llama-server.exe")
    for name in names:
        hits = sorted(root.rglob(name))
        if hits:
            return hits[0]
    return None


def _collect_bin(server: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    src_dir = server.parent
    for item in src_dir.iterdir():
        if item.is_file():
            target = dest / item.name
            shutil.copy2(item, target)
    target_server = dest / server.name
    st = target_server.stat()
    target_server.chmod(st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return target_server


def try_release(
    tag: str,
    dest: Path,
    log: Path,
    *,
    backend: str = "cpu",
    cuda_arch: str = "",
) -> Path | None:
    try:
        if tag and tag not in ("latest", "master", ""):
            url = f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{tag}"
            rel = _gh_json(url)
        else:
            rel = _gh_json("https://api.github.com/repos/ggml-org/llama.cpp/releases/latest")

        assets = rel.get("assets") or []
        candidates = []
        want_cuda = backend == "cuda"
        for a in assets:
            name = str(a.get("name", ""))
            low = name.lower()
            if not low.endswith(".zip"):
                continue
            if "ubuntu" not in low and "linux" not in low:
                continue
            if "x64" not in low and "x86_64" not in low:
                continue
            if want_cuda:
                if "cuda" not in low:
                    continue
            else:
                if any(x in low for x in ("cuda", "vulkan", "rocm", "sycl", "musl", "arm64")):
                    continue
            candidates.append(a)
        if not candidates:
            print(f"— مفيش release asset متوافق (ubuntu x64 {backend}) —")
            return None
        asset = sorted(candidates, key=lambda a: int(a.get("size") or 0))[0]
        print(f"release: {rel.get('tag_name')} · asset: {asset.get('name')}")
        zpath = dest.parent / "llama-release.zip"
        zpath.parent.mkdir(parents=True, exist_ok=True)
        _download(str(asset["browser_download_url"]), zpath)
        extract = dest.parent / "release_extract"
        shutil.rmtree(extract, ignore_errors=True)
        extract.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(extract)
        server = _find_server(extract)
        if not server:
            print("— الـ zip مفيهوش llama-server —")
            return None
        final = _collect_bin(server, dest)
        write_text(
            dest.parent / "llama_version.txt",
            f"source=release\nrelease_tag={rel.get('tag_name')}\nasset={asset.get('name')}\n"
            f"backend={backend}\ncuda_arch={cuda_arch}\n",
        )
        shutil.rmtree(extract, ignore_errors=True)
        zpath.unlink(missing_ok=True)
        return final
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, zipfile.BadZipFile) as exc:
        print(f"— فشل الـ release: {exc} —")
        with log.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(f"\nrelease failed: {exc}\n")
        return None


def build_from_source(
    tag: str,
    dest: Path,
    jobs: int,
    log: Path,
    *,
    backend: str = "cpu",
    cuda_arch: str = "",
) -> Path:
    src = dest.parent / "src"
    if src.exists():
        shutil.rmtree(src, ignore_errors=True)

    clone = ["git", "clone", "--depth", "1"]
    if tag and tag not in ("latest", "master"):
        clone += ["--branch", tag]
    clone += ["https://github.com/ggml-org/llama.cpp.git", str(src)]
    run_cmd(clone, log_path=log)
    commit = run_cmd(["git", "rev-parse", "--short", "HEAD"], cwd=src, quiet=True).stdout.strip()

    build = src / "build"
    cmake = [
        "cmake",
        "-B",
        str(build),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DGGML_NATIVE=ON",
        "-DLLAMA_CURL=OFF",
        "-DGGML_OPENMP=ON",
        "-DLLAMA_BUILD_TESTS=OFF",
        "-DLLAMA_BUILD_EXAMPLES=ON",
        "-DLLAMA_BUILD_SERVER=ON",
    ]
    if backend == "cuda":
        cmake += ["-DGGML_CUDA=ON"]
        if cuda_arch:
            cmake += [f"-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}"]
        print(f"بناء CUDA (arch={cuda_arch or 'auto'}) — ده بياخد وقت أطول.")
    run_cmd(cmake, cwd=src, log_path=log)
    run_cmd(
        ["cmake", "--build", str(build), "--config", "Release", "--target", "llama-server", "-j", str(jobs)],
        cwd=src,
        log_path=log,
    )

    server = _find_server(build / "bin") or _find_server(build)
    if not server:
        raise SystemExit(f"البناء نجح لكن llama-server مش موجود. راجع {log}")
    final = _collect_bin(server, dest)
    write_text(
        dest.parent / "llama_version.txt",
        f"source=source\ncommit={commit}\ntag={tag or 'master'}\n"
        f"backend={backend}\ncuda_arch={cuda_arch}\n",
    )
    # المصدر والـ build مش محتاجين بعد نسخ الـ bin، وتحميلهم في الـ cache بيكبر بلا داعي.
    shutil.rmtree(src, ignore_errors=True)
    return final


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".llama")
    ap.add_argument("--tag", default="", help="tag محدد مثل b7050، أو latest")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    ap.add_argument(
        "--backend",
        default="cpu",
        choices=["cpu", "cuda"],
        help="cpu = GitHub runner · cuda = Kaggle GPU (P100/T4)",
    )
    ap.add_argument(
        "--cuda-arch",
        default="",
        help="arch الـ CUDA: 60 للـ P100 · 75 للـ T4 (فاضي = auto من البيئة)",
    )
    args = ap.parse_args()

    if platform.system() != "Linux":
        print("⚠ هذا السكربت مخصص لـ Linux runner. استخدم LLAMA_SERVER_BIN محلياً.")
        return 2

    base = Path(args.dir).resolve()
    dest = base / "bin"
    log = base / "install.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    env_bin = os.environ.get("LLAMA_SERVER_BIN", "").strip()
    existing = dest / "llama-server"
    if env_bin and Path(env_bin).exists():
        print(f"LLAMA_SERVER_BIN={env_bin}")
        write_text(base / "llama_version.txt", f"source=env\npath={env_bin}\n")
        print(env_bin)
        return 0
    if existing.exists() and not args.force:
        print(f"موجود بالفعل: {existing}")
        print(existing)
        return 0

    server = try_release(args.tag, dest, log, backend=args.backend, cuda_arch=args.cuda_arch)
    if not server:
        print("— التحويل للبناء من المصدر —")
        server = build_from_source(
            args.tag, dest, args.jobs, log, backend=args.backend, cuda_arch=args.cuda_arch
        )

    # اختبار سريع للنسخة
    proc = run_cmd([str(server), "--version"], check=False, quiet=True, timeout=60)
    version = (proc.stdout or "") + (proc.stderr or "")
    print(version.strip()[:800])
    with (base / "llama_version.txt").open("a", encoding="utf-8") as fh:
        fh.write(f"version_output={version.strip()[:500]}\n")
    print(f"LLAMA_SERVER={server}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
