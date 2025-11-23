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
    """Search PubMed for papers matching the query"""
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
    """Get detailed information (Abstract, Authors, DOI, Links) for a specific PMID"""
    logger.info(f"Fetching details for PMID: {pmid}")
    async with httpx.AsyncClient() as client:
        fetch_params = get_params({"db": "pubmed", "id": pmid, "retmode": "xml"})
        resp = await client.get(f"{BASE_URL}/efetch.fcgi", params=fetch_params)
        data = xmltodict.parse(resp.text)
        
        try:
            # Check if PubMed returned valid data
            if 'PubmedArticleSet' not in data or not data['PubmedArticleSet']:
                return f"Error: PMID {pmid} not found. Please check the PMID and try again."
            
            pubmed_article_set = data['PubmedArticleSet']
            if 'PubmedArticle' not in pubmed_article_set or not pubmed_article_set['PubmedArticle']:
                return f"Error: PMID {pmid} not found. Please check the PMID and try again."
            
            pubmed_article = pubmed_article_set['PubmedArticle']
            article = pubmed_article['MedlineCitation']['Article']
            title = article.get('ArticleTitle', 'No title')
            
            # Extract abstract
            abstract_text = ""
            if 'Abstract' in article and 'AbstractText' in article['Abstract']:
                abs_content = article['Abstract']['AbstractText']
                if isinstance(abs_content, list):
                    abstract_text = "\n".join([item.get('#text', '') if isinstance(item, dict) else item for item in abs_content])
                elif isinstance(abs_content, dict):
                    abstract_text = abs_content.get('#text', '')
                else:
                    abstract_text = abs_content
            
            # Extract authors
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

            # Extract DOI and PMC ID
            doi = None
            pmc_id = None
            if 'PubmedData' in pubmed_article and 'ArticleIdList' in pubmed_article['PubmedData']:
                id_list = pubmed_article['PubmedData']['ArticleIdList']['ArticleId']
                if not isinstance(id_list, list):
                    id_list = [id_list]
                for article_id in id_list:
                    if isinstance(article_id, dict):
                        id_type = article_id.get('@IdType')
                        id_value = article_id.get('#text')
                        if id_type == 'doi':
                            doi = id_value
                        elif id_type == 'pmc':
                            pmc_id = id_value

            # Build links
            links = {
                "pubmed": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            }
            if pmc_id:
                links["pmc"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/"
            if doi:
                links["doi"] = f"https://doi.org/{doi}"

            result = {
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "journal": article.get('Journal', {}).get('Title', ''),
                "doi": doi,
                "pmc_id": pmc_id,
                "abstract": abstract_text,
                "links": links
            }
            return json.dumps(result, indent=2, ensure_ascii=False)
        except KeyError:
            return f"Error: PMID {pmid} not found or invalid. Please check the PMID and try again."
        except Exception as e:
            logger.error(f"Error parsing details for PMID {pmid}: {e}")
            return f"Error retrieving details for PMID {pmid}: {str(e)}"

async def advanced_search_pubmed(
    query: str,
    author: str = None,
    journal: str = None,
    pub_date_from: str = None,
    pub_date_to: str = None,
    max_results: int = 5
) -> str:
    """
    Advanced search with filters for author, journal, and publication date.
    Supports both structured parameters and natural language queries.
    """
    logger.info(f"Advanced search - Query: {query}, Author: {author}, Journal: {journal}")
    
    # Build PubMed search query
    query_parts = [f"({query})"]
    
    if author:
        # Handle various author name formats
        query_parts.append(f"({author}[Author])")
    
    if journal:
        # Support both full names and abbreviations
        query_parts.append(f"({journal}[Journal])")
    
    if pub_date_from or pub_date_to:
        # Date range filter
        date_from = pub_date_from if pub_date_from else "1900/01/01"
        date_to = pub_date_to if pub_date_to else "3000/12/31"
        query_parts.append(f'("{date_from}"[PDAT] : "{date_to}"[PDAT])')
    
    final_query = " AND ".join(query_parts)
    logger.info(f"Constructed query: {final_query}")
    
    # Use the same search logic as search_pubmed
    async with httpx.AsyncClient() as client:
        search_params = get_params({
            "db": "pubmed",
            "term": final_query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance"
        })
        resp = await client.get(f"{BASE_URL}/esearch.fcgi", params=search_params)
        data = resp.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return f"No results found for query: {final_query}"

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
                    "source": item.get("source", "Unknown source"),
                    "authors": item.get("authors", [])
                })
        
        return json.dumps(results, indent=2, ensure_ascii=False)

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
                            "description": "Get detailed information (Abstract, Authors, DOI, full-text links) for a specific PMID.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "pmid": {"type": "string"}
                                },
                                "required": ["pmid"]
                            }
                        },
                        {
                            "name": "advanced_search_pubmed",
                            "description": "Advanced search with filters. Can handle natural language requests like 'Smith's 2023 papers on gastric cancer' or structured parameters. Filters: author name, journal name, publication date range.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Main search keywords"},
                                    "author": {"type": "string", "description": "Author name (e.g., 'Smith J', 'Tanaka')"},
                                    "journal": {"type": "string", "description": "Journal name or abbreviation (e.g., 'NEJM', 'Lancet', 'Nature')"},
                                    "pub_date_from": {"type": "string", "description": "Start date in YYYY/MM/DD format"},
                                    "pub_date_to": {"type": "string", "description": "End date in YYYY/MM/DD format"},
                                    "max_results": {"type": "integer", "default": 5}
                                },
                                "required": ["query"]
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
            elif name == "advanced_search_pubmed":
                result_content = await advanced_search_pubmed(
                    query=args.get("query"),
                    author=args.get("author"),
                    journal=args.get("journal"),
                    pub_date_from=args.get("pub_date_from"),
                    pub_date_to=args.get("pub_date_to"),
                    max_results=args.get("max_results", 5)
                )
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
