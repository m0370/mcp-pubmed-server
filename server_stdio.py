import sys
import json
import asyncio
import httpx
import xmltodict
import logging

import os

# Configure logging to stderr so it doesn't interfere with stdout JSON-RPC
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("pubmed-mcp")

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("NCBI_API_KEY")

def get_params(base_params: dict) -> dict:
    """Helper to add API key to params if available"""
    if API_KEY:
        base_params["api_key"] = API_KEY
    return base_params

# --- Tool Implementations ---

async def search_pubmed(query: str, max_results: int = 5) -> str:
    logger.info(f"Searching PubMed for: {query}")
    async with httpx.AsyncClient() as client:
        search_params = get_params({
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance"
        })
        resp = await client.get(f"{BASE_URL}/esearch.fcgi", params=search_params)
        data = resp.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return "No results found."

        summary_params = get_params({
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        })
        resp = await client.get(f"{BASE_URL}/esummary.fcgi", params=summary_params)
        summary_data = resp.json()
        
        results = []
        uid_data = summary_data.get("result", {})
        for pmid in id_list:
            if pmid in uid_data:
                item = uid_data[pmid]
                results.append({
                    "pmid": pmid,
                    "title": item.get("title", "No title"),
                    "pubdate": item.get("pubdate", "Unknown date"),
                    "source": item.get("source", "Unknown source")
                })
        
        return json.dumps(results, indent=2, ensure_ascii=False)

async def get_paper_details(pmid: str) -> str:
    logger.info(f"Fetching details for PMID: {pmid}")
    async with httpx.AsyncClient() as client:
        fetch_params = get_params({"db": "pubmed", "id": pmid, "retmode": "xml"})
        resp = await client.get(f"{BASE_URL}/efetch.fcgi", params=fetch_params)
        data = xmltodict.parse(resp.text)
        
        try:
            article = data['PubmedArticleSet']['PubmedArticle']['MedlineCitation']['Article']
            title = article.get('ArticleTitle', 'No title')
            
            abstract_text = ""
            if 'Abstract' in article and 'AbstractText' in article['Abstract']:
                abs_content = article['Abstract']['AbstractText']
                if isinstance(abs_content, list):
                    abstract_text = "\n".join([item.get('#text', '') if isinstance(item, dict) else item for item in abs_content])
                elif isinstance(abs_content, dict):
                    abstract_text = abs_content.get('#text', '')
                else:
                    abstract_text = abs_content
            
            authors = []
            if 'AuthorList' in article and 'Author' in article['AuthorList']:
                auth_list = article['AuthorList']['Author']
                if isinstance(auth_list, list):
                    for auth in auth_list:
                        if 'LastName' in auth and 'ForeName' in auth:
                            authors.append(f"{auth['LastName']} {auth['ForeName']}")
                elif isinstance(auth_list, dict):
                    if 'LastName' in auth_list and 'ForeName' in auth_list:
                        authors.append(f"{auth_list['LastName']} {auth_list['ForeName']}")

            result = {
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "journal": article.get('Journal', {}).get('Title', ''),
                "abstract": abstract_text
            }
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error parsing details: {str(e)}"

# --- MCP Protocol Handling ---

async def handle_message(message):
    try:
        if "method" not in message:
            return
        
        method = message["method"]
        msg_id = message.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "pubmed-server",
                        "version": "0.1.0"
                    }
                }
            }
            print(json.dumps(response), flush=True)

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "search_pubmed",
                            "description": "Search PubMed for papers matching the query.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "max_results": {"type": "integer", "default": 5}
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "get_paper_details",
                            "description": "Get detailed information (Abstract, Authors) for a specific PMID.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "pmid": {"type": "string"}
                                },
                                "required": ["pmid"]
                            }
                        }
                    ]
                }
            }
            print(json.dumps(response), flush=True)

        elif method == "tools/call":
            params = message.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            
            result_content = ""
            if name == "search_pubmed":
                result_content = await search_pubmed(args.get("query"), args.get("max_results", 5))
            elif name == "get_paper_details":
                result_content = await get_paper_details(args.get("pmid"))
            else:
                raise ValueError(f"Unknown tool: {name}")

            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_content
                        }
                    ]
                }
            }
            print(json.dumps(response), flush=True)
            
        elif method == "notifications/initialized":
            pass # No response needed

        else:
            # Ignore other methods for now
            pass

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        if msg_id is not None:
            error_response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)

async def run_server():
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            message = json.loads(line)
            await handle_message(message)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON")
        except Exception as e:
            logger.error(f"Server loop error: {e}")

if __name__ == "__main__":
    asyncio.run(run_server())
