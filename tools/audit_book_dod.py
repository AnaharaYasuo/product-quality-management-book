import re
import sys
import glob
from pathlib import Path

def check_structure(file_path):
    issues = []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # はじめに(00_)とおわりに(99_)は除外
    filename = Path(file_path).name
    if filename.startswith("00_") or filename.startswith("99_"):
        return issues

    char_count = len(content)
    # 商業DoD基準: 8,000〜12,000字（準備中・初期スケルトン時は警告）
    if char_count < 8000:
        issues.append(f"[DoD-Volume] 文字数が不足しています ({char_count}文字 / 目標: 8,000〜12,000文字)。")

    # Mermaid記法チェック（最低2点）
    mermaid_blocks = re.findall(r'```mermaid', content)
    if len(mermaid_blocks) < 2:
        issues.append(f"[DoD-Diagram] Mermaidダイアグラムが不足しています ({len(mermaid_blocks)}点 / 必須: 2点以上)。")

    # 実践コード・プロンプト・設定チェック（```ブロックの数、最低2点）
    code_blocks = [m for m in re.findall(r'```(\w+)?', content) if m != 'mermaid']
    if len(code_blocks) < 2:
        issues.append(f"[DoD-Code] 実践コード/設定/プロンプトブロックが不足しています ({len(code_blocks)}点 / 必須: 2点以上)。")

    # QA合否判定（Pass/Fail）チェック
    if "合否" not in content and "Pass/Fail" not in content and "判定基準" not in content:
        issues.append(f"[DoD-QA] QA合否判定基準（Pass/Fail Criteria）の記述が見当たりません。")

    # アンチパターン対比チェック
    if "アンチパターン" not in content and "失敗" not in content and "落とし穴" not in content:
        issues.append(f"[DoD-AntiPattern] 失敗事例・アンチパターンとの対比が見当たりません。")

    # 章末ワークショップ / チェックリスト
    if "チェックリスト" not in content and "ワークショップ" not in content and "演習" not in content:
        issues.append(f"[DoD-Workshop] 章末のセルフチェックリストまたは演習課題が見当たりません。")

    return issues

def main():
    target_files = sorted(glob.glob("manuscript/*.md"))
    print("=== Commercial Technical Book DoD Validator ===")
    print(f"Auditing {len(target_files)} manuscript files...\n")

    has_errors = False
    for f in target_files:
        issues = check_structure(f)
        if issues:
            print(f"File: {f}")
            for iss in issues:
                print(f"  [WARN/AUDIT] {iss}")
            print()
            has_errors = True

    if has_errors:
        print("Note: Incomplete chapters detected against Commercial Book DoD.")
    else:
        print("PASSED: All completed chapters meet Commercial Book DoD standards.")

if __name__ == "__main__":
    main()
