#!/usr/bin/env python3
"""tools/verify_book_consistency.py

第3次評価（#148）で見つかった「同じ誤りが戻りやすい欠陥」を決定論的に検査する。

1. Actions の SHA ピン留め：原稿中の `uses: owner/repo[/path]@<40桁SHA> # vX.Y.Z` について、
   SHA がそのタグの指すコミットと一致するかを `git ls-remote` で照合する（ネットワーク必須）。
   `--offline` を付けると照合を省き、形式（40桁SHA＋版コメント）だけを検査する。
2. 閾値の整合性：第2章「本書の閾値の扱い」と食い違う既知の書き方が残っていないか。
3. 表現：本書で使わないと決めた断定・変換誤りが残っていないか。
4. 組版：コードの外に未変換の数式（`$...$`）が残っていないか（PDF/EPUBで生のまま表示される）。
5. データ送信ポリシー：LLM APIを呼ぶコードがある節に「データ送信の注意」があるか（第2章）。
"""
import re
import subprocess
import sys
from pathlib import Path

MANUSCRIPT = Path(__file__).resolve().parents[1] / "manuscript"
USES = re.compile(r"uses:\s*([\w.-]+/[\w.-]+)(?:/[\w./-]+)?@([0-9a-f]{40})(?:\s*#\s*(v[\w.]+))?")
TAG_ONLY = re.compile(r"uses:\s*[\w.-]+/[\w.-]+(?:/[\w./-]+)?@v\d")

# 第2章の閾値表と矛盾する書き方（正規表現, 理由）
FORBIDDEN = [
    (r"MAX_CHANGED_LINES\s*=\s*500", "PRサイズは400行警告/800行ブロックに統一"),
    (r"\"break\":\s*70", "変異スコアの下限は汎用75%/Tier1 80%"),
    (r"殺害率 75%未満", "Tier1の不合格は80%未満（第2章）"),
    (r"単体カバレッジ100%", "カバレッジ100%のノルマ化は第23章と矛盾"),
    (r"DAU/MAU", "ゾンビ機能は「90日間の機能利用率」で定義する"),
    (r"PRサイズ上限400行", "400行は警告、800行がブロック"),
    (r"完全再現", "簡略実装を「完全再現」と称さない"),
    (r"もたらする|行いる", "変換誤り"),
    (r"Alshahwan et al\., FSE 2024; 2025", "ACHの著者はFoster et al."),
    (r"データ白書2022", "存在しない資料名"),
]


def iter_lines():
    for md in sorted(MANUSCRIPT.glob("*.md")):
        for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            yield md.name, i, line


def remote_shas(repo: str, tag: str) -> set[str]:
    res = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repo}", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        capture_output=True, text=True, check=False, timeout=60,
    )
    if res.returncode != 0:
        raise RuntimeError(f"git ls-remote failed for {repo}: {res.stderr.strip()}")
    return {line.split("\t")[0] for line in res.stdout.splitlines() if line.strip()}


def main() -> int:
    offline = "--offline" in sys.argv
    errors: list[str] = []
    cache: dict[tuple[str, str], set[str]] = {}

    in_code = {}
    section_has_llm: dict[tuple[str, str], bool] = {}
    section_has_notice: dict[tuple[str, str], bool] = {}
    current_section: dict[str, str] = {}
    for name, i, line in iter_lines():
        if line.startswith("```"):
            in_code[name] = not in_code.get(name, False)
        elif not in_code.get(name, False):
            if line.startswith("## "):
                current_section[name] = line
            prose = re.sub(r"`[^`]*`", "", line)
            if re.search(r"\$[^\s$][^$]{0,60}\$", prose):
                errors.append(f"{name}:{i}: コード外の未変換数式（Unicodeの平文で書く）: {line.strip()[:80]}")
        key = (name, current_section.get(name, ""))
        if "generativelanguage.googleapis.com" in line or "GEMINI_API_KEY: ${{" in line:
            section_has_llm[key] = True
        if "データ送信の注意" in line:
            section_has_notice[key] = True
        is_code_line = line.lstrip().startswith(("uses:", "- uses:"))
        if is_code_line and TAG_ONLY.search(line):
            errors.append(f"{name}:{i}: タグ指定の uses（SHA固定にする）: {line.strip()}")
        m = USES.search(line)
        if m:
            repo, sha, tag = m.groups()
            if not tag:
                errors.append(f"{name}:{i}: SHAに版コメント（# vX.Y.Z）がない: {line.strip()}")
            elif not offline:
                key = (repo, tag)
                if key not in cache:
                    try:
                        cache[key] = remote_shas(repo, tag)
                    except (RuntimeError, subprocess.TimeoutExpired) as exc:
                        errors.append(f"{name}:{i}: 照合できない（合格扱いにしない）: {exc}")
                        cache[key] = set()
                        continue
                if sha not in cache[key]:
                    errors.append(f"{name}:{i}: {repo}@{tag} のSHAと一致しない: {sha}")
        for pattern, reason in FORBIDDEN:
            if re.search(pattern, line):
                errors.append(f"{name}:{i}: {reason}: {line.strip()[:80]}")

    for (name, section), _ in section_has_llm.items():
        if not section_has_notice.get((name, section)):
            errors.append(f"{name}: 「{section.strip()}」にLLM APIを呼ぶコードがあるが「データ送信の注意」がない")

    if errors:
        print("❌ 整合性検査で問題が見つかりました:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"✅ 整合性検査を通過しました（SHA照合: {'省略' if offline else f'{len(cache)}件'}）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
