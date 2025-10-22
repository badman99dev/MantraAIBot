import httpx
import logging
import re
import os

# Is file ko apne secrets ki zaroorat hai
VERCEL_API_URL = os.environ.get('VERCEL_API_URL', "https://youtube-transcript-dp2flwk98-badals-projects-03fab3df.vercel.app/api/transcript")
logger = logging.getLogger(__name__)

def extract_video_id(url: str) -> str | None:
    """YouTube URL se video ID nikalta hai."""
    patterns = [
        r"(?<=v=)[^&#]+", r"(?<=be/)[^&#]+", r"(?<=embed/)[^&#]+",
        r"(?<=shorts/)[^&#]+", r"(?<=live/)[^&#]+",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(0)
    return None

def fetch_youtube_details_from_api(video_id: str) -> str:
    """
    Gets transcript and details for a YouTube video using its VIDEO ID.
    When a user provides a full YouTube URL, you MUST first extract the 11-character video ID
    (e.g., from 'https://youtu.be/lgl16xZeS3o', the ID is 'lgl16xZeS3o')
    and pass ONLY that ID to this function.
    """
    logger.info(f"[GEMINI-WORKER] Gemini extracted ID: {video_id} and is calling the tool.")
    
    if not video_id or len(video_id) != 11:
        return "Error: Invalid YouTube Video ID received."

    try:
        with httpx.Client() as client:
            api_url_with_param = f"{VERCEL_API_URL}?v={video_id}"
            response = client.get(api_url_with_param, timeout=45.0)
            response.raise_for_status()
            data = response.json()

            if not data or not data.get("success"):
                return "Maaf karna, backend se transcript laane mein dikkat aayi."

            formatted_text = f"वीडियो टाइटल: {data.get('title', 'N/A')}\nचैनल: {data.get('channelTitle', 'N/A')}\nसब्सक्राइबर: {data.get('channelSubscribers', 'N/A')}\nव्यूज: {data.get('viewCount', 'N/A')}\nलाइक्स: {data.get('likeCount', 'N/A')}\n━━━━━━━━━━━━━━━━━━━━━━━\nट्रांसक्रिप्ट:\n{data.get('transcript', 'Transcript not available.')}"
            logger.info("[GEMINI-WORKER] Successfully formatted data for Gemini.")
            return formatted_text

    except Exception as e:
        error_message = f"Backend se transcript laane mein dikkat aayi: {e}"
        logger.error(error_message)
        return error_message
