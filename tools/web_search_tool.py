# File: tools/web_search_tool.py

import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# .env file se Vercel API ka URL lega
# Aapko .env file mein yeh line add karni hogi:
# VERCEL_SEARCH_API_URL="https://ai-tools-backend-b7snaf8j5-badals-projects-03fab3df.vercel.app/api/execute-tool"
VERCEL_API_URL = os.environ.get("VERCEL_SEARCH_API_URL")

def web_search(query: str, research_mode: Optional[str] = "deep") -> str:
    """
    Performs a deep web search and generates a comprehensive report on a given query.
    Use this for any user questions that require up-to-date information from the internet.
    
    Args:
        query (str): The user's search query. This is a required argument.
        research_mode (Optional[str]): The depth of the research. Can be 'normal' for a quick summary or 'deep' for a detailed report. Defaults to 'deep'.
        
    Returns:
        str: A detailed report in text format, ready for the AI to present to the user.
    """
    logger.info(f"[WEB SEARCH TOOL] Called with query: '{query}', mode: '{research_mode}'")

    if not VERCEL_API_URL:
        return "Error: The VERCEL_SEARCH_API_URL is not configured on the server. I cannot perform a web search."

    if not query:
        return "Error: A query must be provided to perform a web search."

    # Vercel API ke liye payload banayein
    payload = {
        "toolName": "web_search",
        "toolInput": {
            "query": query,
            "research_mode": research_mode
        }
    }

    try:
        # httpx ka istemal karke Vercel API ko POST request bhejein
        with httpx.Client() as client:
            response = client.post(VERCEL_API_URL, json=payload, timeout=45.0) # Timeout 45 seconds rakhte hain
            response.raise_for_status() # Agar 4xx ya 5xx error ho to exception raise karega
            
            data = response.json()
        
        # Vercel se mila 'result' seedha return kar dein
        if "result" in data:
            logger.info(f"[WEB SEARCH TOOL] Successfully received a report for query: '{query}'")
            return data["result"]
        else:
            logger.warning(f"[WEB SEARCH TOOL] Vercel API response did not contain a 'result' key. Response: {data}")
            return f"Error: The web search service returned an unexpected response: {data}"

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP Error while calling Vercel search API: {e.response.text}")
        return f"An API error occurred while searching the web: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in the web_search tool: {e}", exc_info=True)
        return f"An internal tool error occurred: {str(e)}"
