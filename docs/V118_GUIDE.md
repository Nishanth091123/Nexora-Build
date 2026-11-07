# Nexora Build 1.18 – Your 14 corrections

Version **1.18.0**. Existing data is not changed. New tables `market_brands` and `market_variants` are added
automatically. New columns: `projects.active_design_id` and `projects.brand_choices` (additive migration 0013).
Two new Python packages are installed by `update.bat`: **pdfplumber** and **pypdfium2** (PDF reading).

## 1. Home – today's work weather tips (bug 1)
- The card **"Today's work – weather tips"** always shows now.
- Tips come from **today's work in Site → Daily Work** (planned or running today / tomorrow).
- If no work is entered for today, the tips come from the current schedule stages.
- If there is no schedule either, you get weather tips for the usual site work: concrete, brickwork, plaster
  and painting.
- A small line under the title says where the tips came from.

## 2. 3D – the ground / stilt floor no longer floats (bug 2)
- Stilt, parking and portico floors get **columns** at every corner, not more than about 12 ft apart, with
  **beams** under the slab.
- Columns are 9"×9", or 12"×12" when 2 or more floors sit above.
- Before, only 2 columns at the front of the parking were drawn.

## 3. Upload drawing (PDF) reads better (bug 3)
- **The plan page is found automatically.** A cover or index sheet first is no problem. "PDF page" stays
  blank (= Auto); type a number only to force a page.
  - If plans are on several pages, the app tells you which ones.
  - Read the other floors with "Add to design".
- **Room names are read at their exact place.** This uses the new pdfplumber reader, so a size written under
  a room is no longer given to the next room.
- **The written size wins.** A box measured wrongly (furniture or hatch lines) is replaced by the size
  written on the drawing. The row is marked so you can check it.
- **More room names understood:** MBR, M.Bed, K.Bed, Kitchenette, Work area, Wash area, Car park, Two wheeler,
  Thinnai, OTS, Courtyard / Mutram, Sit-out, Living cum dining…
- **Text drawn as lines (AutoCAD SHX fonts) or a scanned PDF:**
  - The app says so.
  - The page is turned into a sharp picture for the AI reader, so it works with every AI service.
  - Sizes that are not written on the drawing stay empty. They are never guessed.
- **"Which file reads best?"** sits under the upload box:
  1. DXF.
  2. A PDF plotted with TrueType text and a scale note.
  3. A clear scan.

## 4 & 11. One ACTIVE drawing for every module (bugs 4 and 11)
- The drawing you upload and confirm, or the design version you save, becomes the project's **active
  drawing**.
- **Design → Versions:** the active one has a green **ACTIVE** mark. "Use everywhere" makes another version
  the active one.
- **Design and Vastu** open the active drawing.
- **Estimate** uses the active drawing by itself:
  - **No manual sizes are asked** when a drawing exists.
  - An old saved estimate made from another drawing is recalculated from the active drawing. The old
    estimate versions stay.
  - If you choose manual sizes or Excel, an amber bar offers **"Use the active drawing"**.
  - Details that are not in a drawing (soil SBC, seismic zone…) are still asked.

## 5–9. Material Library – its own page (menu → Material Library)
- **Every material of a house, stage by stage:**
  - Structure, waterproofing, flooring, doors & windows, plumbing, electrical, painting and roofing.
  - 32 groups, from cement, steel, sand and blocks to tiles, taps, wires, paint and roofing sheets.
- **Market brands, names only (no logos).** Some examples:
  - Cement: UltraTech, Ramco, Dalmia, Chettinad, ACC, Ambuja, Sankar, Coromandel King, Zuari, Priya, Maha,
    Bharathi, JSW.
  - Steel: TATA Tiscon, JSW Neosteel, SAIL, Vizag, Jindal Panther, Kamachi, ARS, Agni…
  - Tiles, paint, plywood, pipes, sanitary, wires, switches, fans and sheets the same way.
- **Variants show by themselves:**
  - Cement: OPC 53 / OPC 43 / PPC / PSC.
  - Steel: Fe 500 / 500D / 550D with diameters.
  - Tiles: size, type and finish.
  - Paint: product ranges.
  - Doors, windows, tanks and wires the same way.
- **Your rate.**
  - You type it (₹, unit, GST). The date is kept.
  - Nothing is priced by the app.
  - Rates are visible only with Material Rates permission.
- **A / B / C grade.**
  - You tag each brand once: A = Premium, B = Standard, C = Basic.
  - The estimate's Premium rate then = the average of your A brands that have rates; Standard = B; Basic = C.
  - The app does not rank brands for you.
- **Use in project (★).** Fix a brand for this project only, e.g. Ramco PPC. That project's estimate uses its
  rate. "Assumptions & checks" says so.
- **Search everything as you type:** name, brand or code. Typing a shade code like **09** lists 0901, 0902…
- **Import list (Excel / CSV)** with your dealer's shade card or price list.
  - The Template button gives the columns: category, brand, name, code, colour, unit, rate, GST.
  - Same brand + code updates the row. Nothing is deleted.
- **Paint colour now applies in 3D (bug 6):**
  - A **quick colour** now replaces a library pick on the same walls. Before, the old pick hid it.
  - Shades with a colour from the Material Library can be picked in the 3D material panel.
  - Adding a paint with only a code and no colour gives a warning. The code alone cannot tell the colour.
  - The front feature walls of the Modern / Contemporary style keep their stone / wood. Change them under
    "Feature walls (front)".

## 10. Staircase design (Design → Editor → Staircase)
- **Type:** Auto, dog-legged, straight, L-shape, U / open-well or spiral.
- **Worked out from the floor height and the staircase room:** width, riser, tread, flights and landing.
  You can change any of them.
- **Checks:** riser ≤ 190, tread ≥ 250, 2R+T 550–700, width ≥ 900 mm, ≤ 15 risers per flight, headroom
  ≥ 2.1 m, and whether it fits the room.
  - These are the usual limits for houses. The approving authority's rules decide.
  - Outside a limit you get a warning. Nothing is blocked.
- **Waist slab to IS 456** (M20 / Fe500), and a **bar bending schedule**:
  - main bars, distribution bars, top bars at the supports, and landing bars;
  - quantities per floor.
- **Drawing set:** a new **Staircase Detail** sheet with the plan of the flights, a section with the bars, and
  the checks. It is also in the DXF.
- **Estimate:**
  - The designed concrete, steel and shuttering replace the old average figure.
  - Step finish: granite, tiles, kota or cement.
  - New item: **Staircase railing** (MS / SS / glass / wood), new rate `stair_railing`.
  - Part estimate "Staircase" includes them.
- **3D** uses the riser / tread / type. The flights always climb **clockwise**.
- **Vastu** shows the climbing direction.

## 12. Any plot shape (Design → Confirm details → Plot shape)
- **Ways to give the shape:**
  - **4 sides + one diagonal** (from the survey / FMB sketch);
  - **sides + corner angles**;
  - **corner points**.
  - A live sketch and the area (sq ft and cents) are shown.
- **A missing diagonal or angle is asked.** 4 sides alone do not fix a shape, so it is never guessed.
- **Setbacks are kept from every side.**
  - The house is the largest rectangle that fits.
  - The odd corners stay for garden, parking or sump.
- **Site plan, approval sheet, area statement, FSI / coverage:**
  - drawn on the real outline, with the side lengths;
  - real plot area;
  - provided setbacks measured to each side.
- **Estimate:** the compound wall follows the real perimeter.
- **3D:** the ground and compound wall follow every side.
- **Vastu:** reports corner cuts / extensions.

## 13. Auto + Manual everywhere
- **Setbacks:** four boxes under the plot. Blank = **AUTO** (TNCDBR). Type a value = **MANUAL**, and ↺ goes
  back to auto. A value below the rule is warned on the approval check, never blocked.
- **Estimate quantities:**
  - Type your own quantity in Quantity Takeoff or BOQ. It is marked **MANUAL**, with the auto value under it
    and ↺ to reset.
  - Material, labour and cost follow your quantity.
  - When the plan changes, your manual quantities stay. The checks say if one no longer matches, or differs a
    lot from the new auto value.
- **Staircase, roof sheets, plot shape:** Auto first, every value can be changed.

## 14. AI answers faster
- **Hedged request:** if the first AI service has not answered in 5 s, the next one is asked at the same time.
  The first good answer wins.
- **Skip a failed service:** a service that failed in the last 3 minutes goes to the back of the line.
- **One AI call instead of two** for greetings, Vastu questions, site status and document questions. They go
  straight to the right tool.

## Test checklist (after update.bat says NEXORA 1.18 API: ALL GOOD)
1. **Home:** add a Daily Work item for today (e.g. "Brick work"). The weather tips show brickwork tips.
2. **Design → 3D, a stilt plan:** columns and beams under the first floor. Nothing floats.
3. **Design → Upload a PDF whose plan is on page 2:** it is found. The rooms and the sizes written under them
   are right.
4. **Upload a drawing and confirm → open Estimate:** it calculates from that drawing and does not ask for
   manual sizes.
5. **Design → Versions:** ACTIVE mark; "Use everywhere" on an older one; Estimate follows it.
6. **Material Library:**
   - tag Ramco A and Dalmia B;
   - enter the PPC rates;
   - Estimate → Compare: Premium / Standard cement rates follow;
   - "Use in project" on one brand;
   - import a CSV of shades and search "09".
7. **3D → Quick colour:** pick an exterior colour – the walls change, even after a library pick.
8. **Design → Editor → Staircase:** change the type and the width; the checks and BBS change; the drawing set
   has a Staircase Detail sheet.
9. **Plot shape → 4 sides + diagonal:** generate; check the site plan, approval and 3D outline.
10. **Setbacks:** type front 6 → MANUAL. **Estimate:** type a quantity → MANUAL; ↺ goes back.
11. **AI chat:** "hi" and "check vastu" answer faster.
