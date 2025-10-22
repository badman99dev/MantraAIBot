# tools/tool_manager.py
from .youtube_transcript import fetch_youtube_details_from_api
from .ui_tools import create_quiz, create_buttons # Naye tools import karna

# Saare available tools ki dictionary
AVAILABLE_TOOLS = {
    "fetch_youtube_details_from_api": fetch_youtube_details_from_api,
    "create_quiz": create_quiz,
    "create_buttons": create_buttons,
}
