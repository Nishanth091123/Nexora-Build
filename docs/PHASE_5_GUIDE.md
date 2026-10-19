# Nexora Build – Phase 5 (Site + Projects + Offline)

## Fixes from your Phase 4 check
- **Vastu "Get Improved Plan"** can now also move the staircase (single-floor plans), the living hall (only if the main
  door still works), the passage and the store. After applying, it lists **what is still left to fix by hand**.
  The entrance follows the road side, so it can only change with a different door position.
- **North arrow** is read automatically from DXF / PDF drawings (Phase 4.1).
- **Home page**: the "Welcome back" picture is no longer cropped. It is taller and shows the whole house on big screens.

## New in Phase 5 – Site Management (the approved Site screen)
- **Top bar**:
  - The **site date** picker lets you view or enter any past day.
  - **Add Site Update** (activity, photos, material, attendance, quality, issue, DPR).
- **Overview**:
  - **Project Progress**: the % ring, On Track / Delayed status, plan-vs-actual days ahead or behind, and the Foundation → Columns → Slab → Finishing → Handover steps.
  - Cards for Today's Work, On Site Today, Material Received (% of the estimate) and Issues / Delays.
  - **Current Site Status** (with photo), **Today's Activities** (tick to complete), Site Photos, **Material Tracking** bars,
    **Manpower** by trade with today's attendance, the **Quality Check** list, **Site Timeline (Gantt)**,
    **Site Location & Map** (OpenStreetMap; "Use my current location"), and **Site Insights**.
  - Site Insights covers schedule ahead / behind, next focus, cement use vs estimate, pending or failed checks, open issues, and a rain forecast from the free weather service.
- **Daily Work**:
  - **Daily Progress Report**: weather, work done, tomorrow's plan, remarks, and a **DPR PDF**.
  - **Activities**: location, schedule stage, status, progress and photo. They can also update the stage progress, which moves the project % automatically.
- **Site Photos**: several photos at once from the camera or gallery, with caption, date, location and GPS. Grouped by date, with an enlarged view.
- **Quality Check**:
  - A 15-point standard checklist (foundation → services) with each tolerance, e.g. column plumb 5 mm in 3 m, cover 20/25/40 mm, M20 slump, 48-hour ponding test.
  - Mark each check OK / Fail / Pending with remarks. You can add your own checks.
- **Material Tracking**:
  - Record material **received / used** with rate, supplier and bill number.
  - **Planned (from your latest saved estimate) vs received vs used vs stock at site.**
- **Manpower**:
  - Register workers once: mason, helper (chithal), bar bender, carpenter… with wage, phone and maistry.
  - Then mark daily **P / ½ / A + OT hours**. You see today's count per trade and the wages total. Wages come from the rate library unless a worker has their own.
- **Safety**: toolbox talks, PPE checks, inspections, near misses, incidents, **site issues and delays** (with delay days). Close each one with the action taken.
- **Reports**: DPR PDF for any day, and a **Site Excel report** for any period.
  - The Excel sheets are schedule, activities, daily reports, materials, attendance matrix with wages, quality, and safety & issues.

## New in Phase 5 – Projects
- **Schedule (Gantt)**:
  - "Create schedule" builds the standard house programme from the project's floors and start / end dates: site preparation → foundation → plinth → columns & slab per floor → brick work → services → plastering → flooring → painting → handover.
  - Edit names, dates, weights, milestones and progress (Milestones tab). Overall project progress and On Track / Delayed status now follow the schedule automatically.
- **Stage-wise progress** in Project Details, and the **Milestones** card.
- **Task Management**: add, assign, set due date and priority, start, and complete (tick). Overdue tasks show in red.
- **Approvals**:
  - Request an approval for a drawing, estimate, design, material or other item, and choose the approver.
  - The owner or the chosen approver can **Approve / Ask changes / Reject** with a comment. The full history is kept.

## Offline (installable app)
- Pages and data you have opened are **kept on the device**, so the app still opens without signal.
- **Site updates made without signal are kept on the device.** These are activities, photos, attendance, materials, checks, issues, DPR and tasks. They are **sent automatically when the connection returns**; a bar shows "N updates waiting" with a **Send now** button.
- On a PC / phone browser you can **install** it ("Install app" / "Add to Home screen"). It has its own icon.
- Note: browsers allow offline mode, install and GPS only on **https** or **localhost**.
  On your PC (localhost) it works now. Phones on Wi-Fi over plain http won't get offline mode or GPS.
  They will on the real https address after deployment in Phase 7.

## Install (one CMD window)
1. Close all Nexora CMD windows.
2. Extract `Nexora_Build_Phase5.zip` to `C:\PROJECTS` and choose Replace.
3. Run:
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
```
This adds 11 new tables (schedule, tasks, approvals, daily reports, activities, photos, materials, workers, attendance,
quality, safety) and 2 project columns (site latitude / longitude). Nothing is deleted.
The last line should be `PHASE 1 - 5 API: ALL GOOD`.
Then start the app with `scripts\start.bat`.

## Test checklist
```
[ ] 1. Home – the welcome picture shows the whole house (no bad crop)
[ ] 2. Vastu – BAD drawing (north 315°) → Get Vastu Improved Plan → more rules matched + "still to fix by hand" list
[ ] 3. Projects → Milestones tab → Create schedule → Gantt + table; change a stage progress → overall % and Gantt update
[ ] 4. Projects dashboard: Gantt, Milestones, Tasks (add / tick), Approvals (request → owner Approve / Ask changes)
[ ] 5. Site → Overview: Project Progress steps, 4 cards, empty cards guide you to add data
[ ] 6. Add Site Update → Activity with photo + "also set stage progress" → Overview shows it with the photo
[ ] 7. Site Photos: upload 2–3 photos at once; open one; date grouping
[ ] 8. Daily Work: fill the DPR → Save → DPR PDF opens with activities, manpower, materials, photos
[ ] 9. Manpower: add 3 workers → mark P / ½ / A → Save → wages total; Overview shows the attendance
[ ] 10. Material Tracking: record cement received 100 bags → planned vs received % (needs a saved estimate)
[ ] 11. Quality Check: mark 2 OK, 1 Fail → Overview + insights show it
[ ] 12. Safety: add a delay (2 days) → Issues card = 1 → Close it with an action
[ ] 13. Site Location: "Use my current location" → map appears; insights show the rain forecast
[ ] 14. Reports: Excel for this month opens with all sheets
[ ] 15. Offline: open Site once, then switch Wi-Fi off → reload → app still opens with the offline bar;
        add an activity → "saved on this device"; Wi-Fi on → "1 offline update sent"
[ ] 16. Change the site date to yesterday → entries are saved on that date
```
