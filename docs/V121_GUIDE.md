# Nexora Build 1.21 – Plan view (furnished plan, 2D + 3D)

Design → **3D** tab → new button **Plan view (furnished)**.

## What it shows
One floor seen from the top, like a brochure plan – but made from YOUR plan, so every size is exact.

| Part | Where it comes from |
|---|---|
| Rooms, walls, doors, windows | The plan (same as the drawings) |
| Furniture | Furniture engine – per room type, placed by the room's size, doors and windows |
| Car / bike | Only when the plan has a parking room; size decides 1 car, 2 cars or bikes |
| Staircase | Steps, landing and UP arrow from the staircase design |
| Plants, lawn, compound wall, gate, driveway | Ground floor only – the same choices as "Trees & plants" |
| Colours, floor finishes, furniture colours | The elevation style + materials finalised in 3D |
| Room name + size | From the plan – feet-inch (10'-0" X 12'-0") or metre |

Furniture rules: never in a door swing or walking gap, tall pieces (wardrobe, fridge, TV) never in front of a
window, small rooms get smaller pieces or none. Furniture is a layout idea – it is not in the estimate.

## Controls
- **Floor** – any floor. Several houses on one floor are all shown.
- **2D rendered plan | 3D top cutaway** – 2D is a sharp vector drawing; 3D is the real model with walls cut at
  1.2 m, real light and shadows. In 3D you can still rotate / zoom; Reset returns to the top.
- **Room names & sizes** on / off, **Feet-inch / Metre**.
- **PNG (4K)**, **PDF (A3)** – of what is selected (2D or 3D).
- **AI polish** (optional, free – same Cloudflare / Gemini set-up as AI Render): the picture goes to the AI
  WITHOUT words; room names and sizes are written afterwards from the plan, and the result is marked
  "AI concept render – not to scale". If the AI moves a wall, slide towards "Exactly my design".

## Also changed
- Interior, Walkthrough and Exterior views use the same furniture engine (furniture no longer blocks doors).
- Car in 3D is where the engine parks it; the walkthrough stops you at it.

## Update
`scripts\update.bat` → must end with **NEXORA 1.21 API: ALL GOOD** → `scripts\github_push.bat`.
No new keys, no database change.
