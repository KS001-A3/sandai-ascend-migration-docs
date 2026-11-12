#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_docs.py —— 文档质量门（CI 与本地共用，支持分层目录）

检查项:
  1) 敏感信息：IP / token / 密码 / 真实用户名 / 客户名
  2) 元数据头：docs/ 下的正文文档必须有 '> 版本：...'（README 索引除外）
  3) 相对链接：仓库内 .md 链接必须能解析（跨目录也算）
  4) 文件名规范：正文文档必须是 NN_<主题>.md；分层目录名必须是 NN-英文名

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
    (r"Hdgf@[A-Za-z0-9]+", "明文密码"),
    (r"password\s*[:=]\s*\S+", "疑似明文密码"),
    (r"\bnaqin\b", "真实用户名"),
    (r"\bhdapp\b", "真实用户名"),
    (r"华大序风", "客户名称"),
]

META_RE = re.compile(r"^> 版本[：:]", re.M)
DOC_NAME_RE = re.compile(r"^\d{2}_.+\.md$")
FOLDER_RE = re.compile(r"^\d{2}-[a-z][a-z0-9-]*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


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
        return  # 顶层索引与各层 README 不强求版本头
    if p.parent.parent == DOCS and not META_RE.search(text):
        errs.append(f"{p.relative_to(ROOT)}: 缺少元数据头（> 版本：...）")


def check_name(p: Path, errs: list):
    if p == ROOT / "README.md" or p.name in ("ROADMAP.md", "CONTRIBUTING.md", "CHANGELOG.md"):
        return
    if p.name == "README.md":
        return
    if p.parent.parent == DOCS:
        if not DOC_NAME_RE.match(p.name):
            errs.append(f"{p.relative_to(ROOT)}: 文件名不符合 NN_<主题>.md")


def check_folders(errs: list):
    if not DOCS.exists():
        return
    for d in sorted(DOCS.iterdir()):
        if d.is_dir() and not FOLDER_RE.match(d.name):
            errs.append(f"docs/{d.name}/: 目录名不符合 NN-英文名（如 10-environment）")
        if d.is_dir() and not (d / "README.md").exists():
            errs.append(f"docs/{d.name}/: 缺少分层的 README.md 索引")


def check_links(p: Path, text: str, errs: list):
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

    print(f"检查 {len(files)} 个 Markdown 文件，{len(list(DOCS.glob('*/'))) } 个分层目录")
    for p in files:
        print(f"  - {p.relative_to(ROOT)}")
    print()
    if errs:
        print(f"❌ 失败：{len(errs)} 项")
        for e in errs:
            print("   " + e)
        return 1
    print("✅ 全部通过：无敏感信息 / 元数据头齐全 / 链接可解析 / 命名与分层规范")
    return 0


if __name__ == "__main__":
    sys.exit(main())
