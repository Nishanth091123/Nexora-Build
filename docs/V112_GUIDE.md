# Nexora Build 1.12 – CAD-style drawings, better 3D, Structural (Part 5)

Version **1.12.0**. Existing data is not changed. One new table is added: `structural_designs`.

## 1. Drawings like AutoCAD (your request)
- **Walls** are drawn as **coloured outlines** (orange-red on paper, yellow on the CAD screen) with a light hatch inside. They are cut cleanly at every door and window: no more solid grey walls.
- **Every layer has its own colour and pen weight:**
  - windows cyan, doors purple with a dashed swing
  - dimensions green, D1/W1 marks red, room names blue
  - furniture grey, stairs teal, grid lines red dash-dot
- **Two colour schemes:**
  - **Paper**: coloured lines on white, for printing.
  - **CAD (black)**: the AutoCAD screen look, with a black background.
  - Switch with the colour button in Drawing Sheets. Download **PDF** or **PDF (CAD black)**.
- The DXF layers carry the same AutoCAD colours (walls yellow, windows cyan, dimensions green…).

## 2. 3D – more realistic
- Film-style lighting (ACES tone mapping) with soft reflections, a sharper sun shadow, a sky gradient and a plaster texture on walls.
- **Edge lines** (architectural model look). They can be switched off.
- New view **Structure (RCC frame)**: footings, PCC, columns, plinth beams, floor beams and see-through slabs of the saved structural design.

## 3. Structural (Design → Structural tab) – PRELIMINARY
- **Inputs:** concrete grade, steel grade, **soil SBC (kN/m²)** and **seismic zone**. The last two are always asked and never assumed. Foundation depth and live load are optional.
- **What it does:**
  - **Columns** at wall junctions (spans ≤ 4.5 m, never inside a room such as car parking). The grid is labelled 1,2,3 / A,B,C.
  - **Columns** sized by IS 456 axial capacity. The minimum is 300×300 in zone III+, 230×300 in zone II.
  - **Beams** on the wall lines: depth, bottom/top bars, stirrups (shear check, Table 19).
  - **Slabs** per room: one/two-way, thickness, main and distribution steel (Table 26).
  - **Isolated footings** from your SBC, with punching and one-way shear checks and steel. It warns when footings overlap (combined footing needed).
- **Output:**
  - Schedules C1…, B1…, S1…, F1… and quantities (concrete m³, steel kg approx.).
  - Sheets: **S-01** column layout & grid, **S-02** foundation plan + footing schedule + footing section, **S-03** column schedule + sections, **S-04** beam layout per floor + typical beam detail, **S-05** slab layout per floor, **S-06** notes & quantities.
  - PDF (paper / CAD black) and DXF.
- **Complete PDF** now includes: drawings + structural + estimate.
- Every sheet says **"PRELIMINARY DESIGN – NOT FOR CONSTRUCTION until checked and signed by a qualified structural engineer"**. It covers gravity loads only. Wind / earthquake analysis (IS 875 / IS 1893) is not included; for G+2 and above in zone III+ the app tells you so.

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
scripts\github_push.bat
```
It must end with **NEXORA 1.12 API: ALL GOOD**.

## Test checklist
1. Design → Drawing Sheets → walls show orange outlines with hatch. Click **Paper colours** to switch to **CAD colours (black)**.
2. Download PDF (CAD black): it has a black drawing area with yellow walls and green dimensions.
3. Design → **Structural** → press Calculate without SBC: it asks for SBC and zone. Enter SBC 150, Zone III → Calculate → Save.
4. Check the S-01…S-06 previews, then download the PDF and DXF.
5. 3D View → **Structure (RCC frame)**: red columns, blue beams, yellow footings.
6. 3D Exterior → edge lines and sky look better. Night still works.
