# Apne tools folder se tool functions ko import karna
from .youtube_transcript import fetch_youtube_details_from_api
from .quiz_tool import create_quiz_data

# Yeh list ab code mein direct use nahi ho rahi hai,
# lekin yeh ek central registry ki tarah kaam karti hai
# jisse pata chalta hai ki kaunse tools available hain.
# Hum iska istemaal Gemini ko tools ke baare mein batane ke liye karte hain.
ALL_TOOLS = [
    fetch_youtube_details_from_api,
    create_quiz_data,
]
