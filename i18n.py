import json
import os

LANG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "languages")

# code -> discord SelectOption me dikhne wala naam
LANG_NAMES = {
    "en": "English",
    "hi": "हिन्दी / Hinglish",
    "mr": "मराठी",
    "fr": "Français",
    "id": "Bahasa Indonesia",
    "ar": "العربية",
    "zh": "中文",
    "ja": "日本語",
}

_STRINGS = {}


def load_all():
    """languages/ folder ki saari .json files load karo (startup par ek baar)."""
    for fn in os.listdir(LANG_DIR):
        if fn.endswith(".json"):
            code = fn[:-5]
            with open(os.path.join(LANG_DIR, fn), encoding="utf-8") as f:
                _STRINGS[code] = json.load(f)


def t(lang: str, key: str, **kwargs) -> str:
    """Translate: user ki language -> key -> fallback English -> key hi dikhao.

    Har message me {mention} placeholder ho sakta hai - jo call site user ka
    mention pass karti hai ({mention}) wahi text ke aage dikhega.
    """
    kwargs.setdefault("mention", "")  # bina mention wale calls format se nahi tootenge
    data = _STRINGS.get(lang) or _STRINGS.get("en") or {}
    text = data.get(key) or _STRINGS.get("en", {}).get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


load_all()
