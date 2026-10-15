"""Deterministic local-language WhatsApp onboarding with no farm data access.

Only recognized commands enter storage; user messages are never passed to an
LLM or interpreted as permission to access a farm or update a field.
"""

from __future__ import annotations

SUPPORTED = {"1": "pa", "2": "hi", "3": "en"}
COMMANDS = {"HI", "HELLO", "MENU", "HELP", "STOP", "START", "UPDATES"}
PHRASES = {
    "pa": {
        "welcome": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! 🌾\n1 ਪੰਜਾਬੀ  2 हिंदी  3 English\nਆਪਣੀ ਭਾਸ਼ਾ ਚੁਣੋ।",
        "menu": "ਕਿਸਾਨ ਸਹਾਇਤਾ 🌾\nਖੇਤ ਦੀ ਜਾਣਕਾਰੀ ਲਈ ਸੁਰੱਖਿਅਤ ਖਾਤਾ ਜੋੜਨਾ ਅਗਲਾ ਕਦਮ ਹੈ।\nUPDATES: ਭਵਿੱਖ ਦੇ ਸੁਨੇਹਿਆਂ ਦੀ ਇਜਾਜ਼ਤ\nSTOP: ਸੁਨੇਹੇ ਬੰਦ\nMENU: ਇਹ ਸੂਚੀ",
        "optin": "ਤੁਸੀਂ ਭਵਿੱਖ ਵਿੱਚ ਖੇਤ ਦੀਆਂ ਖ਼ਬਰਾਂ ਲੈਣ ਦੀ ਇਜਾਜ਼ਤ ਦਿੱਤੀ ਹੈ। ਇਹ ਸੇਵਾ ਅਜੇ ਸ਼ੁਰੂ ਨਹੀਂ ਹੋਈ। ਬੰਦ ਕਰਨ ਲਈ STOP ਭੇਜੋ।",
        "stop": "ਭਵਿੱਖ ਦੇ ਸੁਨੇਹੇ ਬੰਦ ਹਨ। ਮਦਦ ਲਈ ਤੁਸੀਂ ਸਾਨੂੰ ਮੁੜ ਲਿਖ ਸਕਦੇ ਹੋ।",
        "unknown": "ਹਾਲੇ ਸਿਰਫ਼ ਭਾਸ਼ਾ ਅਤੇ ਸੁਨੇਹਿਆਂ ਦੀ ਪਸੰਦ ਬਦਲੀ ਜਾ ਸਕਦੀ ਹੈ। MENU ਭੇਜੋ।",
    },
    "hi": {
        "welcome": "नमस्ते! 🌾\n1 ਪੰਜਾਬੀ  2 हिंदी  3 English\nअपनी भाषा चुनें।",
        "menu": "किसान सहायता 🌾\nखेत की जानकारी दिखाने के लिए सुरक्षित खाता जोड़ना अगला चरण है।\nUPDATES: आगे आने वाले संदेशों की अनुमति\nSTOP: संदेश बंद\nMENU: यह सूची",
        "optin": "आपने भविष्य में खेत के संदेश पाने की अनुमति दी है। यह सुविधा अभी शुरू नहीं हुई है। बंद करने के लिए STOP भेजें।",
        "stop": "आगे भेजे जाने वाले संदेश बंद हैं। मदद के लिए आप फिर संदेश भेज सकते हैं।",
        "unknown": "अभी केवल भाषा और संदेशों की पसंद बदली जा सकती है। MENU भेजें।",
    },
    "en": {
        "welcome": "Hello! 🌾\n1 ਪੰਜਾਬੀ  2 हिंदी  3 English\nChoose your language.",
        "menu": "Farm assistance 🌾\nSecure account linking is coming before personal field reports.\nUPDATES: opt in to future farm notifications\nSTOP: opt out\nMENU: show this menu",
        "optin": "You opted in to future farm notifications. They are not available yet. Reply STOP to opt out anytime.",
        "stop": "Future notifications are off. You can still message us for assistance.",
        "unknown": "For now you can only change language or notification preferences. Reply MENU.",
    },
}


def normalized_command(text: str | None) -> str:
    """Return a closed-set command; never store raw farmer conversation text."""
    if not isinstance(text, str):
        return "OTHER"
    token = text.strip().upper()
    return token if token in COMMANDS or token in SUPPORTED else "OTHER"


def interpret(command: str, language: str, updates_opt_in: bool) -> tuple[str, str, bool]:
    """Return next language, subscription flag and localized safe reply."""
    if command in SUPPORTED:
        language = SUPPORTED[command]
        return language, updates_opt_in, PHRASES[language]["menu"]
    if language not in ("pa", "hi", "en"):
        if command == "STOP":
            return "und", False, PHRASES["en"]["stop"]
        return "und", updates_opt_in, PHRASES["en"]["welcome"]
    if command == "STOP":
        return language, False, PHRASES[language]["stop"]
    if command == "UPDATES":
        return language, True, PHRASES[language]["optin"]
    if command == "START":
        # START merely requests the menu; it is not implicit permission to
        # send business-initiated messages. Only explicit UPDATES opts in.
        return language, updates_opt_in, PHRASES[language]["menu"]
    if command in ("MENU", "HI", "HELLO", "HELP"):
        return language, updates_opt_in, PHRASES[language]["menu"]
    return language, updates_opt_in, PHRASES[language]["unknown"]
