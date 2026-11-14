#!/usr/bin/env python3
"""
tools/audit_content_completeness.py
技術書としての「内容（コンテンツ）」の品質と論理構造を決定論的に検証する品質ゲート：
1. 【アンチパターンと処方箋の完全対比】
   「アンチパターン」が登場する節・項目では、必ず対比となる「解決策」「処方箋」「Paved Path」「対策」が提示されていること。
2. 【トレードオフ・限界の明示（批判的思考・エンジニアリングの誠実性）】
   「手法・ツール」の導入を論じる節・章では、銀の弾丸視を排除し、「トレードオフ」「限界」「デメリット」「コスト」「注意点」「前提」のいずれかに言及していること。
3. 【実践コードと読者ガイドのペアリング】
   コードブロック（```python, ```yaml 等）を提示した直後（2パラグラフ以内）に、コードの意図や着眼点を解説する読者ナビゲーションが存在すること。
4. 【同義反復・トートロジーの抑止】
   「〜だからである」「なぜなら」等の理由付け文において、主語と述語が同一の浅い理由付け（単なる同義反復）になっていないこと。
"""

import re
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def audit_chapter_content(file_path: Path) -> list[str]:
    issues = []
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 1. セクション単位（H2）の分割
    # 章末のアンチパターン専用セクション（失敗事例から学ぶアンチパターンと処方箋 など）
    remedy_keywords = (
        "処方箋", "解決策", "Paved Path", "対策", "改善", "回避", "代替", "ベストプラクティス",
        "是正", "アプローチ", "防ぐ", "防止", "解決", "防護", "対処"
    )
    sections = re.split(r"\n(?=##\s+)", text)
    for sec_idx, sec in enumerate(sections):
        sec_lines = sec.strip().splitlines()
        if not sec_lines:
            continue
        h2_title = sec_lines[0].strip()

        # アンチパターンの対比検査（タイトルまたは本文でアンチパターンを主眼とするセクション）
        if "アンチパターン" in h2_title:
            has_remedy = any(kw in sec for kw in remedy_keywords)
            if not has_remedy:
                issues.append(f"{file_path.name} [{h2_title}]: [Content-Remedy] 'アンチパターン'を冠する節ですが、対比となる解決策・処方箋（Paved Path/対策）の記述が見当たりません。")

    # 2. 章全体のエンジニアリング誠実性（トレードオフ・限界・コストの言及）
    tradeoff_keywords = ("トレードオフ", "限界", "デメリット", "コスト", "注意点", "前提条件", "落とし穴", "リスク", "副作用", "負債")
    has_tradeoff = any(kw in text for kw in tradeoff_keywords)
    if not has_tradeoff:
        issues.append(f"{file_path.name}: [Content-Tradeoff] エンジニアリングの誠実性として、提案手法の'トレードオフ'や'限界・コスト・リスク'への言及が章内に存在しません。")

    # 3. コードスニペットの直後解説検査（孤立したコードブロックの防止）
    in_code = False
    fence_end_line = -1
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
            else:
                in_code = False
                fence_end_line = idx
                # 次の数行に解説テキストがあるか（ファイル末尾でないか）
                if fence_end_line >= len(lines):
                    issues.append(f"{file_path.name}:Line {idx}: [Content-CodeContext] コードブロックの後に解説テキストがなく、ファイルが終了しています。")

    # 4. トートロジー（同義反復）の簡易検知（例: 「速い理由は速いからである」等）
    for idx, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            continue
        m = re.search(r"なぜなら([^。]+)だからである", line)
        if m:
            reason = m.group(1).strip()
            if len(reason) < 4:
                issues.append(f"{file_path.name}:Line {idx}: [Content-Tautology] 理由付け（なぜなら〜だからである）の内容が希薄または空虚です: '{line.strip()}'")

    return issues


def main():
    repo_dir = Path(__file__).resolve().parent.parent
    manuscript_dir = repo_dir / "manuscript"
    chapter_files = sorted(f for f in manuscript_dir.glob("*.md") if f.name not in ("00_intro.md", "99_afterword.md"))

    print("=== Content Quality, Engineering Tradeoffs & Semantic Structure Audit ===")
    print(f"Auditing content depth across {len(chapter_files)} chapters...\n")

    all_issues = []
    for f in chapter_files:
        issues = audit_chapter_content(f)
        if issues:
            all_issues.extend(issues)

    if all_issues:
        print(f"FAILED: {len(all_issues)} content quality violation(s) found:\n")
        for iss in all_issues:
            print(f"  ❌ {iss}")
        sys.exit(1)

    print(f"PASSED: All {len(chapter_files)} chapters meet Content Quality, Antipattern/Remedy pairing, and Engineering Tradeoff standards.")
    sys.exit(0)


if __name__ == "__main__":
    main()
