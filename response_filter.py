import logging
from html import escape
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Hamari VIP list. Yahi tags asli format me dikhenge.
# This is the single source of truth for our filter.
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
    The ultimate intelligent sanitizer using BeautifulSoup, built exactly as requested.
    It parses the AI's HTML, finds every tag, and if a tag is not on the
    ALLOWED_TAGS list, it "neuters" it by wrapping the start and end tags
    in `<code>` blocks, effectively turning them into visible plain text
    while preserving the content inside. This is robust and future-proof.
    """
    
    # Use 'html.parser', which is built-in and handles broken HTML gracefully.
    soup = BeautifulSoup(text, 'html.parser')

    # Use find_all(True) to get a list of every single tag in the document.
    # We iterate over a copy of the list (by using list()) because we are modifying the tree in-place.
    for tag in list(soup.find_all(True)):
        
        # Check the tag's name against our VIP list.
        if tag.name not in ALLOWED_TAGS:
            logger.warning(f"Found unsupported tag <{tag.name}>. Wrapping it.")
            
            # --- The Surgery ---
            
            # Step A: Create the opening tag as visible code.
            # We recreate the opening tag as a string to preserve its attributes.
            attrs = " ".join([f'{key}="{escape(str(value))}"' for key, value in tag.attrs.items()])
            opening_tag_str = f"<{tag.name}{' ' if attrs else ''}{attrs}>"
            
            start_code_tag = soup.new_tag("code")
            start_code_tag.string = escape(opening_tag_str)

            # Step B: Create the closing tag as visible code.
            end_code_tag = soup.new_tag("code")
            end_code_tag.string = escape(f"</{tag.name}>")

            # Step C: Place these new code blocks before and after the original content.
            tag.insert_before(start_code_tag)
            tag.insert_after(end_code_tag)
            
            # Step D: Now, remove the original unsupported tag (e.g., <h3>),
            # leaving its content safely in the middle.
            tag.unwrap()

    # Convert the fully corrected soup back into a string.
    # The str() conversion is smart enough to handle this correctly.
    return str(soup)
