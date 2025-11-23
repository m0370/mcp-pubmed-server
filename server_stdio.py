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

# High-impact medical journals (top-tier)
HIGH_IMPACT_JOURNALS = [
    "N Engl J Med",
    "Lancet",
    "Lancet Oncol",
    "JAMA",
    "JAMA Oncol",
    "BMJ",
    "Nature",
    "Nature Medicine",
    "Nature Reviews Cancer",
    "Cell",
    "Science",
    "J Clin Oncol",
    "Ann Oncol",
    "Cancer Cell",
    "Cancer Discov",
    "Clin Cancer Res",
    "Ann Intern Med",
    "Gastroenterology",
    "Gut"
]

def is_high_impact_journal(journal_name: str) -> bool:
    """Check if a journal is in the high-impact list"""
    if not journal_name:
        return False
    # Normalize journal name for comparison
    journal_normalized = journal_name.strip().lower()
    for high_impact in HIGH_IMPACT_JOURNALS:
        if high_impact.lower() in journal_normalized:
            return True
    return False

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
                # Extract author names
                authors = item.get("authors", [])
                author_names = []
                for author in authors[:3]:  # First 3 authors
                    if isinstance(author, dict):
                        author_names.append(author.get("name", ""))
                
                # Detect publication type
                pub_types = item.get("pubtype", [])
                is_review = any("review" in pt.lower() for pt in pub_types)
                
                results.append({
                    "pmid": pmid,
                    "title": item.get("title", "No title"),
                    "authors": ", ".join(author_names) if author_names else "No authors",
                    "pubdate": item.get("pubdate", "Unknown date"),
                    "source": item.get("source", "Unknown source"),
                    "is_review": is_review
                })
        
        # Sort: original articles first, then reviews
        results.sort(key=lambda x: (x["is_review"], id_list.index(x["pmid"])))
        
        # Remove is_review flag from output (internal use only)
        for r in results:
            del r["is_review"]
        
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

async def get_similar_articles(pmid: str, max_results: int = 5, high_impact_only: bool = False) -> str:
    """
    Get similar articles for a given PMID using PubMed's elink API.
    Optionally filter to show only high-impact journal publications.
    """
    logger.info(f"Getting similar articles for PMID: {pmid}, high_impact_only: {high_impact_only}")
    
    async with httpx.AsyncClient() as client:
        # Get similar article PMIDs using elink
        elink_params = get_params({
            "dbfrom": "pubmed",
            "db": "pubmed",
            "id": pmid,
            "cmd": "neighbor_score",
            "retmode": "json"
        })
        
        resp = await client.get(f"{BASE_URL}/elink.fcgi", params=elink_params)
        data = resp.json()
        
        try:
            linksets = data.get("linksets", [])
            if not linksets:
                return "No similar articles found."
            
            linkset = linksets[0]
            linksetdbs = linkset.get("linksetdbs", [])
            
            similar_pmids = []
            for db in linksetdbs:
                if db.get("linkname") == "pubmed_pubmed":
                    links = db.get("links", [])
                    # Get more PMIDs if filtering by high-impact journals
                    fetch_count = max_results * 3 if high_impact_only else max_results
                    for link in links[:fetch_count]:
                        if isinstance(link, dict):
                            similar_pmids.append(str(link.get("id", "")))
                        else:
                            similar_pmids.append(str(link))
                    break
            
            if not similar_pmids:
                return "No similar articles found."
            
            # Get summaries for similar articles
            summary_params = get_params({
                "db": "pubmed",
                "id": ",".join(similar_pmids),
                "retmode": "json"
            })
            resp = await client.get(f"{BASE_URL}/esummary.fcgi", params=summary_params)
            summary_data = resp.json()
            
            # Separate results by journal quality and publication type
            high_impact_results = []
            other_results = []
            uid_data = summary_data.get("result", {})
            
            for pmid_str in similar_pmids:
                if pmid_str in uid_data:
                    item = uid_data[pmid_str]
                    journal = item.get("source", "")
                    title = item.get("title", "No title")
                    
                    # Detect review articles from title
                    # (esummary API doesn't provide detailed publication types)
                    is_review = False
                    review_type = ""
                    title_lower = title.lower()
                    
                    if "meta-analysis" in title_lower or "metaanalysis" in title_lower:
                        is_review = True
                        review_type = " [Meta-Analysis]"
                    elif "systematic review" in title_lower:
                        is_review = True
                        review_type = " [Systematic Review]"
                    elif title_lower.startswith("review") or ": a review" in title_lower or "review article" in title_lower:
                        is_review = True
                        review_type = " [Review]"
                    
                    paper_info = {
                        "pmid": pmid_str,
                        "title": title + review_type,
                        "pubdate": item.get("pubdate", "Unknown date"),
                        "source": journal,
                        "authors": item.get("authors", []),
                        "is_review": is_review
                    }
                    
                    # Categorize by journal impact
                    if is_high_impact_journal(journal):
                        high_impact_results.append(paper_info)
                    else:
                        other_results.append(paper_info)
            
            # Smart fallback logic
            if high_impact_only:
                # Prefer high-impact journals, but fallback if too few
                if len(high_impact_results) >= max_results:
                    results = high_impact_results[:max_results]
                elif len(high_impact_results) >= max_results // 2:
                    # If we have at least half from high-impact, use only those
                    results = high_impact_results[:max_results]
                else:
                    # Not enough high-impact papers, include others
                    results = high_impact_results + other_results
                    results = results[:max_results]
                    logger.info(f"Fallback: Only {len(high_impact_results)} high-impact papers found, including others")
            else:
                # No filtering, combine all results
                results = high_impact_results + other_results
                results = results[:max_results]
            
            if not results:
                return "No similar articles found."
            
            return json.dumps(results, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error getting similar articles: {e}")
            return f"Error retrieving similar articles: {str(e)}"

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
                            "description": "Search PubMed database and return REAL PMIDs with full details. CRITICAL WARNING: The PMIDs returned by this tool are the ONLY valid PMIDs. You MUST NOT generate, guess, or make up any PMIDs. NEVER cite a PMID that was not explicitly returned by this tool. Results are sorted to prioritize original research articles over reviews. Each result includes: PMID, full title, authors (first 3), publication date, journal name.",
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
                            "description": "Advanced PubMed search with filters (author, journal, date range). Returns REAL PMIDs only. CRITICAL WARNING: You MUST NOT generate or guess PMIDs. ONLY use PMIDs explicitly returned by this tool. NEVER cite a PMID that was not returned. Can parse natural language like 'Smith's 2023 gastric cancer papers'.",
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
                        },
                        {
                            "name": "get_similar_articles",
                            "description": "Find similar/related articles for a given PMID. Can optionally filter to show only high-impact journal publications (NEJM, Lancet, JAMA, Nature, etc.). Useful for literature review and finding related research.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "pmid": {"type": "string", "description": "PMID of the reference paper"},
                                    "max_results": {"type": "integer", "default": 5, "description": "Maximum number of similar articles to return"},
                                    "high_impact_only": {"type": "boolean", "default": False, "description": "If true, only return articles from high-impact journals (NEJM, Lancet, JAMA, Nature, etc.)"}
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
            elif name == "advanced_search_pubmed":
                result_content = await advanced_search_pubmed(
                    query=args.get("query"),
                    author=args.get("author"),
                    journal=args.get("journal"),
                    pub_date_from=args.get("pub_date_from"),
                    pub_date_to=args.get("pub_date_to"),
                    max_results=args.get("max_results", 5)
                )
            elif name == "get_similar_articles":
                result_content = await get_similar_articles(
                    pmid=args.get("pmid"),
                    max_results=args.get("max_results", 5),
                    high_impact_only=args.get("high_impact_only", False)
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
