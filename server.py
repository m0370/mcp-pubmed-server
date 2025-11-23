from mcp.server.fastmcp import FastMCP
import httpx
import xmltodict
import json

# Initialize the MCP server
mcp = FastMCP("PubMed Server")

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

@mcp.tool()
async def search_pubmed(query: str, max_results: int = 5) -> str:
    """
    Search PubMed for papers matching the query.
    Returns a list of PMIDs and Titles.
    """
    async with httpx.AsyncClient() as client:
        # 1. Search for PMIDs
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance"
        }
        search_response = await client.get(f"{BASE_URL}/esearch.fcgi", params=search_params)
        search_data = search_response.json()
        
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return "No results found."

        # 2. Fetch summaries to get titles
        summary_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        summary_response = await client.get(f"{BASE_URL}/esummary.fcgi", params=summary_params)
        summary_data = summary_response.json()
        
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

@mcp.tool()
async def get_paper_details(pmid: str) -> str:
    """
    Get detailed information (Abstract, Authors, DOI) for a specific PMID.
    """
    async with httpx.AsyncClient() as client:
        fetch_params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml"
        }
        response = await client.get(f"{BASE_URL}/efetch.fcgi", params=fetch_params)
        
        # Parse XML
        data = xmltodict.parse(response.text)
        
        try:
            article = data['PubmedArticleSet']['PubmedArticle']['MedlineCitation']['Article']
            
            # Extract Title
            title = article.get('ArticleTitle', 'No title')
            
            # Extract Abstract
            abstract_text = ""
            if 'Abstract' in article and 'AbstractText' in article['Abstract']:
                abs_content = article['Abstract']['AbstractText']
                if isinstance(abs_content, list):
                    abstract_text = "\n".join([item.get('#text', '') if isinstance(item, dict) else item for item in abs_content])
                elif isinstance(abs_content, dict):
                    abstract_text = abs_content.get('#text', '')
                else:
                    abstract_text = abs_content
            
            # Extract Authors
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
            
            # Extract DOI
            doi = ""
            if 'ELocationID' in article:
                eloc = article['ELocationID']
                if isinstance(eloc, list):
                    for item in eloc:
                        if item.get('@EIdType') == 'doi':
                            doi = item.get('#text')
                elif isinstance(eloc, dict):
                    if eloc.get('@EIdType') == 'doi':
                        doi = eloc.get('#text')

            result = {
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "journal": article.get('Journal', {}).get('Title', ''),
                "doi": doi,
                "abstract": abstract_text
            }
            
            return json.dumps(result, indent=2, ensure_ascii=False)
            
        except Exception as e:
            return f"Error parsing details for PMID {pmid}: {str(e)}"

if __name__ == "__main__":
    mcp.run()
