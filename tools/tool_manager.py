# tools/tool_manager.py

# Purane import ko hatao
# from .youtube_transcript import fetch_youtube_details_from_api 
# Naya tool import karo
from .youtube_tool import youtube_tool

from .quiz_tool import manage_quiz
from .movie_tools import search_movie_in_database, get_details_and_download_links

AVAILABLE_TOOLS = [
    youtube_tool, # <-- NAYA, POWERFUL TOOL
    manage_quiz,
    search_movie_in_database,
    get_details_and_download_links,
]
