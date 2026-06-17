"""AI Tutor Guardrails — local validation and system prompt configuration."""

import re
from typing import Optional

BLOCKED_RESPONSE = (
    "I am TheFinTrade AI Tutor and can only assist with topics covered in "
    "your enrolled courses and trading education content."
)

SYSTEM_PROMPT = (
    "You are TheFinTrade AI Tutor, a highly specialized assistant for financial markets and trading education.\n\n"
    "Your operational boundaries are strictly limited to:\n"
    "1. Stock Market, Financial Markets, Futures & Options, Technical Analysis, Price Action, Risk Management, Trading Psychology.\n"
    "2. TheFinTrade course content, lessons, quizzes, assignments, and learning materials available in the LMS.\n\n"
    "You MUST adhere to these guidelines:\n"
    "- ONLY answer questions within the allowed topics. If a question is outside these boundaries (e.g., politics, religion, sports, movies, coding/programming, medical/legal/personal advice), you MUST refuse to answer and reply EXACTLY with:\n"
    f"  \"{BLOCKED_RESPONSE}\"\n"
    "- NEVER provide buy or sell signals, guaranteed profit strategies, financial advice, investment recommendations, or portfolio management advice.\n"
    "- For trading-related questions, provide educational explanations only.\n"
    "- ALWAYS include a standard risk disclaimer: \"Disclaimer: Trading and investing in financial markets involve significant risk of loss. All content is for educational purposes only.\"\n"
)

# Allowed keywords/patterns (matched with word boundaries)
ALLOWED_KEYWORDS = [
    # Markets & Trading
    "stock", "share", "trade", "trading", "market", "finance", "option", "future", "derivative", 
    "equity", "commodity", "forex", "crypto", "nifty", "sensex", "banknifty", "bull", "bear",
    "chart", "price", "action", "volume", "indicator", "rsi", "macd", "moving average", "fibonacci",
    "candlestick", "pattern", "support", "resistance", "trend", "risk", "leverage", "margin",
    "portfolio", "psychology", "discipline", "loss", "profit", "broker", "exchange", "nse", "bse",
    "sebi", "demat", "dividend", "ipo", "mutual fund", "bond", "interest", "f&o", "call", "put",
    "strike", "expiry", "premium", "hedging", "fintrade", "thefintrade", "order", "position",
    "stop-loss", "stop loss", "drawdown", "liquidity", "valuation", "dcf", "balance sheet", 
    "financial statement", "p/e", "ratio", "reversal", "breakout", "consolidation", "index", 
    "asset", "capital", "fund", "invest", "investment", "advisor", "adviser", "analyst", "simulat",
    "technical", "analysis", "educat",
    # LMS & Course
    "lms", "course", "lesson", "quiz", "assignment", "exam", "syllabus", "enrolled", "learn", 
    "study", "class", "lecture", "tutor", "notes", "material", "test", "question", "curriculum",
    "module", "enroll", "instruction", "video", "pdf"
]

# Blocked keywords/patterns (matched with word boundaries)
BLOCKED_KEYWORDS = [
    # Programming / Coding
    "code", "coding", "python", "javascript", "html", "css", "programming", "database", "sql", 
    "java", "c++", "c#", "rust", "php", "typescript", "software", "developer", "git", "github", 
    "compile", "api key", "regex", "array", "variable", "function", "class method", "loop",
    # Politics
    "politic", "election", "government", "president", "minister", "senate", "parliament", "congress",
    "democrat", "republican", "trump", "modi", "biden", "obama", "bjp", "politician",
    # Religion
    "relig", "god", "jesus", "allah", "krishna", "hindu", "muslim", "islam", "christian", "church", 
    "temple", "mosque", "bible", "quran", "gita", "deity", "worship", "faith", "spiritual",
    # Sports
    "sport", "cricket", "football", "soccer", "tennis", "basketball", "baseball", "olympic", 
    "kohli", "dhoni", "messi", "ronaldo", "match", "score", "wicket", "stadium", "tournament",
    # Movies / Entertainment
    "movie", "film", "cinema", "actor", "actress", "hollywood", "bollywood", "director", "celebrity", 
    "song", "music", "concert", "singer", "netflix", "drama", "episode", "season", "tv show",
    # Medical
    "medical", "doctor", "medicine", "health", "symptom", "disease", "cure", "sick", "hospital", 
    "prescription", "vaccine", "drug", "illness", "covid", "diagnos",
    # Legal
    "legal advice", "lawyer", "attorney", "lawsuit", "court", "sue", "litigat", "prosecut", "law",
    # Personal
    "relationship", "marry", "divorce", "dating", "friendship", "recipe", "cook", "food",
    # General Knowledge / Geography / History / Trivia
    "capital of", "what is the capital", "geography", "history", "science", "weather in", "how far", "population of"
]

# Capability inquiries and greetings
GREETINGS_OR_HELP = [
    "hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", 
    "who are you", "what can you do", "help me", "how to use", "how can you help", 
    "what is your name", "who is the tutor", "what is this tool"
]


def is_question_allowed_locally(question: str) -> bool:
    """Perform server-side local validation on the question to detect if it's within guardrails.
    Returns True if allowed, False if blocked.
    """
    if not question:
        return False

    q_clean = question.strip().lower()

    # 1. Check for blocked topics / keywords first (using strict word boundaries)
    for blocked in BLOCKED_KEYWORDS:
        escaped_blocked = re.escape(blocked)
        # Match as word root/prefix within word boundaries to catch plural/variant forms
        pattern = rf"\b{escaped_blocked}\w*\b"
        # Special case for phrases like "capital of" or "what is the capital" which can skip boundaries check
        if " " in blocked:
            if blocked in q_clean:
                return False
        elif re.search(pattern, q_clean):
            return False

    # 2. Allow standard greetings and capability questions (using strict word boundaries)
    for greet in GREETINGS_OR_HELP:
        escaped_greet = re.escape(greet)
        if q_clean == greet or re.search(rf"\b{escaped_greet}\b", q_clean):
            return True

    # 3. Check for allowed topics / keywords (using strict word boundaries)
    for allowed in ALLOWED_KEYWORDS:
        escaped_allowed = re.escape(allowed)
        # Match prefix/root within word boundaries, e.g., \btrade\w*\b matches "trading"
        pattern = rf"\b{escaped_allowed}\w*\b"
        if re.search(pattern, q_clean):
            return True

    # Default to False if no allowed keywords match
    return False
