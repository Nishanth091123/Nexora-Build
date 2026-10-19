# Phase 7 – Testing, Restore, GitHub and Going Online

Version **1.7.0-phase7**. This is the last phase. It also includes the two fixes you asked for. There is no separate fix file.

## New in 7.5
- The backend goes to **Render.com** (free, no card). Hugging Face now charges for Docker apps. Your files stay in the private Hugging Face repo, which is still free.
- `scripts\go_online.bat` now prepares the online files and a **render_env.txt** settings file to paste into Render.
- After any update, `scripts\github_push.bat` alone updates both online parts (Render + Vercel).

## New in 7.4
- **Online file storage without a card:** files can be kept in a **private Hugging Face repo** (free, no card). `go_online.bat` sets it up and copies your PC files there. Settings → Backups → Storage then shows **Hugging Face (private)**. After this, the PC app and the online app read the same files.

## New in 7.3
- **Weather location picker:** tap the town name (top right of the weather card) to choose:
  - **Project site** (default)
  - **My current location** (phone / PC location – allow location access when the browser asks)
  - **Search any town** – pick from the matches; it is saved in "Saved places" (remove with ×). Your choice is remembered on this device.
- **Fix:** "Best to pour" hours were shown on a rainy day. Now the pouring window shows only when the whole day is fit for concrete (same rule as the 7-day planner); otherwise it says "No pouring today · rain 80%".

## New in 7.2 – Home page site weather (replaces "Build status")
Everything is rule-based (no AI) and follows the project picked at the top. The weather is a free forecast (Open-Meteo, no key). The site town is taken from the project location; if it can't be found, the card asks once.
1. **Site weather today** – current temperature, a red/amber **safety alert** (thunderstorm, heavy rain, strong wind, extreme heat – today/tomorrow), **today's advice tiles** (no concreting, cement inside, pour early, cure 3×, water breaks, no work at height, good day…) and an hourly rain bar with the **best pouring hours**.
2. **7-day site planner** – a weather column for each day with a rain bar and a Pour ✓/✗ verdict. The **best day for slab / concrete pour** is shown in green, with a week summary (pour days, rain days + mm, hot days, storm days).
3. **Tips for current work** – tips for the current schedule stages (foundation, slab/beam/column, brick work, plaster, painting, services), matched to the weather.
4. **Curing tracker** – concrete work from Site → Daily Work in the last 2 weeks (casting, slab, column, beam, footing, PCC…), shown as "Day 5 / 7" bars. It uses 10 days on hot days (IS 456).
5. Tamil text appears when the app language is Tamil.

Test: Home → check the weather card shows the project town → the 7-day planner shows one green BEST day (or the "no safe day" message) → add a "Slab casting" activity in Site → Daily Work → Home curing tracker shows "Day 1 / 7".

## What is new

**Fixes from your check**
- **Recycle Bin is easy to find.** It is in three places, and only the owner sees it:
  - the left menu, below Settings;
  - your name menu (top right), above Logout;
  - Settings → the "Recycle Bin" tab.
  - If you still can't see it, the browser is showing an old copy. Press **Ctrl + Shift + R** once. A yellow "new version" bar also appears when the screen is old.
- **Left-menu photos fit properly.** The links come first and the photo fills only the space below them, so the two never overlap. The photo always fits the menu width and is never zoomed in. On a short screen you see its middle part.

**Restore tool**
- **Settings → Backups → Recover** (owner only).
  - Pick a backup. The app shows what is in it but missing now (projects, tasks, files and so on), with examples.
  - Tick the types you want and press Recover.
  - Nothing that exists now is changed or overwritten.
  - Every "Delete permanently" first makes a **predelete** backup, so a permanent delete can always be undone this way.
  - Recovered items go back into the **Recycle Bin**. Open it and press **Restore**.
  - If an item's stored file (PDF, photo) was already removed from storage, the app tells you. Upload that file again.
- **`scripts\restore_backup.bat <file>`** rebuilds a whole NEW, empty database from a downloaded backup file. Use it only for disaster recovery. Steps are below.

**Going online**
- **`scripts\go_online.bat`** sets up online file storage and the Render settings; the backend runs on **Render.com** (free, no card).
- **Vercel** hosts the screens (free). It updates itself whenever you push to GitHub.
- **`scripts\github_push.bat`** pushes the code to GitHub safely:
  - It checks that `.env` is ignored.
  - It scans every file for keys and stops if it finds one.
  - Your keys never leave your PC except as Render environment settings you paste yourself.
- Going online makes these work:
  - **Invite links** work from any place.
  - The **phone camera** works for site photos (it needs https).
  - The app can be **installed on a phone** (Chrome menu → "Add to Home screen").

## Install this update (one CMD window)
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
```
The last line must read **`PHASE 1 - 7 API: ALL GOOD`**. Then run `scripts\start.bat` and press **Ctrl + Shift + R** in the browser once.

---

## Going online – step by step (about 40 minutes, once)
Online setup, all free with no card:
- **Files** (drawings, photos, backups) → your **private Hugging Face repo**
- **Backend (API)** → **Render.com**, builds from GitHub
- **Screens** → **Vercel**, builds from GitHub
- **Database** → Neon, the same one as now

Hugging Face no longer hosts Docker apps for free (it now needs PRO), so the backend runs on Render instead.

### Step 1 – Hugging Face token (done)
`.env` has `HF_TOKEN=hf_...` (type **Write**).

### Step 2 – Online files + Render settings
```
cd /d C:\PROJECTS\Nexora_Build
scripts\go_online.bat
```
What this does:
- Copies the PC files to the private repo (safe to run again).
- Sets `STORAGE_BACKEND=hf` in `.env`.
- Makes **render_env.txt** and opens it in Notepad. Keep it open for Step 4. It holds your keys and is never pushed to GitHub.

### Step 3 – Code to GitHub
1. On github.com → **New repository**.
   - Name: **Nexora-Build**, **Private**.
   - Leave README, .gitignore and licence unticked.
2. If Git is not installed, get it from https://git-scm.com/download/win (default options).
3. Run:
```
scripts\github_push.bat
```
You should see `[OK] Secret check passed` and then `[OK] PUSHED`. The first push opens a GitHub login window.

### Step 4 – Backend to Render (free, no card)
1. Go to **render.com** → **Get Started** → sign up with **GitHub**.
2. **New +** → **Web Service** → **Connect** your **Nexora-Build** repository. Allow Render access to it if asked.
3. Fill in the settings:
   | Setting | Value |
   |---|---|
   | Name | `nexora-build-api` |
   | Region | **Singapore**, near your Neon database |
   | Branch | `main` |
   | Root Directory | `backend` |
   | Language / Runtime | **Docker** |
   | Instance Type | **Free** |
4. Open **Environment Variables** → **Add from .env**.
   - Paste everything from render_env.txt (Ctrl+A, Ctrl+C in Notepad) and add the variables.
5. Open **Advanced** → **Health Check Path** → `/api/health`.
6. Press **Deploy Web Service**. The first build takes 5–8 minutes. When the log shows `Ready`, your address appears at the top, for example `https://nexora-build-api.onrender.com`.
7. Open `<address>/api/health` in the browser. It should show `"version":"1.7.5-phase7"` and `"storage":"hf"`.
8. **Delete render_env.txt** from the project folder.

Notes:
- The free service sleeps after 15 minutes with no use. The next visit wakes it in about 1 minute; the app shows "it may be waking up – try again in a minute".
- 750 free hours a month is enough to stay on all month.

### Step 5 – Screens to Vercel
1. Go to **vercel.com** → **Sign up with GitHub** → **Add New → Project** → import **Nexora-Build**.
2. Set **Root Directory** to `frontend`. Vercel detects the framework as **Vite**.
3. Under **Environment Variables**, add `VITE_API_URL` = your Render address (no `/` at the end).
4. Press **Deploy**. You get an address like `https://nexora-build.vercel.app`.
5. Open it and log in as **nishanth_s**. All your projects and files are there.

### Step 6 – Phone
- Open the Vercel address in Chrome on the phone and use the menu → **Add to Home screen**.
- The camera, invite links and offline mode now work from anywhere.

### Updating later (after a new zip)
1. Run `scripts\update.bat` (local test – it must say ALL GOOD).
2. Run `scripts\github_push.bat`.

**Render and Vercel both rebuild by themselves** after the push. The backend takes about 5 minutes and the screens about 1 minute.

The PC version and the online version use the **same database and the same online files**, so both always show the same data.

---

## Full restore into a new database (only if the database is lost)
1. Settings → Backups → **Download** the newest backup. Automatic backups are also in your private Hugging Face files repo under `backups/`.
2. Create a new empty Neon database (Neon → Branches → New branch, or a new project) and copy its connection string.
3. In `.env`, set `DATABASE_URL=` to the NEW connection string. **Do not run start.bat yet.**
4. Run:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\restore_backup.bat "C:\Users\<you>\Downloads\nexora_manual_2026....json.gz"
```
5. You should see `[OK] Restored ... rows`. Then run `scripts\start.bat` (and change `DATABASE_URL` in Render → Environment if you use the online app).

The script refuses to write into a database that already has data, so it cannot mix two databases.

---

## Full test checklist (Phase 1 – 7)
Tick each item on your PC first, then on the online address.

**Login and owner**
1. Log in as nishanth_s.
2. Settings → Users: the owner cannot be deactivated or demoted.

**Fixes (Phase 7)**
3. The left menu shows Settings and **Recycle Bin** below the line.
4. Your name menu (top right) shows **Recycle Bin** above Logout.
5. The left-menu photo sits below the links, fits the menu width, is not zoomed, and changes per page (Home, Design, Site, Vastu, Estimate, Projects, AI, Settings).

**Projects**
6. Create a project, edit it, and upload a document.
7. The Plan Approval tab works: tick an item and attach a file.

**Design**
8. Generate a plan from "30x40 east facing 2BHK, 30 ft road, G+1".
9. The app asks for anything missing instead of guessing.
10. The 2D editor, 3D view and Revisions work.

**Estimate**
11. Manual estimate works.
12. Excel template download and upload work.
13. BOQ Excel/PDF export works.
14. **BBS (Steel)**: add a column, beam and footing, then export to Excel/PDF.

**Vastu**
15. Upload a plan → Vastu report → PDF.

**Site**
16. Add a daily report, an activity and a photo (Camera and Gallery).
17. Record a material entry, attendance, a quality check and a safety item.
18. Photo → **AI check** gives findings.

**AI Assistant**
19. Ask in English and in Tamil.
20. Run an estimate or plan question.
21. Ask a question about an uploaded document.

**Recycle Bin**
22. Delete a test task → it shows in the bin.
23. Restore it.
24. Delete it again → **Delete permanently** (type DELETE).

**Recover**
25. Settings → Backups → open the newest **predelete** backup → **Recover**.
26. The task shows as missing → Recover → it is back in the Recycle Bin → Restore.

**Invite**
27. Create an invite link → open it in another browser → sign up.
28. Owner: Users → Pending → Approve.
29. The new user sees only the allowed projects and modules.

**Backups**
30. Backup Now → the backup appears → Download works.

**Online**
31. `<Render address>/api/health` shows `1.7.5-phase7` and `"storage":"hf"`.
32. The Vercel address opens, login works, and you see the same projects.
33. On the phone: install the app, take a camera photo, and open an invite link from another phone.

**GitHub**
34. The repository on github.com has **no `.env`** file. Search the repository for "API_KEY=": only `.env.example` with empty values should appear.
