# Apne tools folder se tool functions ko import karna
from .youtube_transcript import fetch_youtube_details_from_api
from .quiz_tool import create_quiz # Naya tool import karna

# Yeh woh list hai jise humara bot istemaal karega.
# Yahan par saare available tools ke function daal dein.
AVAILABLE_TOOLS = [
    fetch_youtube_details_from_api,
    create_quiz, # Naye tool ko list mein jodna
]
