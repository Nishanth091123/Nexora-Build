# Nexora Build 1.8 – Part 1: Clients & Projects (owner only)

Version **1.8.0**. Nothing that already works is changed. Existing data stays as it was; new tables and columns are only added.

## What's new
- **Clients** (new menu item, only you see it). Each client has an ID (C-001…), phone, email, address, location and notes.
  - Clients List with search by name, phone or town.
  - Client Documents: Land (Sale Deed, Patta, Chitta, FMB), Site, ID proof, Others. Only you can open these files.
  - Projects List of the selected client, plus **New Project** for that client.
  - **Project Files & Drawings** folders: Architectural, Structural, Estimation (BOQ), Vastu, Approval, Photos, Others.
  - **Project Progress Tracker:** Client Meeting → Site Survey → 2D Design → Structural → Estimation → Vastu Check → Approval Drawing → Submission → Completed. Tap a step to mark it done with a date.
  - **Notes & Activity History** for each project (Add Note).
  - Stats: Total Clients, Total Projects, In Progress, Completed, Submitted, On Hold.
- **Old projects:** a project that already had a typed client name gets a client record automatically on the first start.
- **New Project form:** the Client box suggests your saved clients. A new name makes a new client.
- **Owner-only modules** (Settings → Project Access, top card). Switch ON Design / Estimate / Vastu / Site / AI and only you see that module. Other users lose it from the menu and the server blocks it, even if it was ticked for them. All switches start OFF, so nothing changes for your team until you switch one on.
- **Company:** Settings → Company now has **Proprietor**. It is set to **Praganya Construction · Nishanth S** if it was empty. You can edit it.

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
```
It must end with **NEXORA 1.8 API: ALL GOOD**. Then:
```
scripts\github_push.bat
```
Render and Vercel update themselves in about 5 minutes.

## Test checklist
1. The menu shows **Clients** (owner). Log in as another user: no Clients item.
2. Clients → **New Client** → save → it appears in the list with C-00x.
3. Upload a Patta PDF under Land Documents → Download works.
4. **New Project** from the client → it appears in the client's Projects List.
5. Tap "Client Meeting" in the Progress Tracker → Mark done → it turns green with the date.
6. Add Note → it shows in Notes & Activity History.
7. Settings → Project Access → switch **Vastu** ON → another user no longer sees Vastu. Switch it OFF again.
8. Settings → Company shows Praganya Construction and Proprietor Nishanth S.
9. Delete a test client → it goes to the Recycle Bin → Restore works.
