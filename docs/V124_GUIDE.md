# Nexora Build 1.24 – clean plans, checked before delivery

## Plan generator
- **Passage** – touching passage cells are merged into ONE continuous passage (no split cells).
- **Common toilet** – never bedroom-sized: max about 40 sq ft, the rest of the cell becomes a wash passage.
- **Attached toilet** – stays inside the master bedroom; the door opens from inside the bedroom / its dress area.
  On a tight plot it first becomes compact (4 ft wide) before anything is dropped; a drop is always reported with ⚠.
- **Staircase** – asked in the text ("staircase", "stairs", "படிக்கட்டு") is kept even for a ground-floor-only plan.
- **Main door** – when parking + staircase are in front (no hall on the road side) the door goes on the staircase lobby.
- **Checklist chips** – attached toilet, common toilet and staircase are now listed.

## Automatic validation (`design/validate.py`)
Every plan is checked before it is returned: rooms without a door, unreachable rooms, split passage, overlapping rooms,
bedroom-sized common toilet, attached toilet not opening from its bedroom, minimum sizes, no main door, building outside
the plot, rear gap (note only). A failing layout is retried with the other layout passes; when none passes the user gets
the reasons and the options (no bad plan is handed out).

## Downloads
- "Nexora Build", "Prepared with…", "concept plan – not for construction", "structural design by a qualified engineer",
  the "indicative" estimate note and the "Concept / submission drawing…" line are removed.
- Company-name fallback is now "Praganya Construction".
- No date is printed automatically (design / structural / vastu sheets, BBS, estimate tabs, loan checklist).

## Letterhead (shared)
`backend/app/letterhead.py` + `backend/app/assets/letterhead_header.png`: header on page 1 only, footer line + centred
"Praganya Construction" on every page, ONE right-corner "Seal & Signature" box, client name / date typed by the user.
It is wired into the estimate PDFs in 1.25.

## 1.24.1 – faster "Delete permanently"
- The safety backup before a permanent delete now copies only the tables that delete can touch (a project still takes a full copy because its children go with it). Recover / compare work the same.
- Full backups read in bigger batches and compress faster.
