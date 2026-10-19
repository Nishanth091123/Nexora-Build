# Nexora Build – Phase 2 (Estimate engine)

## New in Phase 2
- **Estimate page** in the approved design: steps bar, input methods, project overview, summary cards
  (cement bags, total cost, cost per sq ft, duration), Quantity Takeoff / Material / Labour / Combined BOQ,
  cost-breakdown donut, floor-wise summary, exports
- **Manual Enter Sizes**: floors (G to G+5, stilt), built-up per floor, rooms, plot, RCC framed / load bearing,
  Basic / Standard / Premium, bricks / AAC / solid blocks, staircase, sump, septic, OH tank, RWH,
  compound wall, gate, parking, contractor margin, GST, contingency, approval fees, extra items
- **Never guesses**: if built-up area or rooms are missing, it asks you to confirm
- **Full coverage**: earthwork → foundation → RCC (footings, columns, beams, slabs, lintels, sunshades, stairs)
  → steel → formwork → masonry → plastering → flooring/tiling/granite → waterproofing → painting →
  doors/windows/grills → plumbing & sanitary → electrical → sump/septic/RWH/compound wall/gate → site water, watchman
- **Every item split** into material + labour (man-days × day wage per trade) + equipment; click a BOQ row for its rate analysis
- **Rate Library**: all-India state dropdown, Tamil Nadu average by default, edit any rate inline, add custom items,
  hide (never delete), "Create <state> rates" copies TN rates for another state
- **Versions**: every Save is a new version (old ones kept); Comparisons tab = Basic vs Standard vs Premium side by side
- **Exports**: BOQ Excel (Summary, BOQ, Materials, Labour, Equipment, Floor-wise, Rate Analysis, Assumptions) and PDF report
- Small fixes: Add User no longer auto-fills name/password; backend page at :8000 shows a "running" message
- **One-window start**: `scripts\start.bat` runs backend + frontend together and opens the browser

## Install (one CMD window)
1. Close the running app windows (Ctrl+C).
2. Right-click `Nexora_Build_Phase2.zip` → Extract All → `C:\PROJECTS` → Replace.
3. Run:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
```
It installs the new packages, updates the database (adds the rate & estimate tables – nothing deleted),
then runs the automatic test (asks your owner password). Expected last line: `PHASE 1 + 2 API: ALL GOOD`.

## Daily use (one CMD window)
```
cd /d C:\PROJECTS\Nexora_Build
scripts\start.bat
```
The browser opens http://localhost:5173 automatically. Stop with **Ctrl+C** (then Y).

## Test checklist
```
[ ] 1. Estimate page opens for your project; the inputs window asks for built-up area / rooms if missing
[ ] 2. Enter 1000 + 1000 sq ft (G+1), 3 bedrooms, 3 toilets → Calculate → summary cards show values
[ ] 3. Quantity Takeoff / Material / Labour / Combined BOQ tabs show tables; filters work
[ ] 4. Click a BOQ row → rate analysis (material + labour + equipment) appears
[ ] 5. Change Spec to Premium → Calculate → cost goes up, cement & steel quantities stay the same
[ ] 6. Save → "Saved v1"; Export → Excel and PDF download and open correctly
[ ] 7. Rate Library → change cement Standard rate → Calculate again → total changes
[ ] 8. Rate Library → choose Kerala → yellow note → "Create Kerala rates" works
[ ] 9. Comparisons → Compare Basic / Standard / Premium shows 3 columns
[ ] 10. Check the numbers against your field knowledge (cement bags/sq ft, steel kg/sq ft, labour) – tell me what to adjust
[ ] 11. A user without Estimate access sees "You don't have Estimate access"
```

## Notes
- Default rates are approximate Tamil Nadu averages (Oct 2026). Please correct them to your market – you know these best.
- Quantities in Phase 2 come from a standard layout model of your inputs (all assumptions are listed on the page).
  In Phase 3 the same engine will take exact quantities from the drawing.
- Structural sizes (columns, footings) are preliminary – final sizes need a qualified structural engineer.
