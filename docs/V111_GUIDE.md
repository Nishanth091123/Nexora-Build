# Nexora Build 1.11 – Part 4: 3D Visualization

Version **1.11.0**. This version adds the **three.js** 3D library. `update.bat` installs it automatically the first time; that run takes 1–2 minutes longer.

## Design → 3D View (new)
A real 3D model (WebGL) built from your plan.
- **What the model shows:**
  - Plinth, and walls with door and window openings
  - Glass windows with frames, wooden doors, sunshades (chajja)
  - Floor slabs, a two-flight staircase with landing, parapet, staircase head room
  - Parking columns
  - Furniture: bed, wardrobe, sofa, dining, kitchen counter, WC, basin, car
  - Surroundings: plot, compound wall with gate, road, trees
- **View modes:**
  - **Exterior**.
  - **Interior**: the top floor is cut at 4.5 ft and the roof is off, so you see the rooms from above.
  - **Walkthrough**: you stand at the main door at eye height. W/S or ↑/↓ to walk, A/D or ←/→ to turn, drag to look.
  - **Exploded**: the floors are separated.
- **Camera:** 3D, Front, Left side, Right side, Rear, Top. Drag to rotate, scroll to zoom, right-drag to pan.
- **Floors:** show "Ground only", "First only"…, or "Up to" a floor.
- **Display options:** furniture, surroundings, roof/terrace, **section cut** (half building), wireframe, auto rotate. **Day / Night** shows lights inside at night.
- **Material & colour options:** exterior walls (cream, white, grey, beige, light blue, brick, stone), interior walls, flooring (vitrified, marble, granite, wood, kota), doors, window frames, terrace, plinth. They are saved with the design (press **Save**).
- **Export:** **Image (PNG)**, **3D model (GLB)** (opens in Windows 3D Viewer / Blender / SketchUp import), **Video**: a 15-second turntable WebM, best in Chrome or Edge.

This is a concept visual for clients. It is not a photo-real render.

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
scripts\github_push.bat
```
It must end with **NEXORA 1.11 API: ALL GOOD**. If you added `RENDER_DEPLOY_HOOK` to `.env`, the push also updates Render by itself.

## Test checklist
1. Design → open a saved design → **3D View** → the house appears with the road, compound wall and trees.
2. Click Front / Left side / Rear / Top.
3. Interior View → you see the rooms with furniture from above.
4. Walkthrough → press W to walk in through the main door.
5. Exterior walls → Brick → Save → reopen the design: it is still brick.
6. Image (PNG) and 3D model (GLB) downloads work. The video gives a .webm file after 15 seconds.
7. Night → the windows glow from inside.

## 1.11.1 – the "hang" fix
- **Cause:** on every start, the backend (on your PC and on Render) removed and re-created the delete-protection triggers on about 35 tables in one step. That needs an exclusive lock on every table. With the PC test server and the Render server using the same Neon database, the locks waited for each other, so a simple save (Site → Workers) hung for 811 seconds. The site tests after it failed for the same reason.
- **Fix:** triggers are now created only when they are missing, each with a 5-second lock limit. Starting a server never blocks the database any more. The protection itself is unchanged.
- The smoke test now removes its test items from the Recycle Bin together at the end, with one safety backup instead of three. That saves about 3–4 minutes.

## 1.11.2 – AI never waits for minutes
- **Cause:** the free AI services were slow or stuck that morning. One chat tried up to 9 models with a 90-second wait each, so the test waited 180 s and the next AI tests failed one after another.
- **Fix:** each AI request now has a total time limit across all providers: picking the tool 15 s, writing the answer 35 s, with at most 30 s per model. When the time is up, the app shows Nexora's own calculated answer (calculator, plan, Vastu, estimate cards still appear) with the note "AI service not reachable".
