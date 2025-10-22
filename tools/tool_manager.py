# Apne tools folder se tool functions ko import karna
from .youtube_transcript import fetch_youtube_details_from_api

# Agar aap kal koi naya tool banate hain (jaise quiz_tool.py),
# toh use yahan import karein:
# from .quiz_tool import create_quiz

# Yeh woh list hai jise humara bot istemaal karega.
# Yahan par saare available tools ke function daal dein.
AVAILABLE_TOOLS = [
    fetch_youtube_details_from_api,
    # create_quiz, # Jab aap naya tool banayenge
]
