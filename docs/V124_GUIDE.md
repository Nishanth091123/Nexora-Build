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

## 1.24.4
- PDF import: a PDF with the floors on separate pages is read page by page – every floor becomes its own drawing group (page order = floor order).
- Checks: every floor of a multi-floor house has a staircase; the car parking is on the road side with nothing in front of it; a parking bay wider than 20 ft under a room gets a "columns only at the edges" note.
- Generator: when the common toilet needs the door cell, the filler passage cell and the toilet swap and the cell becomes a balcony (openings are re-derived on every trial).
- Per-floor toilet counts ("1 attached, 1 common") in a floor-wise prompt are read per floor.

## 1.25.0 – Building Loan Process
- Estimate → Export → "Building Loan Process (one PDF)": cover, 2D plan, oral (quick) estimate, detailed estimate + BOQ, stage-wise payment with loan release stages, common bank document checklist (web-checked Nov 2026; the bank's own list wins).
- Total rate per sq ft is typed by you; the whole estimate is scaled to it (quantities unchanged, a note says so). Client name, date, bank, loan %, loan amount are typed – blank stays blank.
- Estimate PDFs (detailed, bank, client) now use the Praganya letterhead: header band on page 1, footer line + firm name on every page, one blank "Seal & Signature" box. No auto date anywhere.

## 1.26.0 – Interior & Services
- New menu "Interior & Services" (works on the project's active drawing).
- Interior: room-wise kitchen cabinets, wardrobes, TV unit, false ceiling (cove / fluted panel / study table optional). Rates are SUGGESTED DEFAULT RATES from Tamil Nadu (Chennai / Coimbatore) public price pages, checked Nov 2026; every rate and quantity is editable and saved per project. Loose furniture, pooja unit, curtains have no searched rate – you type it. PDF (letterhead) + Excel (live formulas).
- Electrical: points per room (lights, fans, sockets, AC, geyser, exhaust, TV …), switch boards, DB per floor, circuits with MCB / wire size, connected load, supply suggestion. PDF + DXF (layers ELEC_*).
- Plumbing: fixtures per toilet / kitchen / utility, water riser, supply lines, drain lines to the outside wall, soil stacks, tank / sump size (same basis as Site → Water services), stack alignment check between floors. PDF + DXF (layers PLUMB_*).
- Everything is a suggested schematic layout – the licensed electrician / plumber and the local authority decide. No materials are priced for electrical / plumbing (numbers only).
- AI render of rooms stays in Design → 3D (AI Render), stamped "AI concept render – not to scale".

## 1.26.1 – Editable supply + detailed Electrical / Plumbing
- Electrical tab: Supply = Auto / Single phase / Three phase (your choice is used everywhere), water-pump kW, demand factor. Main MCB/MCCB, incoming cable, RCCB and floor DB incomers are sized from it; three-phase circuits are balanced over R/Y/B.
- Electrical PDF: numbered circuits on every point, DB-to-switch-board conduit, switch / socket legs, DB schedule per floor (MCB, wire, phase), switch board schedule, single-line diagram with earth pit. DXF has wiring + circuit-tag layers.
- Plumbing tab: persons, litres per person, overhead tank, sump are editable (blank = automatic).
- Plumbing PDF: pipe sizes, cold and hot lines (geyser), stop-cocks, soil stacks SS1…, waste lines with fall arrows, inspection chambers, fixture / pipe schedule, riser diagram (sump – pump – tank – stack – IC – septic – soak pit).

## 1.27.0 – Design catalog (Interior & Services → "Elevation styles" and "Interior designs")
- Elevation styles: 1,600 styles (5 tops x 4 claddings x 4 window styles x 2 canopies x 10 colour schemes), filter by family / colour / top / cladding / windows. Each picture is drawn on YOUR house (width, floors). "Use this elevation" writes the colours + style into the active drawing as a NEW version: 2D front elevation (coloured wall, cladding band, window frames / arches / louvres, parapet type, canopy), 3D model colours + style and the PDFs follow it. Cladding / pergola are quantities only.
- Interior designs: 636 designs – wardrobe 168, TV unit 144, modular kitchen 180, pooja unit 72, false ceiling 72. Pick per room (floor-wise). Wardrobe / TV unit / kitchen change the quantity (layout) and the price tier of the interior estimate: economy = low, standard = default, premium = high of the searched rate (a rate you typed always wins). Pooja unit and ceiling are shown in the PDF only.
- Pictures are original drawings made by Nexora (no copied photos). "AI photo-like render" sends the picture to the existing free AI render service and marks the result "AI concept render - not to scale".
- Interior estimate PDF gets a "Selected designs" page with the pictures.

## 1.27.1 – Compact layout (no passage)
Single-floor plots with hall + kitchen + dining + 1–2 bedrooms now try a **compact** plan first: front row hall + staircase, middle row kitchen | dining | common toilet, rear row bedrooms with attached toilets. No passage cell; both bedroom doors open from the dining. Four variants (mirrored / kitchen-dining swapped); each is validated, otherwise the old spine layout is used. Not used for car/bike parking in rooms, lounge, pooja, 3+ bedrooms or upper floors.

## 1.27.2 – Staircase head room in the estimate
Plans with a staircase now cost the head room (stair cover) on the terrace: 230 mm walls (8 ft clear), lintel band, RCC roof slab, plaster, door, ventilator, waterproofing, painting, ≈ stair footprint (≈ 82 sq ft for 7.5 × 11 ft). On by default for geometry estimates; switch off with `headroom: false` in the estimate inputs ("Staircase head room" in the Excel input sheet). It is a stair cover, not a room.

## 1.27.3 – Head room switch on the Estimate screen
"Staircase head room (stair cover on terrace)" toggle added under 4. Services & external works. Tick it and press Calculate – the "staircase head room" lines appear in the BOQ. An estimate saved earlier keeps its old inputs: press Calculate again (or make a new estimate).

## 1.27.4 – Elevation by floors, foundation options, external staircase
- Elevation catalog (1,600): 800 styles for a ground-floor-only house (sit-out / portico / plain), 800 for G+1 and above (first-floor balcony, railing or glass). The list follows the active drawing; untick "Only styles made for this plan" to see all. A single floor with a staircase now shows the head room in the elevation.
- Estimate → Services & external works: plinth height, foundation depth, future floors provision (foundation & columns designed for G+1 / G+2 – extra cost shown now), basement (rough allowance, what is NOT included is stated in the notes).
- External staircase (ground-floor-only plans): say "external staircase" in the prompt. No stair room inside the house, the stair is drawn on the site plan, costed (RCC, railing, finish, paint) and the head room becomes a small door cover. It sits in the side setback – needs local body permission. G+1 with an external stair is not built yet (the stair stays inside).

## 1.27.5 – Owner's seal & signature on the PDFs
Settings → Company → "Seal & signature on PDFs" (owner only). Upload a photo of your signature on white paper, switch "Print seal & signature on PDFs" on. The seal reads PROPRIETOR / your signature / PRAGANYA CONSTRUCTION and replaces the blank "Seal & Signature" box in the estimate, loan, interior, electrical-plumbing PDFs and the first signature slot ("Prepared by") of the drawing title block. Off = the boxes stay blank for hand signing (default). The signature is stored in the database (not in the code / GitHub).

## 1.27.6 – Signature photo cleaning
Works with grey / unevenly lit paper (phone photos): the paper is removed locally, the ink becomes one dark-blue colour, photo edges are ignored.

## 1.27.7 – Site plan: septic tank, soak pit, sump, rain-water pit, gate
The site plan now shows (indicative sizes, found in the free yard, never forced): septic tank + soak pit (IS 2470 size by users), sump, rain-water recharge pit and a 10 ft gate, with a list on the sheet. What does not fit is listed ("does not fit … not drawn"). Write "UGD" / "underground drainage" in the prompt and the septic tank is replaced by a sewer-connection note. Rain-water pit on small plots: if it does not fit, use the sump overflow / borewell recharge – confirm with the local body.

## 1.27.8 – Outside staircase in every drawing, soak pit placement
The outside staircase (prompt: "external staircase") now shows in the floor plan (flight + landing + UP arrow), the front elevation (end view with railing), the 2D plan, the rendered plan, the 3D massing and the 3D house view (steps, landing, steel railing, gap in the terrace parapet where it lands). On the site plan the septic tank / soak pit / sump / rain-water pit are labelled by name on the drawing; if a pit does not fit at full size a smaller standard size is tried (soak pit 1.0 m, rain-water pit 0.8 m) before it is reported as "does not fit".

## 1.27.9 – Optional drawings: key plan, column & footing layout + calculation
Design → Drawing Sheets → "Optional drawings (add only if the client asks)". Both are switches, off by default; when off the drawing set is exactly as before. Press Apply, then save the design.
- **Key plan / Location plan**: type place, taluk, district, survey no., plot no., ward, the road in front, other roads (name + compass direction) and landmarks (name + direction + metres). The sheet is drawn only from these entries (a sketch, "not to scale"); empty fields print as blank lines.
- **Column position + footing layout + design calculation**: 3 sheets (column layout with grid, footing layout, column & footing schedule with worked checks). The safe bearing capacity (soil report) and seismic zone MUST be typed – they are never assumed; without them the sheet lists what is missing. The licensed engineer's signature box stays blank. This is a preliminary gravity-load design for approval drawings – the engineer checks and signs.
