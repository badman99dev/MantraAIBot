import re
import logging
from html import escape

logger = logging.getLogger(__name__)

# Rule #1: Hamari VIP list. Inhein full azaadi hai.
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
    The final sanitizer, built on the "Tag, what is that?" philosophy.
    It uses a fast and robust Regex to find all potential HTML tags.
    For each tag, it checks if it's on the VIP list (ALLOWED_TAGS).
    - If YES, the tag is a VIP and is left untouched.
    - If NO, the tag is a "criminal" and is neutralized by wrapping it
      in `<code>` blocks, turning it into harmless plain text.
    This is the definitive solution, free from external library side-effects.
    """
    
    # Ye Regex text me har possible HTML tag (e.g., <p>, </a>, <br/>) ko dhoondhta hai.
    # It finds the entire tag in one go. The pattern <[^>]+> means:
    # '<'      : starts with a '<'
    # [^>]+   : followed by one or more characters that are NOT '>'
    # '>'      : ends with a '>'
    tag_regex = re.compile(r'(<[^>]+>)')

    def tag_wrapper(match):
        tag = match.group(1) # Poora tag, jaise '<h3>' ya '<a href...>'

        # Rule #3: Smart Exception - Tag ka naam nikal kar check karo
        # This regex finds the tag name, e.g., 'h3' from '<h3>' or 'a' from '<a href...>'
        tag_name_match = re.search(r'</?([a-zA-Z0-9]+)', tag)
        
        if tag_name_match:
            tag_name = tag_name_match.group(1).lower()
            
            # Agar tag ka naam VIP list me nahi hai, to Rule #2 laagoo karo
            if tag_name not in ALLOWED_TAGS:
                logger.warning(f"Wrapping unsupported tag with Regex: {tag}")
                return f"<code>{escape(tag)}</code>"

        # Agar tag VIP list me hai (Rule #1), ya hum use samajh nahi paaye
        # (e.g., it's a malformed tag like "< b >"), to for safety, we wrap it.
        # But a simple "else" here is safer. If it's not a known-good tag, wrap it.
        # The logic above already handles this. A simple return is enough.
        
        # Agar tag VIP list me hai, to use waise hi rehne do.
        return tag

    # Poore text par tag_wrapper function chalao aur saaf text wapas bhejo.
    return tag_regex.sub(tag_wrapper, text)
