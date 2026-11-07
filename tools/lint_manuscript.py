import re
import sys
import glob
from pathlib import Path

def lint_markdown(file_path):
    issues = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    prev_header_level = 0
    in_code_block = False

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()

        # コードブロック判定
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # 1. 1文の長さチェック（150文字超過は読みにくい）
        sentences = re.split(r'。|\. ', line)
        for s in sentences:
            if len(s.strip()) > 150:
                issues.append(f"Line {idx}: [Readability] 1文が150文字を超えています ({len(s.strip())}文字)。文を分割することを検討してください。")

        # 2. 見出し階層の飛びチェック
        header_match = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if header_match:
            level = len(header_match.group(1))
            if prev_header_level > 0 and level > prev_header_level + 1:
                issues.append(f"Line {idx}: [Structure] 見出しレベルが飛んでいます (H{prev_header_level} -> H{level})。")
            prev_header_level = level

        # 3. ら抜き言葉の簡易検知
        ra_nuki = ["出れる", "見れる", "着れる", "食べれる", "来れる", "信じれる"]
        for word in ra_nuki:
            if word in line:
                issues.append(f"Line {idx}: [Grammar] ら抜き言葉が検出されました: '{word}'")

        # 4. 二重否定の簡易検知
        if "ないわけではない" in line or "なくはない" in line:
            issues.append(f"Line {idx}: [Style] 二重否定が検出されました。肯定的な表現への言い換えを検討してください。")

    return issues

def main():
    target_files = sorted(glob.glob("manuscript/*.md"))
    total_issues = 0

    print(f"=== Markdown & Japanese Style Linter ===")
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
        print(f"FAILED: Found {total_issues} issues in manuscripts.")
        sys.exit(1)
    else:
        print("PASSED: All manuscript files passed static checks.")
        sys.exit(0)

if __name__ == "__main__":
    main()
