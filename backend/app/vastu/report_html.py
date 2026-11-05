"""1.16 – printable Vastu report (HTML) in Tamil or English. The browser shapes Tamil letters correctly, so the
person prints it / saves it as PDF. Same content as the PDF: title, score + floor-wise scores, 8-direction overview,
every floor with the 16-zone mandala, main door pada, room-wise cards (current → better → why → remedy), site
checks, recommendations and before / after (best option)."""
from __future__ import annotations

import html as H

from ..design.exports import FILL
from . import more as M
from .engine import ZONE_NAME

T = {
    "en": {"title": "Vastu Report", "score": "Vastu score", "floors": "Floor-wise score", "overview": "Direction overview",
           "plan": "Plan with 16 Vastu zones", "door": "Main door – 32 pada check", "rooms": "Room-wise guidance",
           "current": "Now", "better": "Better", "why": "Why", "remedy": "Simple remedy", "site": "Site & fixtures",
           "reco": "Recommendations", "tips": "General tips", "before": "Before", "after": "After (suggested option)",
           "ba": "Before / after", "client": "Client", "project": "Project", "facing": "Facing", "date": "Date",
           "design": "Design", "ask": "Details still needed (answer them in the Vastu page)", "rules": "rules matched",
           "status": {"matched": "Matched", "partly": "Partly", "not_matched": "Needs attention"},
           "ov": {"Excellent": "Excellent", "Good": "Good", "Needs Attention": "Needs attention"}, "print": "Print / Save as PDF",
           "note16": "Orange lines: 16 zones (22.5° each) from the building centre; yellow square: Brahmasthan (centre)."},
    "ta": {"title": "வாஸ்து அறிக்கை", "score": "வாஸ்து மதிப்பெண்", "floors": "தளம் வாரியான மதிப்பெண்", "overview": "திசை கண்ணோட்டம்",
           "plan": "16 வாஸ்து பகுதிகளுடன் வரைபடம்", "door": "முதன்மை வாசல் – 32 பதம் சோதனை", "rooms": "அறை வாரியான வழிகாட்டல்",
           "current": "இப்போது", "better": "சிறந்தது", "why": "ஏன்", "remedy": "எளிய பரிகாரம்", "site": "மனை & பொருத்தங்கள்",
           "reco": "பரிந்துரைகள்", "tips": "பொது குறிப்புகள்", "before": "முன்", "after": "பின் (பரிந்துரை)",
           "ba": "முன் / பின்", "client": "வாடிக்கையாளர்", "project": "திட்டம்", "facing": "முகப்பு", "date": "தேதி",
           "design": "வடிவமைப்பு", "ask": "இன்னும் தேவையான விவரங்கள் (வாஸ்து பக்கத்தில் பதிலளிக்கவும்)", "rules": "விதிகள் பொருந்துகின்றன",
           "status": {"matched": "பொருந்துகிறது", "partly": "பகுதியாக", "not_matched": "கவனம் தேவை"},
           "ov": {"Excellent": "மிகச் சிறப்பு", "Good": "நல்லது", "Needs Attention": "கவனம் தேவை"}, "print": "அச்சிடு / PDF ஆக சேமி",
           "note16": "ஆரஞ்சு கோடுகள்: மையத்திலிருந்து 16 பகுதிகள் (ஒவ்வொன்றும் 22.5°); மஞ்சள் சதுரம்: பிரம்மஸ்தானம்."},
}
COL = {"matched": "#16a34a", "partly": "#d97706", "not_matched": "#dc2626"}
OVCOL = {"Excellent": "#dcfce7", "Good": "#dbeafe", "Needs Attention": "#fef3c7"}


def e(x) -> str:
    return H.escape(str(x if x is not None else ""))


def svg_plan(plan: dict, level: int, result: dict | None, size: int = 520, mandala: bool = True, lang: str = "en") -> str:
    b = plan["building"]
    bw, bd = float(b["w"]), float(b["d"])
    k = (size - 60) / max(bw, bd)
    W, Hh = bw * k + 60, bd * k + 60
    ox, oy = 30, 30
    X = lambda x: ox + x * k
    Y = lambda y: oy + (bd - y) * k  # plan y away from the road → up
    lv = plan["levels"][level]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {Hh:.0f}" width="{W:.0f}" height="{Hh:.0f}" '
           f'font-family="Arial, Noto Sans Tamil, Latha, Nirmala UI, sans-serif">']
    status = {}
    for c in (result or {}).get("checks", []):
        if c.get("room_id") and c.get("level") == level and c["rule"] not in ("entrance", "door_pada"):
            status[c["room_id"]] = c["status"]
    for r in lv["rooms"]:
        st = status.get(r["id"])
        out.append(f'<rect x="{X(r["x"]):.1f}" y="{Y(r["y"] + r["d"]):.1f}" width="{r["w"] * k:.1f}" height="{r["d"] * k:.1f}" '
                   f'fill="{FILL.get(r["type"], "#ffffff")}" stroke="{COL.get(st, "#334155")}" stroke-width="{2.2 if st else 1}"/>')
        out.append(f'<text x="{X(r["x"] + r["w"] / 2):.1f}" y="{Y(r["y"] + r["d"] / 2) + 4:.1f}" font-size="10" font-weight="700" '
                   f'text-anchor="middle" fill="#0f172a">{e(r["name"][:18])}</text>')
    if mandala:
        cx, cy = X(bw / 2), Y(bd / 2)
        out.append(f'<rect x="{X(bw / 3):.1f}" y="{Y(2 * bd / 3):.1f}" width="{bw / 3 * k:.1f}" height="{bd / 3 * k:.1f}" '
                   f'fill="#fde68a" fill-opacity="0.35" stroke="#f59e0b" stroke-dasharray="4 3"/>')
        rays = (result or {}).get("mandala") or M.mandala_lines(plan)
        names = M.ZONE16_TA if lang == "ta" else None
        for i, rr in enumerate(rays):
            ex, ey = X(bw / 2 + rr["dx"] * bw / 2), Y(bd / 2 + rr["dy"] * bd / 2)
            out.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#f97316" stroke-width="1" stroke-dasharray="5 3"/>')
            nxt = rays[(i + 1) % 16]
            mx, my = (rr["dx"] + nxt["dx"]) / 2, (rr["dy"] + nxt["dy"]) / 2
            m = max(abs(mx), abs(my)) or 1
            lx, ly = X(bw / 2 + mx / m * bw / 2 * 0.82), Y(bd / 2 + my / m * bd / 2 * 0.82)
            z = M.ZONES16[(M.ZONES16.index(rr["after"]) + 1) % 16]
            out.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="10" font-weight="800" text-anchor="middle" fill="#c2410c">'
                       f'{e(z)}</text>')
    # main door + pada marks
    door = (result or {}).get("door")
    for o in lv.get("openings", []):
        if o["type"] == "main_door":
            out.append(f'<line x1="{X(o["x1"]):.1f}" y1="{Y(o["y1"]):.1f}" x2="{X(o["x2"]):.1f}" y2="{Y(o["y2"]):.1f}" '
                       f'stroke="{COL.get(door["status"], "#2563eb") if door else "#2563eb"}" stroke-width="6"/>')
            if door:
                out.append(f'<text x="{X((o["x1"] + o["x2"]) / 2):.1f}" y="{Y((o["y1"] + o["y2"]) / 2) - 8:.1f}" font-size="11" '
                           f'font-weight="800" text-anchor="middle" fill="#1d4ed8">{e(door["code"])}</text>')
    # north arrow
    up, right = plan["compass"]["up"], plan["compass"]["right"]
    nx, ny = right[1], up[1]
    ax, ay = W - 22, 22
    out.append(f'<line x1="{ax - nx * 12:.1f}" y1="{ay + ny * 12:.1f}" x2="{ax + nx * 12:.1f}" y2="{ay - ny * 12:.1f}" stroke="#0f172a" stroke-width="2"/>'
               f'<circle cx="{ax + nx * 12:.1f}" cy="{ay - ny * 12:.1f}" r="3.5" fill="#dc2626"/>'
               f'<text x="{ax + nx * 20:.1f}" y="{ay - ny * 20 + 4:.1f}" font-size="12" font-weight="800" text-anchor="middle" fill="#dc2626">N</text>')
    out.append("</svg>")
    return "".join(out)


def html(plan: dict, res: dict, project: dict, meta: dict, best: dict | None, lang: str = "en") -> str:
    t = T["ta" if lang == "ta" else "en"]
    zname = (lambda z: M.ZONE_TA.get(z, z) if lang == "ta" else ZONE_NAME.get(z, z))
    s = res["summary"]
    parts = [f"""<!doctype html><html lang="{'ta' if lang == 'ta' else 'en'}"><head><meta charset="utf-8">
<title>{e(meta.get('code', ''))} {e(t['title'])}</title>
<style>
body{{font-family:Arial,'Noto Sans Tamil','Latha','Nirmala UI',sans-serif;color:#0f172a;margin:24px;font-size:13px}}
h1{{color:#0f2350;margin:0 0 4px}} h2{{color:#0f2350;border-bottom:2px solid #e2e8f0;padding-bottom:4px;margin-top:22px}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #cbd5e1;padding:5px 7px;vertical-align:top;text-align:left}}
th{{background:#eef2ff}} .muted{{color:#64748b}} .pill{{display:inline-block;border-radius:999px;padding:2px 10px;font-weight:700}}
.grid8{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;max-width:520px}} .cell{{border-radius:10px;padding:8px;border:1px solid #e2e8f0}}
.cards{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}} .card{{border:1px solid #e2e8f0;border-radius:10px;padding:8px}}
.ba{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} .page{{page-break-before:always}}
@media print{{.noprint{{display:none}} body{{margin:10mm}}}}
</style></head><body>
<button class="noprint" onclick="print()" style="float:right;padding:8px 14px">{e(t['print'])}</button>
<h1>{e(t['title'])} – {e(project.get('name', ''))}</h1>
<div class="muted">{e(t['project'])}: {e(meta.get('code', ''))} · {e(t['client'])}: {e(meta.get('client') or '—')} ·
{e(t['design'])} v{e(meta.get('version', ''))} · {e(t['facing'])}: {e(str(plan.get('facing') or '').replace('-', ' ').title())} ·
N {e(res.get('north_deg', 0))}° · {e(t['date'])}: {e(meta.get('date', ''))}</div>
<h2>{e(t['score'])}: {res.get('score', 0)} / 100</h2>
<p><b>{s['matched']} / {s['total']}</b> {e(t['rules'])} · {e(s['label'])}</p>
<table><tr><th>{e(t['floors'])}</th><th>Score</th><th>✔</th><th>~</th><th>✖</th></tr>"""]
    for f in res.get("floors", []):
        parts.append(f"<tr><td>{e(f['name'])}</td><td><b>{f['score']}</b></td><td>{f['matched']}</td><td>{f['partly']}</td><td>{f['not_matched']}</td></tr>")
    parts.append(f"</table><h2>{e(t['overview'])}</h2><div class='grid8'>")
    ov = res.get("overview8") or {}
    for z in ["NW", "N", "NE", "W", "", "E", "SW", "S", "SE"]:
        if not z:
            parts.append("<div class='cell' style='text-align:center;font-size:28px'>🧭</div>")
            continue
        o = ov.get(z, {"status": "Good", "items": []})
        parts.append(f"<div class='cell' style='background:{OVCOL.get(o['status'], '#fff')}'><b>{e(zname(z))}</b><br>"
                     f"<span class='pill'>{e(t['ov'].get(o['status'], o['status']))}</span><div class='muted' style='font-size:11px'>"
                     f"{e(', '.join(o.get('items', [])[:3]))}</div></div>")
    parts.append("</div>")
    door = res.get("door")
    if door:
        parts.append(f"<h2>{e(t['door'])}</h2><p><span class='pill' style='background:{COL[door['status']]};color:#fff'>"
                     f"{e(door['code'])} {e(door['name'])}</span> – {e(door['advice'])}</p>"
                     f"<p class='muted'>{e(door['side_name'])}: {door['side_ft']} ft · 8 × {door['pada_ft']} ft · "
                     f"{e(', '.join(door['padas'][door['side']]))}</p>")
    for li, lv in enumerate(plan["levels"]):
        parts.append(f"<h2 class='{'page' if li else ''}'>{e(t['plan'])} – {e(lv['name'])}</h2>{svg_plan(plan, li, res, 560, True, lang)}"
                     f"<p class='muted'>{e(t['note16'])}</p>")
    parts.append(f"<h2 class='page'>{e(t['rooms'])}</h2><div class='cards'>")
    for c in res["checks"]:
        if c.get("level") == -1:
            continue
        parts.append(f"<div class='card' style='border-left:5px solid {COL[c['status']]}'><b>{e(c['title'])}</b> "
                     f"<span class='muted'>{e(c['room'])} · {e(c.get('level_name', ''))}</span><br>"
                     f"<span style='color:{COL[c['status']]};font-weight:700'>{e(t['status'][c['status']])}</span> – {e(c['message'])}"
                     + (f"<br><b>{e(t['current'])}:</b> {e(c.get('current', ''))} → <b>{e(t['better'])}:</b> {e(c['better'])}" if c.get("better") else "")
                     + f"<br><b>{e(t['why'])}:</b> {e(c['why'])}"
                     + (f"<br><b>{e(t['remedy'])}:</b> {e(c['remedy'])}" if c.get("remedy") else "") + "</div>")
    parts.append("</div>")
    site = [c for c in res["checks"] if c.get("level") == -1]
    if site or res.get("questions"):
        parts.append(f"<h2>{e(t['site'])}</h2><table>")
        for c in site:
            parts.append(f"<tr><td>{e(c['title'])}</td><td style='color:{COL[c['status']]};font-weight:700'>{e(t['status'][c['status']])}</td>"
                         f"<td>{e(c['message'])}{('<br><span class=muted>' + e(c['remedy']) + '</span>') if c.get('remedy') and c['status'] != 'matched' else ''}</td></tr>")
        parts.append("</table>")
        if res.get("questions"):
            parts.append(f"<p><b>{e(t['ask'])}:</b> " + "; ".join(e(q["question"]) for q in res["questions"]) + "</p>")
    if res.get("suggestions"):
        parts.append(f"<h2>{e(t['reco'])}</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in res["suggestions"]) + "</ul>")
    parts.append(f"<h2>{e(t['tips'])}</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in res.get("tips", [])) + "</ul>")
    if best:
        parts.append(f"<h2 class='page'>{e(t['ba'])} ({res.get('score', 0)} → {best['score']})</h2><p>{e(best['label'])}: "
                     f"{e('; '.join(best.get('changes', [])))}</p><div class='ba'><div><b>{e(t['before'])}</b>"
                     f"{svg_plan(plan, 0, res, 420, False, lang)}</div><div><b>{e(t['after'])}</b>"
                     f"{svg_plan(best['plan'], 0, None, 420, False, lang)}</div></div>")
    parts.append(f"<p class='muted' style='margin-top:20px'>{e(res['note'])}</p></body></html>")
    return "".join(parts)
