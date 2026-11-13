#!/usr/bin/env python3
"""
tools/verify_epub.py
生成された KDP 入稿用 EPUB ファイルを展開せずに ZIP/XHTML レベルで決定論的にスモーク検証する：
1. EPUB MIME type (`application/epub+zip`) および `EPUB/content.opf` の存在検証
2. KDP推奨仕様の表紙画像（`cover-image`、1600x2560px PNG）がマニフェスト登録・同梱されていること
3. 目次（`EPUB/nav.xhtml`）のタイトルが「目次」であり、全7部の部見出しが含まれていること
4. 本文 XHTML 内に未変換の `<pre class="mermaid">` コードブロックが 0 件であること
5. 本文 XHTML 内に事前レンダリングされた `.mermaid-figure` 画像が原稿の Mermaid 総数（75件）と一致し、
   すべての参照先 PNG がアーカイブ内に実在・有効な PNG ヘッダを持つこと
6. 康熙部首・CJK互換漢字の混入が 0 件であり、巻末に「奥付」が収録されていること
"""

import posixpath
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def count_manuscript_mermaids(repo_dir: Path) -> int:
    pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)
    total = 0
    for md in sorted((repo_dir / "manuscript").glob("*.md")):
        total += len(pattern.findall(md.read_text(encoding="utf-8")))
    return total


def png_dimensions(data: bytes, label: str) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError(f"[EPUB-Smoke] {label} is not a valid PNG binary")
    return struct.unpack(">II", data[16:24])


def verify_epub(epub_path: Path, expected_mermaids: int) -> None:
    if not epub_path.exists():
        raise RuntimeError(f"[EPUB-Smoke] File not found: {epub_path}")

    with zipfile.ZipFile(epub_path, "r") as zf:
        names = set(zf.namelist())
        if "mimetype" not in names:
            raise RuntimeError("[EPUB-Smoke] Missing 'mimetype' entry in EPUB")
        mime = zf.read("mimetype").decode("ascii", errors="replace")
        if mime != "application/epub+zip":
            raise RuntimeError(f"[EPUB-Smoke] Unexpected mimetype: {mime!r}")

        if "EPUB/content.opf" not in names:
            raise RuntimeError("[EPUB-Smoke] Missing 'EPUB/content.opf'")

        opf_xml = zf.read("EPUB/content.opf").decode("utf-8")
        root = ET.fromstring(opf_xml)
        ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}

        title_el = root.find(".//dc:title", ns)
        if title_el is None or "プロダクト品質管理の実践ガイド" not in (title_el.text or ""):
            raise RuntimeError("[EPUB-Smoke] Missing or invalid <dc:title> in content.opf")

        # 1. 表紙画像の検証 (1600x2560 PNG)
        cover_href = None
        for item in root.findall(".//opf:manifest/opf:item", ns):
            if "cover-image" in (item.attrib.get("properties") or "").split():
                cover_href = item.attrib.get("href")
                break
        if not cover_href:
            raise RuntimeError("[EPUB-Smoke] No manifest item with properties='cover-image' found in content.opf")

        cover_zip_path = posixpath.normpath(posixpath.join("EPUB", cover_href))
        if cover_zip_path not in names:
            raise RuntimeError(f"[EPUB-Smoke] Cover image missing in archive: {cover_zip_path}")
        cw, ch = png_dimensions(zf.read(cover_zip_path), cover_zip_path)
        if (cw, ch) != (1600, 2560):
            raise RuntimeError(f"[EPUB-Smoke] Expected cover PNG 1600x2560, got {cw}x{ch}")

        # 2. 目次（nav.xhtml）の検証
        if "EPUB/nav.xhtml" not in names:
            raise RuntimeError("[EPUB-Smoke] Missing 'EPUB/nav.xhtml'")
        nav_txt = zf.read("EPUB/nav.xhtml").decode("utf-8")
        if ">目次<" not in nav_txt:
            raise RuntimeError("[EPUB-Smoke] TOC title in nav.xhtml is not '目次'")
        for roman in ("I", "II", "III", "IV", "V", "VI", "VII"):
            if f"第{roman}部：" not in nav_txt:
                raise RuntimeError(f"[EPUB-Smoke] Missing '第{roman}部：' in EPUB nav.xhtml")

        # 3. 全 XHTML の走査（未変換Mermaidゼロ・全図解画像実在・康熙部首ゼロ・奥付存在）
        xhtml_files = sorted(n for n in names if n.startswith("EPUB/text/") and n.endswith(".xhtml"))
        raw_mermaid_blocks = 0
        rendered_figures = 0
        kangxi_hits = 0
        has_colophon = False

        for xf in xhtml_files:
            xtxt = zf.read(xf).decode("utf-8")
            if '<pre class="mermaid"' in xtxt or "sourceCode mermaid" in xtxt:
                raw_mermaid_blocks += len(re.findall(r'mermaid', xtxt))
            for m_fig in re.finditer(r'<div class="mermaid-figure">.*?<img[^>]+src="([^"]+)"', xtxt, flags=re.DOTALL):
                rendered_figures += 1
                rel_src = m_fig.group(1)
                img_zip_path = posixpath.normpath(posixpath.join(posixpath.dirname(xf), rel_src))
                if img_zip_path not in names:
                    raise RuntimeError(f"[EPUB-Smoke] Missing diagram image {img_zip_path} referenced from {xf}")
                iw, ih = png_dimensions(zf.read(img_zip_path), img_zip_path)
                if iw < 20 or ih < 20:
                    raise RuntimeError(f"[EPUB-Smoke] Invalid diagram dimensions {iw}x{ih} in {img_zip_path}")
            kangxi_hits += len(re.findall(r"[\u2E80-\u2FDF\uF900-\uFAFF]", xtxt))
            if "奥付" in xtxt and "第1版 第1刷" in xtxt:
                has_colophon = True

        if raw_mermaid_blocks > 0:
            raise RuntimeError("[EPUB-Smoke] Found unrendered raw Mermaid code block(s) in EPUB XHTML!")
        if rendered_figures != expected_mermaids:
            raise RuntimeError(
                f"[EPUB-Smoke] Expected {expected_mermaids} rendered Mermaid figures in EPUB, got {rendered_figures}"
            )
        if kangxi_hits > 0:
            raise RuntimeError(f"[EPUB-Smoke] Found {kangxi_hits} Kangxi/compatibility CJK character(s) in EPUB XHTML!")
        if not has_colophon:
            raise RuntimeError("[EPUB-Smoke] Missing colophon ('奥付' / '第1版 第1刷') in EPUB!")

    print(
        f"✅ PASSED: EPUB verified at {epub_path} "
        f"({epub_path.stat().st_size:,} bytes, cover={cw}x{ch}px, diagrams={rendered_figures}/{expected_mermaids}, raw_mermaid=0)"
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/verify_epub.py <path-to-epub>", file=sys.stderr)
        return 2
    repo_dir = Path(__file__).resolve().parent.parent
    epub_path = Path(sys.argv[1])
    expected_mermaids = count_manuscript_mermaids(repo_dir)
    verify_epub(epub_path, expected_mermaids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
