# Nexora Build 1.13 – your 12 corrections

Version **1.13.0**. Existing designs, estimates and projects are not changed.

## 1. Clients
- **Total Projects** now counts only real projects. Archived projects and the "SMOKE TEST" project are left out.
- **Client details and documents are kept ONLY on your PC:**
  - Data: `C:\PROJECTS\Nexora_Build\local_data\clients.db`
  - Documents: `local_data\client_files\C-001\…`
  - Nothing goes to Neon, Render or GitHub. `local_data` is in `.gitignore`, and `github_push.bat` stops if it is ever not ignored.
- **First start on the PC:** clients saved earlier in the cloud are copied to the PC. A backup zip is made first, then the cloud copies are removed.
- **Online app (phone / Vercel):** no Clients menu. The page says "kept only on your PC".
- **New buttons on the Clients page:**
  - **Backup (zip)**: download all clients and documents.
  - **Recycle bin**: restore, or delete permanently. A backup zip is made before every permanent delete.
  - An automatic backup is made once a day in `local_data\backups`.
- **Tip:** copy the `local_data` folder to a pen drive / Google Drive now and then. It is your only copy.

## 2. Downloads everywhere (no need to Save first)
Anything not saved yet is marked **"draft"**.

| Where | What you can download |
|---|---|
| AI Floor Plan / 2D Editor | This floor (PNG / SVG), Plan PDF, DXF, Full drawing set |
| Drawing Sheets | Each sheet alone (PDF A3 / PNG / SVG), title sheet, door & window schedule, full set, CAD black, DXF |
| Structural | Each sheet alone (PDF / PNG), notes sheet, full set, DXF – works before Save too |
| 3D | This view, **Front · Left · Right · Rear · 3D** (5 PNG), **all views on one sheet**, flat (no perspective) elevations, GLB, video |
| Vastu | Report PDF (no save needed), Vastu plan PNG / SVG |
| Estimate | Excel / PDF / Bank / Client copy straight from the screen. Floor-wise BOQ and Payment schedule have their own buttons |
| BBS | Excel / PDF without saving |

## 3. Estimate
- **Floor-wise BOQ** and **Payment schedule** were empty for estimates saved before 1.8. They are now worked out automatically when you open such an estimate. The same saved rates are used, so totals do not change.
- Exports of old estimates also include them.

## 4. Structural sheets
- The red "PRELIMINARY DESIGN – NOT FOR CONSTRUCTION" line is removed from all sheets.
- Design notes and the signature boxes stay.
- A small note stays only on the screen.

## 5. Elevation door / window mix-up – fixed
- The front elevation now shows only doors and windows that are really seen from the road.
- Internal doors near the front are no longer drawn on the elevation. That was the "window below, door above" mix-up.
- A main door behind the car parking is now shown.
- Plain doors are drawn as single leaf; the main door as double leaf.
- 2D and 3D use the same rule.

## 6. 3D – realistic, steady, real walkthrough
- **4 elevation styles** (saved with the design):
  - **Modern** (your reference photo): stone + wood cladding, black window frames, deep roof overhang with wood ceiling and downlights, glass balcony rail, entrance canopy with stone pillars and steps, stone-pillar compound wall with black slat gate, paver drive, lawn, path lights, car.
  - **Contemporary**: two-tone, grey tile cladding, wooden fins, terrace pergola.
  - **Traditional TN**: tiled hip roof, thinnai on both sides of the door, round pillars, tiled entrance roof, arched window hoods, balustrade.
  - **Basic**: the earlier simple look.
- **Day / Evening / Night**: in the evening, windows glow warm and the soffit lights are on.
- **Shake / blur fixed:**
  - No more overlapping surfaces (the flicker).
  - Shadows are drawn once, so they no longer crawl.
  - Smoother rotation.
  - The camera no longer jumps when you pick a colour.
  - No resize loop.
- **Walkthrough:**
  - You start at the gate and walk in at eye height.
  - **Keys:** W/S walk, A/D step sideways, ←/→ turn, drag to look, Shift = faster. On mobile, use the on-screen arrows.
  - Walls and the car stop you. Doors are open.
  - **Stairs:** walk to the staircase and press **E** (up) / **Q** (down), or use the button.
  - **Go to room…** jumps straight to any room. The room name shows at the top. **Esc** exits.
- **Honest note:** browser 3D is a clear, accurate concept of your plan, not a photo. For photo-quality images, download **GLB** and render it in Blender (steps are shown under the 3D view).

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
scripts\github_push.bat
```
It must end with **NEXORA 1.13 API: ALL GOOD**.

## Test checklist
1. **Clients:** Total Projects shows the real count, and the green "only on this PC" bar is shown. Open the online app: there is no Clients menu.
2. **Design → AI Floor Plan:** the download bar is under the plan. Without saving, download the PNG and the Plan PDF.
3. **Drawing Sheets:** choose Front Elevation → **This sheet: PDF**. Only one page comes. Doors and windows match the 3D.
4. **Structural:** Calculate → download one sheet without Save. There is no red line on the sheets.
5. **3D:** pick each style → Evening → Front. Click **All views on one sheet**.
6. **3D:** Walkthrough → walk in from the gate → staircase → E → first floor → Go to room… → Esc.
7. **Estimate:** open an old estimate → Floor-wise BOQ and Payment schedule show values.
