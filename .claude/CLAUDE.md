# CLAUDE.md - mcp-pubmed-server プロジェクト開発ガイド

## プロジェクト概要

このプロジェクトは、PubMed（医学文献データベース）にアクセスするためのMCP (Model Context Protocol) サーバーです。
Claude DesktopやAntigravity、VS Code + Claude Codeなどから利用できます。

## 開発時の重要なルール

### 1. TODO.mdの管理

**必須事項:**
- 新しい機能を実装する前に、必ず `TODO.md` を確認すること
- 機能実装後は、必ず `TODO.md` に進捗を反映すること
- 完了した機能には ✅ マークを付け、完了日を記録すること

**TODO.mdの場所:**
- `/Users/tgoto/Library/Mobile Documents/com~apple~CloudDocs/my web site/mcp-pubmed-server/TODO.md`
- このファイルは `.gitignore` に含まれており、GitHubにはプッシュされません（内部管理用）

**更新タイミング:**
- 機能実装の計画を立てたとき
- 機能実装が完了したとき
- 新しいタスクを追加するとき

### 2. コミット・プッシュのルール

**コミットメッセージ:**
- 日本語または英語で記述
- 変更内容を明確に記載
- 複数の変更がある場合は箇条書きで詳細を追記

**プッシュ前の確認:**
- `TODO.md` が `.gitignore` に含まれていることを確認
- API Keyなどの機密情報がコードに含まれていないことを確認
- README.mdが最新の機能を反映しているか確認

### 3. コーディング規約

**Python:**
- 型ヒントを使用する（例: `def search_pubmed(query: str, max_results: int = 5) -> str:`）
- 関数にはdocstringを記載する
- 非同期関数には `async/await` を使用

**API Key管理:**
- API Keyは環境変数から取得する（`os.environ.get("NCBI_API_KEY")`）
- コードに直接埋め込まない
- `get_params()` ヘルパー関数を使用してすべてのAPIリクエストにキーを付与

**エラーハンドリング:**
- 検索結果が0件の場合の処理を必ず実装
- XMLパースエラーに対応
- ユーザーフレンドリーなエラーメッセージを返す

### 4. ドキュメント更新

**README.md:**
- 新機能を追加したら、必ず「特徴」セクションを更新
- 使用例を追加（自然言語での指示例を含める）
- VS Code + Claude Codeでの利用方法も記載

**言語:**
- README.mdは日本語で記述
- コード内のコメントは英語または日本語
- コミットメッセージは英語推奨（日本語も可）

### 5. テスト

**動作確認:**
- 新機能実装後は、必ず実際にMCPクライアントから呼び出して動作確認
- エラーケース（検索結果0件、不正なPMIDなど）も確認

**テストスクリプト:**
- 必要に応じて `test_*.py` ファイルを作成
- ただし、これらは `.gitignore` に追加してプッシュしない

### 6. プロジェクト構成

```
mcp-pubmed-server/
├── .claude/
│   └── CLAUDE.md          # このファイル（開発ガイド）
├── .venv/                 # 仮想環境（gitignore）
├── .gitignore
├── LICENSE                # MIT License
├── README.md              # 日本語ドキュメント
├── requirements.txt       # 依存ライブラリ
├── server_stdio.py        # メインサーバー（Stdio版）
├── server.py              # 旧版（mcp SDK使用）
└── TODO.md                # タスク管理（gitignore、内部用）
```

### 7. 将来の拡張方針

**優先度の高い機能:**
- 引用文献の自動生成（Vancouver, APA形式）
- MeSH用語の取得
- 関連論文の推薦

**ブログ記事執筆:**
- blog_writingディレクトリのルール（CLAUDE.md）に従う
- タイトル案: 「LLMでPubMed検索を可能にするための汎用的MCPサーバー」
- 技術的な解説と実用例をバランスよく記載

---

## よくある作業フロー

### 新機能を追加する場合

1.  `TODO.md` を確認し、実装する機能を決定
2.  `TODO.md` に実装計画を追記（必要に応じて）
3.  `server_stdio.py` にコードを追加
4.  MCPプロトコルハンドラ（`tools/list`, `tools/call`）に登録
5.  `README.md` を更新（特徴、使用例）
6.  動作確認
7.  `TODO.md` に完了マークと完了日を記録
8.  コミット・プッシュ

### バグ修正の場合

1.  問題を特定
2.  修正
3.  動作確認
4.  コミット・プッシュ（TODO.mdの更新は不要）

### ドキュメント更新のみの場合

1.  README.mdまたはCLAUDE.mdを編集
2.  コミット・プッシュ

---

## 注意事項

- このプロジェクトはオープンソース（MIT License）です
- API Keyなどの機密情報は絶対にコミットしないこと
- TODO.mdは内部管理用のため、GitHubにプッシュしないこと
