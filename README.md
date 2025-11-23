# PubMed MCP Server

PubMedから論文を検索・取得するためのツールを提供するMCP (Model Context Protocol) サーバーです。
Claude DesktopやAntigravityなどのAIエージェントが、医学文献データベースに直接アクセスすることを可能にします。

## 特徴

- **PubMed検索**: キーワードを使用して論文を検索できます。
- **論文詳細の取得**: 特定の論文のアブストラクト（要約）、著者、書誌情報などを取得できます。
- **API Key対応**: NCBI API Keyを設定することで、レート制限を緩和（最大10リクエスト/秒）できます。
- **Stdio通信**: 標準入出力（Stdio）を使用して通信するため、外部HTTPサーバーを立てる必要がなく、安全かつ高速です。

## 前提条件

- Python 3.10 以上
- ライブラリ: `httpx`, `xmltodict`

## セットアップ手順

1.  **リポジトリのクローン:**
    ```bash
    git clone https://github.com/m0370/mcp-pubmed-server.git
    cd mcp-pubmed-server
    ```

2.  **仮想環境の作成:**
    ```bash
    python3 -m venv .venv
    ```

3.  **依存ライブラリのインストール:**
    ```bash
    ./.venv/bin/pip install -r requirements.txt
    ```

## 設定 (Configuration)

MCPクライアントの設定ファイル（例: `claude_desktop_config.json`）に以下の設定を追加してください。

```json
{
  "mcpServers": {
    "pubmed": {
      "command": "/absolute/path/to/mcp-pubmed-server/.venv/bin/python3",
      "args": [
        "/absolute/path/to/mcp-pubmed-server/server_stdio.py"
      ],
      "env": {
        "NCBI_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

*   `/absolute/path/to/...` の部分は、実際にこのリポジトリを配置したディレクトリの絶対パスに書き換えてください。
*   **API Keyの設定（任意）**: `env` セクションに `NCBI_API_KEY` を設定すると、APIのレート制限が緩和されます（キーなし: 3回/秒 → キーあり: 10回/秒）。

## 使い方

設定完了後、AIに対して以下のように話しかけることで機能を利用できます。

> 「HER2陽性胃癌の治療に関する最新の論文を検索して」
> 「PMID 12345678 のアブストラクトを取得して要約して」

## 仕組み

1.  **MCPプロトコル**: JSON-RPC 2.0 プロトコルを使用し、標準入力（stdin）でリクエストを受け取り、標準出力（stdout）でレスポンスを返します。
2.  **PubMed API**: 内部で NCBI E-utilities API (`esearch`, `efetch`) を呼び出し、データを取得しています。
3.  **ローカル実行**: HTTPサーバーではなく、MCPクライアントのサブプロセスとしてローカルで動作するため、セキュリティリスクが低く、レスポンスも高速です。

## ファイル構成

- `server_stdio.py`: メインのサーバー実装（Stdio版）。通常はこちらを使用します。
- `requirements.txt`: 必要なPythonライブラリ一覧。
- `server.py`: (旧版) `mcp` SDKを使用した実装例。環境によっては動作しない場合があります。

## ライセンス

MIT
