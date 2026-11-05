# Nexora Build 1.14 – 2 corrections + Part 6 Approval Drawing

Version **1.14.0**. Existing data is not changed. New columns are added only:
- `clients.doc_checklist`
- `permit_checklists.site_info`
- `permit_checklists.workflow`

## Correction 1 – Clients back in the app, documents stay with you
- The Clients section works as before (owner only), on the PC and online.
- **Client documents are not uploaded any more.** The Client Documents card is now a **checklist**:
  - It lists Patta, Sale deed, Parent documents, EC, FMB, Layout copy, Tax receipt, Aadhaar, PAN, Photo and Site photos.
  - Mark each one **Received** (the date is set), **Pending** or **Not needed**.
  - You can add any other document.
  - Keep the files themselves in your own laptop folder for that client ID.
- **Clients from 1.13:** at the first PC start, the client records saved by 1.13 on the PC come back into the app automatically, with the same IDs.
  - Documents you uploaded in 1.13 are marked "Received".
  - The files stay in `C:\PROJECTS\Nexora_Build\local_data\client_files\C-00x\`. Nothing is uploaded and nothing is deleted.
- Total Projects still counts only real projects (no archived, no SMOKE TEST).

## Correction 2 – Walkthrough: no blur, no wait, no shake
- **No more waiting when the walkthrough starts:**
  - The model is not built again; only the doors open.
  - Room lights are fixed, so the screen no longer freezes while lights are added.
- **Smooth movement:** the camera glides when you walk, turn and climb steps, so it no longer jumps.
- **Sharper and faster:**
  - The slow "log depth" mode is removed.
  - If the laptop is slow, the 3D view lowers its resolution a little to stay smooth, and goes back up when it can.

## Part 6 – Approval Drawing (Design → Approval Drawing tab)
1. **Site & owner details**
   - Approval authority (DTCP / CMDA / Corporation / Municipality / Village Panchayat).
   - Owner name, Survey/S.F. No., village, taluk, district, plot/layout, road name, landmark, licensed engineer + Reg. No.
   - Permitted FSI / coverage.
   - Marks for RWH pit / sump / septic tank on the site plan.
   - Fields marked * are required. If they are missing, the app asks; it never guesses.
2. **Rule check (required vs provided):**
   - Setbacks front / rear / left / right, from the room positions.
   - Building height.
   - FSI and coverage, when you enter the permitted values.
   - Car parking and RWH.
   - Red = not OK. Fix it in the 2D editor.
3. **Approval drawing (ONE sheet, A1 / A2 / A3):**
   - Every floor plan, site plan with the **actual setbacks provided** (ft + m), front elevation, section A-A.
   - Key plan, title "Proposed construction of residential building at S.F. No…, … village, … taluk, … district for Thiru/Tmt …".
   - Area statement, setback table, door & window schedule, notes.
   - Owner + licensed engineer signature boxes (empty), and an empty "For office use" box. No seal or signature is printed.
   - **Preview** in the app, **PDF**, **PDF (CAD colours)**, **DXF**. Works without saving the design (marked "draft").
4. **Fee calculator:**
   - Enter YOUR rates once per authority, from the local body's current fee order. Basis: per m² built-up, per m² plot, % of estimate, or fixed.
   - The amounts are worked out for this project.
   - **Copy amounts to the checklist** fills the fee table.
5. **Approval progress:**
   - Stages: Drawing ready → Documents collected → Application submitted (application no.) → Site inspection → Fee demand → Fees paid (receipt no.) → Approval received (permit no.).
   - "Drawing ready" and "Application submitted" also tick the project tracker on the Clients page.
6. **Documents checklist for approval** (the same one as Projects → Permit) is at the bottom.

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
scripts\github_push.bat
```
It must end with **NEXORA 1.14 API: ALL GOOD**.

## Test checklist
1. **Clients:** your clients from 1.13 are back. Open one and mark Patta as Received → Save. "1 of 11 received" is shown. Open the online app: Clients is there too.
2. **3D → Walkthrough:**
   - It starts at once.
   - Walk with W/S, turn with arrows: smooth.
   - Staircase → E → First floor.
3. **Design → Approval Drawing:**
   - Leave Survey No. empty → PDF → it asks for it.
   - Fill the * fields → Save → **Preview**: one sheet with all drawings and tables.
   - Download the A1 PDF and the DXF.
4. Enter a fee rate (e.g. Scrutiny fee ₹/m²) → Save my rates → the amount appears → Copy amounts to the checklist.
5. Tick "Application submitted" with an application no. → the Clients page tracker shows Submission done.
