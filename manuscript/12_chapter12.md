# 第12章：プロセスの「静的検証（Lint & ガードレール）」

ソフトウェア工学において「シフトレフト」という標語が叫ばれて久しい。コードを書いた後の結合テストや受入れテストではなく、単体テストやコミット前の静的コード解析によって欠陥を早期検出する思想である。しかし、なぜ私たちはこの優れた原則を「開発プロセスそのもの」に等しく適用してこなかったのだろうか。

どれほど綿密に定義された開発標準やPR（プルリクエスト）ガイドラインが存在しても、それが「開発者の善意」や「個人のチェックリスト目視」に依存している限り、過密スケジュールやヒューマンエラーによって確実に形骸化する。「うっかり忘れた」「急いでいたので後で修正するつもりだった」という言葉とともに、未検証コードのマージ、壊れたテスト、空欄だらけのPR説明文、トレーサビリティの欠落したコミットが本流ブランチへと雪崩れ込む。

本章では、開発プロセスそのものに静的検査（Lint）と自動防護壁（Guardrails）を張り巡らせ、「間違った状態ではコミットもプッシュもマージも物理的にできない世界」を機械的かつ決定論的に構築する技術体系を詳解する。

---

## 12.1 プロセスガードレールの思想：「人間を信じるのではなく、間違えようがない仕組みを信じる」

従来のプロセス品質管理における最大の誤謬は、「教育・指導によって人間の注意力や遵守意識を高めようとすること」である。認知心理学やシステム安全工学が証明している通り、疲労・時間的圧力・注意散漫に晒された人間がヒューマンエラーを完全に排除することは原理的に不可能である。

品質保証（QA）エンジニアやテクニカルリードが目指すべきは、「人間を疑うこと」でも「人間の善意に甘えること」でもなく、「エラーを犯すことが不可能な環境（ポカヨケ / Poka-yoke）」を開発インフラとして配備することである。

```mermaid
flowchart TD
    subgraph BadPattern["従来の人間依存型プロセス（破綻の構図）"]
        A1["開発者（高負荷・疲労）"] --> B1["規約ドキュメント（形骸化）"]
        B1 --> C1["PR作成・セルフチェック"]
        C1 --> D1["見落としによる本流への欠陥混入"]
    end

    subgraph GoodPattern["ガードレール主導型プロセス（決定論的保証）"]
        A2["開発者"] --> B2{"コミットLint（ローカル阻止）"}
        B2 -->|"違反時：即時遮断"| A2
        B2 -->|"合格"| C2{"RulesetとCI（自動検査）"}
        C2 -->|"DoD違反：マージ不可"| D2["DangerとAI Gatekeeper"]
        D2 -->|"完全合格のみ許可"| E2["本流ブランチ保護マージ"]
    end
```

プロセスガードレールには、以下の4つの本質的原則が存在する：

1. **決定論的フィードバック（Deterministic Feedback）**: ルール違反は主観的な感情論ではなく、明確な終了コード（Exit Code 1）と修正ガイダンスによって即座に機械から突き返されなければならない。
2. **最短のフィードバックループ（Shift-Left to the Millisecond）**: 違反の検知は「レビュー時」ではなく「コミット時（ローカル）」、「マージ後」ではなく「PRオープン時（リモート）」に極限まで前倒しされる。
3. **心理的安全性の担保（Psychological Safety through Invariance）**: ガードレールが機能している現場では、形式的な指摘をする必要が消滅する。レビュー担当者は設計やロジックの本質的議論に集中できる。
4. **バイパスの透明化と監査証跡（Transparent Bypassing and Auditability）**: 緊急障害対応（Hotfix）等で例外的にガードレールを迂回する場合は、事後監査が可能なログと承認フローが不可分に結合されていなければならない。

---

## 12.2 GitHub Branch Protection & Rulesetの実践

GitHubにおけるブランチ保護は、かつての単純な「Branch Protection Rules」から、より粒度が細かく柔軟なポリシー統制が可能な「GitHub Rulesets」へと進化を遂げた。組織的な品質保証を実現するためには、リポジトリ層および組織（Organization）層で堅牢なRulesetをコード化（Configuration as Code）する必要がある。

### 必須とすべきガードレール要件

1. **直接プッシュの完全禁止（Restrict Creations and Updates）**: `main`, `production` ブランチに対する直接コミットおよびForce Push（`git push -f`）を全ユーザー（管理者を含む）に対して恒久的に遮断する。
2. **線形コミット履歴の強制（Require Linear History）**: 不必要なマージコミットの乱立を防ぎ、`git bisect` による障害原因の特定を容易にするため、Squash MergeまたはRebase Mergeを強制する。
3. **必須ステータスチェック（Required Status Checks）**: CIパイプライン（ビルド、単体テスト、静的解析、セキュリティスキャン、ドキュメントDoD検査）の成功（Success）をマージの絶対前提条件とする。
4. **最新ブランチの要求（Require Branches to be Up to Date Before Merging）**: 他のPRがマージされて本流が進んだ場合、リベースまたは最新の取り込みを行わない限りマージボタンを活性化させない。これにより、マージ時のセマンティックな衝突や競合欠陥を防ぐ。
5. **署名付きコミットの要求（Require Signed Commits）**: GPGまたはSSHキーによるコミット署名を必須化し、コミット作成者のなりすましを排除する。

```mermaid
sequenceDiagram
    autonumber
    actor Dev as 開発者
    participant Git as Local Git
    participant GH as GitHub Ruleset
    participant CI as GitHub Actions CI
    participant Main as 本流ブランチ (main)

    Dev->>Git: git push -f origin main
    Git->>GH: Force Push要求
    GH-->>Dev: 拒絶: Force push is prohibited by Ruleset

    Dev->>Git: git checkout -b feat/... && git push
    Git->>GH: フィーチャーブランチ作成（許可）
    Dev->>GH: PR作成
    GH->>CI: Required Status Checks トリガー
    CI-->>GH: CI実行中 (Pending: Merge Blocked)
    CI-->>GH: 全チェックPass (Success)
    GH-->>Dev: Merge可能化 (Linear Squash Mergeのみ)
    Dev->>GH: マージ実行
    GH->>Main: 反映完了
```

---

## 12.3 コミットメッセージLintとPRテンプレートの自動検証

プロセスの静的検証における第一の防壁は、コミットメッセージとPRの記述そのものに対する検査である。

### 12.3.1 commitlintによるトレーサビリティの強制

コミットメッセージは、変更の文脈（なぜ、何を変更したのか、どのIssueに対応しているのか）を後世に伝える恒久的な設計ドキュメントである。`Conventional Commits` 規約を採用し、`husky` や `pre-commit` と連携した `commitlint` によって、不正なメッセージをコミットの瞬間にローカルで遮断する。

```javascript
// commitlint.config.js
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // 新機能・原稿執筆
        'fix',      // バグ修正・誤字脱字修正
        'docs',     // ドキュメント整備
        'style',    // コードスタイル・フォーマット（動作に影響なし）
        'refactor', // リファクタリング
        'perf',     // パフォーマンス改善
        'test',     // テスト追加・修正
        'build',    // ビルドシステム・外部依存変更
        'ci',       // CI/CD設定変更
        'chore',    // その他雑務
        'revert'    // 変更の取り消し
      ]
    ],
    'subject-case': [2, 'never', ['upper-case']],
    'subject-full-stop': [2, 'never', '.'],
    'subject-empty': [2, 'never'],
    'type-empty': [2, 'never']
  }
};
```

### 12.3.2 PRテンプレートの必須フィールド静的検証

GitHubのデフォルト機能では、PRテンプレートに記述された項目が空欄のまま送信されてもシステムは警告を発しない。これを放置すると、Issue番号の未記載、影響範囲の未入力、チェックボックスの無視が常態化する。

これを防ぐため、GitHub Actions上でPR本文のMarkdown構文木を解析し、必須セクションの記入漏れを検出するCIワークフローを配備する。

```yaml
# .github/workflows/lint-pr-description.yml
name: Lint Pull Request Description

on:
  pull_request:
    types: [opened, edited, synchronize]

jobs:
  validate-pr:
    runs-on: ubuntu-latest
    steps:
      - name: Validate PR Body Structure
        uses: actions/github-script@60a0d83039c74a4aee543508d2ffcb1c3799cdea # v7.0.1
        with:
          script: |
            const body = context.payload.pull_request.body;
            if (!body) {
              core.setFailed('PR本文が空です。PRテンプレートの全項目を記入してください。');
              return;
            }

            const requiredSections = [
              '## 概要',
              '## 変更理由',
              '## テスト・検証内容'
            ];

            const missingSections = [];
            for (const section of requiredSections) {
              if (!body.includes(section)) {
                missingSections.push(section);
              }
            }

            if (missingSections.length > 0) {
              core.setFailed(`必須セクションが不足しています: ${missingSections.join(', ')}`);
            }

            // Issue紐付けチェック（Closes #xx または Fixes #xx）
            const issueLinkRegex = /(close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#[0-9]+/i;
            if (!issueLinkRegex.test(body)) {
              core.setFailed('Issueへのリンク（例: Closes #123）が含まれていません。トレーサビリティを確保してください。');
            }
```

---

## 12.4 PRサイズ・鮮度のガードレール：Dangerによる巨大PRと負債の防止

PRのサイズ（変更行数・ファイル数）と、コードレビューの品質および欠陥見落とし率には極めて強い正の相関がある。変更行数が400行を超えたPRのレビューは、実質的に「斜め読み」となり、重大なロジック欠陥やセキュリティホールが看過される原因となる。

オープンソースの自動レビューツール `Danger`（JavaScript / Ruby）を活用することで、PRのメタ情報、差分量、付随成果物の過不足を動的に監視し、基準を超過した変更に対して即座に警告（Warn）またはマージ阻止（Fail）を発動できる。

```javascript
// dangerfile.js
import { danger, warn, fail, message } from 'danger';

const pr = danger.github.pr;
const modifiedFiles = danger.git.modified_files;
const createdFiles = danger.git.created_files;
const allChangedFiles = [...modifiedFiles, ...createdFiles];

// 1. 巨大PRの検出（本書共通閾値：400行超で警告、800行超でブロック）
const WARN_CHANGED_LINES = 400;
const FAIL_CHANGED_LINES = 800;
const totalLinesChanged = danger.github.pr.additions + danger.github.pr.deletions;
if (totalLinesChanged > FAIL_CHANGED_LINES) {
  fail(`🛑 このPRの変更行数は ${totalLinesChanged} 行です。800行を超えるPRは分割してください。`);
} else if (totalLinesChanged > WARN_CHANGED_LINES) {
  warn(`⚠️ このPRの変更行数は ${totalLinesChanged} 行です。400行を超えるとレビュー品質が低下しやすいため、分割を検討してください。`);
}

// 2. 実装コード変更時のテストコード同根チェック
const hasAppChanges = allChangedFiles.some(file => file.startsWith('src/') || file.startsWith('lib/'));
const hasTestChanges = allChangedFiles.some(file => file.includes('test') || file.includes('spec'));

if (hasAppChanges && !hasTestChanges) {
  warn('⚠️ プロダクションコードが変更されていますが、テストコード（tests/ または spec/）の変更が含まれていません。テストの追加または更新が必要です。');
}

// 3. ドキュメントおよびCHANGELOGの更新チェック
const hasChangelog = allChangedFiles.includes('CHANGELOG.md');
if (hasAppChanges && !hasChangelog) {
  message('📝 ユーザーに影響する変更がある場合は、`CHANGELOG.md` への追記を忘れないでください。');
}

// 4. 原稿・マークダウンファイルのDoD静的検査
const manuscriptFiles = allChangedFiles.filter(file => file.startsWith('manuscript/') && file.endsWith('.md'));
for (const file of manuscriptFiles) {
  message(`📖 原稿ファイル \`${file}\` が更新されました。Commercial DoD基準がCIで検証されます。`);
}
```

上記の `dangerfile.js` をGitHub Actions上で自動実行し、PRへ検証結果コメントを投稿するためのセットアップ手順は以下の通りである。

```yaml
# .github/workflows/danger-pr-guard.yml
name: Danger PR Guardrail
on: [pull_request]

# 初回導入時のハマり防止：PRへのコメント投稿とステータス更新のため以下の権限スコープ明示が必須
permissions:
  contents: read
  pull-requests: write

jobs:
  danger:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
      - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af # v4.1.0
        with:
          node-version: '20'
      - run: npm install --no-save danger
      - name: Run Danger JS
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: npx danger ci --failOnErrors=true
```

※初回実行時のトラブルシューティング：近年のGitHub Actionsでは、リポジトリのデフォルト `GITHUB_TOKEN` 権限が読み取り専用（Read-only）に制限されているケースが多く見られる。そのまま `npx danger ci` を実行すると、`403 Resource not accessible by integration` エラーでコメント投稿に失敗するため注意されたい。上記のようにワークフロー内に `permissions: pull-requests: write` を明示することで、初回から確実に動作させることができる。また、PR変更行数の上限閾値（`MAX_CHANGED_LINES = 500`）は現場に応じた調整が有効である。初期構築期や自動生成コードが多い現場ではまず `800〜1,000行（Warnのみ）` から緩やかに始め、逆に決済コア等の高信頼性領域では `300行（超過時はFail）` に引き締めるなど、成熟度に応じたトレードオフ調整を行うこと。

---

## 12.5 AI確証工程：PR変更内容とDoDチェックボックスの乖離検知

プロセスの静的検証における最大の盲点の一つが、「PR作成者がチェックボックス（`[x]`）にチェックを入れているが、実際にはその作業を一切やっていない」という虚偽申告問題である。

例えば、PRテンプレートに `[x] 単体テストを実行し全件パスを確認した`、`[x] ドキュメントを最新化した` と記載されていながら、Gitの変更差分にはテストコードの修正もドキュメントファイルの更新も存在しないというケースは日常的に発生する。人間レビュアーはこれを突き合わせる作業に多大な認知リソースを浪費するか、あるいは「チェックがついているから大丈夫だろう」と盲目的に信じてスルーしてしまう。

この課題を解決するため、Git差分とPR本文のDoDチェックボックスを突合する「AI Process Gatekeeper」をCIパイプラインに組み込む。

設計の原則は、**マージを止めるのは決定論的に判定できる乖離だけ**にすることである。LLMによる意味的な照合は見落としを拾うのに役立つが、誤判定もある。そこでLLMの結果は助言として扱い、指摘があったときやAPI障害で監査できなかったときは、人のレビューへエスカレーションする（第8章・第24章と同じ方針）。

```mermaid
flowchart TD
    A["PR作成または差分更新"] --> B["AI Process Gatekeeper (CI)"]
    B --> C{"決定論的チェック
(チェック項目と変更ファイルの機械照合)"}
    C -->|"違反あり"| G["CI Failure（ハードブロック）"]
    C -->|"違反なし"| E{"LLMによる意味的照合（助言）"}
    E -->|"食い違いなし"| F["CI Pass"]
    E -->|"指摘あり / API障害"| H["needs-human-review ラベル付与
人のレビューで判断"]
    G --> R["開発者が修正して再プッシュ"]
    R --> B
```

### AI Gatekeeperの実装スクリプト

```python
# tools/ai_gatekeeper_check.py
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

NEEDS_HUMAN = "NEEDS_HUMAN_REVIEW"


def get_changed_files() -> list[str]:
    for base in ("origin/main...HEAD", "HEAD~1...HEAD"):  # 浅いクローン時は HEAD~1 にフォールバック
        res = subprocess.run(
            ["git", "diff", "--name-only", base], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        if res.returncode == 0:
            return [f for f in res.stdout.splitlines() if f.strip()]
    return []


def deterministic_check(pr_body: str, files: list[str]) -> list[str]:
    """機械的に判定できる乖離だけを、ハードブロックの対象にする。"""
    errors = []
    checked = lambda label: re.search(rf"- \[[xX]\] .*{label}", pr_body) is not None  # noqa: E731
    if checked("テスト") and not any("test" in f.lower() or "spec" in f.lower() for f in files):
        errors.append("「テスト追加済み」にチェックがありますが、テストファイルの変更がありません。")
    if checked("ドキュメント") and not any(f.endswith(".md") or f.startswith("docs/") for f in files):
        errors.append("「ドキュメント更新済み」にチェックがありますが、ドキュメントの変更がありません。")
    return errors


def llm_advisory(pr_body: str, files: list[str]) -> dict:
    """意味的な乖離をLLMに指摘させる。結果は助言として扱い、マージ可否は決めない。"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"verdict": NEEDS_HUMAN, "reasons": ["APIキー未設定のためAI監査は未実施"]}
    prompt = (
        "PR本文の申告内容と変更ファイル一覧を照合し、申告と実態の食い違いを列挙してください。\n"
        "食い違いが無ければ verdict を PASS、あれば FAIL としてください。\n\n"
        f"【PR本文】:\n{pr_body[:5000]}\n\n【変更ファイル一覧】:\n" + "\n".join(files[:300])
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "OBJECT",
                "properties": {
                    "verdict": {"type": "STRING", "enum": ["PASS", "FAIL"]},
                    "reasons": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["verdict", "reasons"],
            },
        },
    }
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return json.loads(res["candidates"][0]["content"]["parts"][0]["text"])
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as exc:
        # 障害時は「合格」ではなく「未実施」として人に判断を戻す（fail-closed）
        return {"verdict": NEEDS_HUMAN, "reasons": [f"AI監査API障害のため未実施: {exc}"]}


if __name__ == "__main__":
    body = os.environ.get("PR_BODY", "")
    changed = get_changed_files()

    hard_errors = deterministic_check(body, changed)
    advisory = llm_advisory(body, changed)
    print(f"[AI助言] {advisory}")
    if advisory.get("verdict") != "PASS":
        # ワークフロー側でこの出力を読み、needs-human-review ラベルを付ける
        print("::notice::AI監査で確認事項があります。needs-human-review ラベルを付与してください。")

    if hard_errors:
        for e in hard_errors:
            print(f"❌ {e}")
        sys.exit(1)
    print("✅ 決定論的チェックを通過しました（AI助言は人のレビューで確認してください）。")
```

※JSON Modeスキーマ検証とリトライ設計の補足：Gemini APIの `response_schema`（Structured Outputs）を指定することで、出力形式の揺れは大幅に抑えられる。ただし巨大なPR差分を送信した際には、出力の途中切れ（`finishReason: MAX_TOKENS`）による `json.JSONDecodeError` や一時的な通信瞬断が発生することがある。実運用では `git_diff` を先頭20,000文字にトランケートした上でタイムアウトを `15〜20秒` に設定する。さらにHTTP 429/503発生時には2秒・4秒の指数バックオフ（最大2回リトライ）を挟み、それでも失敗した場合は「AI監査未実施」として人のレビューに回す。障害時に合格へ倒してはならない。

---

## 12.6 緊急リリース（Hotfix）と例外バイパスの統制設計

ガードレールを導入する際、現場の開発者から必ず提起されるのが「深夜の重大本番障害時に、厳格なCIやガードレールが邪魔をして復旧が遅れたらどうするのか」という反論である。

この懸念に対して「例外のない完璧な厳格さ」を強要すると、開発者は裏道（個人の管理者権限を用いた強制的ルール解除など）を探し始め、結果としてプロセスそのものが形骸化する。優れたプロセスエンジニアリングとは、「例外運用（Hotfixバイパス）をあらかじめアーキテクチャとして設計し、その行使に対して極めて高い可視性と代償を課すこと」である。

### Hotfixバイパスの4段階統制

1. **専用ラベルまたはブランチ命名による一時的緩和**:
   - `hotfix/critical-*` ブランチまたは `hotfix-bypass` ラベルが付与されたPRに限り、時間のかかる一部のE2Eテストやドキュメント検証をスキップ可能とする。
2. **2名以上のエマージェンシー承認（Two-Person Rule）**:
   - 通常レビューは1名でよいが、例外バイパス時は「セキュリティリード」または「オンコール統括者」を含む2名以上の明示的承認を必須とする。
3. **インシデント起因Issueの強制紐付け**:
   - PagerDutyやOpsgenie、あるいは重大インシデント管理チケットのURLが指定されていない場合、例外パイプラインの実行を拒絶する。
4. **事後修復チケットの自動発行（Technical Debt Auto-Ticketing）**:
   - 例外バイパスによってマージが行われた瞬間に、GitHub Actionsが自動的に「【至急】Hotfixバイパスによる負債解消・テスト補完」というIssueを起票し、Slackの全社アラートチャンネルへ通知する。このチケットがクローズされるまで、次の通常リリースタグ作成をブロックする。

```mermaid
stateDiagram-v2
    [*] --> 通常フロー: 通常PR作成
    通常フロー --> 全ガードレール検査: フルCIとレビュー実行
    全ガードレール検査 --> 本流マージ: オールグリーン

    [*] --> 緊急インシデント: P0本番障害発生
    緊急インシデント --> Hotfixブランチ作成: hotfix/*
    Hotfixブランチ作成 --> エマージェンシー申請: P0チケットIDと理由明記
    エマージェンシー申請 --> 二重承認: オンコールリードとセキュリティ承認
    二重承認 --> 最小CI検証: 単体テストとビルドのみ実行
    最小CI検証 --> 例外マージ: 本流へ即時反映
    例外マージ --> 負債自動起票: GitHub Issue起票とSlack通知
    負債自動起票 --> 事後追跡: テスト補完と通常検証完了
    事後追跡 --> [*]: クローズ確認
```

### プロセスガードレールのQA合否判定基準（Pass/Fail Criteria）

本章で扱ったガードレールの合否判定基準を整理する。数値はいずれも第2章「本書の閾値の扱い」に従う出発点の目安である。

| 検査項目 | 合格（Pass） | 警告（Warn） | 不合格（Fail / ブロック） |
| :--- | :--- | :--- | :--- |
| コミットメッセージ | Conventional Commits準拠 | 該当なし | 規約違反（commitlint） |
| PRサイズ | 400行以内 | 400行超〜800行以内 | 800行超 |
| PR本文とDoDの整合 | 決定論的チェック違反0件 | AI助言で確認事項あり（人のレビューへ） | チェック済み項目と変更ファイルの機械的な食い違い |
| Issue紐付け | `Closes #N` 等の記載あり | 該当なし | 記載なし |

---

## 12.7 アンチパターン対比：形骸化するプロセス vs 機能するガードレール

プロセス品質管理の導入において、多くの組織が陥る失敗パターンと、その処方箋を対比表で整理する。

| 観点 | アンチパターン（形骸化するプロセス） | ベストプラクティス（機能するガードレール） |
| :--- | :--- | :--- |
| **ルールの伝達** | 膨大な社内Wikiに「開発規約」を記述し、新人に通読を義務付ける。 | Git Hooks（pre-commit）やRulesetで物理的にルール違反を遮断する。 |
| **レビューの役割** | レビュアーが「インデント」「コミットメッセージ」「PR記述」の指摘に忙殺される。 | 形式的ルールはすべてLintやCIが落とす。人間は設計・ビジネス価値のみを議論する。 |
| **PRの粒度** | 2週間分の作業が詰め込まれた3,000行のPRが提出され、誰も読まずにApproveする。 | DangerやBotが400行超のPRに警告を発し、800行超のPRはマージをブロックする。 |
| **DoDの遵守** | PRのチェックボックスが単なる「通過儀礼」となり、ノーチェックで送信される。 | AI GatekeeperがGit差分と照合し、虚偽や未達のチェックを自動検知してリジェクトする。 |
| **緊急対応** | 管理者がGitHubの設定画面で一時的にBranch Protectionを解除し、戻し忘れる。 | 監査ログ付きのHotfix自動ワークフローを設計し、事後チケットを自動生成して追跡する。 |

---

## 12.8 実践ワークショップ：リポジトリ健全性のセルフアセスメント

読者のチームやリポジトリにおいて、プロセスガードレールがどの程度機能しているかを客観的に評価するためのチェックシートである。

### プロセス健全性スコアカード（各項目 0〜2点）

1. **ブランチ保護**:
   - `main` や `production` ブランチへの直接プッシュおよびForce Pushが完全に禁止されているか？
2. **必須CIのブロック力**:
   - テストやリントが1件でも失敗している状態では、誰も物理的にマージできないよう設定されているか？
3. **コミットメッセージの標準化**:
   - commitlint等のツールが導入され、不正なコミットメッセージがローカルで遮断されているか？
4. **PRサイズの監視**:
   - 変更量が大きすぎるPRに対して、自動的に警告や分割を促す仕組みが存在するか？
5. **PRテンプレートの記述検証**:
   - 必須セクションの未記入やIssueリンク漏れを、CIやBotが自動検出してブロックしているか？
6. **DoDと実態の突き合わせ**:
   - 「テスト実施」「ドキュメント更新」などの宣言が、実際のコード差分と一致しているか検証されているか？
7. **例外運用の監査可能性**:
   - 緊急時のバイパス運用がシステム化され、事後修復タスクが自動起票される仕組みがあるか？

- **合算スコアの診断**:
  - **12〜14点【卓越】**: プロセスがコードとして統制されており、ヒューマンエラーによる品質低下が極小化されている。
  - **8〜11点【発展途上】**: 基本的な保護はあるが、依然として人間の注意力や善意への依存が残存している。
  - **0〜7点【危険】**: プロセスが形骸化しており、いつ重大インシデントや品質破綻が起きてもおかしくない状態である。即時のガードレール導入が推奨される。

---

## 12.9 本章のまとめと次章への接続

本章で論じたプロセスの静的検証（Lint & ガードレール）は、高品質なソフトウェアを高速にデリバリーするための「不可逆な安全網」である。

- **人間を信じるのではなく、仕組みを信じる**: ルール違反は精神論で指導するのではなく、システムによって物理的に阻止する。
- **多層防壁の構築**: ローカルの `commitlint` から、GitHub Ruleset、Danger、AI Gatekeeperに至る多段の検証パイプラインを敷く。
- **例外の制御**: 緊急リリース（Hotfix）を排除するのではなく、透明化された例外レーンと事後負債回収を設計する。

しかし、静的検証によって「ルールに沿ったPR」が揃ったとしても、開発フロー全体のどこで滞留（ボトルネック）や特定レビュアーへの負荷集中が起きているかまでは把握できない。そこで次章（第13章）では、DORA指標やフローメトリクス・ジニ係数を用いて開発現場の淀みを定量的に可視化・デバッグする「プロセスの動的検証」へと歩を進める。
