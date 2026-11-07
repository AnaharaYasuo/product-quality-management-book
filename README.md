# プロダクト品質管理の極意（仮）

Amazon Kindle ダイレクト・パブリッシング（KDP）向けの電子書籍執筆リポジトリです。
Markdownで執筆し、GitHub Actionsにより自動でEPUBファイルがビルドされます。

## ディレクトリ構成

```text
├── .github/
│   └── workflows/
│       └── build-epub.yml    # Push時にEPUBを自動ビルド・Artifacts保存するワークフロー
├── manuscript/               # 原稿Markdownファイル置き場
│   ├── metadata.yaml         # 書籍メタデータ（タイトル、著者、言語など）
│   ├── style.css             # 電子書籍用スタイルシート
│   ├── 00_intro.md           # はじめに
│   ├── 01_chapter1.md        # 第1章
│   └── 99_afterword.md       # おわりに
├── images/                   # 原稿内で使用する画像
└── README.md
```

## 執筆フロー

1. `manuscript/` 配下のMarkdownファイルを編集・追加します。
2. 変更をコミットしてGitHub（`main` ブランチ）にプッシュします。
3. GitHub Actionsが自動実行され、EPUBファイルが生成されます。
4. GitHubリポジトリの **Actions** タブから最新の実行結果を開き、「Artifacts」から生成された `.epub` ファイルをダウンロードしてKindleアプリやKindle Previewerで確認できます。

## 書籍メタデータ変更

書籍のタイトルや著者名は [manuscript/metadata.yaml](manuscript/metadata.yaml) で設定できます。
