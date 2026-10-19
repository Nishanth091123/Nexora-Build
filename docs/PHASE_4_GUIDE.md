# Nexora Build – Phase 4 (Drawing Upload + Vastu)

## New in Phase 4
- **Drawing Upload** (Design Studio → Drawing Upload tab, the Vastu page, or Estimate → Image / PDF Plan):
  - **DXF** (best): walls, room names and sizes are read exactly. Several floors drawn side by side on one sheet are
    detected and you choose which floor each one is. If the DXF does not say its units, it asks you to confirm them.
  - **Vector PDF**: lines and text are read. The scale comes from the "SCALE 1:100" note or the room sizes written on
    the drawing. If neither is there, you type one known width.
  - **JPG / PNG / scanned PDF**: read by AI vision (Gemini first, then Groq, then OpenRouter).
    It copies only the sizes written on the drawing. A room without a written size is marked amber.
  - **You check every room** in the table: name, type, width, depth and position. You can add rooms and untick rows you don't want.
    Then you confirm the **north direction** on the dial, and which side of the drawing the road is on.
  - Plot size and road width are optional. When you give them, the Tamil Nadu setbacks are **checked** against your drawing.
  - **Save as design**: the drawing becomes a normal design. It opens in the 2D editor, and the 3D view, estimate,
    revisions and Vastu all work on it. You can also add an uploaded floor to an existing design as an upper floor.
- **Vastu Intelligence** (the approved Vastu screen):
  - Steps 1–4, the **Analyzed Plan** (2D / 3D) with the 8-zone + centre Vastu grid, and rooms outlined
    green / amber / red. **Edit Plan** opens the same design in the 2D editor.
  - **Plan Details** and the **Vastu Analysis Result**, shown as "X of Y rules matched". There is no percentage score.
  - **Direction Overview**: North / East / South / West rated Excellent / Good / Needs Attention.
    "Adjust north" is for plots that are not straight to the compass.
  - **Room-wise Vastu Suggestions** for the main entrance (the side the door faces), kitchen, master bedroom, bedrooms,
    pooja, toilets, staircase, living, dining, parking, the centre (Brahmasthan), North-East kept light and South-West kept heavy.
    Click any row to see the reason.
  - **Vastu Recommendations** and general tips: water tank, sump, slope and openings.
  - **Generate Vastu Plan / Get Vastu Improved Plan**:
    - It swaps whole rooms of suitable size on the same floor, and only when that improves the result without breaking doors or minimum sizes.
    - You see the plan before and after, and the changes are saved only when you press "Save as new design version".
    - For uploaded drawings, the suggestions work the same way.
  - **Download Report** gives a PDF with the plan and Vastu grid, the direction overview, room-wise checks, suggestions and tips.
    **Save Analysis** keeps the report in the project. Nothing is ever deleted.

## Install (one CMD window)
1. Close the running app (Ctrl+C, or close its window).
2. Right-click `Nexora_Build_Phase4.zip` → Extract All → `C:\PROJECTS` → Replace.
3. Run:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
```
This installs `pypdf` and `Pillow` and adds the `drawing_analyses` and `vastu_reports` tables. Nothing is deleted.
The last line should be `PHASE 1 + 2 + 3 + 4 API: ALL GOOD`.
Then start the app with `scripts\start.bat`.

## Test checklist
```
[ ] 1. Design → Revisions → DXF download of a saved design → Drawing Upload tab → upload that DXF
[ ] 2. Rooms table fills; "Floors on this sheet" shows Ground + First; units question → choose ft → Apply
[ ] 3. Tick "I confirm the north direction" (set the dial), give plot 30 × 40 and road 30 ft → Update preview → plan + setback check
[ ] 4. Save as design → opens in 2D editor; Revisions shows it with a green "Drawing" badge
[ ] 5. Upload a real DXF of yours → check rooms / sizes are right (tell me what was missed)
[ ] 6. Upload a JPG / PNG photo of a hand / printed plan → AI reads rooms; amber rows = please check; fix and save
[ ] 7. Upload a vector PDF plan (from AutoCAD "Plot to PDF") → rooms read; if scale unknown, type the building width → Scale
[ ] 8. Vastu page → choose a design → plan with zone grid + coloured outlines, "X of Y rules matched", N/E/S/W overview
[ ] 9. Click a room-wise row → reason shows; "Adjust north" → change → Re-check
[ ] 10. "Get Vastu Improved Plan" → before / after + changes → Save as new design version (or a clear message if no safe swap)
[ ] 11. Download Report → PDF opens (plan + grid, overview, checks, tips); Save Analysis shows "Last saved"
[ ] 12. Estimate → Input Methods → Image / PDF Plan open the Drawing Upload tab
[ ] 13. Check the Vastu rules against what your clients expect – tell me what to change (rules are easy to adjust)
```

## Notes
- AI reading of pictures depends on how clear the picture is. Sizes not written on the drawing are measured from the picture,
  so always check the amber rows. DXF is the most accurate input.
- The AI keys come from `.env`. If one provider fails or a model is retired, the next one is tried automatically.
- Vastu results are traditional guidance. Structural safety and TNCDBR rules always come first.
