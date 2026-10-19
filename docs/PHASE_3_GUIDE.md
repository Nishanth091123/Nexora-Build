# Nexora Build – Phase 3 (Design Studio)

## New in Phase 3
- **AI Floor Plan**: type the request in English / Tanglish, for example
  `30x40 east facing 2BHK, car parking, G+1, 30 ft road`. Tamil direction words such as kizhakku and merku are understood.
  - **It never guesses.** If the plot size, facing, road width, floors or bedrooms are missing, it asks you.
    "4 rooms" gets a question back: bedrooms, or rooms in total?
  - **Tamil Nadu setbacks are applied automatically** (TNCDBR 2019 Rule 35(1)(a)). They depend on the road width,
    the building height and the plot width. Corner plots, CBA and EWS areas are supported. You never type setbacks.
  - **Rooms per floor table**: change the bedrooms, toilets, hall, kitchen, pooja or parking on each floor, then press Regenerate.
  - **If the rooms don't fit**, nothing is removed silently. You see the reason and buttons for the options that do fit
    (one bedroom less, no car parking, or one more floor).
  - The generator keeps the staircase in the same place on every floor and follows common Vastu preferences where the facing allows:
    kitchen in the SE, master bedroom in the SW, pooja in the NE.
- **2D Editor**:
  - Drag a room to move it. Its attached toilet and dress move with it.
  - Drag the blue handles to resize a room, or type the exact size.
  - Add, duplicate or delete rooms, rename them, and change the room type.
  - Undo / Redo (Ctrl+Z / Ctrl+Y), snap to 3" / 6" / 1', and copy one floor's layout to another.
  - **Walls, doors, windows and checks are derived again after every change.** The checks cover overlaps, rooms outside the setback,
    rooms without a window, and rooms with no door access.
- **Estimate auto-update**: the Quick Estimate card (Basic / Standard / Premium) is recalculated from the drawing after every change and shows the cost difference.
- **3D View**: drag to rotate. You see walls with the door and window openings, parapets, and the roof on or off.
- **Revisions**: every Save is a new version and old versions are kept. You can open, hide (never deleted), export the
  **Plan PDF** and **DXF** (opens in AutoCAD / LibreCAD), and **Compare** any two versions:
  rooms added, removed or resized, wall lengths, and the change in the estimate.
- **Estimate page → "2D Drawing"** input method:
  - Choose a saved design. Walls, doors, windows, rooms and floor areas are measured from the drawing (geometry mode).
    The design's **Estimate** button goes there directly.
  - "Use manual sizes instead" switches back.
- Drawing Upload (PDF / image / DXF) comes in Phase 4.

## Install (one CMD window)
1. Close the running app (Ctrl+C in its window).
2. Right-click `Nexora_Build_Phase3.zip` → Extract All → `C:\PROJECTS` → Replace.
3. Run:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
```
This adds the `designs` table (nothing is deleted) and runs the automatic test, which asks for your owner password.
The last line should be `PHASE 1 + 2 + 3 API: ALL GOOD`.

Then start the app as usual:
```
scripts\start.bat
```

## Test checklist
```
[ ] 1. Design → AI Floor Plan → click the first example → Generate Plan → plan appears with orange setback line, road at the bottom, N arrow
[ ] 2. Setbacks card: 30 ft road → front 3 m; G+1 on a 30 ft plot → side 1 m both sides, rear nil
[ ] 3. Type "20x40 4 rooms north facing" → it asks for road width, floors and whether 4 rooms means bedrooms (no plan made)
[ ] 4. Fill the form (road width, floors, bedrooms) → Generate from form → plan appears
[ ] 5. Rooms per floor: put 3 bedrooms on a small ground floor → Regenerate → you see the reason + option buttons → click one
[ ] 6. Ground / First Floor buttons switch floors; staircase is in the same place on both
[ ] 7. Save → "Saved v1"
[ ] 8. 2D Editor → drag a room, resize with blue handles, type a size → walls/doors redraw and Quick Estimate shows +/- change
[ ] 9. Undo / Redo work; Add room → Store appears; Delete removes it
[ ] 10. Save again → v2.  Revisions → Compare v1 → v2 shows the room changes and the cost difference
[ ] 11. Revisions → PDF opens (one page per floor); DXF opens in AutoCAD / LibreCAD
[ ] 12. 3D View → drag to rotate; Show roof works
[ ] 13. Estimate button (top) → Estimate page shows Source "2D Drawing #…"; BOQ / Excel / PDF work as before
[ ] 14. Estimate page → Input Methods → 2D Drawing → choose a design → calculates; Manual still works
[ ] 15. Check room sizes, setbacks and the plans against your field knowledge – tell me what to adjust
```

## Notes
- Plans are **concept plans**. Verify the setbacks with the local body (DTCP / CMDA / Panchayat).
  Structural sizes need a qualified engineer.
- Minimum sizes used: bedroom 9 ft wide and 80 sq ft (master 100 sq ft), kitchen 6.5 ft, toilet 4 × 6 ft, staircase 7 × 10.5 ft, car parking 8.5 × 15 ft.
- Building height = 1.5 ft plinth + floors × floor height. Plans above 12 m (9 m in EWS) are outside Rule 35(1)(a) and are refused with a message.
