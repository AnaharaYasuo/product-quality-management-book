import glob
import re
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 各章の正規テーマキーワード定義（次章予告や他章参照が旧構成の草案と食い違っていないかを決定論的に検査）
CHAPTER_TOPIC_ANCHORS = {
    1: ["確証", "Assurance", "DORA", "ISO/IEC 25010"],
    2: ["シフトレフト", "二大成果物", "Verification", "Validation"],
    3: ["企画", "要求", "PRD", "プレモーテム"],
    4: ["UI", "UX", "デザイン", "WCAG"],
    5: ["機能仕様", "受入基準", "Three Amigos", "Example Mapping", "Gherkin"],
    6: ["アーキテクチャ", "設計", "ADR", "OpenAPI", "C4"],
    7: ["ソースコード", "静的解析", "SAST", "AutoCommenter"],
    8: ["インフラ", "CI/CD", "IaC", "Terraform", "Checkov"],
    9: ["テスト資産", "ミューテーション", "Mutation", "Flaky", "TestGen"],
    10: ["類型", "ウォーターフォール", "スクラム", "カンバン", "トランクベース"],
    11: ["仕様化", "DoD", "DoR", "テンプレート"],
    12: ["静的検証", "ガードレール", "commitlint", "Danger", "Gatekeeper"],
    13: ["動的検証", "DORA", "フローメトリクス", "ボトルネック"],
    14: ["自動テスト", "Testcontainers", "Playwright", "自己修復", "E2E"],
    15: ["シフトライト", "カナリア", "SLO", "エラーバジェット", "ポストモーテム"],
    16: ["サプライチェーン", "SBOM", "SLSA", "Cosign", "TruffleHog", "DevSecOps"],
    17: ["データ品質", "機械学習", "Great Expectations", "ドリフト", "ISO/IEC 25012"],
    18: ["LLM", "RAG", "Ragas", "LLM-as-a-Judge", "レッドチーミング"],
    19: ["エージェント", "AI-native", "サンドボックス", "改ざん"],
    20: ["全員品質", "Whole-Team", "イネーブラー", "品質コーチ"],
    21: ["ロードマップ", "成熟度", "ROI", "チェンジマネジメント"],
    22: ["リスクベース", "CoQ", "品質コスト", "Tier"],
    23: ["Goodhart", "グッドハート", "メトリクスハック", "ペアメトリクス", "Paved Path"],
    24: ["決定論的アンカー", "Deterministic", "共謀", "アンカー"],
    25: ["妥当性確認", "Validation", "25019", "ゾンビ機能", "機能を捨てる"],
}


def check_structure(file_path):
    issues = []
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    filename = Path(file_path).name
    if filename.startswith("00_") or filename.startswith("99_"):
        return issues

    # 章番号整合性チェック（例: 05_chapter5.md -> H1は「# 第5章：...」、H2は「5.1, 5.2...」）
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
            if h1:
                h1_text = h1.group(1)
                if not h1_text.startswith(f"第{ch_num}章："):
                    issues.append(
                        f"[DoD-Numbering] Line {idx}: H1見出しは「# 第{ch_num}章：タイトル」（全角コロン付き）に統一してください: {h1_text}"
                    )

            h2 = re.match(r"^##\s+(\d+)\.(\d+)\s+", line)
            if h2:
                c_no, s_no = int(h2.group(1)), int(h2.group(2))
                if c_no != ch_num:
                    issues.append(f"[DoD-Numbering] Line {idx}: H2章番号が不一致です ({c_no}.{s_no} / 期待: {ch_num}.x)")
                sec_nums.append((idx, s_no))

            # 次章・最終章への接続（Cross-Reference）整合性チェック
            next_ref = re.search(r"(?:次章|最終章)（第(\d+)章）", line)
            if next_ref:
                ref_ch = int(next_ref.group(1))
                if ref_ch != ch_num + 1:
                    issues.append(
                        f"[DoD-CrossRef] Line {idx}: 次章番号が不正です（第{ch_num}章の次章として第{ref_ch}章が参照されています）"
                    )
                else:
                    expected_keywords = CHAPTER_TOPIC_ANCHORS.get(ref_ch, [])
                    if expected_keywords and not any(kw.lower() in line.lower() for kw in expected_keywords):
                        issues.append(
                            f"[DoD-CrossRef] Line {idx}: 次章（第{ref_ch}章）の予告内容が実際の第{ref_ch}章のテーマ（{expected_keywords}）と一致していません: {line.strip()}"
                        )

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
    print("=== Commercial Technical Book DoD & Cross-Reference Validator ===")
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
        print("PASSED: All 25 chapters meet Commercial Book DoD, H1 format, and Cross-Reference standards.")
        sys.exit(0)


if __name__ == "__main__":
    main()
