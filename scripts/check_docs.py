#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_docs.py —— 文档质量门（CI 与本地共用，支持分层目录）

只做「结构性」检查，不内置任何内部专有名词：
  1) 通用敏感信息：IP / GitHub token / 密码赋值 / 邮箱 / Windows 绝对路径
  2) 元数据头：正文文档必须有 '> 版本：...'
  3) 相对链接：仓库内 .md 链接必须能解析（跨目录也算）
  4) 命名与分层：正文文件名 NN_<主题>.md；目录名 NN-中文名；每层必须有 README
  5) 代号规范：由内部发布流程负责替换（HDJY / sandai），本仓不保存原词清单。

退出码: 0 通过; 1 有错误
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

VERSION_ALLOW = {"8.6.1.6", "1.0.18", "1.0.22"}  # 形似 IP 的版本号白名单

FORBIDDEN = [
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP 地址"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub token"),
    (r"password\s*[:=]\s*\S+", "疑似明文密码"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "邮箱"),
    (r"[A-Za-z]:\\[^\s`'\"]+", "Windows 绝对路径"),
    (r"C:Users[A-Za-z0-9_.\\-]*", "Windows 路径（缺反斜杠）"),
    # 内部工程痕迹
    (r"sandai-workspace|internal-refs|/workspace/claude_code", "内部工作区路径"),
    (r"(?:工作区|交付包|内部资料|内部调研)[\\/]", "内部目录结构"),
    (r"D:\\\\?work|D:worksandai", "本地绝对路径"),
    (r"\bGitLab\b|genomics\.cn|华为", "内部平台/厂商名"),
    (r"<§>|<PROCESS_DOC>|物种X|物种[A-F]|<GITLAB_IP>|<internal_gitlab>|<凭证文件>", "旧占位符残留"),
    # 合同/商业信息
    (r"\d+\s*(?:[~～/–-]\s*)?(?:若干)?人天", "工作量/报价"),
    (r"8\.5\s*M|0\.005\s*%|\b10\s*M\s*(?:samples|/s|samples/s)", "合同阈值"),
    (r"corn|yeast|ecoli|arabidopsis|rice_hifi|\brice\b|HG002", "验收物种名"),
    (r"\b28\s*(个|条|/\s*28)|2507404|acceptance_v0", "验收数据细节"),
    # 安全披露
    (r"xchacha20poly1305|chacha|ChaCha|4096B|硬编码|secretstream|crypto\.cpp|对称加密算法|加密模块|同密钥", "加密实现披露"),
    # 渲染/格式
    (r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "控制字符"),
    (r"（\s*见\s*）|（\s*）|//\|", "空引用/表格残渣"),
]

# 允许出现的通用占位符（CONTRIBUTING 中定义）
ALLOWED_PLACEHOLDERS = {
    "<GPU_HOST>", "<JUMP_HOST>", "<CLIENT_HOST>", "<PORT>", "<APT_MIRROR>",
    "<user>", "<jump_user>", "<data_batch>", "<LOCAL_PATH>", "<WORKSPACE>",
    "<N>", "<M>", "<PERF_TARGET>", "<PREPOST_TARGET>", "<ACC_TARGET>",
    "<Q_TARGET>", "<METH_TARGET>", "<EFFORT>", "<PORTABLE_PYTHON>",
}

META_RE = re.compile(r"^> 版本[：:]", re.M)
DOC_NAME_RE = re.compile(r"^\d{2}_.+\.md$")
FOLDER_RE = re.compile(r"^\d{2}-[^/\s]+$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
LOOSE_LINK_RE = re.compile(r"\]\(([^)\n]*)\)")


def iter_markdown():
    yield from sorted(ROOT.glob("*.md"))
    yield from sorted(DOCS.rglob("*.md"))


def check_secrets(p: Path, text: str, errs: list):
    for pat, desc in FORBIDDEN:
        for m in re.finditer(pat, text):
            if m.group(0) in VERSION_ALLOW:
                continue
            line = text[: m.start()].count("\n") + 1
            errs.append(f"{p.relative_to(ROOT)}:{line}: 敏感信息（{desc}: {m.group(0)}）")


def check_meta(p: Path, text: str, errs: list):
    if p.parent == DOCS or p.name == "README.md":
        return
    if p.parent.parent == DOCS and not META_RE.search(text):
        errs.append(f"{p.relative_to(ROOT)}: 缺少元数据头（> 版本：...）")


def check_name(p: Path, errs: list):
    if p == ROOT / "README.md" or p.name in ("ROADMAP.md", "CONTRIBUTING.md", "CHANGELOG.md"):
        return
    if p.name == "README.md":
        return
    if p.parent.parent == DOCS and not DOC_NAME_RE.match(p.name):
        errs.append(f"{p.relative_to(ROOT)}: 文件名不符合 NN_<主题>.md")


def check_folders(errs: list):
    if not DOCS.exists():
        return
    for d in sorted(DOCS.iterdir()):
        if not d.is_dir():
            continue
        if not FOLDER_RE.match(d.name):
            errs.append(f"docs/{d.name}/: 目录名不符合 NN-中文名（如 10-环境与构建）")
        if not (d / "README.md").exists():
            errs.append(f"docs/{d.name}/: 缺少分层的 README.md 索引")


def check_links(p: Path, text: str, errs: list):
    # 先查畸形链接：目标里带空格/反引号 → GitHub 不渲染为链接（历史事故：`00 项目梳理`-总览...）
    for m in LOOSE_LINK_RE.finditer(text):
        raw = m.group(1).strip()
        if not raw or raw.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if " " in raw or "`" in raw:
            line = text[: m.start()].count("\n") + 1
            errs.append(f"{p.relative_to(ROOT)}:{line}: 畸形链接（目标含空格/反引号：{raw[:60]}）")

    for m in LINK_RE.finditer(text):
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if target.startswith("<"):
            continue
        path_part = target.split("#")[0]
        if not path_part:
            continue
        resolved = (p.parent / path_part).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            errs.append(f"{p.relative_to(ROOT)}: 链接指向仓库外（{target}）")
            continue
        if not resolved.exists():
            errs.append(f"{p.relative_to(ROOT)}: 链接不存在（{target}）")


def main() -> int:
    errs: list[str] = []
    files = list(iter_markdown())
    for p in files:
        text = p.read_text(encoding="utf-8")
        check_secrets(p, text, errs)
        check_meta(p, text, errs)
        check_name(p, errs)
        check_links(p, text, errs)
    check_folders(errs)

    print(f"检查 {len(files)} 个 Markdown 文件，{len([d for d in DOCS.iterdir() if d.is_dir()])} 个分层目录")
    for p in files:
        print(f"  - {p.relative_to(ROOT)}")
    print()
    if errs:
        print(f"❌ 失败：{len(errs)} 项")
        for e in errs:
            print("   " + e)
        return 1
    print("✅ 全部通过：无 IP/token/密码/邮箱/绝对路径；元数据头齐全；链接可解析；命名与分层规范")
    return 0


if __name__ == "__main__":
    sys.exit(main())
