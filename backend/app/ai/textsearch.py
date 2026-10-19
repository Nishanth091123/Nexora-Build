"""Small keyword search (BM25) that understands English, Tamil and common Tanglish construction words."""
from __future__ import annotations

import math
import re

STOP = set("""a an the is are was were be been of to in on for and or with by at from as it this that these those
what which how why when where who whom do does did can could should would will shall may might my our your their
me we you i he she they them his her its into about than then so if not no yes please tell give show need want
pannunga panna sollunga kudunga venum enna epdi eppadi evlo evvalavu la ku ah aa oru intha antha
ft feet sq sqft mm cm m nos no many much need use used using like get""".split())

# Tanglish / Tamil word → English search terms
SYN = {
    "kambi": "steel bar tmt", "கம்பி": "steel bar tmt", "siment": "cement", "சிமெண்ட்": "cement",
    "manal": "sand", "மணல்": "sand", "jalli": "aggregate", "ஜல்லி": "aggregate", "sengal": "brick",
    "செங்கல்": "brick", "thoon": "column", "thoonu": "column", "தூண்": "column", "pillar": "column",
    "virisal": "crack", "விரிசல்": "crack", "keeral": "crack", "eeram": "damp dampness", "ஈரம்": "damp dampness",
    "ozhugal": "leak leakage", "ozhugudhu": "leak leakage", "ஒழுகுது": "leak leakage", "ஒழுகல்": "leak leakage",
    "padikattu": "staircase stair", "படிக்கட்டு": "staircase stair", "maadi": "slab roof terrace",
    "மாடி": "slab roof terrace", "thalam": "floor", "தளம்": "floor", "poochu": "plaster", "பூச்சு": "plaster",
    "karaiyan": "termite", "கரையான்": "termite", "mazhai": "rain", "மழை": "rain", "kalavai": "mix ratio",
    "கலவை": "mix ratio", "kuzhai": "pipe", "குழாய்": "pipe", "vayar": "wire", "வயர்": "wire",
    "salavu": "cost", "selavu": "cost", "செலவு": "cost", "vilai": "rate price", "விலை": "rate price",
    "alavu": "size", "அளவு": "size", "vaasthu": "vastu", "vasthu": "vastu", "வாஸ்து": "vastu",
    "curing": "curing", "க்யூரிங்": "curing", "centring": "formwork centring", "shuttering": "formwork",
    "tiles": "tile", "டைல்ஸ்": "tile", "paint": "paint", "பெயிண்ட்": "paint", "cube": "cube test",
    "beam": "beam", "பீம்": "beam", "slab": "slab", "ஸ்லாப்": "slab", "footing": "footing foundation",
    "adithalam": "foundation", "அடித்தளம்": "foundation",
    "வெடிப்பு": "crack", "vedippu": "crack", "கீறல்": "crack", "கான்கிரீட்": "concrete", "காங்கிரீட்": "concrete",
    "காங்கரட்": "concrete", "கான்க்ரீட்": "concrete", "kankrit": "concrete", "concrit": "concrete",
    "சுவர்": "wall", "suvar": "wall", "தூண்கள்": "column", "நீர்க்கசிவு": "leak leakage damp", "கசிவு": "leak leakage",
    "தண்ணீர்": "water", "தொட்டி": "tank sump", "பெயிண்டிங்": "paint", "டைல்": "tile", "கம்பிகள்": "steel bar", "settu": "setback", "setback": "setback",
}

_word = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?|[஀-௿]+", re.I)


def tokens(text: str) -> list[str]:
    out = []
    for w in _word.findall((text or "").lower()):
        if w in STOP or (len(w) < 2 and not w.isdigit()) or (w.isdigit() and len(w) < 3):
            continue
        if w in SYN:
            out.extend(SYN[w].split())
        elif not w.isascii() and len(w) > 3:  # Tamil words carry suffixes: காங்கரட்டில் → காங்கரட்
            for k, v in SYN.items():
                if not k.isascii() and len(k) >= 3 and w.startswith(k):
                    out.extend(v.split())
                    break
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss") and w.isascii():
            w = w[:-1]
        out.append(w)
    return out


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.4, b: float = 0.7):
        self.toks = [tokens(d) for d in docs]
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.avg = (sum(len(t) for t in self.toks) / self.n) if self.n else 0
        df: dict[str, int] = {}
        for t in self.toks:
            for w in set(t):
                df[w] = df.get(w, 0) + 1
        self.idf = {w: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.tf = []
        for t in self.toks:
            d: dict[str, int] = {}
            for w in t:
                d[w] = d.get(w, 0) + 1
            self.tf.append(d)

    def scores(self, query: str) -> list[float]:
        q = list(dict.fromkeys(tokens(query)))
        out = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            dl = len(self.toks[i]) or 1
            for w in q:
                f = tf.get(w)
                if not f:
                    continue
                s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1)))
            out.append(s)
        return out

    def top(self, query: str, k: int = 5, min_score: float = 0.5) -> list[tuple[int, float]]:
        sc = self.scores(query)
        order = sorted(range(len(sc)), key=lambda i: -sc[i])
        return [(i, sc[i]) for i in order[:k] if sc[i] >= min_score]
