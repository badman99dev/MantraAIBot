from google.generativeai.protos import Tool # <-- Hum yahan se import karenge

from .youtube_transcript import fetch_youtube_details_from_api
from .quiz_tool import send_quiz_poll

google_search_tool = Tool(
    google_search_retrieval={} # <-- Humari library mein aise likhte hain
)

AVAILABLE_TOOLS = [
    fetch_youtube_details_from_api,
    send_quiz_poll,
    google_search_tool,
]
