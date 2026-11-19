# Nexora Build 1.23 – Connected plan

## Rules (Nishanth's answers)
1. **Hall + Dining combined** → a bedroom opens directly from the hall (then dining → lounge → passage → stair). Never through the kitchen, a toilet or another bedroom.
2. **Common toilet next to the hall** → opens from the hall itself (passage only when it is not next to the hall).
3. **Car parking** → a door from the parking into the hall (the room that holds the main door).
4. The attached toilet opens only into its own bedroom / dress area.
5. Every room must be reachable from the main door. **You walk through hall / dining / lounge / passage / stair only** – a bedroom, kitchen or toilet is a dead end (before 1.23 a plan could "reach" a bedroom through a toilet or the kitchen and look fine).

## What changed in the generator
* `geometry.py`: new `ACCESS` order, `PASS` / `DEPENDENT` reachability, parking→entrance door, a bedroom may open through its own dress area.
* `layout.py`: **middle passage** (`mid`, `mid1..3`): the passage sits between two groups of rooms, so rooms on both sides open into it; the passage keeps the same x in every row.
* `generate()` order: strict plan with every asked room → strict plan with the toilet / bedroom the plot cannot hold removed (**⚠ reported in the notes**) → kitchen as a last resort (**⚠ reported**).
* Sweep (8 plots × 5 facings × 1–3 BHK × 1–2 floors): 225 plans, **0 bedroom→kitchen doors, 0 unreachable rooms**; 15 combinations still cannot be built (20×40 2BHK / 25×40 3BHK – the plot is too small, a clear question is returned).

## Uploaded drawings
* `drawing/sheet.py` reads what is WRITTEN on the sheet: plot (`30'-0" X 40'-0"` confirmed by PLOT AREA / PLOT WIDTH), setbacks (FRONT / REAR / SIDES), road width, facing. The Plot, Gap-from-road, Gap-on-left and Road-width boxes are filled from it – nothing is guessed.
* `exact.py`: a closed region whose box already matches the written size is the room (even if a door swing makes it "not rectangular"); open-plan rooms sit in the nearest free corner of the shared area.
* `connect.py`: rooms are MOVED (never resized) by ≤ 1.3 ft so neighbours touch and nothing overlaps; the check list says how many were moved.

## Known limits (honest)
* Door swing arcs on a drawing are not read yet – doors on an upload are inferred by the rules above. A hall that is L-shaped around a sit-out (as in the 30×40 North sample) is a rectangle in the model, so overlaps are reported and the opening may have to be placed in the 2D editor.
* JPG / PNG positions come from the AI vision reader and are approximate.
