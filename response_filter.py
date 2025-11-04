import re
import logging
from html import escape

logger = logging.getLogger(__name__)

# Hamare VIP Keywords. Inke aage-peeche waale < > safe rahenge.
ALLOWED_KEYWORDS = [
    'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
    'tg-spoiler', 'a', 'code', 'pre'
]

# Step 1: Ek "Super Regex" banate hain jo aapke rules ko follow karta hai.
# Yeh Regex do tarah ki cheezein dhoondhta hai:
#
# Part 1: (THE VIPs)
# < /? (b|strong|i|em|...|tg-spoiler|a|code|pre) ... >
# Iska matlab hai: Ek '<' jiske baad optional '/' ho, phir hamara ek VIP keyword ho,
# phir kuch bhi ho (jaise href="..."), aur aakhir mein ek '>'.
# Ye poora hissa ek group mein capture ho jayega.
#
# Part 2: (THE CRIMINALS)
# < | >
# Iska matlab hai: Ya phir, koi bhi akela '<' ya '>' dhoondho.
#
# Yeh poora Regex ek hi baar mein VIPs aur Criminals, dono ko pakad leta hai.

vip_pattern = '|'.join(ALLOWED_KEYWORDS)
# This is the master Regex that implements your philosophy.
MASTER_REGEX = re.compile(
    # Group 1: The VIPs. Captures a full, well-formed allowed tag.
    r'(</?(' + vip_pattern + r')(?:\s+[^>]*)?>)' +
    
    # OR
    r'|' +
    
    # Group 2: The Criminals. Captures any stray '<' or '>' character.
    r'(<|>)',
    
    re.IGNORECASE
)


def sanitize_html(text: str) -> str:
    """
    The final sanitizer, built on the "Neutralize the < and >" philosophy.
    It doesn't recognize "tags". It only recognizes two things:
    1. VIP structures: < followed by an allowed keyword.
    2. Criminal characters: any other < or >.
    
    It leaves the VIPs untouched and neutralizes the criminals by escaping them.
    This is the direct implementation of the user's final plan.
    """

    def neutralizer(match):
        # Hamara Regex do groups deta hai. Hum check karte hain ki kaun sa match hua.
        vip_structure = match.group(1)
        criminal_char = match.group(2)

        # Rule 1: Agar VIP structure match hua hai, to use zinda rehne do.
        if vip_structure:
            return vip_structure
        
        # Rule 2: Agar akela criminal character (< ya >) match hua hai, to use neutralize kar do.
        elif criminal_char:
            logger.warning(f"Neutralizing criminal character: '{criminal_char}'")
            return escape(criminal_char)
        
        # Fallback, jo kabhi nahi chalna chahiye.
        return match.group(0)

    # Poore text par is naye, philosophy-driven neutralizer ko chalao.
    return MASTER_REGEX.sub(neutralizer, text)
