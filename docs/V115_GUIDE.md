# Nexora Build 1.15 – corrections + Material Library

Version **1.15.0**. Existing data is not changed. One new table is added: `library_items` (your own materials).

## Corrections
1. **Window / door merge – fixed at the root.**
   - The floor-plan engine placed the hall window on the same wall as the main door, on top of it. It happened in 158 places across 248 test plans.
   - Now a window always goes to a free part of the wall (at least 1 ft away from a door). If that wall has no room, it goes to the next outside wall.
   - Two rooms can no longer put a door in the same spot.
   - Larger sizes typed in the door/window schedule cannot push a window into a door.
   - Fixed in the 2D plan, the elevation, the sheets and the 3D, because they all come from the same engine.
   - Tip: open an old design and press Save once to get the corrected positions.
2. **Interior view – one floor at a time.** Choose Ground / First / … above the 3D view. Only that floor is shown, with its walls cut at 4½ ft so you see the rooms and furniture.
3. **Walkthrough hang / blur:**
   - The house is now drawn as ~60 big pieces instead of ~700 small ones, so it is about 9× lighter for the graphics card.
   - The extra room lights are removed, because every light slows every pixel. Rooms are lit by a soft, even sky light.
   - If the laptop is slow, the view lowers its resolution a little to stay smooth, and goes back up when it can.
4. **Trees inside the house – fixed.** Trees and plants are placed only where they cannot touch the building or its roof overhang.
5. **Client documents removed.** The Clients page has no documents section any more (no upload, no checklist). Client details, projects, tracker and notes stay.

## Material Library (3D tab, below the view)
- **Parts of the house you can choose:**
  - Exterior walls, feature walls (front), plinth, terrace, doors, window frames, compound wall.
  - Interior walls, ceiling, flooring, toilet floor, toilet wall tiles (up to 7 ft), kitchen counter.
- **One room only:** pick a room, then give it its own wall colour or floor (e.g. the master bedroom in wooden flooring).
- **Built-in options:**
  - 17 paint colours.
  - Stone, slate, wood panels, grey tiles, brick, marble.
  - Vitrified, marble, granite, wooden, red oxide, Kota and anti-skid floors.
  - Wall tiles and mosaic.
  - Teak / walnut / oak / rosewood / laminate doors.
  - Aluminium / UPVC / wood frames.
  - Granite / quartz counters.
- **Add your own** (owner):
  - Any name, brand, **shade / product code**, colour picker, matt / satin / gloss, rate.
  - **Photo** of the tile / granite / stone / wood: upload it, or paste a picture link from a website. The 3D view lays that photo on the wall or floor. "The photo covers __ ft" sets the tile size.
  - Your items stay in the library for every project. Remove an item via Settings → Recycle Bin.
- The 3D view changes as you click. Picks are saved with the design (press Save).
- **Showcase:**
  - Every pick in one list: where it is used, the item, brand, shade code and rate, with a 3D picture on top.
  - **Download (PNG)** or **Print / Save as PDF** to show the client.

## Install
```
cd /d C:\PROJECTS\Nexora_Build
scripts\update.bat
scripts\github_push.bat
```
It must end with **NEXORA 1.15 API: ALL GOOD**.

If you see `getaddrinfo failed` again, it is the internet / DNS, not the app. Check the internet, run `ipconfig /flushdns`, or try a mobile hotspot, then run update.bat again.

## Test checklist
1. Open a design whose hall window touched the main door → Save → Drawing Sheets → Front Elevation: the door and window are apart.
2. 3D → **Interior** → click First Floor → only that floor shows.
3. 3D → **Walkthrough** → it is smooth, with no trees inside.
4. 3D → Material library:
   - Exterior walls → Sky blue; Feature walls → Exposed brick; Flooring → Black granite.
   - One room: Master bedroom → Floor → Wooden flooring.
5. **Add your own** → Floor tile, name + code + a photo → pick it for a room → the photo shows on the floor in 3D.
6. **Showcase** → Download PNG / Print.
7. **Clients:** no documents section.
