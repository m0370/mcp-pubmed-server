# PubMed MCP Server

PubMedから論文を検索・取得するためのツールを提供するMCP (Model Context Protocol) サーバーです。
Claude DesktopやAntigravityなどのAIエージェントが、医学文献データベースに直接アクセスすることを可能にします。

## 特徴

- **PubMed検索**: キーワードを使用して論文を検索できます。
- **高度な絞り込み検索**: 著者名、雑誌名、発行日などで絞り込んだ検索が可能です。自然言語での指示にも対応しています。
- **関連論文の推薦**: 特定の論文（PMID）から関連論文を自動的に見つけます。高IF雑誌優先モードでは、高品質論文を優先的に表示し、不足時は自動的に他の論文も含めます。レビュー論文・メタアナリシスは自動検出して明示します。
- **論文詳細の取得**: 特定の論文のアブストラクト（要約）、著者、書誌情報、DOI、全文リンク（PubMed Central、DOI）などを取得できます。
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

### VS Code + Claude Codeでの利用

VS Codeで「Claude Code」拡張機能を使用している場合も、同様にMCPサーバーを利用できます。

1.  **VS Codeの設定ファイルを開く**:
    *   `Cmd + Shift + P` (macOS) または `Ctrl + Shift + P` (Windows/Linux) でコマンドパレットを開く
    *   「Preferences: Open User Settings (JSON)」を選択

2.  **設定を追加**:
    `settings.json` に以下を追加してください。

    ```json
    {
      "claude.mcpServers": {
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

3.  **VS Codeを再起動**: 設定を反映させるため、VS Codeを再起動してください。

**注意**: 拡張機能によって設定キーが異なる場合があります（`claude.mcpServers` または `mcpServers` など）。詳細は各拡張機能のドキュメントをご確認ください。


## 使い方

設定完了後、AIに対して以下のように話しかけることで機能を利用できます。

### 基本的な検索
> 「HER2陽性胃癌の治療に関する最新の論文を検索して」

### 高度な絞り込み検索
> 「Smithさんの2023年の胃癌に関する論文を探して」
> 「NEJMに掲載された免疫療法の論文を検索して」
> 「2020年から2024年の間に発表されたPD-1阻害薬の論文を見つけて」

### 論文詳細の取得
> 「PMID 12345678 のアブストラクトを取得して要約して」
> 「この論文の全文リンクを教えて」

### 関連論文の推薦
> 「PMID 39282917 に関連する論文を探して」
> 「この論文に関連する高IF雑誌の論文だけ教えて」
> 「NEJM、Lancet、Natureなどの一流雑誌に掲載された関連論文を見つけて」

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
