# Nexora Build – Phase 1 (Foundation)

## What's in Phase 1
- **Login / Register** – owner `nishanth_s` is created on first start; new users register and wait for your approval
- **Owner lock** – owner can never be deleted, deactivated or demoted (blocked in the app AND inside the database)
- **Data safety** – projects, files, logs, access rows can never be deleted (database triggers). "Delete" = hide / archive
- **Projects page** – stats, project cards with HD images, create / edit, project details, team, recent activity, document upload/download (PDF, PNG, JPG, DXF, Excel, Word; DWG → convert message)
- **Settings** – Company info + logo, Users (add / approve / deactivate / reset password), Roles, Project Access matrix (View, Edit, Design, Estimate, Site, Vastu, AI per user per project), Units, AI preferences, Notifications, Security (change password, session timeout, self-registration on/off), Backups (automatic daily + Backup Now + download), Audit Logs
- **8-page app shell** in the approved design – sidebar images change per page, Tamil / English toggle (த / EN button)
- Design, Site, Vastu, Estimate, AI pages show their layout with "Coming in Phase N" – built in later phases

## Step 1 – Copy files
Right-click `Nexora_Build_Phase1.zip` → **Extract All** → choose `C:\PROJECTS` → Extract → **Replace the files in the destination**.
It merges into `C:\PROJECTS\Nexora_Build`.
Your `.env` and images are NOT in the zip, so they stay safe.

## Step 2 – Setup (one time, ~5 minutes)
```
cd /d C:\PROJECTS\Nexora_Build
scripts\setup_phase1.bat
```
It installs backend + frontend packages and asks you:
- **Owner login email** (only if not already in .env)
- **Owner password** – type twice (hidden). This is your login password.

## Step 3 – Run (two CMD windows)
Window 1:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\run_backend.bat
```
Wait for `Ready. Storage backend: local`.

Window 2:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\run_frontend.bat
```
Open **http://localhost:5173** in Chrome. Login: `nishanth_s` + your password.

## Step 4 – Automatic API test (Window 3, backend must be running)
```
cd /d C:\PROJECTS\Nexora_Build
backend\.venv\Scripts\activate
python scripts\smoke_test.py
```
Expected last line: `PHASE 1 API: ALL GOOD`. (It creates a project "SMOKE TEST" and archives it.)

## Step 5 – Manual test checklist
```
[ ] 1. Login as nishanth_s works; wrong password shows an error
[ ] 2. Projects → New Project → create "30x40 Residential House" (Thanjavur) – card appears with image
[ ] 3. Click the card → Project Details shows plot, facing, dates; Edit → change progress to 20 → ring shows 20%
[ ] 4. Upload a PDF in "Project Drawings & Documents" → appears; click it → downloads
[ ] 5. Try uploading a .dwg → message to convert to DXF 2018 / vector PDF
[ ] 6. Top-right project selector switches between projects
[ ] 7. Settings → General → Company Information → Edit → save your company name; Change Logo works
[ ] 8. Settings → Users & Teams → Add User (test user) → appears Active
[ ] 9. Logout → Create account (another test user) → login says "waiting for approval"
[ ] 10. Login as owner → Users → Approve → that user can now log in but sees NO projects
[ ] 11. Settings → Project Access → tick View + Estimate for that user on one project → user now sees only that project
[ ] 12. Owner row has no Deactivate button (owner is permanent)
[ ] 13. Settings → Backups → Backup Now → a backup appears → Download works
[ ] 14. Settings → Audit Logs shows logins, uploads, approvals
[ ] 15. த button → menus switch to Tamil; EN → back to English
[ ] 16. Sidebar: Site page shows the construction image, Vastu page shows the sunset house
[ ] 17. Stop backend (Ctrl+C), start again → everything is still there (data in Neon)
[ ] 18. Mobile: Chrome → F12 → phone view → ☰ menu opens the sidebar
```
Reply with the checklist (✅/❌) + screenshot of any error.

## Notes
- Files are saved in `backend\storage` until Cloudflare R2 keys are added to `.env` (then new files go to R2 automatically).
- Users are never deleted – deactivate them.
- Your password can be changed in Settings → Security. `OWNER_INITIAL_PASSWORD` in .env is used only the very first time.
