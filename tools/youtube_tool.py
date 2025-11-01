# tools/youtube_tool.py

import os
import httpx
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

# Apne .env file se Vercel API ka URL lega
YOUTUBE_API_URL = os.environ.get("YOUTUBE_API_URL")

def youtube_tool(mode: str, query: Optional[str] = None, video_id: Optional[str] = None) -> str:
    """
    A powerful tool to interact with YouTube. It has two modes: 'search' to find videos, channels, and playlists,
    and 'analyze_video' to get a detailed, LLM-friendly report for a specific video.
    
    Args:
        mode (str): The operation to perform. Must be either 'search' or 'analyze_video'.
        query (Optional[str]): The search term. Required only when mode is 'search'.
        video_id (Optional[str]): The 11-character YouTube video ID. Required only when mode is 'analyze_video'.
        
    Returns:
        str: A formatted string containing the results or a detailed report for the AI to present to the user.
    """
    logger.info(f"[YOUTUBE TOOL] Called with mode: '{mode}'")

    if not YOUTUBE_API_URL:
        return "Error: YOUTUBE_API_URL environment variable is not set."

    try:
        # === MODE 1: SEARCH YOUTUBE ===
        if mode == 'search':
            if not query:
                return "Error: 'query' is required for 'search' mode."
            
            search_url = f"{YOUTUBE_API_URL}/api/analyze_search?q={query}"
            logger.info(f"[YOUTUBE TOOL] Hitting search URL: {search_url}")

            with httpx.Client() as client:
                response = client.get(search_url, timeout=45.0)
                response.raise_for_status()
                data = response.json()

            if not data.get("results"):
                return f"No search results found for '{query}'."

            # Search results ko LLM ke liye format karo
            report_lines = [f"Here are the top search results for '{query}':\n"]
            for item in data["results"]:
                report_lines.append("---")
                if item['type'] == 'video':
                    report_lines.append(f"Type: Video")
                    report_lines.append(f"Title: {item['title']}")
                    report_lines.append(f"Video ID: {item['videoId']}")
                    report_lines.append(f"Channel: {item['channelName']} {'(Verified)' if item.get('isVerified') else ''}")
                    report_lines.append(f"Views: {item['views']} | Uploaded: {item['uploadDate']} | Length: {item['length']}")
                    if item.get('specialProperties'):
                        report_lines.append(f"Properties: {', '.join(item['specialProperties'])}")
                
                elif item['type'] == 'channel':
                    report_lines.append(f"Type: Channel")
                    report_lines.append(f"Name: {item['name']} {'(Verified)' if item.get('isVerified') else ''}")
                    report_lines.append(f"Handle: {item.get('handle', 'N/A')}")
                    report_lines.append(f"Subscribers: {item['subscribers']} | Videos: {item['videoCount']}")
                    report_lines.append(f"Description: {item['description']}")

            return "\n".join(report_lines)

        # === MODE 2: ANALYZE A SPECIFIC VIDEO ===
        elif mode == 'analyze_video':
            if not video_id:
                return "Error: 'video_id' is required for 'analyze_video' mode."

            analyze_url = f"{YOUTUBE_API_URL}/api/analyze_video?v={video_id}"
            logger.info(f"[YOUTUBE TOOL] Hitting analyze URL: {analyze_url}")
            
            with httpx.Client() as client:
                response = client.get(analyze_url, timeout=60.0)
                response.raise_for_status()
                # Ye endpoint direct text report deta hai, to hum usko seedha return kar denge
                return response.text

        # Invalid mode
        else:
            return "Error: Invalid mode specified. Use 'search' or 'analyze_video'."

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP Error in youtube_tool: {e.response.text}")
        return f"An API error occurred: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error in youtube_tool: {e}", exc_info=True)
        return f"An internal tool error occurred: {str(e)}"
