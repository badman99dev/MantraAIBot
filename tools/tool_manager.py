# tools/tool_manager.py

# Apne tools folder se tool functions ko import karna
from .youtube_transcript import fetch_youtube_details_from_api
from .ui_tools import create_quiz, create_buttons

# Saare available tools ki ek dictionary.
# Key (chaabi): Tool ka naam (string). Yeh wahi naam hai jo Gemini use karega.
# Value (maan): Asli Python function.
AVAILABLE_TOOLS = {
    "fetch_youtube_details_from_api": fetch_youtube_details_from_api,
    "create_quiz": create_quiz,
    "create_buttons": create_buttons,
}
