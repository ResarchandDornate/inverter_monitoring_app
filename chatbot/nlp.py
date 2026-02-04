from rapidfuzz import fuzz
from .intents import INTENTS

SIMILARITY_THRESHOLD = 70  # safe value


def detect_intent(user_text: str):
    """
    Returns intent name or None
    """
    text = user_text.lower().strip()

    best_intent = None
    best_score = 0

    for intent, phrases in INTENTS.items():
        for phrase in phrases:
            score = fuzz.partial_ratio(text, phrase)
            if score > best_score:
                best_score = score
                best_intent = intent

    if best_score >= SIMILARITY_THRESHOLD:
        return best_intent

    return None
