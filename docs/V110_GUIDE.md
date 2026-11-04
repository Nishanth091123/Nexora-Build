# Nexora Build 1.10 – Part 3: Drawing sheets

Version **1.10.0**. Existing designs are not changed.

## New: Design → Drawing Sheets tab
- **Sheets are made automatically from the plan:**
  - A-02 Site Plan: plot, setback dimensions, road, north.
  - A-03 onward: one floor plan per floor, with D1/W1/V1 marks and overall dimensions.
  - **Front Elevation:** floors, plinth, front doors and windows with sunshades, parapet, staircase head room, levels in metres and total height.
  - **Section A-A:** cut through the staircase. It shows footings, plinth, slabs, walls with door and window openings, the stair flight, head room and floor levels.
- **Door & Window Schedule:**
  - Marks D1, D2…, O1, W1…, V1 with size (ft-in), sill, count per floor, total and material.
  - **Change sizes per type** (for example, all windows 4' x 4', main door 4' x 7'6") and the material, then press **Apply sizes**. The plan, 3D, quantities and estimate all update. Save the design to keep the sizes.
- **Area Details:** built-up and carpet per floor, plot area, FSI achieved, ground coverage, open space, building height.
- **Downloads** (from a saved design):
  - **Drawing Set PDF (A3):** A-01 title sheet (drawing list, area statement, FSI, coverage, setbacks), site plan, floor plans, elevation, section, and the door & window schedule.
  - Every sheet has the **Praganya Construction / Nishanth S** title block, the real scale (1:50, 1:75, 1:100… on A3), sheet number and date. There are empty boxes for the signatures of preparer, owner and licensed engineer/architect. No seal or "approved" stamp is printed.
  - **DXF (AutoCAD):** all drawings side by side, on layers.
- The old plan PDF now shows the firm name too.

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
scripts\github_push.bat
```
It must end with **NEXORA 1.10 API: ALL GOOD**. Then check `<Render address>/api/health` shows **1.10.0**. If not: Render → Manual Deploy → Deploy latest commit.

## Test checklist
1. Design → open a saved design → **Drawing Sheets** → the Front Elevation and Section A-A pictures appear.
2. Click Site Plan and each floor plan → the D1/W1 marks are visible.
3. Door & Window Schedule → set Window width 4 → Apply sizes → the schedule shows W1 4'-0" and the Quick Estimate changes a little.
4. Save the design → **Drawing Set PDF (A3)** → 7+ pages, with the title block showing Praganya Construction on every page.
5. DXF → it opens in AutoCAD / DWG TrueView / LibreCAD.

## 1.10.1 – drafted look, one PDF, Render deploys by itself
- **Drawings look like an office CAD drawing now (plot pens):**
  - Cut walls are heavy and black; doors are brown, with the leaf and a dashed swing; windows use the cyan 3-line symbol; dimensions are green with tick marks and room-by-room chain dimensions; D1/W1 marks are red; room names are blue.
  - Furniture is drawn: bed, wardrobe, sofa, dining table, kitchen counter with sink and hob, WC and basin, car.
  - Also: toilet tile grid, stair treads with an UP arrow, earth hatch, level markers ▽, sunshades with shadow, coping, footing/PCC hatch in the section.
  - Line weights are real millimetres on paper (0.5 / 0.35 / 0.25 / 0.18 / 0.13). The DXF layers carry the same colours.
- **One PDF for everything:**
  - Design → Drawing Sheets → **Complete PDF (drawings + estimate)**.
  - Estimate → Export → **Complete PDF (drawings + bank estimate)**.
  - Both give the A3 drawing set and the estimate in one file.
- **No more Manual Deploy (once):**
  - render.com → nexora-build-api → **Settings → Deploy Hook → Copy**.
  - Add this line to your `.env` (never pushed to GitHub): `RENDER_DEPLOY_HOOK=<paste>`.
  - From now on `github_push.bat` starts the Render deploy itself and waits until `/api/health` shows the new version.
