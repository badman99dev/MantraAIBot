import os
import logging
from dotenv import load_dotenv
import httpx

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Gemini AI Library
import google.generativeai as genai

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']
VERCEL_API_URL = "https://gyanflow-backend-n5clvllqw-badals-projects-03fab3df.vercel.app/api/getTranscript"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- 2. SYSTEM PROMPT (Bot ki Personality) ---
SYSTEM_PROMPT_TEMPLATE = """
You are MantraAIBot 🤖. Your personality is friendly, witty, and helpful, like a knowledgeable friend.
You are talking to a user named '{user_name}'.

Your core rules:
1.  **Human-like Tone:** Always respond in a natural, conversational tone. Avoid robotic or overly formal language.
2.  **Emoji Power:** Use emojis in every response to make the conversation more engaging and lively. 😎🔥🎬💡
3.  **Use Full Context:** When you get information from the YouTube tool, you receive everything: video title, channel name, views, likes, and the transcript. Use this rich data! For example, you can say "Ah, I see this video is from the channel 'Channel Name'..." or "With over a million views, this is a popular one!".
4.  **Be Helpful:** Your main goal is to assist the user, whether it's a casual chat or summarizing a complex video.
"""

# --- 3. TOOL DEFINITION (Aapka Vercel API) ---
async def fetch_youtube_details_from_api(video_url: str) -> str:
    """
    Calls a Vercel API to get the complete YouTube video details including the transcript,
    title, channel name, views, likes, etc., all in a single formatted text block.
    """
    logger.info(f"Calling Vercel API for URL: {video_url}")
    try:
        async with httpx.AsyncClient() as client:
            params = {"youtubeUrl": video_url}
            response = await client.get(VERCEL_API_URL, params=params, timeout=45.0)
            response.raise_for_status()
            logger.info("Successfully received data from Vercel API.")
            return response.text
    except httpx.HTTPStatusError as e:
        error_message = f"Transcript API se error aaya (Status: {e.response.status_code}). Shayad video private hai ya URL galat hai."
        logger.error(error_message)
        return error_message
    except Exception as e:
        error_message = f"Transcript laane mein ek anjaan dikkat aayi: {e}"
        logger.error(error_message)
        return error_message

# --- 4. GEMINI MODEL & CHAT MANAGEMENT ---
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=[fetch_youtube_details_from_api]
)

user_chats = {}

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    """
    Har user ke liye ek unique chat session manage karta hai.
    Agar user naya hai, toh uske liye system prompt ke saath session banata hai.
    """
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_name} ({user_id}).")
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user_name)
        # Session ki shuruaat mein hi bot ko uski personality de dete hain
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am MantraAIBot, and I'm ready to chat with {user_name} in a friendly and helpful way, using emojis! 😎"}]}
        ]
        user_chats[user_id] = model.start_chat(history=initial_history)
    return user_chats[user_id]

# --- 5. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command by asking Gemini to generate a welcome message."""
    user = update.effective_user
    logger.info(f"User {user.first_name} ({user.id}) triggered /start.")
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # User ke liye chat session get ya create karna
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    
    # Gemini ko welcome message generate karne ke liye ek special instruction
    welcome_instruction = "Please greet me warmly as a new user. Introduce yourself as MantraAIBot and briefly mention what you can do (chat and summarize YouTube videos)."
    
    try:
        response = await chat_session.send_message_async(welcome_instruction)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in /start for user {user.id}: {e}")
        # Fallback static message agar Gemini fail ho jaye
        await update.message.reply_text(f"नमस्ते {user.first_name}! 😎 मैं MantraAIBot हूँ। मुझसे बात करने के लिए धन्यवाद!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all regular text messages."""
    user = update.effective_user
    message_text = update.message.text
    
    logger.info(f"Message from {user.first_name} ({user.id}): {message_text}")
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # User ke liye chat session get ya create karna
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    
    try:
        response = await chat_session.send_message_async(message_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error handling message for user {user.id}: {e}")
        await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई है। कृपया थोड़ी देर बाद फिर से कोशिश करें।")

# --- 6. MAIN BOT EXECUTION ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 MantraAIBot is up and running with a dynamic welcome!")
    app.run_polling()

if __name__ == "__main__":
    main()
