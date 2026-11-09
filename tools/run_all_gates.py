#!/usr/bin/env python3
"""
tools/run_all_gates.py
本書が提唱する「舗装された道路（Paved Path：第23章）」および「決定論的アンカー（第24章）」の統合実行ランナー。
1コマンドで以下のすべての品質ゲートをローカルまたはCI上で直列・決定論的に検証する：
1. 日本語スタイル・コードフェンス整合性・技術用語契約・埋め込みコードAST検査 (tools/lint_manuscript.py)
2. 商業技術書DoD・章番号連番整合性監査 (tools/audit_book_dod.py)
3. Mermaid全75図のAST構文パース＆SVG描画検証 (tools/validate_mermaid.py)
"""

import subprocess
import sys
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GATES = [
    ("Gate 1: Manuscript Style, Terminology Contract & Embedded Code AST", [sys.executable, "tools/lint_manuscript.py"]),
    ("Gate 2: Commercial DoD & Chapter/Section Numbering Audit", [sys.executable, "tools/audit_book_dod.py"]),
    ("Gate 3: Mermaid Diagram AST & Real-Browser SVG Validation", [sys.executable, "tools/validate_mermaid.py"]),
]


def main():
    print("=" * 72)
    print("  Assurance-Driven Development: Paved-Path Quality Gate Runner")
    print("=" * 72)
    start_all = time.time()

    for name, cmd in GATES:
        print(f"\n>>> Running [{name}] ...")
        t0 = time.time()
        res = subprocess.run(cmd)
        elapsed = time.time() - t0
        if res.returncode != 0:
            print(f"\n❌ BLOCKED at [{name}] ({elapsed:.1f}s). Fix the reported issues before pushing.")
            sys.exit(res.returncode)
        print(f"✅ [{name}] PASSED ({elapsed:.1f}s)")

    total_elapsed = time.time() - start_all
    print("\n" + "=" * 72)
    print(f"🎉 ALL DETERMINISTIC QUALITY GATES PASSED in {total_elapsed:.1f}s!")
    print("=" * 72)
    sys.exit(0)


if __name__ == "__main__":
    main()
