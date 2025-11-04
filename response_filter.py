import re
import logging
from html import escape

# We get the logger for this file.
logger = logging.getLogger(__name__)

# The VIP List. This is the only list of guests allowed inside.
ALLOWED_TAGS = {
    'b', 'strong',      # Bold
    'i', 'em',          # Italic
    'u', 'ins',          # Underline
    's', 'strike', 'del',# Strikethrough
    'tg-spoiler',        # Spoiler
    'a',                 # Link
    'code',              # Inline Code
    'pre'                # Code Block
}

def sanitize_html(text: str) -> str:
    """
    The ultimate sanitizer with reporting.
    It uses a fast and robust Regex to find ALL potential HTML tags.
    For each tag, it strictly checks if it's on the VIP list (ALLOWED_TAGS).
    - If YES, the tag is a VIP and is left untouched.
    - If NO, the tag is neutralized, and a WARNING log (yellow color) is generated.
    Finally, it logs the fully sanitized text for review.
    """
    
    # "Proof of Life" to ensure the new filter is running.
    logger.info("✅✅✅ SANITIZER V-FINAL+LOGS IS ALIVE! ✅✅✅")

    tag_regex = re.compile(r'(<[^>]+>)')

    def validator(match):
        potential_tag = match.group(1)
        tag_name_match = re.search(r'</?([a-zA-Z0-9-]+)', potential_tag)
        
        if tag_name_match:
            tag_name = tag_name_match.group(1).lower()
            if tag_name in ALLOWED_TAGS:
                return potential_tag

        # If the guest is not on the VIP list, KICK THEM OUT and REPORT IT.
        # We use logger.warning() which usually shows up as YELLOW in logs.
        logger.warning(f"🛡️ Neutralized unsupported tag: {potential_tag}")
        return f"<code>{escape(potential_tag)}</code>"

    # Run the bouncer on the entire text.
    sanitized_text = tag_regex.sub(validator, text)
    
    # Log the final, clean text before sending it out.
    logger.info(f"✨ Final Sanitized Text: {repr(sanitized_text)}")
    
    return sanitized_text
