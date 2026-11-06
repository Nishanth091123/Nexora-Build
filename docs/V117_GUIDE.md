# Nexora Build 1.17 – Doors fixed at the root, realistic walkthrough, Roofing sheets everywhere

Version **1.17.0**. Existing data is not changed. No new tables (sheet roofs are saved inside the design,
new rate codes are added to the Rate Library automatically).

## 1. Doors / openings – fixed at the root
Tested on 336 generated plans (20×30 to 40×60, 4 facings, G / G+1 / G+2, 1–4 bedrooms):

| | Before (1.16) | Now (1.17) |
|---|---|---|
| Rooms with no way in (fully closed) | 170 | **0** |
| Bedroom opening only into another bedroom | 93 | **0** |
| Window on top of a door | 0 | 0 |

- Every room is opened from a room you can already walk into: hall / dining / passage / staircase / lounge.
  - A bedroom **never** opens into another bedroom.
  - An attached toilet opens into its own bedroom.
  - A common toilet opens from a common area.
  - The wash passage may open from the kitchen.
- If two doors want the same spot, the door moves along the wall. It is never dropped silently any more.
- When the rooms do not allow it, the plan engine makes a **passage**: a 3½ ft (or 3 ft) strip from the hall /
  staircase along the back rooms, or across a row. A room is never made smaller than its minimum size for this.
- If a plot really cannot give every room access (e.g. 4 bedrooms on a small ground floor), you get the
  options instead: 3 bedrooms, no car parking, or G+1.
- Old saved designs: open the design and press **Save** to get the new doors. If a room still cannot be reached,
  the Checks box says which one. Generating the plan again gives the passage.

## 2. Walkthrough – more real, sharper
- **Sharper walls and floors:**
  - The wall texture is 4× finer, so it no longer goes soft when you walk close to it.
  - Floors and your own tile / granite photos stay sharp at an angle.
- **Soft corner shadows** where the walls meet the floor and the ceiling.
- **Room details:** skirting, cornice (bedroom / hall / dining), ceiling fan, tube light, switch board beside
  every door, curtains at the windows of bedrooms and living rooms.
- **Better furniture:**
  - Bedroom: bed with legs, two pillows, blanket, side tables with lamps, wardrobe with handles.
  - Hall: sofa with cushions and arms, coffee table, TV unit, rug, plant in a pot.
  - Dining: 4–6 chairs with backs.
  - Kitchen: loft cabinets, hob and sink.
  - Toilet: WC with cistern, mirror and shower.
- **Photo mode (HD)** button: saves exactly what you see (also inside the walkthrough) as a 3200 px picture with
  fine shadows – for showing to clients.
- **Quality High** also gives polished floors that reflect a little. Medium / Low stay light for slow laptops.

## 3. Roofing sheets (Design → 2D Editor → "Roof & sheets")
- **Where:** all four can be used together.
  1. **Full roof:** a sheet roof instead of the RCC slab of the top floor.
  2. **Terrace shed:** a shed on the RCC terrace, the whole terrace or part of it.
  3. **Head room:** the staircase mumty gets a sheet instead of a slab.
  4. **Part of a floor:** sit-out / car parking / utility / balcony.
- **Sheet:** GI, Galvalume colour-coated, PUF insulated panel, fibre-cement (ACC), polycarbonate.
  - Thickness and colour are your choice.
- **Shape:** gable, mono-pitch (choose the high side) or hip. You also set the slope, overhang and clear height.
- **Support:** MS truss + purlins, or purlins only.
  - Member sizes (top / bottom chord, web, purlin, posts) and purlin spacing are written on the drawing **as you
    enter them**, with a note to confirm them with the structural engineer.
- Size and position start from the building / staircase / chosen room. Change them if needed.
- **Used everywhere:**
  - **Drawings:**
    - Front elevation and Section A-A show the sheet, the truss and the posts.
    - New sheets: **Roof Plan** (ridge, slope arrows, sizes) and **Truss & Purlin Detail**.
    - Available as PDF, CAD-colour PDF and DXF.
    - Building height now includes the sheet ridge.
  - **Approval drawing:** elevation and section with the sheet, sheet-roof area in the area statement, height
    rule check with the ridge.
  - **Estimate / BOQ:**
    - Sheet (m² incl. laps), ridge / hip cap, flashing, MS truss / purlin / post steel (kg), enamel paint,
      gutter with down pipes, anchor bolts.
    - A full sheet roof removes the top RCC slab, the terrace waterproofing, the parapet and the top ceiling plaster.
    - A head-room sheet removes the mumty slab.
    - New "Roofing" group in the cost breakdown.
    - New work **"Roofing sheet"** in Part Estimate, with sheet m² and steel kg under "Materials needed".
  - **Rate Library:** new rates for sheet_gi, sheet_galvalume, sheet_puff, sheet_acc, sheet_polycarbonate,
    sheet_ridge, ms_struct, gutter and anchor_bolt. They are Tamil Nadu averages – edit them like any other rate.
  - **Structural:**
    - No slab panels under a full sheet roof; the columns get the light roof load instead.
    - New table of sheet-roof loads (dead + live as per IS 875-2), span, trusses, reaction and steel kg.
  - **BBS:** a removed slab simply has no bars. Truss steel is in Structural → sheet-roof table and on the
    Truss sheet (MS sections are not rebars).
  - **3D:**
    - Ribbed sheets in your colour; polycarbonate is see-through.
    - Steel trusses, purlins, posts, ridge cap and gutters are drawn.
    - No slab or terrace parapet under a full sheet roof.
  - **Showcase:** lists the sheet roofs with the trees and plants.
  - **Vastu:** checks the slope of a mono-pitch roof. Lower towards North / East is the traditional preference.

## Update steps (CMD)
```
cd C:\PROJECTS\Nexora_Build
scripts\update.bat
```
It must end with **NEXORA 1.17 API: ALL GOOD**. Then:
```
scripts\github_push.bat
```
