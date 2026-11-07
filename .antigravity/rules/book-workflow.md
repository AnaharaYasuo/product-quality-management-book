# プロダクト品質管理書籍プロジェクト 開発・執筆ルール

本リポジトリ（`product-quality-management-book`）はAmazon Kindle ダイレクト・パブリッシング（KDP）向け電子書籍の執筆プロジェクトです。
当プロジェクトにおいて、AIアシスタントおよび作業者は以下のルールを厳格に遵守すること。

---

## 1. ブランチ戦略とリリース規約

1. **`main` ブランチへの直接コミット・直接プッシュは絶対禁止**
   - 必ず作業ブランチ（`feat/*`, `fix/*`, `docs/*` 等）を作成して作業し、プルリクエスト（PR）経由でマージすること。
2. **`production` ブランチの役割**
   - **`production` ブランチこそがAmazon KDPへのリリース（出版）対象**。
   - `production` へのマージは **`main` ブランチからのみ** 許可される（直接コミット・プッシュ禁止）。
3. **成果物ビルド（GitHub Actions）**
   - `main` ブランチへのマージ時: 開発版プレビュー用EPUBが自動生成される。
   - `production` ブランチへのマージ時: KDP入稿用の正式リリース版EPUBが自動生成される。

---

## 2. SDD（仕様・Issue駆動）開発・執筆フロー

原稿の執筆、構成案の変更、機能追加・修正はすべて **SDD（Spec-Driven Development）** の思想に基づき、GitHub Issueを起点とする。

1. **GitHub Issue 作成（仕様・要件定義）**
   - 執筆・変更を行う前に、必ずGitHub Issueを作成し、「執筆・変更の目的」「対象章や構成」「満たすべき品質要件」を記述する。
2. **作業ブランチの作成**
   - `feat/issue-<No>-<title>` などの形式でIssueに紐付くブランチを作成する。
3. **執筆・編集作業**
   - `manuscript/` 配下のMarkdownファイルおよび `metadata.yaml` などを編集。
4. **`main` 宛てプルリクエスト（PR）の作成**
   - 変更内容を説明し、`Closes #<Issue番号>` を記載してPRを作成する。
5. **`main` へのマージとプレビュー検証**
   - ActionsでビルドされたEPUBで内容・レイアウトを確認。
6. **`production` へのリリースPR**
   - 一定のまとまり（章の完成、推敲完了時など）で `main` -> `production` のPRを作成・マージして正式リリースとする。

---

## 3. 執筆環境と構成

- 原稿: `manuscript/` 配下のMarkdown（`.md`）ファイル
- スタイル: `manuscript/style.css`
- メタデータ: `manuscript/metadata.yaml`
- 画像: `images/`
- ビルドツール: GitHub Actions上のPandoc
