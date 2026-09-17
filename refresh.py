# ILANG
# [TYPE:script][PROJECT:vpsticker][LANG:zh]
# ::ROLE{一条命令跑完"抓取 -> 渲染 -> 部署"三件事 供计划任务无人值守调用}
# ::WHY{站点文案承诺每 6 小时更新，但这条链路必须真的有人按点触发。
#       GitHub Actions 需要仓库配 remote 且只能用仓库里的代码；本机计划任务不需要。}
# ::PRECOND{用户级环境变量 CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID（持久化，不写文件）}
# ::MUST{每一步失败都要以非零退出码结束，不许把失败当成功}
# ::MUST{抓取失败的厂商要在日志里点名，不许静默跳过}
# ::BOUNDARY{never:把令牌写进仓库或任何文件|scope:permanent}
# ::BOUNDARY{never:编价格 编优惠 编佣金|scope:permanent}
"""refresh.py — 抓取 + 渲染 + 部署，一条命令跑完。

本机无人值守用（Windows 计划任务）。跟 deploy.sh 的区别：
deploy.sh 只管"渲染 + 部署"，且依赖 bash 能读到环境变量 —— 在这台机器上读不到。
本脚本自己负责把三件事按顺序做完，并把最后 4 行结论写进 refresh.log 和 state.json。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 计划任务的控制台是 GBK 代码页。先把 stdout/stderr 换成 UTF-8 且不因编不出来就崩，
# 否则任何一条带非 GBK 字符的日志都会把整条链路带死。
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "refresh.state.json"
LOG = ROOT / "refresh.log"

# 计划任务里 sys.executable 可能是 pythonw.exe 或干脆为空，所以留一个明确的回退。
_FALLBACK_PY = Path(r"C:\Users\Administrator\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe")


def resolve_python() -> str:
    """挑一个能用的解释器。优先用当前进程的，不存在就回退到托管安装的绝对路径。"""
    exe = (sys.executable or "").strip()
    if exe and Path(exe).exists() and Path(exe).name.lower() != "pythonw.exe":
        return exe
    if _FALLBACK_PY.exists():
        return str(_FALLBACK_PY)
    return exe or "python"


PY = resolve_python()

NODE = Path(r"C:\Users\Administrator\.workbuddy-ai\binaries\node\versions\22.22.2-2\node.exe")
WRANGLER = Path(
    r"C:\Users\Administrator\.workbuddy-ai\binaries\node\versions\22.22.2-2"
    r"\node_modules\wrangler\bin\wrangler.js"
)
PROJECT = os.environ.get("VPSTICKER_PAGES_PROJECT", "vpsticker")

# 应用进程的环境块里 http_proxy / HTTP_PROXY 并存，会让子进程创建失败。
# 抓取和部署都走直连，清掉更省事。
_PROXY_KEYS = (
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
)


def log(msg: str) -> None:
    """写一条日志。

    注意：计划任务的控制台是 GBK 代码页，而抓取回来的文本可能带替换字符（\\ufffd），
    直接 print 会抛 UnicodeEncodeError 把整条链路带崩。所以先把控制台输出降级成
    "编不出来的字符就丢掉"，文件那头永远写完整 UTF-8。
    """
    line = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] {msg}"
    try:
        print(line, flush=True)
    except (UnicodeEncodeError, OSError):
        try:
            sys.stdout.buffer.write(line.encode("ascii", "replace") + b"\n")
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run(step: str, argv: list[str]) -> tuple[bool, str]:
    """跑一步。返回 (是否成功, 输出尾部)。失败不抛异常，交给调用方决定。"""
    log(f"==> {step}")
    # 子进程也强制 UTF-8：计划任务控制台是 GBK，子脚本的中文输出会变成乱码写进日志。
    env = {k: v for k, v in os.environ.items() if k not in _PROXY_KEYS}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(
            argv,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        log(f"!! {step} 超时（30 分钟）")
        return False, "timeout"
    except FileNotFoundError as e:
        log(f"!! {step} 找不到可执行文件：{argv[0]}（{e}）")
        return False, f"FileNotFoundError: {argv[0]}"
    except OSError as e:
        # 计划任务环境下起子进程可能因权限/路径问题失败，别让它冒泡成裸 traceback
        log(f"!! {step} 启动子进程失败：{type(e).__name__}: {e}")
        return False, f"{type(e).__name__}: {e}"
    tail = (proc.stdout or "")[-4000:] + (proc.stderr or "")[-2000:]
    for line in tail.splitlines():
        if line.strip():
            log("   " + line.strip()[:300])
    ok = proc.returncode == 0
    log(f"{'OK' if ok else 'FAILED'} {step} (exit={proc.returncode})")
    return ok, tail


def read_generated_at() -> str:
    p = ROOT / "data" / "offers.json"
    if not p.exists():
        return ""
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("generated_at", "")
    except Exception:  # noqa: BLE001
        return ""


def count_ok_sources() -> tuple[int, int]:
    p = ROOT / "data" / "offers.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return 0, 0
    src = data.get("sources", [])
    return sum(1 for s in src if s.get("status") == "ok"), len(src)


def fail(stage: str, detail: str = "") -> int:
    state = {
        "status": "failed",
        "stage": stage,
        "detail": detail,
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"refresh 失败：{stage} {detail}")
    return 1


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log("=" * 60)
    log(f"refresh 开始 (project={PROJECT})")

    # ---- 0. 凭证（只从环境读，绝不落盘）----
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not token:
        return fail("credential", "缺少 CLOUDFLARE_API_TOKEN")
    if not account:
        return fail("credential", "缺少 CLOUDFLARE_ACCOUNT_ID")
    if not NODE.exists():
        return fail("credential", f"找不到 node: {NODE}")
    if not WRANGLER.exists():
        return fail("credential", f"找不到 wrangler: {WRANGLER}")

    before = read_generated_at()

    # ---- 1. 抓取 ----
    ok, tail = run("抓取公开定价页 (scraper.py)", [PY, "scraper.py"])
    if not ok:
        return fail("scrape", tail[-500:])

    after = read_generated_at()
    ok_n, total_n = count_ok_sources()
    log(f"   数据时间戳 {before} -> {after}；出数 {ok_n}/{total_n} 家")

    # 抓取跑通了但数据时间戳没动 = 写盘环节有问题，不能当成功
    if after == before:
        return fail("scrape_write", f"offers.json 的 generated_at 没变（仍是 {before}）")

    # 一家都没出数 = 抓取整体坏了，别拿空站覆盖线上
    if ok_n == 0:
        return fail("scrape_empty", "0 家出数，拒绝用空数据部署")

    # 有厂商没出数就点名，但不到失败的地步（部分厂商抽风是常态）
    if ok_n < total_n:
        log(f"   ⚠️ 有 {total_n - ok_n} 家未出数，已在 sources 页如实标注")

    # ---- 2. 渲染 ----
    ok, tail = run("渲染静态站 (build.py)", [PY, "build.py"])
    if not ok:
        return fail("build", tail[-500:])

    # ---- 3. 部署 ----
    ok, tail = run(
        "部署到 Cloudflare Pages",
        [
            str(NODE), str(WRANGLER), "pages", "deploy", "site/",
            "--project-name", PROJECT,
            "--branch", "main",
            "--commit-dirty=true",
        ],
    )
    if not ok:
        return fail("deploy", tail[-500:])

    # wrangler 的退出码不可靠，以输出里有没有成功标志为准
    if "Deployment complete" not in tail and "Success" not in tail:
        return fail("deploy_verify", "没看到 Deployment complete 标志")

    state = {
        "status": "ok",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_generated_at": after,
        "sources_ok": ok_n,
        "sources_total": total_n,
        "project": PROJECT,
    }
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"refresh 完成：数据 {after}，{ok_n}/{total_n} 家出数，已部署 {PROJECT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        # 无人值守场景下绝不能裸抛 traceback：写清楚、留状态、给非零码。
        import traceback

        log(f"未预期的异常：{type(exc).__name__}: {exc}")
        for line in traceback.format_exc().splitlines():
            log("   " + line)
        STATE.write_text(
            json.dumps(
                {
                    "status": "failed",
                    "stage": "unexpected",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise SystemExit(1)
