import os
import logging
import re
import json
from dotenv import load_dotenv
import httpx
import threading
from flask import Flask
import datetime # Time ke liye
import pytz     # Timezone ke liye

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Gemini AI Library
import google.generativeai as genai
from google.generativeai.types import content_types

# --- 0. FLASK WEB SERVER SETUP ---
app_flask = Flask(__name__)
@app_flask.route('/')
def hello_world():
    return "MantraAIBot is alive and kicking!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']
VERCEL_API_URL = "https://youtube-transcript-dp2flwk98-badals-projects-03fab3df.vercel.app/api/transcript"
IST = pytz.timezone('Asia/Kolkata') # Indian Standard Time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- 2. SYSTEM PROMPT (Time Awareness ke Saath) ---
SYSTEM_PROMPT_TEMPLATE = """
You are MantraAI 🤖, a friendly, witty, and helpful AI assistant with a memory of time.
You are chatting with a user named '{user_name}'. Don't repeat the user's name repeatedly. Talk like a real friend. Don't respond robotically. Change your mood according to the user's mood. Generally, be in a funny and cool mood. 
Your core rules:
1.  **Tone:** Be conversational. Answer in the same language the user asked. For Hindi, use देवनागरी लिपि ( devnagri script) and mix some English (Hinglish) to be realistic.
2.  **Emojis:** Use emojis to be engaging.’
3.  **Context:** When you get YouTube tool info, use it! Mention the channel name, views etc.
4.  **Goal:** Be helpful.Write clear answers without using Markdown. Use spaces appropriately, as per the Telegram chat interface.
5. **spaicel font** ℱℴ𝓃𝓉 𝒞𝒽𝒶𝓃ℊℯ𝓇(Cursive),𝔽𝕠𝕟𝕥 ℂ𝕙𝕒𝕟𝕘𝕖𝕣(Double Struck),𝓕𝓸𝓷𝓽 𝓒𝓱𝓪𝓷𝓰𝓮𝓻(Bold Cursive),𝙵𝚘𝚗𝚝 𝙲𝚑𝚊𝚗𝚐𝚎𝚛(Mon space),𝗧𝗲𝘅𝘁(bold),𝑇𝑒𝑥𝑡(italic),𝙏𝙚𝙭𝙩(italic bold),𝙏𝙚𝙭𝙩(Sans-Serif Bold Italic)
5.  **primary launguage** तुम्हारा मुख्य भाषा हिंदी है और हिंदी शब्द देवनागरी में लिखना है जबकि अंग्रेजी words English में अपने जवाब में मॉडर्न हिंदी का use करना और जैसे "मैं teacher हूं 👨‍🏫" यहां teacher शब्द इंग्लिश में है जबकि बंकी हिंदी देवनागरी में है ये आजकल की बोलचाल की  हिंदी भाषा है 
information about you : You were created and trained by the MANTRA AI team so you can help people 100% free.You are being accessed from the Telegram app.
limitation and solutions:This is a Telegram app, so there is no markdown support here. To work around this, you can use Special fonts, for example →𝗧𝗲𝘅𝘁(bold),𝑇𝑒𝑥𝑡(italic),𝙏𝙚𝙭𝙩(italic bold),𝚃𝚎𝚡𝚝(Monospace),𝙏𝙚𝙭𝙩(Sans-Serif Bold Italic) And you will have to pay better attention to structuring your response to make it look neat and tidy.You can use this while writing English so that the words look beautiful even without markdown.
upcoming features:You will be able to convert many files into different formats like pdf to image, image to pdf, jpg to png, png to jpg etc. You will be able to convert files in many such formats as per your wish.Secondly, you will be able to create new things like image generation, PDF generation.third You will be able to generate quizzes which will help students to check their exam preparation.Fourthly, you will be able to view and analyze images, pdf, txt directly which will further help the user.  Fifth, you can search for information from the web using live search.

--- TIME AWARENESS RULES (VERY IMPORTANT) ---
1.  **Current Time:** You are always given the current date and time at the end of the prompt.
2.  **Message Timestamps:** The entire conversation history is formatted with timestamps `[HH:MM:SS]`.
3.  **USE THIS DATA:** You MUST use this time information to make your responses deeply personal and realistic.
    - **React to Time Gaps:** If a user replies after a long time, mention it. Example: "Hey! Kafi der baad reply kiya, sab theek hai?" or "Welcome back!"
    - **Refer to Past Days:** Mention things from "yesterday" (कल), "a few days ago", etc. Example: "कल humne jo baat ki thi..."
    - **Acknowledge Time of Day:** Notice if it's morning, night, or afternoon. Example: "इतनी रात को research? Lage raho! 🔥" or "Good morning! Aaj kya plan hai?"
    - **Create Follow-ups:** Example: "kal tumne quiz nahi kiya, koi baat nahi, aaj kar lena."

--- YOUR CORE IDENTITY & OTHER RULES ---
- My Name: MantraAI, created by the MANTRA AI team to help people for free.
- My Primary Language: Modern Hinglish (Devanagari + common English words).
- Use Special font to make the answer look beautiful or to highlight a word: 𝗧𝗲𝘅𝘁, 𝑇𝑒𝑥𝑡, 𝚃𝚎𝚡𝚝.
- I must be helpful and use context from my tools.
- I must not use Markdown.
"""

# --- 3. TOOL DEFINITION ---
def fetch_youtube_details_from_api(video_id: str) -> str:
    """
    Gets transcript and details for a YouTube video using its VIDEO ID.
    When a user provides a full YouTube URL, you MUST first extract the 11-character video ID
    (e.g., from 'https://youtu.be/lgl16xZeS3o', the ID is 'lgl16xZeS3o')
    and pass ONLY that ID to this function.
    """
    logger.info(f"[GEMINI-WORKER] Gemini extracted ID: {video_id} and is calling the tool.")
    if not video_id or len(video_id) != 11: return "Error: Invalid YouTube Video ID received."
    try:
        with httpx.Client() as client:
            api_url_with_param = f"{VERCEL_API_URL}?v={video_id}"
            response = client.get(api_url_with_param, timeout=45.0)
            response.raise_for_status()
            data = response.json()
            if not data or not data.get("success"): return "Maaf karna, backend se transcript laane mein dikkat aayi."
            formatted_text = f"""
वीडियो टाइटल: {data.get('title', 'N/A')}
चैनल: {data.get('channelTitle', 'N/A')}
सब्सक्राइबर: {data.get('channelSubscribers', 'N/A')}
व्यूज: {data.get('viewCount', 'N/A')}
लाइक्स: {data.get('likeCount', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━
ट्रांसक्रिप्ट:
{data.get('transcript', 'Transcript not available.')}
"""
            return formatted_text
    except Exception as e:
        return f"Backend se transcript laane mein dikkat aayi: {e}"

# --- 4. GEMINI MODEL & CHAT MANAGEMENT ---
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[fetch_youtube_details_from_api]
)
user_chats = {}

def format_conversation_for_gemini(history: list) -> str:
    """Conversation history ko timestamp ke saath ek formatted string banata hai."""
    formatted_lines = []
    current_date_header = None
    for entry in history:
        message_time = entry['timestamp'].astimezone(IST)
        message_date_str = message_time.strftime('%Y-%m-%d')
        if message_date_str != current_date_header:
            formatted_lines.append(f"\n--- {message_time.strftime('%A, %d %B %Y')} ---")
            current_date_header = message_date_str
        time_str = message_time.strftime('%H:%M:%S')
        role = "User" if entry['role'] == 'user' else "MantraAI"
        formatted_lines.append(f"[{time_str}] {role}: {entry['content']}")
    return "\n".join(formatted_lines)

# --- 5. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Start ko bhi normal message ki tarah handle karna
    await handle_message(update, context, is_start_command=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, is_start_command: bool = False):
    user = update.effective_user
    message_timestamp = update.message.date if update.message else datetime.datetime.now(pytz.utc)

    if is_start_command:
        message_text = "User has just started the conversation. Greet them warmly and introduce yourself."
    else:
        message_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    if user.id not in user_chats:
        user_chats[user.id] = []
    
    user_chats[user.id].append({'role': 'user', 'timestamp': message_timestamp, 'content': message_text})

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user.first_name)
    history_string = format_conversation_for_gemini(user_chats[user.id])
    current_time_ist = datetime.datetime.now(IST)
    current_time_string = f"\n--- Current Time: {current_time_ist.strftime('%A, %d %B %Y - %H:%M:%S IST')} ---"
    
    # Hum har baar poora context bhej rahe hain, isliye `start_chat` use nahi kar rahe
    full_prompt = [
        system_prompt,
        "--- CONVERSATION HISTORY ---",
        history_string,
        current_time_string,
        "MantraAI's turn to speak:"
    ]

    try:
        response = await model.generate_content_async(full_prompt, tools=[fetch_youtube_details_from_api])
        
        # Manual Function Calling Loop
        if response.candidates[0].content.parts[0].function_call:
            fc = response.candidates[0].content.parts[0].function_call
            tool_name = fc.name
            
            logger.info(f"Executing tool '{tool_name}' manually.")
            if tool_name == 'fetch_youtube_details_from_api':
                tool_args = {key: value for key, value in fc.args.items()}
                tool_result = fetch_youtube_details_from_api(**tool_args)
                
                # Tool ka result wapas Gemini ko bhejna
                response = await model.generate_content_async(
                    full_prompt + [
                        content_types.to_part(response.candidates[0].content), # Pehla function call
                        content_types.to_part( # Doosra function response
                            dict(function_response=dict(name=tool_name, response=dict(content=tool_result)))
                        )
                    ],
                    tools=[fetch_youtube_details_from_api]
                )
        
        bot_reply_text = response.text
        bot_reply_timestamp = datetime.datetime.now(pytz.utc)
        user_chats[user.id].append({'role': 'model', 'timestamp': bot_reply_timestamp, 'content': bot_reply_text})

        await update.message.reply_text(bot_reply_text)
        
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई ਹੈ।")

# --- 6. MAIN BOT EXECUTION ---
def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🚀 Telegram Bot is starting polling...")
    app.run_polling()

if __name__ == "__main__":
    logger.info("🚀 Starting Flask server in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Bot in the main thread...")
    run_bot()
