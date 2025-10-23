from .youtube_transcript import fetch_youtube_details_from_api
from .quiz_tool import send_quiz_poll # Naya tool

AVAILABLE_TOOLS = [
    fetch_youtube_details_from_api,
    send_quiz_poll, # Naya tool
]
