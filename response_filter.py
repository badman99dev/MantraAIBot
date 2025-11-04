import re
import logging
from html import escape

logger = logging.getLogger(__name__)

# Hamare VIP Keywords. Inke aage-peeche waale < > safe hain.
# IMPORTANT: Hyphenated tags like 'tg-spoiler' must be included.
ALLOWED_KEYWORDS = [
    'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
    'tg-spoiler',  # <-- THE IMPORTANT ONE
    'a', 'code', 'pre'
]

# Step 1: Create a regex pattern that knows all our VIP keywords, INCLUDING hyphens.
# This will look like: (b|strong|i|em|...|tg-spoiler|...|/b|/strong|...)
allowed_pattern = '|'.join(ALLOWED_KEYWORDS + ['/' + k for k in ALLOWED_KEYWORDS])

# Step 2: This is the main regex to find all structures that look like tags.
# It's designed to be smart and capture two types of things.
TAG_FINDER_REGEX = re.compile(
    # Group 1: Matches and captures our perfectly formed VIP tags.
    # It now correctly handles attributes and hyphens in tag names.
    # Example: <a href="...">, <b>, </u>, <tg-spoiler>
    r'(<(' + allowed_pattern + r')(?:\s+[^>]*)?>)' +
    
    # OR
    r'|' +
    
    # Group 2: Matches and captures any stray < or > that is NOT part of a VIP tag.
    r'(<|>)',
    
    re.IGNORECASE
)


def sanitize_html(text: str) -> str:
    """
    The ultimate sanitizer, built on the "Neutralize the Criminals" philosophy.
    It finds every < and > in the text.
    It only allows them to exist if they are part of a well-formed, allowed tag
    (including hyphenated ones like <tg-spoiler>).
    All other "stray" < and > characters are neutralized by escaping them.
    This is the most direct and robust way to prevent any and all parsing errors.
    """

    def neutralizer(match):
        # The regex gives us two possible groups. We check which one matched.
        vip_tag = match.group(1)
        stray_char = match.group(2)

        # Case 1: A VIP tag was found (e.g., <b> or <tg-spoiler>). It's safe. Let it pass.
        if vip_tag:
            return vip_tag
        
        # Case 2: A stray < or > was found. It's a criminal. Neutralize it.
        elif stray_char:
            logger.warning(f"Neutralizing stray character: '{stray_char}'")
            return escape(stray_char)
        
        # This part should ideally never be reached, but it's a good fallback.
        return match.group(0)

    # Run the neutralizer on the entire text.
    return TAG_FINDER_REGEX.sub(neutralizer, text)
