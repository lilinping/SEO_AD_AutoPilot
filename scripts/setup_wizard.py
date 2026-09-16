#!/usr/bin/env python3
"""SEO-AD AutoPilot — 交互式首次配置向导 (Setup Wizard)

用法:
  python scripts/setup_wizard.py        # 交互模式（逐步引导）
  python scripts/setup_wizard.py --auto # 非交互模式（全部使用默认值）
  make wizard                           # 通过 Makefile 调用

向导步骤:
  1. 检查环境依赖（Python 版本、Node.js、Docker）
  2. 创建虚拟环境并安装依赖
  3. 引导填写 .env 关键配置项
  4. 验证 OpenAI API Key 连通性
  5. 初始化数据库（Alembic）
  6. 打印彩色启动命令说明
"""

from __future__ import annotations
import argparse, getpass, json, os, shutil, subprocess, sys
from pathlib import Path


# ── 颜色工具 ──────────────────────────────────────────────────────────────────
def _c(s: str, code: str) -> str:
    """添加 ANSI 颜色；Windows 非 WT_SESSION 时降级为纯文本。"""
    if sys.platform == "win32" and not os.getenv("WT_SESSION"):
        return s
    return "\033[" + code + "m" + s + "\033[0m"

def ok(m: str)   -> None: print(_c("  ✅  " + m, "32"))
def warn(m: str) -> None: print(_c("  ⚠️   " + m, "33"))
def err(m: str)  -> None: print(_c("  ❌  " + m, "31"))
def info(m: str) -> None: print(_c("  ℹ️   " + m, "36"))
def head(m: str) -> None:
    bar = "─" * 58
    print(_c("\n" + bar + "\n  " + m + "\n" + bar, "1"))


def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    dd = "****" if (secret and default) else default
    suffix = (" [" + dd + "]") if dd else ""
    full = _c("  → " + prompt + suffix + ": ", "36")
    val = getpass.getpass(full) if secret else input(full)
    return val.strip() or default


def run(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


# ── Step 1: 环境检查 ───────────────────────────────────────────────────────────
def step_check() -> bool:
    head("Step 1/6  环境检查")
    all_ok = True
    v = sys.version_info
    if v >= (3, 9):
        ok("Python " + str(v.major) + "." + str(v.minor) + "." + str(v.micro))
    else:
        err("Python " + str(v.major) + "." + str(v.minor) + " 不符合要求（需要 3.9+）")
        all_ok = False

    if shutil.which("node"):
        r = run(["node", "--version"], capture=True, check=False)
        ok("Node.js " + r.stdout.strip())
    else:
        warn("Node.js 未找到 — Web 前端无法启动（API 仍正常）")

    if shutil.which("pnpm"):
        ok("pnpm")
    elif shutil.which("node"):
        info("pnpm 未安装，将通过 npm 自动安装")

    if shutil.which("git"):
        ok("git")
    else:
        warn("git 未安装")

    if shutil.which("docker"):
        ok("docker（可使用 make docker-up 一键启动）")
    else:
        info("docker 未安装，将使用本地运行模式")

    return all_ok


# ── Step 2: venv + 依赖 ────────────────────────────────────────────────────────
def step_venv() -> Path:
    head("Step 2/6  Python 虚拟环境")
    venv = Path(".venv")
    if venv.exists():
        ok(".venv 已存在，跳过创建")
    else:
        info("创建 .venv ...")
        run([sys.executable, "-m", "venv", ".venv"])
        ok(".venv 创建成功")

    is_win = sys.platform == "win32"
    pip = venv / ("Scripts/pip.exe" if is_win else "bin/pip")
    info("安装 Python 依赖（约 1-2 分钟）...")
    try:
        run([str(pip), "install", "--upgrade", "pip", "-q"])
        run([str(pip), "install", "-r", "requirements.txt", "-q"])
        ok("Python 依赖安装完成")
    except subprocess.CalledProcessError:
        warn("Python 依赖安装失败，请手动运行: pip install -r requirements.txt")

    # Added pnpm install check for frontend deps (Developer/User Convenience Improvement)
    if shutil.which("pnpm"):
        info("检测到 pnpm，正在安装 Node.js 前端依赖 (pnpm install)...")
        try:
            run(["pnpm", "install"], check=True)
            ok("Node.js 前端依赖安装完成")
        except Exception as e:
            warn(f"Node.js 前端依赖安装失败 ({e})，请在 apps/web 下手动运行 pnpm install")
    else:
        warn("未找到 pnpm，跳过 Node.js 依赖安装。请在安装 Node.js 和 pnpm 后运行 pnpm install")
    return venv


# ── Step 3: 配置 .env ──────────────────────────────────────────────────────────
def step_env(auto: bool) -> dict:
    head("Step 3/6  环境变量配置")
    env_p = Path(".env")
    ex_p  = Path(".env.example")

    if not ex_p.exists():
        warn(".env.example 不存在，跳过配置")
        return {}

    def parse(p: Path) -> dict:
        d: dict = {}
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, _, v = ln.partition("=")
                d[k.strip()] = v.strip()
        return d

    cfg = {**parse(ex_p), **(parse(env_p) if env_p.exists() else {})}
    if env_p.exists():
        ok(".env 已存在，保留现有配置")

    if not auto:
        info("只需填写关键项，直接按 Enter 使用默认值\n")
        key_defs = [
            ("OPENAI_API_KEY",         "OpenAI API Key",                True,  ""),
            ("DATABASE_URL",           "数据库 URL",                    False,
             "sqlite+aiosqlite:///./seo_ad_bot.db"),
            ("REDIS_URL",              "Redis URL（空 = 内存缓存）",     False, ""),
            ("SEO_AD_BOT_ENVIRONMENT", "运行环境（development/production）",
             False, "development"),
            ("SENTRY_DSN",             "Sentry DSN（可选，错误追踪）",   False, ""),
        ]
        for key, label, secret, fallback in key_defs:
            cur = cfg.get(key, fallback)
            if key == "OPENAI_API_KEY" and "sk-your" in cur:
                cur = ""
            val = ask(label, cur, secret)
            if val:
                cfg[key] = val

    # 写入 .env（保留原始注释结构）
    lines = ex_p.read_text(encoding="utf-8").splitlines()
    out = []
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.partition("=")[0].strip()
            if k in cfg:
                out.append(k + "=" + cfg[k])
                continue
        out.append(ln)
    env_p.write_text("\n".join(out) + "\n", encoding="utf-8")
    ok(".env 已保存 → " + str(env_p.absolute()))
    return cfg


# ── Step 4: 验证 OpenAI API Key ────────────────────────────────────────────────
def step_validate_key(cfg: dict) -> None:
    head("Step 4/6  验证 OpenAI API Key")
    key = cfg.get("OPENAI_API_KEY", "")
    if not key or "sk-your" in key:
        warn("未配置 OpenAI API Key，跳过验证")
        info("获取 Key: https://platform.openai.com/api-keys")
        return
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": "Bearer " + key},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            count = len(data.get("data", []))
            ok("API Key 有效（可用模型数: " + str(count) + "）")
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        if e.code == 401:
            err("API Key 无效（HTTP 401），请检查后重试")
        else:
            warn("OpenAI 返回 HTTP " + str(e.code) + "，请稍后验证")
    except Exception as e:
        warn("无法连接 OpenAI（" + str(e) + "），请检查网络")


# ── Step 5: 数据库初始化 ───────────────────────────────────────────────────────
def step_db(venv: Path) -> None:
    head("Step 5/6  数据库初始化")
    is_win  = sys.platform == "win32"
    alembic = venv / ("Scripts/alembic.exe" if is_win else "bin/alembic")
    if not alembic.exists():
        warn("alembic 未找到，跳过；可手动运行: make db-migrate")
        return
    try:
        run([str(alembic), "upgrade", "head"])
        ok("数据库迁移完成")
    except subprocess.CalledProcessError:
        warn("迁移失败，请手动运行: make db-migrate")


# ── Step 6: 启动说明 ───────────────────────────────────────────────────────────
def step_guide(venv: Path) -> None:
    head("Step 6/6  启动说明")
    is_win   = sys.platform == "win32"
    uvicorn  = str(venv / ("Scripts/uvicorn.exe" if is_win else "bin/uvicorn"))
    activate = ("call " + str(venv) + r"\Scripts\activate.bat") if is_win \
               else ("source " + str(venv) + "/bin/activate")

    print()
    ok("🎉 SEO-AD AutoPilot 配置完成！\n")
    guide_lines = [
        _c("  方式 1: Make 命令（推荐）", "1"),
        "    make dev              # API + Web 同时启动",
        "    make dev-api          # 仅 API",
        "    make wizard           # 重新运行向导",
        "",
        _c("  方式 2: Docker Compose", "1"),
        "    make docker-up        # 含 Redis + DB 一键启动",
        "",
        _c("  方式 3: 手动启动", "1"),
        "    " + activate,
        "    " + uvicorn + " apps.api.seo_ad_autopilot.app:create_app "
                           "--factory --reload --port 8000",
        "",
        "  访问地址:",
        "    API:     http://127.0.0.1:8000",
        "    Swagger: http://127.0.0.1:8000/docs",
        "    Metrics: http://127.0.0.1:8000/metrics/summary",
        "    Web:     http://localhost:3000",
        "",
        "  常用命令:",
        "    make help             # 查看所有命令",
        "    make test             # 运行测试",
        "    make lint             # 代码检查",
        "    make cache-flush      # 清空 Agent 缓存",
    ]
    for line in guide_lines:
        print(line)


# ── 主程序 ────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="SEO-AD AutoPilot 首次配置向导")
    parser.add_argument("--auto", action="store_true", help="非交互模式，全部使用默认值")
    args = parser.parse_args()

    print()
    print(_c("╔════════════════════════════════════════════════════╗", "1;36"))
    print(_c("║   SEO-AD AutoPilot — 首次配置向导 (Setup Wizard)   ║", "1;36"))
    print(_c("╚════════════════════════════════════════════════════╝", "1;36"))

    if not Path("requirements.txt").exists():
        err("请在项目根目录运行此脚本: python scripts/setup_wizard.py")
        sys.exit(1)

    if not step_check():
        err("环境检查未通过，请先安装必要依赖后重试")
        sys.exit(1)

    venv = step_venv()
    cfg  = step_env(auto=args.auto)
    step_validate_key(cfg)
    step_db(venv)
    step_guide(venv)


if __name__ == "__main__":
    main()
