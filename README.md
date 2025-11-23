# PubMed MCP Server

A Model Context Protocol (MCP) server that provides tools to search and retrieve papers from PubMed.
This server allows AI agents (like Claude Desktop or Antigravity) to directly access medical literature.

## Features

- **Search PubMed**: Search for papers using keywords.
- **Get Paper Details**: Retrieve abstracts, authors, and metadata for specific papers.
- **API Key Support**: Supports NCBI API Key for higher rate limits.
- **Stdio Communication**: Uses standard input/output for MCP communication (no HTTP server required).

## Prerequisites

- Python 3.10 or higher
- `httpx` and `xmltodict` libraries

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/m0370/mcp-pubmed-server.git
    cd mcp-pubmed-server
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv .venv
    ```

3.  **Install dependencies:**
    ```bash
    ./.venv/bin/pip install -r requirements.txt
    ```

## Configuration

Add the following configuration to your MCP client settings (e.g., `claude_desktop_config.json`):

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

*   Replace `/absolute/path/to/...` with the actual full path to your directory.
*   (Optional) Add your NCBI API Key to the `env` section to increase rate limits (up to 10 requests/second). Without a key, the limit is 3 requests/second.

## Usage

Once configured, you can ask the AI:

> "Search for recent papers on HER2 positive gastric cancer treatment."
> "Get the abstract for PMID 12345678."

## How it Works

1.  **MCP Protocol**: The server implements the Model Context Protocol using JSON-RPC 2.0 over Stdio. It listens for requests on `stdin` and sends responses to `stdout`.
2.  **PubMed API**: It uses the NCBI E-utilities API (`esearch` and `efetch`) to query the PubMed database.
3.  **No External Server**: Unlike HTTP-based MCP servers, this runs as a local subprocess managed directly by the MCP client, ensuring security and low latency.

## Files

- `server_stdio.py`: The main server implementation (Stdio based).
- `requirements.txt`: Python dependencies.
- `server.py`: (Legacy) Implementation using the `mcp` SDK (requires Python 3.10+ and compatible environment).

## License

MIT
