# tools/movie_tools.py

import os
import httpx
import logging
import json

logger = logging.getLogger(__name__)

# .env file se URL uthayega
MOVIE_API_BASE_URL = os.environ.get("MOVIE_API_URL", "https://filimizila-direct-movie-link-extractor.onrender.com")

def search_movie_in_database(movie_name: str) -> str:
    """
    Searches for a movie or series and returns a list of possible matches with their URLs.
    This is the FIRST step. Use this to find the correct URL for a movie.
    The output is a JSON string of a list like: [{'title': 'Movie Title', 'url': 'http://...'}].
    """
    logger.info(f"[GEMINI-WORKER] Executing search for movie: '{movie_name}'")
    
    if not movie_name:
        return "Error: Movie name cannot be empty."

    try:
        search_url = f"{MOVIE_API_BASE_URL}/api/search?q={movie_name}"
        with httpx.Client() as client:
            response = client.get(search_url, timeout=30.0)
            response.raise_for_status()
            results = response.json()
        
        if not results or "error" in results:
            return f"No results found for '{movie_name}'."
        
        # Sirf zaroori data (title aur url) hi string format mein AI ko wapas bhejo
        # Gemini JSON strings ko aasani se samajh leta hai
        simplified_results = [{"title": r.get("title"), "url": r.get("url")} for r in results[:10]] # Limit to 10
        return json.dumps(simplified_results)

    except Exception as e:
        logger.error(f"Error in search_movie_in_database tool: {e}", exc_info=True)
        return f"An internal tool error occurred: {str(e)}"

def get_details_and_download_links(movie_page_url: str) -> str:
    """
    Fetches all details and direct download links for a specific movie page URL.
    This is the SECOND step. Use this ONLY after you have the correct URL from the 'search_movie_in_database' tool.
    The output is a JSON string containing all details and links.
    """
    logger.info(f"[GEMINI-WORKER] Fetching details for URL: '{movie_page_url}'")
    
    if not movie_page_url or not movie_page_url.startswith("http"):
        return "Error: A valid movie page URL is required."

    try:
        fetch_url = f"{MOVIE_API_BASE_URL}/api/fetch"
        with httpx.Client() as client:
            response = client.post(fetch_url, json={"url": movie_page_url}, timeout=60.0)
            response.raise_for_status()
            data = response.json()
        
        # Poora data JSON string mein convert karke AI ko bhejo
        return json.dumps(data)

    except Exception as e:
        logger.error(f"Error in get_details_and_download_links tool: {e}", exc_info=True)
        return f"An internal tool error occurred: {str(e)}"
