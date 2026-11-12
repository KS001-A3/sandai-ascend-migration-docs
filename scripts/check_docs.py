#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_docs.py —— 文档质量门（CI 与本地共用）

检查项:
  1) 敏感信息：IP / token / 密码 / 真实用户名 / 客户名
  2) 元数据头：docs/*.md 必须有 '> 版本：...'
  3) 相对链接：仓库内 .md 链接必须能解析
  4) 文件名规范：docs/ 下必须是 NN_<主题>_<类型>.md

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
NAME_RE = re.compile(r"^\d{2}_.+\.md$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def iter_markdown():
    yield from sorted(ROOT.glob("*.md"))
    yield from sorted(DOCS.glob("*.md"))


def check_secrets(p: Path, text: str, errs: list):
    for pat, desc in FORBIDDEN:
        for m in re.finditer(pat, text):
            if m.group(0) in VERSION_ALLOW:
                continue
            line = text[: m.start()].count("\n") + 1
            errs.append(f"{p.relative_to(ROOT)}:{line}: 敏感信息（{desc}: {m.group(0)}）")


def check_meta(p: Path, text: str, errs: list):
    if p.parent == DOCS and not META_RE.search(text):
        errs.append(f"{p.relative_to(ROOT)}: 缺少元数据头（> 版本：...）")


def check_name(p: Path, errs: list):
    if p.parent == DOCS and not NAME_RE.match(p.name):
        errs.append(f"{p.relative_to(ROOT)}: 文件名不符合 NN_<主题>_<类型>.md")


def check_links(p: Path, text: str, errs: list):
    for m in LINK_RE.finditer(text):
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if target.startswith("<"):  # 占位符链接
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

    print(f"检查 {len(files)} 个 Markdown 文件")
    for p in files:
        print(f"  - {p.relative_to(ROOT)}")
    print()
    if errs:
        print(f"❌ 失败：{len(errs)} 项")
        for e in errs:
            print("   " + e)
        return 1
    print("✅ 全部通过：无敏感信息 / 元数据头齐全 / 链接可解析 / 命名规范")
    return 0


if __name__ == "__main__":
    sys.exit(main())
