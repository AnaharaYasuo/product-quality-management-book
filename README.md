# プロダクト品質管理の実践ガイド（Kindle電子書籍）

Amazon Kindle ダイレクト・パブリッシング（KDP）向けの商業技術書『**プロダクト品質管理の実践ガイド ―― 高品質なプロダクトを継続的に届けるための設計とプロセス**』の原稿・ビルド・品質監査リポジトリです。
Markdownで執筆し、GitHub Actionsにより自動で多層品質ゲート検証（静的解析・リンク検証・W3C EPUBCheck・編集者AIレビュー）およびEPUBファイルのビルドが行われます。

## 書籍の構成（全7部・25章）

詳細な章立てと各章のスコープは [docs/TABLE_OF_CONTENTS.md](docs/TABLE_OF_CONTENTS.md) を参照してください。

- **第I部：パラダイムシフトと二大成果物モデル**（第1章〜第2章）
- **第II部：【徹底実践】プロダクト成果物の検証・レビュー・監査**（第3章〜第9章）
- **第III部：【徹底実践】開発プロセス成果物のバリエーションと品質保証**（第10章〜第13章）
- **第IV部：動的検証・シフトライト・セキュリティ品質**（第14章〜第16章）
- **第V部：AIプロダクトと自律型AIエージェントの品質保証**（第17章〜第19章）
- **第VI部：組織変革・カルチャーと品質の未来**（第20章〜第21章）
- **第VII部：品質のトレードオフ・倫理・現場のリアリズム**（第22章〜第25章）
- **巻頭・巻末**：はじめに（`00_intro.md`）／おわりに ＆ 巻末付録（`99_afterword.md`）

## 運用ルール（重要）

本プロジェクトは **SDD（仕様・Issue駆動）** および **PRベースの運用** を徹底しています。
詳細は [docs/DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md) および [docs/EDITORIAL_REVIEW_GUIDELINES.md](docs/EDITORIAL_REVIEW_GUIDELINES.md) を参照してください。

- **`production` ブランチ**: リリース（KDP出版）対象。`main` からのPRマージのみ許可。
- **`main` ブランチ**: 執筆統合ブランチ。直接コミット禁止。作業ブランチからのPRマージのみ許可。
- **変更手順**: すべての変更はまず **GitHub Issue** を起票し、作業ブランチで執筆・修正 ➔ `main` へのPR ➔ `production` へのPR の順に行います。

## ディレクトリ構成

```text
├── .github/
│   └── workflows/
│       ├── build-epub.yml                # Push/Tag時にEPUBを自動ビルド・Artifacts/Releases保存
│       ├── verify-manuscript.yml         # Markdownlint・日本語Linter・リンクチェック・EPUBCheck
│       ├── verify-editorial-quality.yml  # PR時の編集者AI品質ゲート（12大次元・ペルソナ評価）
│       └── full-book-review.yml          # 全章一括の編集者AIレビュー＆改善Issue自動起票
├── docs/
│   ├── DEVELOPMENT_RULES.md              # ブランチ戦略・SDD運用ルール
│   ├── EDITORIAL_REVIEW_GUIDELINES.md    # 商業出版・編集者レビュー基準（12大評価次元）
│   └── TABLE_OF_CONTENTS.md              # 全7部・25章の詳細目次・構成設計書
├── manuscript/                           # 原稿Markdownファイル置き場
│   ├── metadata.yaml                     # 書籍メタデータ（タイトル、著者、言語など）
│   ├── style.css                         # 電子書籍用スタイルシート
│   ├── 00_intro.md                       # はじめに
│   ├── 01_chapter1.md 〜 25_chapter25.md # 第1章〜第25章（本編）
│   └── 99_afterword.md                   # おわりに ＆ 巻末付録
├── tools/                                # 原稿品質監査・Linterスクリプト群
│   ├── lint_manuscript.py                # 日本語表現・見出し階層・文長Linter
│   ├── audit_book_dod.py                 # 商業技術書DoD（文字数・図解・コード・合否基準）監査
│   └── evaluate_chapter_editorial.py     # LLM-as-a-Judge 編集者レビュー評価エンジン
├── images/                               # 原稿内で使用する画像
└── README.md
```

## 書籍メタデータ変更

書籍のタイトルや著者名は [manuscript/metadata.yaml](manuscript/metadata.yaml) で設定できます。
