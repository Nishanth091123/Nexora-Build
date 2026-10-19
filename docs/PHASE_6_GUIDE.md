# Nexora Build – Phase 6 (AI Assistant)

## New in 6.6
- **Delete (owner only) + Recycle Bin**:
  - A red 🗑 button next to:
    - Projects (Project Details), documents and files
    - Designs, estimates, the Vastu report, drawing analyses
    - Schedule stages, tasks, approvals
    - Site activities, photos, material entries, quality checks, safety / issues, workers
    - BBS sheets
  - Other users never see it.
  - Deleted items go to **Settings → Recycle Bin**: **Restore**, **Delete permanently**, or **Empty bin**.
  - A full backup is taken automatically before any permanent delete, and stored files are removed too.
  - The **Archived projects** list (e.g. old SMOKE TEST projects) lets you unarchive them or move them to the bin.
  - The owner account and the audit log are never deleted.
- **Invite links** (Settings → Users & Teams → Invite links):
  - Choose a role (Site Engineer, QS…) and the projects / modules, then **Copy link** and send it.
  - The person signs up at `/join/…` and appears as **Pending**. They can work only after you **Approve**.
  - Their access is already set from the link; change it any time in Project Access. **Stop** a link any time.
  - The 🔔 bell shows join requests, approvals waiting for you, and overdue tasks.
  - Until Phase 7 (online), only this PC can open the links.
- **BBS (Bar Bending Schedule)** – Estimate → **BBS (Steel)**:
  - Add columns, beams, footings and slabs with the sizes and bars from your structural drawing.
    Missing values are **asked**, never assumed.
  - For each bar: bar shape sketch, cutting length (bend deductions, 135° hooks, 50d laps), number of bars and kg.
  - Steel to order by diameter (kg and 12 m bars).
  - **Member drawings**: column lap zone (middle half), close tie zones (IS 13920), beam stirrup zones, footing / slab mesh.
  - Save, then download Excel or a **PDF with drawings**.
- **Plan Approval checklist** – Projects → **Plan Approval**:
  - DTCP / CMDA / Corporation / Municipality / Panchayat document list.
  - Status for each document and a file attached to it; add your own items.
  - Fees (with a 1% labour cess hint from your estimate), application / approval number and date, and the approved plan copy.
  - **Document pack (ZIP)**: a summary PDF plus all attached files.
  - The app does **not** submit the application.
- **AI photo check**:
  - Site Photos → open a photo → **AI check**, or attach a site photo in the AI chat.
  - Gives findings with severity and confidence, likely cause, what to check and the fix.
  - Runs only when you click. Only a small text result is saved (no copies of the photo).
  - It is guidance, so confirm on site.

## Fixes in 6.5
- **Old screens after an update**: the browser could keep an old copy of the app. Now:
  - the built app always checks for a new version;
  - the offline cache was renewed (v7);
  - a yellow bar appears if the screen is older than the server, with a **Reload now** button.
- **Site tab stays open**: the tab is kept in the address (e.g. `/site?tab=photos`). A page reload (for example after the phone camera app) returns to Site Photos, not Overview.

## Fixes in 6.3
- The sidebar "Need Help? / Open AI Assistant" box is removed.
- **Site Photos**:
  - New **Camera** button: opens the phone camera app, or the PC webcam with a Capture button.
  - New **Gallery** button: pick one or many saved photos.
  - Photos are made smaller before upload, so they go up faster on site.
  - Upload no longer gets stuck waiting for the GPS permission prompt.
  - The Activity form has the same Camera / Gallery buttons.
- **AI answer "0.99…"**: a safety-classifier model (llama-prompt-guard) was being used for answers.
  These models are now excluded. Answers that are only a number or very short are rejected, and the next model is tried.
- When the AI is not reachable, the note now says why: no key, invalid key, or free limit reached.
- **Tamil search**: Tamil words like காங்கரட்டில் / வெடிப்பு are now understood.
  A new knowledge entry covers concrete cracks.

## Fixes in 6.2 (from your check)
- **Faster**:
  - `update.bat` now **builds** the app and `start.bat` serves the built version. This is much faster than development mode.
  - Pages load only when opened.
  - The offline cache runs only in the built app.
  - The backend prints `SLOW …` lines for any request over 1.5 s. If loading is still slow, send me those lines.
- **SMOKE TEST project**:
  - The test project is now always archived, even if the test stops half-way.
  - Old leftovers are archived on the next run.
- **Estimate → Input Methods → Excel (BOQ/Rate)** now works:
  1. Download the template.
  2. Fill in the Inputs, Extra Items and Rates sheets.
  3. Upload it, and the estimate is calculated.
  - Rate changes in the file update the rate library (owner only, logged).
- **Sidebar picture** is now different for every page.
- The Estimate "3D Model" card now shows the drawing in 3D, and Settings → Material Rates shows the real rate library.
  Both were old "coming soon" boxes.

## What is new – the approved AI Assistant screen
- **8 tabs**: Chat Assistant, Drawing Analysis, Document Q&A, Quantity Calculator, Design Suggestions,
  Site Troubleshooting, Material Guide, Code & Standards.
- **Left column**: Choose AI Agent (General, Drawing Analyst, Quantity Expert, Design Advisor, Site Engineer,
  Material Expert, Vastu Advisor, Code & Standards) and the **Project Context** card (change project there).
- **Right column**: Quick Actions, Recent Conversations (View All → pin / hide), Suggested Prompts.
- **Chat**:
  - Type or **speak** (mic → Groq Whisper; Tamil / English / Tanglish).
  - **Attach** a drawing or document.
  - Choose the answer language: Auto / English / தமிழ் / Tanglish.
  - Answers can include cards: **floor plan** (2D, level tabs), Key Features, **Material Quantity table**,
    estimate, calculator result, Vastu score, site status, drawing rooms, TN setbacks.
  - **Sources** show where an answer came from: IS code / NBC / TNCDBR entries, or your own document with its page.
  - 👍 / 👎 feedback.
- **Buttons on a plan**:
  - **Download Plan (PDF)**, **View 3D Model**, **Generate BOQ (Excel)**, **Modify Plan** (opens the 2D editor), **Check Vastu**.
  - The first time you use Download, Modify or BOQ, the plan / estimate is saved as a new version in the project, only once.

## How the AI works (safe by design)
1. The AI (Gemini → Groq → OpenRouter, automatic fallback) only **chooses the tool** and **explains** the result.
2. **All numbers come from Nexora's engines**: design generator, estimate engine, Vastu, site, calculators, TN setbacks.
3. **It never guesses dimensions**:
   - If facing, road width, floors, bedrooms or toilets are missing, it **asks** with a small form.
   - "20×40, 4 rooms – cost?" → it asks whether that means 4 bedrooms or 4 rooms in total.
   - A number the AI adds that you did not write is removed automatically.
4. If the rooms don't fit the plot after TN setbacks, it shows **options** (one bedroom less / no car / one more floor).
5. **Document Q&A (RAG)**:
   - Your PDFs (with text), Word, Excel, CSV and TXT files are read, split into parts and searched by keyword.
   - With a Gemini key, they are also searched by meaning (pgvector embeddings in Neon).
   - Scanned drawings have no text, so use Drawing Analysis for them.
6. **If no AI key works**, you still get the calculated cards with a short plain answer and a note.
7. Conversations are **never deleted**. "Hide" only hides them.

## Built-in knowledge (cited as sources)
- **Codes and standards**:
  - IS 456: grades, cover, columns, slabs, beams, curing, formwork removal, slump, nominal mixes.
  - IS 1786, IS 269 / 1489 / 455, NBC room sizes and stairs, TNCDBR setbacks, IS 875 / 1893 loads.
  - IS 2212 brickwork, IS 1661 plaster.
- **Materials**: OPC / PPC / PSC, M-Sand / P-Sand, brick / AAC / fly ash, TMT, aggregate, waterproofing, tiles, paint,
  pipes, wires.
- **Site problems**: plaster cracks, dampness, honeycombing, slab leakage, settlement, column plumb, cube test,
  rain / hot weather, anti-termite.
- **Material Guide tab**: types, IS code, where to use, pros / cons, tips, and your **current rate** from the rate library.
- **Quantity Calculator tab**: concrete, brick work, AAC, plaster, steel weight, tiles, paint, area (cent / ground / acre),
  staircase, water tank / sump, excavation. Each result can show its full calculation steps.

## Install (one CMD window)
1. Close all Nexora CMD windows.
2. Extract `Nexora_Build_Phase6.zip` to `C:\PROJECTS` and choose **Replace**.
3. Run:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
```
This adds 4 new tables (AI conversations, messages, indexed documents, document parts) and 1 vector column for search.
Nothing is deleted. No new Python packages are needed.

The last line should be `PHASE 1 - 6 API: ALL GOOD`.

Then start the app:
```
scripts\start.bat
```

Optional `.env` settings: these are all blank by default, which means automatic.
- `GROQ_MODEL`
- `OPENROUTER_MODEL`
- `GEMINI_EMBED_MODEL`
- `GROQ_WHISPER_MODEL`

Your keys stay only in `.env`. Never paste them in chat.

Voice needs the microphone permission. It works on `localhost` now, and on phones after the https deployment (Phase 7).

## Test checklist
```
[ ] 1. AI Assistant page looks like the approved screen (agents left, chat centre, quick actions right)
[ ] 2. Type: "30x40 site ku ground floor plan suggest pannunga. 3 bedroom, hall, kitchen, dining, parking"
       → it asks only what is missing (facing / road width) with a form → fill → plan + key features + material table
[ ] 3. On that plan: View 3D Model, Download Plan (PDF), Generate BOQ (Excel), Modify Plan (opens editor), Check Vastu
[ ] 4. "20x40, 4 rooms – cost?" → asks: 4 bedrooms or 4 rooms in total? (no guessing)
[ ] 5. "1200 sq ft G+1 house cost" → asks per floor / total, bedrooms, toilets → estimate card; try Premium spec
[ ] 6. "how many cement bags for 1 m3 M20" → 9 bags card with "How it is calculated"
[ ] 7. Tamil question: "சுவர்ல விரிசல் வருது என்ன பண்ணலாம்?" → answer in Tamil with sources [1]
[ ] 8. Mic: speak a question in Tamil / English → text appears in the box → send
[ ] 9. Document Q&A: Add document (a PDF / Word spec) → Ready → ask a question → answer quotes the document + page
[ ] 10. Drawing Analysis: upload the Vastu test DXF → rooms table → "Confirm & save in Design" opens the importer
[ ] 11. Quantity Calculator, Material Guide (rates), Code & Standards, Site Troubleshooting tabs work
[ ] 12. Recent Conversations: open an old chat; View All → pin / hide
[ ] 13. A user without AI access on a project sees the "no access" message
[ ] 14. (6.6) Delete a test task / photo / design → Settings → Recycle Bin → Restore → Delete again → Delete permanently (type DELETE)
[ ] 15. (6.6) Recycle Bin → Archived projects: move old SMOKE TEST projects to the bin → Empty bin
[ ] 16. (6.6) Invite link: create → copy → open it in a private window → sign up → bell shows the request → Approve → log in as that user
[ ] 17. (6.6) Estimate → BBS (Steel): column + beam + footing → Calculate → Save → PDF shows bar shapes and the lap / tie drawings
[ ] 18. (6.6) Projects → Plan Approval: change authority, mark documents, attach a file, Document pack (ZIP)
[ ] 19. (6.6) Site Photos → open a photo → AI check (needs an AI key with vision – Gemini / Groq)
```
