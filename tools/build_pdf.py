#!/usr/bin/env python3
"""
tools/build_pdf.py
全27原稿ファイル（manuscript/*.md）から印刷・閲覧用のA4版PDFおよびプレビューHTMLを生成し、
生成されたDOMおよびPDFに対して以下の決定論的E2Eスモークテストを実施する：
1. Markdown変換時にMermaidブロックおよびフェンス付きコードブロックを退避し、
   コード例内部の `#` や `##` がH1/H2見出しや目次に誤変換されることを完全に防止する。
2. 康熙部首（U+2F00..U+2FDF）およびCJK互換漢字を標準統合漢字へ正規化し、標準フォントを優先指定する。
3. Playwright（Headless Chromium）上でMermaid v10による全図解のSVGレンダリングを実行。
4. DOM上の全 `.mermaid-container` を検査し、`Syntax error in text` や未描画SVG、または横幅過大（viewBox width > 2200px）の図解があればビルド失敗（Exit Code 1）とする。
5. `<pre><code>` 内部に `<h1` や `<h2` タグが混入していないこと、および未変換の `$$` 数式や康熙部首が0件であることをE2E検証する。
"""

import argparse
import asyncio
import html
import re
import sys
import unicodedata
from pathlib import Path
import markdown

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def normalize_kangxi_and_compat_cjk(text: str) -> str:
    """康熙部首（U+2F00..U+2FDF）およびCJK互換漢字（U+F900..U+FAFF）のみを標準統合漢字へ正規化する。"""
    out = []
    for ch in text:
        cp = ord(ch)
        if (0x2F00 <= cp <= 0x2FDF) or (0x2E80 <= cp <= 0x2EFF) or (0xF900 <= cp <= 0xFAFF):
            out.append(unicodedata.normalize("NFKC", ch))
        else:
            out.append(ch)
    return "".join(out)


def build_combined_html(repo_dir: Path, html_out: Path) -> int:
    md_files = sorted((repo_dir / "manuscript").glob("*.md"))
    style_css = (repo_dir / "manuscript" / "style.css").read_text(encoding="utf-8")

    chapters_html = []
    toc_items = []
    total_mermaid = 0

    mermaid_pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)

    for idx, f in enumerate(md_files):
        raw_md = normalize_kangxi_and_compat_cjk(f.read_text(encoding="utf-8"))

        # 1. Mermaidブロックをプレースホルダに退避（markdownパーサーが <|-- 等をHTMLタグと誤認して破壊するのを防止）
        mermaid_store = []

        def stash_mermaid(match):
            nonlocal total_mermaid
            total_mermaid += 1
            code = match.group(1)
            token = f"@@MERMAID_BLOCK_{len(mermaid_store)}@@"
            mermaid_store.append(code)
            return f"\n\n{token}\n\n"

        md_without_mermaid = mermaid_pattern.sub(stash_mermaid, raw_md)

        # 1.5. すべてのフェンス付きコードブロック（```...``` / ````...````）を一時退避
        #      （コード例内部の `#` や `##` がH1/H2見出しや目次に誤変換されるのを防ぐため）
        code_fence_store = []
        lines_stashed = []
        in_fence = False
        fence_marker = ""
        current_fence_lines = []

        for line in md_without_mermaid.splitlines():
            s = line.strip()
            m = re.match(r"^(`{3,}|~{3,})(.*)$", s)
            if m:
                marker, lang = m.group(1), m.group(2).strip()
                if not in_fence:
                    in_fence = True
                    fence_marker = marker
                    current_fence_lines = [line]
                    continue
                elif len(marker) >= len(fence_marker) and marker[0] == fence_marker[0] and lang == "":
                    current_fence_lines.append(line)
                    token = f"@@CODE_FENCE_{len(code_fence_store)}@@"
                    code_fence_store.append("\n".join(current_fence_lines))
                    lines_stashed.append(token)
                    in_fence = False
                    fence_marker = ""
                    current_fence_lines = []
                    continue
            if in_fence:
                current_fence_lines.append(line)
            else:
                lines_stashed.append(line)

        if current_fence_lines:
            lines_stashed.extend(current_fence_lines)

        md_stashed = "\n".join(lines_stashed)

        # 2. H1・H2見出しに目次ジャンプ用IDを付与（コードブロック外の真の見出しのみ対象）
        h1_match = re.search(r"^#\s+(.+)$", md_stashed, re.MULTILINE)
        ch_id = f"chapter-{idx:02d}"
        title_text = f.stem
        if h1_match:
            title_text = h1_match.group(1).strip()
            md_stashed = re.sub(
                r"^#\s+(.+)$",
                f'<h1 id="{ch_id}">\\1</h1>',
                md_stashed,
                count=1,
                flags=re.MULTILINE,
            )

        h2_list = []

        def h2_repl(m):
            h2_title = m.group(1).strip()
            h2_id = f"{ch_id}-sec-{len(h2_list)+1}"
            h2_list.append((h2_id, h2_title))
            return f'<h2 id="{h2_id}">{h2_title}</h2>'

        md_stashed = re.sub(r"^##\s+(.+)$", h2_repl, md_stashed, flags=re.MULTILINE)
        toc_items.append((ch_id, title_text, h2_list))

        # 2.5. 退避したフェンス付きコードブロックを復元してからMarkdownパーサーへ渡す
        for c_idx, c_block in enumerate(code_fence_store):
            md_stashed = md_stashed.replace(f"@@CODE_FENCE_{c_idx}@@", c_block)

        md_without_mermaid = md_stashed

        # 3. Markdown -> HTML 変換
        html_body = markdown.markdown(
            md_without_mermaid,
            extensions=["tables", "fenced_code", "sane_lists"],
        )

        # 4. 退避したMermaidコードをHTMLエスケープして復元
        for m_idx, m_code in enumerate(mermaid_store):
            escaped_code = html.escape(m_code, quote=False)
            placeholder_html = f"<p>@@MERMAID_BLOCK_{m_idx}@@</p>"
            replacement_html = f'<div class="mermaid-container"><pre class="mermaid">\n{escaped_code}\n</pre></div>'
            if placeholder_html in html_body:
                html_body = html_body.replace(placeholder_html, replacement_html)
            else:
                html_body = html_body.replace(f"@@MERMAID_BLOCK_{m_idx}@@", replacement_html)

        chapters_html.append(f'<section class="chapter-section" data-source="{f.name}">\n{html_body}\n</section>')

    # 目次に部（Part）の区切りを表示する（キー: その部の最初の章番号）
    part_starts = {
        1: "第I部：パラダイムシフトと二大成果物モデル",
        3: "第II部：プロダクト成果物の検証・レビュー・監査",
        10: "第III部：開発プロセス成果物のバリエーションと品質保証",
        14: "第IV部：動的検証・シフトライト・セキュリティ品質",
        17: "第V部：AIプロダクトと自律型AIエージェントの品質保証",
        20: "第VI部：組織変革・カルチャーと品質の未来",
        22: "第VII部：品質のトレードオフ・倫理・現場のリアリズム",
    }
    toc_html = ['<nav class="toc-page"><h1 class="toc-title">目次（Table of Contents）</h1><ul class="toc-root">']
    for ch_id, title_text, h2_list in toc_items:
        m_ch = re.match(r"第(\d+)章", title_text)
        if m_ch and int(m_ch.group(1)) in part_starts:
            toc_html.append(f'<li class="toc-part">{part_starts[int(m_ch.group(1))]}</li>')
        toc_html.append(f'<li class="toc-h1"><a href="#{ch_id}">{title_text}</a>')
        if h2_list:
            toc_html.append('<ul class="toc-h2">')
            for h2_id, h2_title in h2_list:
                toc_html.append(f'<li><a href="#{h2_id}">{h2_title}</a></li>')
            toc_html.append("</ul>")
        toc_html.append("</li>")
    toc_html.append("</ul></nav>")

    full_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>プロダクト品質管理の実践ガイド — 高品質なプロダクトを継続的に届けるための設計とプロセス</title>
<style>
{style_css}

@page {{
  size: A4;
  margin: 20mm 18mm 20mm 18mm;
}}

body {{
  font-family: "Noto Sans CJK JP", "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif;
  line-height: 1.75;
  color: #222;
  margin: 0;
  padding: 0;
  font-size: 10.5pt;
}}

.cover-page {{
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 240mm;
  text-align: center;
  page-break-after: always;
  border: 2px solid #2b5b84;
  padding: 20mm;
  box-sizing: border-box;
}}

.cover-page .book-title {{
  font-size: 26pt;
  font-weight: bold;
  color: #1a3c5a;
  margin-bottom: 12pt;
  border: none;
  page-break-before: avoid;
}}

.cover-page .book-subtitle {{
  font-size: 14pt;
  color: #444;
  margin-bottom: 40pt;
}}

.cover-page .book-meta {{
  font-size: 12pt;
  color: #555;
  margin-top: auto;
}}

.toc-page {{
  page-break-after: always;
}}

.toc-page h1.toc-title {{
  page-break-before: avoid;
}}

.toc-root {{
  list-style: none;
  padding-left: 0;
}}

.toc-part {{
  margin-top: 14pt;
  padding: 3pt 6pt;
  background: #eef3f8;
  color: #1a3c5a;
  font-weight: bold;
  font-size: 11pt;
}}

.toc-h1 {{
  margin-top: 8pt;
  font-weight: bold;
}}

.toc-h1 > a {{
  color: #1a3c5a;
  text-decoration: none;
}}

.toc-h2 {{
  list-style: disc;
  padding-left: 20pt;
  font-weight: normal;
  font-size: 9.5pt;
  margin-top: 2pt;
  margin-bottom: 4pt;
}}

.toc-h2 a {{
  color: #444;
  text-decoration: none;
}}

h1 {{
  page-break-before: always;
  font-size: 18pt;
  color: #1a3c5a;
  border-bottom: 2px solid #2b5b84;
  padding-bottom: 6pt;
  margin-top: 0;
}}

h2 {{
  font-size: 13.5pt;
  color: #1a3c5a;
  border-left: 5px solid #2b5b84;
  padding-left: 8pt;
  margin-top: 18pt;
  page-break-after: avoid;
}}

h3 {{
  font-size: 11.5pt;
  color: #2b5b84;
  margin-top: 14pt;
  page-break-after: avoid;
}}

p {{
  text-indent: 0;
  margin: 6pt 0;
}}

pre {{
  background-color: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 4px;
  padding: 8pt;
  font-size: 8.5pt;
  line-height: 1.45;
  white-space: pre-wrap;
  word-wrap: break-word;
  page-break-inside: avoid;
}}

code {{
  font-family: Consolas, "Courier New", monospace;
  font-size: 9pt;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 9pt;
  margin: 10pt 0;
  page-break-inside: auto;
}}

tr {{
  page-break-inside: avoid;
  page-break-after: auto;
}}

th, td {{
  border: 1px solid #ccc;
  padding: 5pt 6pt;
  vertical-align: top;
}}

th {{
  background-color: #eef3f8;
  color: #1a3c5a;
  font-weight: bold;
}}

.mermaid-container {{
  margin: 12pt 0;
  text-align: center;
  page-break-inside: avoid;
}}

.mermaid {{
  background: #ffffff;
  border: 1px solid #e0e0e0;
  padding: 10pt;
  display: flex;
  justify-content: center;
}}

.mermaid svg {{
  max-width: 100% !important;
  height: auto !important;
  max-height: 180mm;
}}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
    flowchart: {{ htmlLabels: true, curve: 'basis' }}
  }});
</script>
</head>
<body>
  <div class="cover-page">
    <div class="book-title">プロダクト品質管理の実践ガイド</div>
    <div class="book-subtitle">高品質なプロダクトを継続的に届けるための設計とプロセス<br>（AI時代のプロダクト・プロセス確証バイブル）</div>
    <div class="book-meta">
      <p>著者：Anahara Yasuo</p>
      <p>版数：第1版 第1刷（全7部・25章＋巻末付録）</p>
      <p>Copyright © 2026 Anahara Yasuo. All rights reserved.</p>
      <p>掲載サンプルコードは MIT License で提供（LICENSE-CODE 参照）</p>
    </div>
  </div>
  {''.join(toc_html)}
  {''.join(chapters_html)}
</body>
</html>
"""

    html_out.parent.mkdir(parents=True, exist_ok=True)
    html_out.write_text(full_html, encoding="utf-8")
    return total_mermaid


async def render_and_smoke_test_pdf(html_out: Path, pdf_out: Path, expected_mermaid_count: int):
    from playwright.async_api import async_playwright

    # 静的HTML検証：コードブロック内の見出し誤変換・康熙部首・未変換LaTeX数式の検査
    html_text = html_out.read_text(encoding="utf-8")
    kangxi_hits = re.findall(r"[\u2E80-\u2FDF\uF900-\uFAFF]", html_text)
    if kangxi_hits:
        raise RuntimeError(f"Smoke test failed: {len(kangxi_hits)} Kangxi/compatibility CJK character(s) found in HTML!")
    if "$$" in html_text:
        raise RuntimeError("Smoke test failed: unrendered LaTeX display math '$$' found in HTML!")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception:
            browser = await p.chromium.launch(
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                headless=True,
            )

        page = await browser.new_page()
        await page.goto(html_out.as_uri(), wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(4000)

        # 決定論的E2Eスモークテスト：全Mermaid図解の正常レンダリング・横幅上限・コード内見出し混入ゼロ確認
        audit = await page.evaluate("""() => {
            const sections = document.querySelectorAll('section.chapter-section');
            const containers = Array.from(document.querySelectorAll('.mermaid-container'));
            const errors = [];
            const wideDiagrams = [];
            containers.forEach((c, idx) => {
                const txt = c.innerText || '';
                const html = c.innerHTML || '';
                const sec = c.closest('section.chapter-section');
                const src = sec ? sec.getAttribute('data-source') : 'unknown';
                if (txt.includes('Syntax error') || html.includes('Syntax error') || html.includes('class="error-icon"') || !html.includes('<svg')) {
                    errors.push({ index: idx + 1, source: src, snippet: txt.slice(0, 120) });
                } else {
                    const svg = c.querySelector('svg');
                    if (svg) {
                        const vb = svg.getAttribute('viewBox');
                        if (vb) {
                            const parts = vb.trim().split(/[\\s,]+/);
                            const w = parseFloat(parts[2]);
                            if (w > 2200) {
                                wideDiagrams.push({ index: idx + 1, source: src, width: Math.round(w) });
                            }
                        }
                    }
                }
            });
            const codeBlocks = Array.from(document.querySelectorAll('pre code'));
            const leakedHeadings = [];
            codeBlocks.forEach((cb) => {
                if (cb.innerHTML.includes('<h1 id=') || cb.innerHTML.includes('<h2 id=')) {
                    leakedHeadings.push(cb.innerText.slice(0, 80));
                }
            });
            return {
                sectionCount: sections.length,
                mermaidCount: containers.length,
                errors: errors,
                wideDiagrams: wideDiagrams,
                leakedHeadings: leakedHeadings
            };
        }""")

        print(f"[Smoke Test] Sections rendered: {audit['sectionCount']} (expected: 27)")
        print(f"[Smoke Test] Mermaid diagrams rendered: {audit['mermaidCount']} (expected: {expected_mermaid_count})")

        if audit["sectionCount"] != 27:
            await browser.close()
            raise RuntimeError(f"Smoke test failed: expected 27 sections, got {audit['sectionCount']}")

        if audit["mermaidCount"] != expected_mermaid_count:
            await browser.close()
            raise RuntimeError(
                f"Smoke test failed: expected {expected_mermaid_count} Mermaid diagrams, got {audit['mermaidCount']}"
            )

        if audit["errors"]:
            for err in audit["errors"]:
                print(f"  ❌ Render Error in Diagram #{err['index']} ({err['source']}): {err['snippet']}")
            await browser.close()
            raise RuntimeError(f"Smoke test failed: {len(audit['errors'])} Mermaid diagram(s) had syntax/render errors in combined DOM!")

        if audit["wideDiagrams"]:
            for wd in audit["wideDiagrams"]:
                print(f"  ❌ Overly Wide Diagram #{wd['index']} ({wd['source']}): viewBox width={wd['width']}px (> 2200px)")
            await browser.close()
            raise RuntimeError(f"Smoke test failed: {len(audit['wideDiagrams'])} Mermaid diagram(s) exceed maximum readable width!")

        if audit["leakedHeadings"]:
            await browser.close()
            raise RuntimeError(f"Smoke test failed: {len(audit['leakedHeadings'])} code block(s) contain leaked <h1>/<h2> tags!")

        pdf_out.parent.mkdir(parents=True, exist_ok=True)
        await page.pdf(
            path=str(pdf_out),
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template='<div style="font-size:8px; color:#888; width:100%; text-align:right; padding-right:18mm;">プロダクト品質管理の実践ガイド</div>',
            footer_template='<div style="font-size:9px; color:#666; width:100%; text-align:center;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
            margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
        )
        await browser.close()

        pdf_size = pdf_out.stat().st_size
        if pdf_size < 500_000:
            raise RuntimeError(f"Smoke test failed: generated PDF is unexpectedly small ({pdf_size} bytes)")
        print(f"PASSED: PDF built and verified at {pdf_out} ({pdf_size:,} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Build & E2E-verify full book HTML and PDF")
    parser.add_argument("--html-out", default="output/product-quality-management.html", help="Output HTML path")
    parser.add_argument("--pdf-out", default="output/product-quality-management.pdf", help="Output PDF path")
    args = parser.parse_args()

    repo_dir = Path(__file__).resolve().parent.parent
    html_out = Path(args.html_out)
    pdf_out = Path(args.pdf_out)

    print("=== Building Combined Book HTML & PDF with E2E Smoke Verification ===")
    expected_mermaid = build_combined_html(repo_dir, html_out)
    asyncio.run(render_and_smoke_test_pdf(html_out.resolve(), pdf_out.resolve(), expected_mermaid))


if __name__ == "__main__":
    main()
