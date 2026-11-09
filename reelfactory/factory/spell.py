"""Optional Hindi dictionary hook. It was TESTED with the GNU Aspell Hindi word list (LibreOffice/dictionaries hi_IN) and
REJECTED: the list lacks basic words (ने, में, और, का, नहीं) and good lines scored as badly as garbage, because it
needs Hunspell affix rules to be useful. The hook stays for a future, better dictionary: while no file exists at DIC
it returns None and every caller skips the check."""

from __future__ import annotations

import re

from . import ROOT

DIC = ROOT / "tools" / "dictionaries" / "hi_IN" / "hi_IN.dic"
# names of our characters and sports loanwords that a general dictionary does not know
ALLOW = set("""सचिन सूर्या दादाजी आंटी पिंटू गोलू मीना कोच अंकल ब्रूनो कैच शॉट बल्ला बैटिंग आउट टॉस छक्का अंपायर टीम कप्तान
गेंद बॉल क्रिकेट डैश एक्स सीटी बोला पकड़ा पकड़ ली छक्का मारकर घुमा घुमाया फेंकी डाली चाय कुर्सी आँगन पतंग भौंका भौंकता
जम्हाई दौड़ा दौड़कर उछल सोते हँस हँसते हँसकर नन्हे क्लास तैयार जादूगर आँखें बंद ग़ायब क़िस्मत पूँछ शुक्रिया तालियाँ""".split())
_words: set[str] | None = None


def _load() -> set[str] | None:
    global _words
    if _words is None:
        if not DIC.exists():
            return None
        out = set()
        for i, line in enumerate(DIC.read_text(encoding="utf-8", errors="ignore").splitlines()):
            if i and line:
                out.add(line.split("/")[0].strip())
        _words = out
    return _words


def unknown_words(text: str) -> list[str] | None:
    words = _load()
    if words is None:
        return None
    toks = re.findall(r"[ऀ-ॿ]+", text)
    return [t for t in toks if t not in words and t not in ALLOW]


def unknown_ratio(text: str) -> float | None:
    toks = re.findall(r"[ऀ-ॿ]+", text)
    unk = unknown_words(text)
    if unk is None or not toks:
        return None
    return len(unk) / len(toks)
