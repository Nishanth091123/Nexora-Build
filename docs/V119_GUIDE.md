# Nexora Build 1.19 – Items 15 to 22

Version **1.19.0**. Existing data is not changed. One new column, `projects.site_data` (JSON, additive
migration 0014), holds the marking levels, water-services inputs, change requests and handover details.
No new Python packages.

## 15. Parking entrance – no column in the middle
- The road side of the car parking / stilt / portico is kept **clear**. Columns go only at the two ends of the
  opening, and one beam spans it.
- This applies to the **3D view** and the **structural design** (grid, beam schedule, footings).
- The front beam over the opening is sized for the full span:
  - deeper first, then wider (230 → 300 → 380 mm);
  - over 4.5 m: a note to check the beam schedule;
  - over 6 m: a warning to use a deep or transfer beam, checked by an engineer;
  - if no normal beam works, it says so – it never hides it.

## 16. Site marking guide (Site → Marking & Handover → Marking guide)
Everything is made from the **active drawing**, with a printable **PDF**:
- **BM:** the road crown at the gate is ±0.000. You write where it is painted.
- **Setting out:**
  - the reference line at the front setback;
  - grid A, B, C… and 1, 2, 3… with offsets from the first line and from the boundaries (mm and ft-in);
  - the 3-4-5 squaring check, building diagonals and batter boards.
- **Footing pits:** grid point, centre, footing / PCC / pit size and pit depth. This needs the structural design
  of the drawing, which asks soil SBC and seismic zone.
- **Level table** from the BM and from the ground floor FFL:
  - ground level, footing bottom, parking;
  - plinth beam, and for each floor: FFL, sill, lintel, slab bottom and top;
  - terrace and parapet.
- **Room marking:** room corners from the grid origin, size, diagonal, and every door / window (wall, distance
  from the corner, width, sill, top).
- **Sunken toilets:** sunk depth, toilet FFL 15 mm lower, 1:100 slope to the floor trap.
- **Car ramp:** rise from the road, length at 1:10 and 1:8, the space available, a warning if it is too steep,
  and the steps from the parking up to the house.
- **Staircase:**
  - first riser position;
  - riser and tread marks on the wall, the pitch line;
  - the waist (soffit) line offset (waist ÷ cos θ);
  - landing level, headroom check;
  - a step-by-step table with levels.
- **Terrace:** outlets, 1:100 slope, the fall to the farthest point, and screed thickness.
- **Drainage:** inspection chambers with distances, invert levels at 1:40 and depths. The last chamber is
  checked against the sewer level.
- **Gate and compound wall.**

Missing site values (ground level, sewer level, foundation depth) are **asked, never guessed**. Until they are
given, the guide shows "?". Plinth, parking level and sunken depth are **auto** values that you can change
(they then show as **manual**); ↺ puts a value back to auto.

## 17. Change requests → cost & time (Marking & Handover → Change requests)
- Add items from your **rate library** (or your own rate), as **extra** or **omitted** work.
- You can also pick **drawing before / after**: the app estimates both drawings and shows the cost
  difference and the change in time.
- You can type the days yourself, or leave them **auto**.
- Saved as **VO-001, VO-002…** (pending). Record the client's decision (approved / rejected, with their name).
- **Variation sheet PDF** with empty signature boxes – no seals and no "APPROVED" stamp.
- Rejected requests stay in the list.

## 18. Steel cutting optimiser (Marking & Handover → Steel cutting)
- Choose a saved **BBS**. The app packs every cut length into **12 m bars**, longest first, allowing for the cut.
- It shows:
  - bars to order per diameter;
  - the cutting pattern for each bar ("57 bars: 12 × 964 mm");
  - off-cuts you can re-use;
  - waste %;
  - kg saved compared with cutting mark by mark;
  - ₹ saved, only if the steel rate is in your rate library.
- Bars longer than 12 m are shown with laps of 50 d. PDF included.

## 19. Rain water harvesting, sump, tanks, septic (Marking & Handover → Water & septic)
- **Asked:** soil type, whether there is a sewer line in the road, and any well / borewell in the plot.
- **Auto, editable:**
  - persons (5 per house);
  - 135 L per person per day;
  - sump storage of 1.5 days.
- **Sizes:**
  - **sump:** litres and inside size;
  - **overhead tank;**
  - **septic tank:** IS 2470 table, 2 chambers. If there is a sewer, no septic tank;
  - **RWH recharge well:** 1.0 m dia, depth by soil type, one well per 100 m² of roof as the starting number. TNCDBR
    2019 Rule 63 / Annexure XXII and the local body decide;
  - **rain-water pipes.**
- **Positions** in the open spaces, kept out of the car path where possible:
  - sump and septic tank as far apart as possible;
  - a warning when they are close, and the 15 m rule when there is a well;
  - under the driveway only as a last choice, with a vehicle-load cover slab noted.
- **Sketch, estimate** from your rate library, and **client approval** (name required). PDF included.

## 20. Sun path & shadows in 3D
- In the 3D view, tick **Sun path & shadows**. Pick a **date** and slide the **time**: the real sun position for
  the site moves the shadows.
- The site comes from the project's location; if it is not set, central Tamil Nadu is used and the app says so.
- **Sunshade suggestion** for each face of the building in the hot months (March – June):
  - hours of sun on each face;
  - chajja depth for 1.2 m windows;
  - east / west faces with low sun get fins / louvres advice.

## 21. Handover pack (Marking & Handover → Handover pack)
One PDF for the owner:
- building summary;
- **as-built notes**;
- **brands used** (from the Material Library choices);
- **warranties** – years, start date and service contact, filled in by you;
- water & drainage sizes and positions;
- a **maintenance calendar** (terrace before the monsoon, RWH, sump, septic, paint, electrical…);
- keys / documents handed over;
- signature boxes.

The **drawing sheets of the active drawing are attached** at the end.

## 22. Floor-by-floor requests and several houses on one floor
- Type the request floor by floor in English, Tanglish or Tamil, for example:
  *"30x55 south facing 30 ft road. Ground floor car parking + staircase inside + 2BHK. First floor 1BHK for
  rental and 2BHK owner stay."* or *"கிரவுண்ட் ஃப்ளோர்ல கார் பார்க்கிங் 2 BHK, ஃபர்ஸ்ட் ஃப்ளோர்ல ரெண்டலுக்கு 1 BHK, ஓனர் 2 BHK"*.
- Before drawing, you get the **"Confirm rooms / houses per floor"** table:
  - change the number of houses, the BHK, or owner / rental;
  - **Split into houses** on any upper floor;
  - then press **Looks right – Generate**.
- In AI chat you get the same check: "Looks right – draw it".
- **Each house is separate:**
  - its own main door opens from the common staircase / lobby;
  - a 9" wall between houses, and no door between them;
  - every room is reachable inside the house.
- Drawings show **"HOUSE A – 1 BHK (RENTAL)"**.
- The area statement and the approval sheet show the **carpet area of each house**.
- If the houses don't fit, the app says how much area is needed against what is available, and gives options:
  - fewer houses;
  - smaller BHK;
  - move a house to another floor;
  - setbacks.
- Where a separate dining does not fit, it is merged into the hall, and the app says so.
- In the middle houses a room may have no outside wall; the app warns about this so you can add a duct or
  light well.

## Update
1. Run `scripts\update.bat`. It must end with **NEXORA 1.19 API: ALL GOOD**.
2. Then run `scripts\github_push.bat`.
