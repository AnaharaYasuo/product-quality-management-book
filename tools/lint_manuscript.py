#!/usr/bin/env python3
"""
tools/lint_manuscript.py
原稿（manuscript/*.md）の決定論的品質ゲート：
1. 文章可読性（1文150文字上限）
2. 見出し階層構造（H1 -> H2 -> H3 の飛び検知）
3. コードフェンス整合性（ネストされた ``` の未エスケープ・閉じ忘れ検知）
4. 日本語文法・表記規律（ら抜き言葉、二重否定）
5. 技術用語・概念契約辞書（SASTと静的検証の混同、カバレッジ計測ツールと静的解析の混同、誤字・誤変換の遮断）
6. 埋め込みコードブロック構文検証（Python AST / JSON / YAML / TOML の実パース検査）
"""

import ast
import glob
import json
import re
import sys
import tomllib
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 技術用語・概念契約および誤変換防止ルール辞書
TERMINOLOGY_CONTRACTS = [
    (
        r"SAST\s*[（(]\s*静的(?:解析|検証)\s*[)）]",
        "[Terminology-Contract] SASTは「静的アプリケーションセキュリティテスト（Static Application Security Testing）」です。「SAST（静的解析）」や「SAST（静的検証）」と略さず、Linter等の静的解析と明確に区別してください。"
    ),
    (
        r"SAST.{0,10}静的検証|静的検証.{0,10}SAST",
        "[Terminology-Contract] SASTを「静的検証」と呼称しています。「静的アプリケーションセキュリティテスト（SAST）」または「静的セキュリティ解析」と記述してください。"
    ),
    (
        r"静的解析ツールが.{0,15}カバレッジ",
        "[Terminology-Contract] 行・分岐カバレッジの測定は実行時トレース（動的計測）であり、静的解析ツールではありません。「カバレッジ計測ツール」と記述してください。"
    ),
    (
        r"ポストレモート",
        "[Typo-Contract] 「ポストレモート」は誤記です。「ポストモーテム（Post-mortem）」に修正してください。"
    ),
    (
        r"(?:例外|エラー|Exception|シグナル)を?補足|Exception補足",
        "[Typo-Contract] 例外やエラーをCatchすることは「補足」ではなく「捕捉（ほそく）」です。"
    ),
    (
        r"シュミレーション|シュミレータ",
        "[Typo-Contract] 「シュミレーション」は誤記です。「シミュレーション」に修正してください。"
    ),
    (
        r"ディプロイ",
        "[Typo-Contract] 表記揺れ：「ディプロイ」ではなく「デプロイ」に統一してください。"
    ),
    (
        r"確立(?:的|分布|モデル)",
        "[Typo-Contract] 統計・数学用語の「確率（Probability）」が「確立」と誤変換されています。"
    ),
    (
        r"対称療法",
        "[Typo-Contract] 「対称療法」は誤変換です。「対症療法」に修正してください。"
    ),
]


def lint_markdown(file_path: str):
    issues = []
    content = Path(file_path).read_text(encoding="utf-8")
    lines = content.splitlines()

    prev_header_level = 0
    in_code_block = False
    fence_marker = ""
    fence_lang = ""
    fence_start_line = 0
    code_buffer = []

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()

        # コードブロック境界判定（3個以上のバッククォートまたはチルダ）
        fence_match = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
        if fence_match:
            marker, lang = fence_match.group(1), fence_match.group(2).strip().lower()
            if not in_code_block:
                in_code_block = True
                fence_marker = marker
                fence_lang = lang
                fence_start_line = idx
                code_buffer = []
                continue
            else:
                # 同一マーカー長で言語指定がある場合はネスト衝突エラー
                if lang != "" and marker == fence_marker:
                    issues.append(
                        f"Line {idx}: [Fence-Collision] コードブロック（Line {fence_start_line} で開始）の内部で同じ長さの `{marker}{lang}` が使われており、コードブロックが途中で破壊されています。外側のブロックを ````（4連バッククォート）に変更してください。"
                    )
                elif len(marker) >= len(fence_marker) and marker[0] == fence_marker[0] and lang == "":
                    # コードブロック終了時に埋め込みコードの構文検証を実行
                    code_text = "\n".join(code_buffer)
                    validate_embedded_code(fence_lang, code_text, fence_start_line, issues)
                    in_code_block = False
                    fence_marker = ""
                    fence_lang = ""
                    continue

        if in_code_block:
            code_buffer.append(line)
            # コードブロック内でも誤字契約（ポストレモート等）は検査する
            for pat, msg in TERMINOLOGY_CONTRACTS:
                if re.search(pat, line):
                    issues.append(f"Line {idx}: {msg}")
            continue

        # 1. 1文の長さチェック（150文字超過は読みにくい）
        sentences = re.split(r"。|\. ", line)
        for s in sentences:
            if len(s.strip()) > 150:
                issues.append(
                    f"Line {idx}: [Readability] 1文が150文字を超えています ({len(s.strip())}文字)。文を分割することを検討してください。"
                )

        # 2. 見出し階層の飛びチェック
        header_match = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if header_match:
            level = len(header_match.group(1))
            if prev_header_level > 0 and level > prev_header_level + 1:
                issues.append(
                    f"Line {idx}: [Structure] 見出しレベルが飛んでいます (H{prev_header_level} -> H{level})。"
                )
            prev_header_level = level

        # 3. ら抜き言葉の簡易検知
        ra_nuki = ["出れる", "見れる", "着れる", "食べれる", "来れる", "信じれる"]
        for word in ra_nuki:
            if word in line:
                issues.append(f"Line {idx}: [Grammar] ら抜き言葉が検出されました: '{word}'")

        # 4. 二重否定の簡易検知
        if "ないわけではない" in line or "なくはない" in line:
            issues.append(f"Line {idx}: [Style] 二重否定が検出されました。肯定的な表現への言い換えを検討してください。")

        # 5. 技術用語・概念契約 & 誤変換チェック
        for pat, msg in TERMINOLOGY_CONTRACTS:
            if re.search(pat, line):
                issues.append(f"Line {idx}: {msg}")

    if in_code_block:
        issues.append(f"Line {fence_start_line}: [Fence-Unclosed] コードブロックがファイル末尾まで閉じられていません。")

    return issues


def validate_embedded_code(lang: str, code_text: str, start_line: int, issues: list):
    if not code_text.strip():
        return
    if lang == "python":
        try:
            ast.parse(code_text)
        except SyntaxError as e:
            issues.append(
                f"Line {start_line}: [Embedded-Python-AST] 掲載されているPythonコードに構文エラーがあります: {e.msg} (block line {e.lineno})"
            )
    elif lang == "json":
        try:
            json.loads(code_text)
        except Exception as e:
            issues.append(
                f"Line {start_line}: [Embedded-JSON-Syntax] 掲載されているJSONコードに構文エラーがあります: {e}"
            )
    elif lang in ("yaml", "yml") and HAS_YAML:
        try:
            list(yaml.safe_load_all(code_text))
        except Exception as e:
            issues.append(
                f"Line {start_line}: [Embedded-YAML-Syntax] 掲載されているYAMLコードに構文エラーがあります: {e}"
            )
    elif lang == "toml":
        try:
            tomllib.loads(code_text)
        except Exception as e:
            issues.append(
                f"Line {start_line}: [Embedded-TOML-Syntax] 掲載されているTOMLコードに構文エラーがあります: {e}"
            )


def main():
    target_files = sorted(glob.glob("manuscript/*.md"))
    total_issues = 0

    print("=== Markdown, Terminology Contract & Embedded Code AST Linter ===")
    print(f"Checking {len(target_files)} manuscript files...\n")

    for f in target_files:
        issues = lint_markdown(f)
        if issues:
            print(f"File: {f}")
            for iss in issues:
                print(f"  - {iss}")
            total_issues += len(issues)
            print()

    if total_issues > 0:
        print(f"FAILED: Found {total_issues} issue(s) in manuscripts.")
        sys.exit(1)
    else:
        print("PASSED: All manuscript files passed style, terminology contract, fence integrity, and embedded code AST checks.")
        sys.exit(0)


if __name__ == "__main__":
    main()
