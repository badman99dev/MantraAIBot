# FILE 1: config.py

import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai

# --- 1. SETUP ---
# .env file se saare secrets load karta hai
load_dotenv()

# --- Environment Variables ---
# Telegram Bot ka token
TOKEN = os.environ['BOT_TOKEN']

# Gemini AI ki API key
GEMINI_KEY = os.environ.get('GEMINI_KEY')
if not GEMINI_KEY:
    raise ValueError("GEMINI_KEY .env file mein nahi mili. Please add karein.")

# Kaunsa Gemini model use karna hai
MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

# --- Logging Setup ---
# Bot ke actions ko log karne ke liye setup
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Gemini AI Configuration ---
# Gemini library ko API key ke saath configure karta hai
genai.configure(api_key=GEMINI_KEY)

# --- History Management Constants ---
# Chat history mein kitne tokens rakhne hain, uski limit
MAX_HISTORY_TOKENS = 50000
TRIM_BUFFER_TOKENS = 5000
