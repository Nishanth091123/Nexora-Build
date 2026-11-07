# Nexora Build 1.20 – Realistic 3D + free AI Render

Version **1.20.0** (it includes everything from 1.19). No database change. No new Python or npm packages.

## Before you update – Cloudflare keys (only for AI Render)
Put these two lines in `C:\PROJECTS\Nexora_Build\.env`, and add the same two on **Render → nexora-build-api →
Environment**:
```
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_AI_TOKEN=your_workers_ai_token
```
Never send them in chat. Without them everything else works; only AI Render says "not set up".

## Option 1 – more realistic 3D (free, inside the app)
- **New style "Luxury"** (first in the style list), the look of today's modern Indian elevations:
  - white **curved frame band** round the upper floors at the front;
  - white **CNC jaali screens** with black frames in front of the upper-floor front windows;
  - **frameless glass railings** with a slim steel top rail and **flower planter boxes**;
  - **wooden louvre ceilings with downlights** over balconies / sit-outs;
  - a **stone cladding strip** where the staircase / toilets meet the front; smooth putty everywhere else;
  - **up-down wall lights** beside the windows – at Evening / Night they glow and wash the wall;
  - a **flower bed with garden spike lights** inside the front compound wall, and a white compound wall.
- **All styles:**
  - stone, wood and pavers now have **relief** (joints and grain catch the light);
  - interiors in Modern / Luxury get a **gypsum false-ceiling border with a warm cove light** and **skirting** in the
    hall, bedrooms and dining.
- **Photo mode (HD)** now adds **realistic shading** (soft contact shadows in corners, window reveals and under the
  slabs). If a computer's graphics card cannot do it, the normal photo is saved – never a broken picture.
- **Plan engine:** a hall / bedroom on the road side now gets its window on the **front wall** (before, it could go on
  the side wall and the front elevation looked blank). The plan sweep is still 0 closed rooms.

## Option 2 – AI Render (free)
1. Open **Design → 3D**, choose a style, light and camera angle (Exterior, or Interior / Walkthrough for inside).
2. Press **AI Render (photo)**.
3. Optional: type what to add (e.g. "grey granite steps, pink bougainvillea, rainy evening").
4. Set **Keep my design ↔ More creative**. Keep it high to stay close to your drawing.
5. Press **Make AI render** and wait 20–60 s. **Compare with 3D**, **Download**, or press again for another try.

How it works:
- **Your 3D view is the base**, so the floors, windows and outline come from your drawing.
- **Free only:** Cloudflare Workers AI daily allowance, about 20–50 renders a day. It resets at 5:30 am India time.
  When the allowance is used up, the app says so.
- If Google gives your Gemini key free image quota, that is tried as a second option. Nothing is paid.
- Every render is stamped **"AI concept render – not to scale"**. It is for showing the client – the drawing stays
  the working document.

## Update
1. Add the Cloudflare lines to `.env` and to Render (above).
2. Run `scripts\update.bat`. It must end with **NEXORA 1.20 API: ALL GOOD**.
   - `scripts\update.bat --full` also makes one real AI render to test your Cloudflare token (uses 1 free render).
3. Then run `scripts\github_push.bat`.
