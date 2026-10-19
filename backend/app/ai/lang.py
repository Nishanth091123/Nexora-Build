"""Which language to answer in: Tamil script → Tamil, Tanglish (Tamil in English letters) → Tanglish, else English."""
from __future__ import annotations

import re

TANGLISH = set("""pannunga pannu panna pannalam pannanum sollunga sollu kudunga kudu kodunga venum vendum vendam enna
ennanu epdi eppadi evlo evvalavu enga yenna yeppadi irukku iruku irukka illa illai aagum agum aaguma aaguma
nalla romba konjam ippo ippa appo athu adhu ithu idhu intha antha veedu veetuku veetu kattanum katta kattuna
naan nan naanga neenga unga enga engaluku mudiyuma mudiyum theriyuma sari seri thaan dhaan ku kku la le
selavu salavu vilai alavu thoon kambi manal jalli sengal maadi padikattu virisal ozhugudhu eeram""".split())


def detect(text: str, default: str = "en") -> str:
    t = text or ""
    tamil = len(re.findall(r"[஀-௿]", t))
    latin = len(re.findall(r"[A-Za-z]", t))
    if tamil and tamil >= latin * 0.25:
        return "ta"
    words = re.findall(r"[a-z]+", t.lower())
    if words and sum(1 for w in words if w in TANGLISH) >= max(1, len(words) // 8):
        return "tanglish"
    return default if default in ("en", "ta", "tanglish") else "en"


def instruction(lang: str) -> str:
    return {
        "ta": "Answer in Tamil (Tamil script). Keep technical words and units in English where Tamil engineers "
              "normally do (cement, slab, column, M20, kg, m³, sq ft).",
        "tanglish": "Answer in Tanglish – Tamil words written in English letters, mixed with English technical "
                    "words, the way the user wrote (e.g. 'Ungaluku 3 bedroom plan ready, cement 320 bags varum').",
        "en": "Answer in simple English.",
    }.get(lang, "Answer in simple English.")
