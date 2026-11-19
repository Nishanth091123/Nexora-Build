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

## 1.24.2 – instructions followed exactly, PDF import built from the real walls
**Generator (typed text and the rooms table)**
- The rooms table is sent as a strict request: the plan has EXACTLY the rooms chosen (bedrooms, attached / common toilets,
  dining, pooja, parking, staircase). When the plot cannot hold them, nothing is changed silently – you get the reason and
  options (one bedroom less, no car parking, add a floor, no pooja, several changes together …) plus
  "Adjust automatically", which lists every change it made.
- New spine layout engine (`design/spine.py`): hall / dining strip + ONE passage + stair; every room opens from hall,
  dining or the passage; no filler passage cells; the common toilet stays small; upper floors repeat the same stair and passage.
- Ground floor is made deeper when an upper floor needs more depth (big plots with many bedrooms upstairs).
- The void above the car porch on an upper floor is an Open Terrace, not a second passage.
- Tanglish / Tamil counts ("ore attached bathroom", "2 common toilet", "ground floor mattum") are understood.

**PDF / DXF import (`drawing/place.py`)**
- Rooms are placed from the drawing's own wall geometry: a written-size room sits where its walls are (hugging walls,
  not on walls, not on other rooms) – no more shifted / scattered boxes.
- Open plan (hall + dining in one area) with a small closed room in a corner (sit-out in the hall) is kept as an
  L = two rectangles (same name, "part 2"); the written size is never reduced and nothing is pushed away.
- Unlabelled hollows inside the walls become ONE passage (grown to touch its neighbours); hollows outside the walls
  (setback, beside the parking) are not passages. An "(EXT.)" staircase is reached from outside.
- The title-block word "Drawing" is no longer read as a drawing room.
- When the walls of a sheet cannot be trusted (hatched walls, no closed rooms) the earlier name-position method is used.

## 1.24.3 – fixes from the 1.24.2 test run
- Import of a DXF / PDF no longer needs scipy; numpy is now in requirements.txt (the wall-based placement needs it; without it the old method is used and a note is added instead of failing).
- Options for a request with several houses on one floor are no longer searched (took ~3 min) – the message lists the options. Other option searches stop after 15 s.
- Smoke test reads the 422 body correctly (`detail.questions`).
