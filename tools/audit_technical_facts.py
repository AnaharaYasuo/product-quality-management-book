#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次情報に基づく技術ファクト検証 & 埋め込みPythonコード実ツール静的解析 (RAG + Ruff Gate)

【本スクリプトが解決する課題】
LLM単独の「優秀なエンジニアロールプレイ監査」は、2023年末改訂のISO規格（ISO/IEC 25019:2023等）や
実コードの未使用変数・未定義シンボルに対してハルシネーションや見落としを起こしやすい。
そこで本スクリプトは以下の3層防御（Defense-in-Depth）を実行する：

1. [Layer 1: Deterministic RAG Ground-Truth Check]
   `docs/knowledge_base/technical_ground_truth.yaml`（一次情報の正解知識ベース）を読み込み、
   旧規格との混同パターン（`deterministic_fact_rules`）および必須一次情報契約（`required_fact_assertions`）を
   決定論的に全章検査する。
2. [Layer 2: Executable Static Analysis via Ruff]
   原稿内の全 ```python コードブロックを一時ファイルに抽出し、実ツール `ruff`（E, F, B, PLE）で
   未定義関数（F821）、未使用インポート（F401）、ループ変数の未使用バグ（B007）等を機械的に摘発する。
3. [Layer 3: Optional RAG-Grounded Principal Engineer AI Review (--llm)]
   `GEMINI_API_KEY` が指定され `--llm` フラグが渡された場合、`technical_ground_truth.yaml` の全文を
   システムプロンプトへRAG注入（Grounding）した上で、章単位の深い技術整合性レビューを実行する。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

MANUSCRIPT_DIR = Path("manuscript")
KNOWLEDGE_BASE_PATH = Path("docs/knowledge_base/technical_ground_truth.yaml")


def extract_python_blocks(text: str) -> List[Tuple[int, str]]:
    """Markdownテキストから ```python コードブロックの (開始行番号, コード本文) リストを抽出する。"""
    lines = text.splitlines()
    blocks: List[Tuple[int, str]] = []
    in_fence = False
    fence_marker = ""
    fence_lang = ""
    start_line = 0
    buf: List[str] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_fence:
            m = re.match(r"^(`{3,}|~{3,})\s*([^\s`~]*)", stripped)
            if m:
                in_fence = True
                fence_marker = m.group(1)
                fence_lang = (m.group(2) or "").lower()
                start_line = idx
                buf = []
        else:
            if re.match(rf"^{re.escape(fence_marker)}\s*$", stripped):
                if fence_lang in ("python", "py"):
                    blocks.append((start_line, "\n".join(buf) + "\n"))
                in_fence = False
                fence_marker = ""
                fence_lang = ""
                buf = []
            else:
                buf.append(line)
    return blocks


def verify_rag_ground_truth(kb: dict, md_files: List[Path]) -> List[str]:
    """Layer 1: 知識ベース (YAML) に定義された決定論的ファクト契約を検証する。"""
    errors: List[str] = []
    fact_rules = kb.get("deterministic_fact_rules", [])
    req_assertions = kb.get("required_fact_assertions", [])

    file_map: Dict[str, str] = {}
    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        file_map[md_path.name] = content
        lines = content.splitlines()
        for rule in fact_rules:
            rule_id = rule["id"]
            pattern = rule["pattern"]
            msg = rule["message"]
            for line_no, line in enumerate(lines, start=1):
                if re.search(pattern, line):
                    errors.append(
                        f"[{rule_id}] {md_path.name}:{line_no}: {msg}\n"
                        f"    該当行: {line.strip()}"
                    )

    for req in req_assertions:
        req_id = req["id"]
        target_file = req["file"]
        must_contain = req.get("must_contain", [])
        msg = req["message"]
        if target_file not in file_map:
            errors.append(f"[{req_id}] 対象ファイル {target_file} が存在しません。")
            continue
        content = file_map[target_file]
        for keyword in must_contain:
            if keyword not in content:
                errors.append(
                    f"[{req_id}] {target_file}: 必須一次情報キーワード '{keyword}' が欠落しています。({msg})"
                )

    return errors


def verify_embedded_python_with_ruff(md_files: List[Path]) -> Tuple[int, List[str]]:
    """Layer 2: 埋め込み Python スニペットを抽出し、実ツール Ruff で静的解析を実行する。"""
    errors: List[str] = []
    snippet_count = 0

    with tempfile.TemporaryDirectory(prefix="book_ruff_audit_") as tmpdir:
        tmp_root = Path(tmpdir)
        snippet_meta: Dict[str, Tuple[str, int]] = {}

        for md_path in md_files:
            text = md_path.read_text(encoding="utf-8")
            blocks = extract_python_blocks(text)
            for b_idx, (start_line, code) in enumerate(blocks, start=1):
                snippet_count += 1
                fname = f"{md_path.stem}__block{b_idx}_L{start_line}.py"
                fpath = tmp_root / fname
                fpath.write_text(code, encoding="utf-8")
                snippet_meta[fname] = (md_path.name, start_line)

        if snippet_count == 0:
            return 0, []

        cmd = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "E,F,B,PLE",
            "--ignore",
            "E501",
            "--output-format",
            "json",
            str(tmp_root),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0 and proc.stdout.strip():
            try:
                findings = json.loads(proc.stdout)
                for item in findings:
                    filename = Path(item["filename"]).name
                    md_name, block_start = snippet_meta.get(filename, (filename, 1))
                    rel_row = item.get("location", {}).get("row", 1)
                    abs_line = block_start + rel_row
                    code_id = item.get("code", "RUFF")
                    message = item.get("message", "")
                    errors.append(
                        f"[Ruff:{code_id}] {md_name}:{abs_line} (block@{block_start}): {message}"
                    )
            except json.JSONDecodeError:
                errors.append(f"[Ruff-RawError] {proc.stdout}\n{proc.stderr}")

    return snippet_count, errors


def run_rag_grounded_llm_audit(kb_raw_yaml: str, md_files: List[Path]) -> List[str]:
    """Layer 3 (Optional): 一次情報 YAML を RAG 注入した Principal Engineer LLM レビュー。"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ℹ️ [Layer 3] GEMINI_API_KEY が未設定のため、LLM RAG監査はスキップします（決定論的RAG検査・Ruff検査は完了）。")
        return []

    warnings_or_errors: List[str] = []
    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        prompt = (
            "あなたはソフトウェア品質工学・国際規格・セキュリティのPrincipal Engineer監査官です。\n"
            "自身の曖昧な記憶（パラメトリック記憶）に頼らず、必ず以下の【一次情報・正解知識ベース (YAML)】を絶対的な根拠（Ground Truth）として、\n"
            "対象原稿に規格の誤記・用語の取り違え・技術的矛盾がないかを厳密に監査してください。\n\n"
            f"【一次情報・正解知識ベース (YAML)】\n```yaml\n{kb_raw_yaml}\n```\n\n"
            f"【監査対象原稿: {md_path.name}】\n```markdown\n{text[:15000]}\n```\n\n"
            '出力形式（JSONのみ）: {"has_factual_error": true/false, "issues": ["具体的な誤りと修正案"]}'
        )
        req_body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.0},
        }
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                parsed = json.loads(res["candidates"][0]["content"]["parts"][0]["text"])
                if parsed.get("has_factual_error"):
                    for issue in parsed.get("issues", []):
                        warnings_or_errors.append(f"[LLM-RAG-Audit] {md_path.name}: {issue}")
        except Exception as exc:
            print(f"⚠️ [Layer 3] {md_path.name} のLLM監査呼び出し中に例外が発生しました: {exc}")

    return warnings_or_errors


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="RAG知識ベースに基づく技術ファクト検証とRuff静的解析ゲート")
    parser.add_argument("--llm", action="store_true", help="GEMINI_API_KEY を用いた RAG グラウンディング LLM 監査も併せて実行する")
    args = parser.parse_args()

    if not KNOWLEDGE_BASE_PATH.exists():
        print(f"❌ 知識ベースファイルが見つかりません: {KNOWLEDGE_BASE_PATH}")
        return 1

    kb_raw = KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8")
    kb = yaml.safe_load(kb_raw)
    md_files = sorted(MANUSCRIPT_DIR.glob("*.md"))

    print("================================================================================")
    print("🔬 Technical Fact Knowledge Base (RAG) & Ruff Embedded Code Audit")
    print("================================================================================")

    # Layer 1: Deterministic RAG Ground-Truth Check
    rag_errors = verify_rag_ground_truth(kb, md_files)
    print(
        f"📚 [Layer 1: RAG Ground-Truth Check] Standards={len(kb.get('standards', {}))}, "
        f"Rules={len(kb.get('deterministic_fact_rules', []))}, "
        f"RequiredAssertions={len(kb.get('required_fact_assertions', []))} -> Violations={len(rag_errors)}"
    )

    # Layer 2: Ruff Static Analysis on Embedded Python Blocks
    snippet_count, ruff_errors = verify_embedded_python_with_ruff(md_files)
    print(
        f"🐍 [Layer 2: Ruff Embedded Python Static Analysis] Snippets={snippet_count} -> Violations={len(ruff_errors)}"
    )

    # Layer 3: Optional RAG-Grounded LLM Audit
    llm_errors: List[str] = []
    if args.llm:
        llm_errors = run_rag_grounded_llm_audit(kb_raw, md_files)
        print(f"🤖 [Layer 3: RAG-Grounded Principal Engineer AI Audit] Findings={len(llm_errors)}")

    all_errors = rag_errors + ruff_errors + llm_errors
    if all_errors:
        print("\n❌ 技術ファクト検証または埋め込みコード静的解析でエラーが検出されました:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\n✅ PASSED: 一次情報知識ベース（RAG）整合性および全埋め込みPythonコードのRuff静的解析に完全合格しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
