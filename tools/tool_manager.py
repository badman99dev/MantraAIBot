# tools/tool_manager.py

from .youtube_transcript import fetch_youtube_details_from_api
from .quiz_tool import send_quiz_poll
from .movie_tools import search_movie_in_database, get_details_and_download_links

AVAILABLE_TOOLS = [
    fetch_youtube_details_from_api,
    send_quiz_poll,
    search_movie_in_database,
    get_details_and_download_links,
]
