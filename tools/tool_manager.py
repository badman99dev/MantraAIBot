# File: tools/tool_manager.py

# ... (baki ke imports waise hi rahenge) ...
from .youtube_tool import youtube_tool
from .quiz_tool import manage_quiz
from .movie_tools import search_movie_in_database, get_details_and_download_links
from .web_search_tool import web_search # <<<--- YEH NAYI LINE ADD KAREIN

AVAILABLE_TOOLS = [
    web_search, # <<<--- YEH NAYA TOOL LIST MEIN ADD KAREIN
    youtube_tool,
    manage_quiz,
    search_movie_in_database,
    get_details_and_download_links,
]
