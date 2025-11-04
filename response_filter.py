import re
import logging

logger = logging.getLogger(__name__)

# ==========================================================
# ===> OUR VIP GUEST LIST (The Only Allowed HTML Tags) <===
# ==========================================================
# Note: Using a set for faster lookups
ALLOWED_TAGS = {
    'b', 'strong',  # Bold
    'i', 'em',      # Italic
    'u', 'ins',      # Underline
    's', 'strike', 'del',  # Strikethrough
    'tg-spoiler',    # Spoiler
    'a',             # Link
    'code',          # Inline Code
    'pre'            # Code Block
}

def sanitize_html(text: str) -> str:
    """
    Cleans the AI's response by removing any HTML tags that are not in our ALLOWED_TAGS list.
    This acts as a safety net to prevent Telegram API errors from unsupported tags.
    """
    
    # This regex finds all HTML tags (e.g., <p>, <blockquote>, </a>, <br/>)
    # and captures the tag name (e.g., "p", "blockquote", "a", "br") in a group.
    tag_regex = re.compile(r'</?([a-zA-Z0-9]+).*?>')

    def tag_replacer(match):
        """
        This function is called for every tag found by the regex.
        It decides whether to keep the tag or remove it.
        """
        # Get the tag name (e.g., 'p' from '<p>') and convert to lowercase
        tag_name = match.group(1).lower()
        
        if tag_name in ALLOWED_TAGS:
            # If the tag is on our VIP list, keep it as it is.
            return match.group(0)
        else:
            # If the tag is not allowed, remove it by returning an empty string.
            logger.warning(f"Sanitizer removed unsupported tag: {match.group(0)}")
            return ""

    # Use re.sub with our custom replacer function to clean the text
    sanitized_text = tag_regex.sub(tag_replacer, text)
    
    return sanitized_text
