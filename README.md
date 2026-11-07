# プロダクト品質管理の実践ガイド（Kindle電子書籍）

Amazon Kindle ダイレクト・パブリッシング（KDP）向けの電子書籍執筆リポジトリです。
Markdownで執筆し、GitHub Actionsにより自動でEPUBファイルがビルドされます。

## 運用ルール（重要）

本プロジェクトは **SDD（仕様・Issue駆動）** および **PRベースの運用** を徹底しています。
詳細は [docs/DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md) を参照してください。

- **`production` ブランチ**: リリース（KDP出版）対象。`main` からのPRマージのみ許可。
- **`main` ブランチ**: 執筆統合ブランチ。直接コミット禁止。作業ブランチからのPRマージのみ許可。
- **変更手順**: すべての変更はまず **GitHub Issue** を起票し、作業ブランチで執筆・修正 ➔ `main` へのPR ➔ `production` へのPR の順に行います。

## ディレクトリ構成

```text
├── .github/
│   └── workflows/
│       └── build-epub.yml    # Push時にEPUBを自動ビルド・Artifacts保存するワークフロー
├── docs/
│   └── DEVELOPMENT_RULES.md  # ブランチ戦略・運用ルール
├── manuscript/               # 原稿Markdownファイル置き場
│   ├── metadata.yaml         # 書籍メタデータ（タイトル、著者、言語など）
│   ├── style.css             # 電子書籍用スタイルシート
│   ├── 00_intro.md           # はじめに
│   ├── 01_chapter1.md        # 第1章
│   └── 99_afterword.md       # おわりに
├── images/                   # 原稿内で使用する画像
└── README.md
```

## 書籍メタデータ変更

書籍のタイトルや著者名は [manuscript/metadata.yaml](manuscript/metadata.yaml) で設定できます。
