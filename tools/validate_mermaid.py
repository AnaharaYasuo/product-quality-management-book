#!/usr/bin/env python3
"""
tools/validate_mermaid.py
原稿（manuscript/*.md）内の全Mermaidコードブロックを抽出し、
本物のMermaidエンジン（Playwright + Mermaid v10）で構文パース・SVG描画検証・横幅可読性検査を行う品質ゲートスクリプト。

1つでも Syntax error または横幅過大（viewBox width > 2200px による文字潰れ）が検出された場合は、
該当ファイル名・行番号・エラー詳細を出力し Exit Code 1 で終了する。
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def extract_mermaid_blocks(target_files: List[Path]) -> List[Dict[str, Any]]:
    blocks = []
    bracket_pairs = [("「", "」"), ("（", "）"), ("『", "』"), ("【", "】")]
    for f in target_files:
        text = f.read_text(encoding="utf-8")
        lines = text.splitlines()
        in_mermaid = False
        start_line = 0
        buf = []
        for idx, line in enumerate(lines, 1):
            if not in_mermaid and line.strip().startswith("```mermaid"):
                in_mermaid = True
                start_line = idx
                buf = []
            elif in_mermaid and line.strip() == "```":
                in_mermaid = False
                code = "\n".join(buf)
                for ob, cb in bracket_pairs:
                    if code.count(ob) != code.count(cb):
                        raise RuntimeError(
                            f"[Mermaid Syntax] Unbalanced brackets '{ob}{cb}' ({code.count(ob)} vs {code.count(cb)}) in {f.name}:{start_line}"
                        )
                blocks.append({
                    "file": str(f),
                    "filename": f.name,
                    "start_line": start_line,
                    "end_line": idx,
                    "code": code
                })
            elif in_mermaid:
                buf.append(line)
    return blocks


async def validate_blocks_with_mermaid(blocks: List[Dict[str, Any]]) -> int:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception:
            browser = await p.chromium.launch(
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                headless=True
            )

        page = await browser.new_page()
        await page.set_content("""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
          <meta charset="utf-8">
          <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
          <script>
            mermaid.initialize({
              startOnLoad: false,
              theme: 'default',
              securityLevel: 'loose',
              flowchart: { htmlLabels: true, curve: 'basis' }
            });
          </script>
        </head>
        <body><div id="app"></div></body>
        </html>
        """, wait_until="networkidle", timeout=60000)

        error_count = 0
        for idx, b in enumerate(blocks):
            res = await page.evaluate("""async ({id, code}) => {
                try {
                    await mermaid.parse(code);
                    const { svg } = await mermaid.render('mermaid_test_' + id, code);
                    if (svg.includes('Syntax error in text') || svg.includes('class="error-icon"')) {
                        return { ok: false, error: 'Rendered SVG contains Syntax error' };
                    }
                    const m = svg.match(/viewBox="([^"]+)"/);
                    if (m) {
                        const parts = m[1].trim().split(/[\\s,]+/);
                        const w = parseFloat(parts[2]);
                        if (w > 2200) {
                            return { ok: false, error: 'Diagram is too wide (viewBox width=' + Math.round(w) + 'px > 2200px); convert flowchart LR / horizontal subgraph to vertical flowchart TD so text remains readable on A4 PDF.' };
                        }
                    }
                    return { ok: true };
                } catch (err) {
                    return { ok: false, error: err && err.message ? err.message : String(err) };
                }
            }""", {"id": idx, "code": b["code"]})

            if not res["ok"]:
                error_count += 1
                print(f"❌ [Mermaid Validation Error] {b['file']}:{b['start_line']}-{b['end_line']}")
                print(f"   Reason: {res['error']}")
                print("   Code:")
                for l_idx, code_line in enumerate(b["code"].splitlines(), b["start_line"] + 1):
                    print(f"     {l_idx:4d} | {code_line}")
                print("-" * 60)

        await browser.close()
        return error_count


def main():
    target_files = sorted(Path("manuscript").glob("*.md"))
    blocks = extract_mermaid_blocks(target_files)

    print("=== Mermaid Diagram Syntax & Readability Width Validator ===")
    print(f"Scanning {len(blocks)} Mermaid diagrams across {len(target_files)} manuscript files...\n")

    if not blocks:
        print("No Mermaid diagrams found.")
        sys.exit(0)

    error_count = asyncio.run(validate_blocks_with_mermaid(blocks))

    if error_count > 0:
        print(f"\nFAILED: {error_count} / {len(blocks)} Mermaid diagram(s) failed syntax or width validation.")
        sys.exit(1)
    else:
        print(f"PASSED: All {len(blocks)} Mermaid diagrams parsed and rendered cleanly within readable width bounds.")
        sys.exit(0)


if __name__ == "__main__":
    main()
