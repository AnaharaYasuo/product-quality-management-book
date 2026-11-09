import re
import sys
import glob
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def check_structure(file_path):
    issues = []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = Path(file_path).name
    if filename.startswith("00_") or filename.startswith("99_"):
        return issues

    # 章番号整合性チェック（例: 05_chapter5.md -> H1は「第5章」、H2は「5.1, 5.2...」）
    ch_match = re.match(r"^(\d+)_chapter(\d+)\.md$", filename)
    if ch_match:
        ch_num = int(ch_match.group(2))
        in_fence = False
        fence_marker = ""
        sec_nums = []
        for idx, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            m_fence = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
            if m_fence:
                marker, lang = m_fence.group(1), m_fence.group(2).strip()
                if not in_fence:
                    in_fence = True
                    fence_marker = marker
                elif len(marker) >= len(fence_marker) and marker[0] == fence_marker[0] and lang == "":
                    in_fence = False
                continue
            if in_fence:
                continue

            h1 = re.match(r"^#\s+(.+)$", line)
            if h1 and f"第{ch_num}章" not in h1.group(1):
                issues.append(f"[DoD-Numbering] Line {idx}: H1見出しに「第{ch_num}章」が含まれていません: {h1.group(1)}")

            h2 = re.match(r"^##\s+(\d+)\.(\d+)\s+", line)
            if h2:
                c_no, s_no = int(h2.group(1)), int(h2.group(2))
                if c_no != ch_num:
                    issues.append(f"[DoD-Numbering] Line {idx}: H2章番号が不一致です ({c_no}.{s_no} / 期待: {ch_num}.x)")
                sec_nums.append((idx, s_no))

        for i in range(len(sec_nums) - 1):
            if sec_nums[i + 1][1] != sec_nums[i][1] + 1:
                issues.append(
                    f"[DoD-Numbering] Line {sec_nums[i+1][0]}: セクション番号が連番になっていません ({ch_num}.{sec_nums[i][1]} -> {ch_num}.{sec_nums[i+1][1]})"
                )

    char_count = len(content)
    # 商業DoD基準: 8,000字以上
    if char_count < 8000:
        issues.append(f"[DoD-Volume] 文字数が不足しています ({char_count}文字 / 目標: 8,000文字以上)。")

    # Mermaid記法チェック（最低2点）
    mermaid_blocks = re.findall(r"```mermaid", content)
    if len(mermaid_blocks) < 2:
        issues.append(f"[DoD-Diagram] Mermaidダイアグラムが不足しています ({len(mermaid_blocks)}点 / 必須: 2点以上)。")

    # 実践コード・プロンプト・設定チェック（```ブロックの数、最低2点）
    code_blocks = [m for m in re.findall(r"`{3,}(\w+)", content) if m != "mermaid"]
    if len(code_blocks) < 2:
        issues.append(f"[DoD-Code] 実践コード/設定/プロンプトブロックが不足しています ({len(code_blocks)}点 / 必須: 2点以上)。")

    # QA合否判定（Pass/Fail）チェック
    if "合否" not in content and "Pass/Fail" not in content and "判定基準" not in content:
        issues.append("[DoD-QA] QA合否判定基準（Pass/Fail Criteria）の記述が見当たりません。")

    # アンチパターン対比チェック
    if "アンチパターン" not in content and "失敗" not in content and "落とし穴" not in content:
        issues.append("[DoD-AntiPattern] 失敗事例・アンチパターンとの対比が見当たりません。")

    # 章末ワークショップ / チェックリスト
    if "チェックリスト" not in content and "ワークショップ" not in content and "演習" not in content:
        issues.append("[DoD-Workshop] 章末のセルフチェックリストまたは演習課題が見当たりません。")

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
                print(f"  [FAIL] {iss}")
            print()
            has_errors = True

    if has_errors:
        print("FAILED: Incomplete or non-compliant chapters detected against Commercial Book DoD.")
        sys.exit(1)
    else:
        print("PASSED: All 25 chapters meet Commercial Book DoD & structural numbering standards.")
        sys.exit(0)


if __name__ == "__main__":
    main()
