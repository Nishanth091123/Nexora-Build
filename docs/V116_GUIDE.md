# Nexora Build 1.16 – Trees, sharp 3D, Clients removed, Approval / Rates permissions, Estimate downloads, Vastu upgrade

Version **1.16.0**. Existing data is not changed and nothing is deleted. Two columns are added to
`project_access` (`can_approval`, `can_rates`, both OFF by default = owner only).

## 1. Trees & plants (3D tab → "Trees & plants around the house")
- Choose each type: **Coconut (Thennai), Neem (Vembu), Mango (Maa), Areca palm (Paakku), Shrubs / flowering plants,
  Potted plants at the entrance, Lawn**.
- For each: ON / OFF, **how many**, and **where** – Front yard / Sides / Rear yard / Along the compound wall.
- New realistic models: palms with curved trunks and drooping fronds, neem and mango with a branch frame and leafy
  crowns, flowering shrubs, terracotta pots. No more balls.
- **Always outside the house and the roof overhang** (checked against every floor). If the chosen yard is too small,
  big trees are placed just outside the compound (never on the road).
- Lawn OFF = plain earth.
- Saved with the design (press Save) and listed in the **Showcase** (PNG / print).

## 2. Walkthrough blur – fixed
- The picture no longer lowers its resolution while you move or press a button (that was the blur).
- New **Quality: High / Medium / Low** box above the 3D view. Chosen once on each computer; it never changes by itself.
  - High = sharpest (default). Medium / Low only for a slow laptop (fewer pixels, simpler / no shadows).
- The walk glide is quicker, so there is no smear when you turn.

## 3. Clients section removed (option B)
- Gone: Clients menu, Clients page, client cards, project tracker and project notes.
- The project keeps its **Client name** (used in title blocks and reports).
- No client records are made any more (startup linking and project save are switched off).
- Old client data stays in the database (not deleted).

## 4. Approval and Material Rates – owner only, separate permissions
- **Approval** = Design → Approval Drawing tab + Projects → Plan Approval tab (documents, fees, application / permit no.).
- **Material Rates** = Estimate → Rate Library (view + edit rates) + rates of your own items in the Material Library.
- Even with Design / Estimate access, another user sees these only when you tick **Approval** / **Material Rates**
  for them (Settings → Project Access, or in the invite link).
- Locked on the server, not just hidden. Estimate amounts stay visible as before.

## 5. Estimate downloads
- A **PDF / Excel download bar under every tab**: Overview, Floor-wise BOQ, Quantity Takeoff, Material Estimate,
  Cost Analysis, BOQ, Payment Schedule, Comparisons (BBS keeps its own downloads).
- File names have the project code + name, e.g. `P-001_Kumar_House_BOQ_Estimate.pdf`.
- New tab **Part Estimate**:
  - Choose the floor (All / Foundation / Plinth / Ground / First / … / Terrace / External) and the work
    (Excavation, Foundation & PCC, Columns, Beams, Slab, Staircase, Brickwork, Plastering, Flooring, Painting,
    Doors & Windows, Plumbing, Electrical, External works…).
  - Shows the items (qty, rate, amount), **materials needed** (cement bags, steel kg with an approximate dia split,
    M-sand, P-sand, aggregate, bricks, mixing water), labour and the total.
  - Download PDF / Excel – e.g. `P-001_Kumar_House_Ground_Floor_Slab_Estimate.pdf`. Works without saving (draft).
  - Direct cost of that part. Transport, contingency, margin and GST are added only in the full estimate.

## 6. Vastu upgrade (points 1–11)
1. **Floor-wise scores** + a total score out of 100.
2. **16-zone mandala** on the plan with the **Brahmasthan** (centre) marked. "16 zones" tick box above the plan.
3. **Main door – 32 padas**: which pada the door is in (e.g. E4 Indra), and how many feet to move it to reach a
   preferred pada.
4. New checks: sump, borewell, overhead tank, septic tank, rain-water pit, gate, staircase turn (clockwise),
   facing while praying, cook's facing at the stove, head side while sleeping, toilet seat N–S.
5. Plot shape (cut / extension), road sides, T-junction (veedhi soolai). Anything not in the drawing is **asked**
   (Site & Fixtures → Answer), never guessed.
6. **8-direction overview** (N / NE / E / SE / S / SW / W / NW: Excellent / Good / Needs attention), like the mockup.
7. **Room-wise cards**: now → better → why → simple remedy (neutral, traditional guidance).
8. **2–3 improved plan options** with scores, side by side. "Save as new version" on the one you like.
9. **Live Vastu in the 2D editor**: press "Vastu" in the editor toolbar – score per floor, 16 zones and door pada
   update as you move rooms. (Needs Vastu access.)
10. **Report**: title, score, all floors with the 16-zone plan, door pada, room-wise guidance, site checks,
    recommendations, before / after. **English PDF**, plus **Tamil (and English) print** – opens in a new tab,
    use Print → Save as PDF (the browser draws Tamil letters correctly).
11. **My Vastu Rules** (owner): click zones per room – green preferred / yellow acceptable / grey avoid. Used in
    every check, option and report. "Back to built-in rules" restores the default.
- Language button (தமிழ் / English) at the top of the Vastu page.
- Vastu stays a normal module permission (no change).

## Update steps (CMD)
```
cd C:\PROJECTS\Nexora_Build
scripts\update.bat
```
It must end with **NEXORA 1.16 API: ALL GOOD**. Then:
```
scripts\github_push.bat
```

## 1.16.1 fix
- Settings → Project Access → "Owner-only modules" switches were stored in the old Clients code; removing Clients
  removed them too. They are back (own small module), same data, nothing lost.
