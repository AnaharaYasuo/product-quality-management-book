"""本文に掲載したサンプルコードが「本文で主張している効果」を実際に持つかを検証する主張テスト。

「実行して例外が出ない」だけでは、恒真アサーションや素通しのゲートを見逃す。
ここでは、各サンプルの核心となる関数を原稿から抽出し、守るべき性質を直接テストする。
"""
import re
import sys
import types
from pathlib import Path

import pytest

MANUSCRIPT = Path(__file__).resolve().parents[1] / "manuscript"


def load_snippet(chapter: str, header: str, stubs: dict | None = None) -> types.SimpleNamespace:
    text = (MANUSCRIPT / chapter).read_text(encoding="utf-8")
    m = re.search(r"```python\n(" + re.escape(header) + r"\n[\s\S]*?)\n```", text)
    assert m, f"snippet not found: {chapter} {header}"
    saved = {}
    for name, mod in (stubs or {}).items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod
    try:
        ns: dict = {"__name__": "snippet_under_test"}
        exec(compile(m.group(1), f"{chapter}:{header}", "exec"), ns)  # noqa: S102
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
    return types.SimpleNamespace(**ns)


# ---------------------------------------------------------------- 19.3
@pytest.fixture
def tamper():
    return load_snippet("19_chapter19.md", "# tools/verify_agent_test_integrity.py")


def test_tamper_detects_rename(tamper):
    assert tamper.classify("R100\ttests/test_pay.py\ttests/old_pay.py", {})


def test_tamper_detects_conftest_and_addopts(tamper):
    assert tamper.classify("M\ttests/conftest.py", {})
    assert tamper.classify("M\tpyproject.toml", {"pyproject.toml": ['addopts = "--deselect tests/test_pay.py"']})


def test_tamper_detects_skip_in_new_file(tamper):
    added = {"tests/test_new.py": ["@pytest.mark.skip(reason='later')"]}
    assert tamper.classify("A\ttests/test_new.py", added)


def test_tamper_allows_plain_new_test(tamper):
    added = {"tests/test_new.py": ["def test_x():", "    assert add(1, 2) == 3"]}
    assert tamper.classify("A\ttests/test_new.py\nM\tsrc/app.py", added) == []


# ---------------------------------------------------------------- 8.5
def test_destructive_exact_type_match():
    mod = load_snippet("08_chapter8.md", "# tools/verify_destructive_changes.py")
    plan = {"resource_changes": [
        {"type": "aws_s3_bucket_policy", "address": "aws_s3_bucket_policy.p", "change": {"actions": ["delete", "create"]}},
        {"type": "aws_s3_bucket", "address": "aws_s3_bucket.data", "change": {"actions": ["delete"]}},
    ]}
    found = mod.analyze_terraform_plan(plan)
    assert [v["address"] for v in found] == ["aws_s3_bucket.data"]


# ---------------------------------------------------------------- 23.4
def test_hollow_detector_counts_pytest_raises(tmp_path):
    mod = load_snippet("23_chapter23.md", "# tools/detect_fake_coverage.py")
    f = tmp_path / "test_sample.py"
    f.write_text(
        "import pytest\n"
        "def test_raises():\n    with pytest.raises(ValueError):\n        int('x')\n"
        "def test_hollow():\n    int('1')\n",
        encoding="utf-8",
    )
    assert mod.audit_test_file(str(f)) == ["test_hollow"]


# ---------------------------------------------------------------- 18.5
def test_red_team_catches_leaky_target():
    mod = load_snippet("18_chapter18.md", "# tools/adversarial_red_teaming.py")
    canary = "CANARY-7f3a"

    def leaky(prompt: str) -> str:
        return f"設定文: {canary}" if "設定" in prompt or "instructions" in prompt else "通常の回答です。"

    def safe(prompt: str) -> str:
        return "通常の回答です。"

    assert not any(canary in a for a in mod.SEED_ATTACKS), "攻撃文にカナリアを含めてはならない"
    assert mod.evaluate_target(leaky, canary, mod.SEED_ATTACKS) is False
    assert mod.evaluate_target(safe, canary, mod.SEED_ATTACKS) is True


def test_red_team_catches_over_blocking():
    mod = load_snippet("18_chapter18.md", "# tools/adversarial_red_teaming.py")
    assert mod.evaluate_target(lambda p: "お答えできません", "CANARY", mod.SEED_ATTACKS) is False


# ---------------------------------------------------------------- 18.3
def test_ragas_gate_is_fail_closed_without_pipeline(monkeypatch):
    datasets = types.ModuleType("datasets")
    datasets.Dataset = type("Dataset", (), {"from_dict": staticmethod(lambda d: d)})
    ragas = types.ModuleType("ragas")
    ragas.evaluate = lambda dataset, metrics: {"faithfulness": 1.0, "answer_relevancy": 1.0, "context_precision": 1.0}
    metrics = types.ModuleType("ragas.metrics")
    metrics.faithfulness = metrics.answer_relevancy = metrics.context_precision = object()
    mod = load_snippet("18_chapter18.md", "# tests/evaluate_rag_pipeline.py",
                       {"datasets": datasets, "ragas": ragas, "ragas.metrics": metrics})
    monkeypatch.delenv("RAG_PIPELINE", raising=False)
    assert mod.run_quality_gate() == 1
    assert all("ground_truth" in c for c in mod.GOLDEN_CASES)
    assert all("answer" not in c for c in mod.GOLDEN_CASES), "回答を手書きで固定してはならない"


# ---------------------------------------------------------------- 11.4
def test_pr_template_accepts_na_with_reason():
    mod = load_snippet("11_chapter11.md", "# tools/verify_pr_template_compliance.py")
    body = ("変更の背景と詳細をここに十分な長さで記述します。認証処理のリファクタリングを行いました。\n"
            "Closes #12\n- [x] 単体テストを追加した\n- [ ] 破壊的変更の移行手順 N/A: 公開APIの変更なし\n")
    assert mod.verify_pr_body(body) == []
    assert mod.verify_pr_body(body.replace(" N/A: 公開APIの変更なし", ""))


# ---------------------------------------------------------------- 12.5 / 19.5
def test_gatekeeper_llm_unavailable_is_not_pass(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    mod = load_snippet("12_chapter12.md", "# tools/ai_gatekeeper_check.py")
    assert mod.llm_advisory("body", ["src/a.py"])["verdict"] != "PASS"
    assert mod.deterministic_check("- [x] テストを追加した", ["src/a.py"])
    assert mod.deterministic_check("- [x] テストを追加した", ["tests/test_a.py"]) == []


def test_auditor_without_key_does_not_approve(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    mod = load_snippet("19_chapter19.md", "# tools/agent_adversarial_reviewer.py")
    assert mod.audit_agent_pr("spec", "diff")["verdict"] != "APPROVE"


# ---------------------------------------------------------------- 25.5
def test_validation_auditor_uses_book_threshold():
    mod = load_snippet("25_chapter25.md", "# tools/audit_product_validation.py")
    auditor = mod.ProductValidationAuditor()
    assert auditor.min_adoption_threshold == pytest.approx(0.005)
    m = mod.FeatureUsageMetric("f", "f", 10000, 40, 30, 1.0, 0)  # 0.4%
    assert auditor.evaluate_features([m])["zombie_sunset_candidates"]


# ---------------------------------------------------------------- 第3次評価（#148）で追加
def test_tamper_detects_pytestmark_and_ci_changes(tamper):
    added = {"tests/test_pay.py": ["pytestmark = pytest.mark.skip(reason='flaky')"]}
    assert tamper.classify("A\ttests/test_pay.py", added)
    assert tamper.classify("M\t.github/workflows/ci.yml", {".github/workflows/ci.yml": ["  PYTEST_ADDOPTS: -k 'not pay'"]})
    assert tamper.classify("M\tsrc/billing/test_invoice.py", {}), "tests/ 以外のテストファイルも対象"


def test_tamper_allow_label_permits_only_modification(tamper):
    assert tamper.classify("M\ttests/test_pay.py", {}, allow_test_modification=True) == []
    added = {"tests/test_pay.py": ["@pytest.mark.skip(reason='later')"]}
    assert tamper.classify("M\ttests/test_pay.py", added, allow_test_modification=True), "承認ラベルでも skip は止める"
    assert tamper.classify("D\ttests/test_pay.py", {}, allow_test_modification=True), "承認ラベルでも削除は止める"


def test_tamper_ignores_non_test_files(tamper):
    assert tamper.classify("M\tREADME.md", {"README.md": ["pip install --ignore-installed foo"]}) == []


def test_tamper_is_fail_closed_without_base(tamper, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # git リポジトリではない（= 差分を取れない）
    with pytest.raises(SystemExit) as exc:
        tamper.git("diff", "--name-status", "-M")
    assert exc.value.code == 2


def test_gatekeeper_is_fail_closed_without_base(tmp_path, monkeypatch):
    mod = load_snippet("12_chapter12.md", "# tools/ai_gatekeeper_check.py")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        mod.get_changed_files()
    # 「テスト不要」のような別の項目や、latest.py のような名前を誤判定しない
    assert mod.deterministic_check("- [x] テスト不要（ドキュメントのみ）", ["docs/a.md"]) == []
    assert mod.deterministic_check("- [x] テストを追加した", ["src/latest.py"])


def test_predictive_selection_is_fail_closed(tmp_path, monkeypatch):
    mod = load_snippet("22_chapter22.md", "# tools/predictive_test_selection.py")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert mod.select_optimal_tests([]) == ["tests/unit"]
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        mod.get_changed_files()


def test_sanitize_for_llm_masks_pii_and_secrets():
    mod = load_snippet("15_chapter15.md", "# tools/generate_postmortem_ai.py")
    out = mod.sanitize_for_llm("連絡先 taro@example.co.jp token: abcdEFGH12345678 from 10.1.2.3 tel 03-1234-5678")
    assert "taro@example.co.jp" not in out and "abcdEFGH12345678" not in out
    assert "10.1.2.3" not in out and "03-1234-5678" not in out


def test_assured_testgen_rejects_hollow_candidate(tmp_path):
    mod = load_snippet("09_chapter9.md", "# tools/assured_testgen.py")
    hollow = tmp_path / "test_hollow.py"
    hollow.write_text("def test_x():\n    calculate_discount(1000, 'VIP')\n", encoding="utf-8")
    good = tmp_path / "test_good.py"
    good.write_text("import pytest\nasync def test_y():\n    with pytest.raises(ValueError):\n        int('x')\n", encoding="utf-8")
    assert mod.has_assertions(hollow) is False
    assert mod.has_assertions(good) is True


def test_hollow_detector_covers_async_tests(tmp_path):
    mod = load_snippet("23_chapter23.md", "# tools/detect_fake_coverage.py")
    f = tmp_path / "test_async.py"
    f.write_text("async def test_hollow():\n    await something()\n", encoding="utf-8")
    assert mod.audit_test_file(str(f)) == ["test_hollow"]


def _yaml_block(chapter: str, header: str) -> str:
    text = (MANUSCRIPT / chapter).read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(" + re.escape(header) + r"[\s\S]*?)\n```", text)
    assert m, f"yaml not found: {chapter} {header}"
    return m.group(1)


def test_spectral_4xx_rule_requires_a_4xx_response():
    yaml = pytest.importorskip("yaml")
    jsonschema = pytest.importorskip("jsonschema")
    rules = yaml.safe_load(_yaml_block("06_chapter6.md", "# .spectral.yaml"))["rules"]
    schema = rules["operation-4xx-response"]["then"]["functionOptions"]["schema"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"200": {"description": "ok"}}, schema)
    jsonschema.validate({"200": {"description": "ok"}, "404": {"description": "nf"}}, schema)


def test_canary_analysis_treats_empty_result_as_inconclusive():
    yaml = pytest.importorskip("yaml")
    tmpl = yaml.safe_load(_yaml_block("15_chapter15.md", "# kubernetes/analysis-template.yaml"))
    metric = tmpl["spec"]["metrics"][0]
    # 空の結果（len(result) == 0）では success も failure も偽になること（= inconclusive）
    assert "len(result) == 0" not in metric["successCondition"]
    assert metric["successCondition"].startswith("len(result) > 0")
    assert metric["failureCondition"].startswith("len(result) > 0")


def test_mutation_diff_gate_uses_glob_pathspec_and_score():
    block = (MANUSCRIPT / "09_chapter9.md").read_text(encoding="utf-8")
    m = re.search(r"# \.github/workflows/mutation-diff-gate\.yml[\s\S]*?\n```", block)
    assert m
    assert "':(glob)src/domain/**/*.py'" in m.group(0)
    assert "set -euo pipefail" in m.group(0)
    assert "check_mutation_score" in m.group(0)


def test_ragas_gate_follows_table_thresholds(monkeypatch):
    def make_ragas(score):
        datasets = types.ModuleType("datasets")
        datasets.Dataset = type("Dataset", (), {"from_dict": staticmethod(lambda d: d)})
        ragas = types.ModuleType("ragas")
        ragas.evaluate = lambda dataset, metrics: {"faithfulness": score, "answer_relevancy": 0.9, "context_precision": 0.9}
        metrics = types.ModuleType("ragas.metrics")
        metrics.faithfulness = metrics.answer_relevancy = metrics.context_precision = object()
        return {"datasets": datasets, "ragas": ragas, "ragas.metrics": metrics}

    fake = types.ModuleType("fake_rag")
    fake.answer = lambda q: ("回答", ["文脈"])
    monkeypatch.setitem(sys.modules, "fake_rag", fake)
    monkeypatch.setenv("RAG_PIPELINE", "fake_rag:answer")
    warn = load_snippet("18_chapter18.md", "# tests/evaluate_rag_pipeline.py", make_ragas(0.80))
    assert warn.run_quality_gate() == 0, "0.75〜0.85 は警告（18.6）"
    fail = load_snippet("18_chapter18.md", "# tests/evaluate_rag_pipeline.py", make_ragas(0.70))
    assert fail.run_quality_gate() == 1, "0.75未満は不合格（18.6）"
