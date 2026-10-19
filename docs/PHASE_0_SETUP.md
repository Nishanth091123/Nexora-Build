# Nexora Build – Phase 0 Setup Guide

Goal of Phase 0: your laptop tools + all free accounts + API keys ready, and the 17 images placed.
No app code yet. Phase 1 starts after you send me "Phase 0 OK".

---

## Step 1 – Unzip
Unzip `Nexora_Build_Phase0.zip` into `C:\PROJECTS\` so you get:

```
C:\PROJECTS\Nexora_Build\
  frontend\public\images\   (17 HD images – already renamed)
  backend\                  (empty – Phase 1)
  docs\PHASE_0_SETUP.md     (this file)
  docs\mockups\             (6 UI reference screens)
  scripts\check_setup.bat
  .env.example
  .gitignore
```

## Step 2 – Install tools on the laptop (skip any you already have)
| Tool | Version | Download |
|---|---|---|
| Git | latest | https://git-scm.com/download/win |
| Node.js | 22 LTS | https://nodejs.org (choose LTS) |
| Python | 3.11 or 3.12 | https://www.python.org/downloads (tick "Add python.exe to PATH") |
| VS Code (optional) | latest | https://code.visualstudio.com |

Then open CMD and run:
```
cd C:\PROJECTS\Nexora_Build
scripts\check_setup.bat
```
All lines must show a version number. Send me a screenshot if anything says "NOT FOUND".

## Step 3 – Accounts (all free, login with the same Gmail)

### 3.1 GitHub repo
1. https://github.com/new
2. Repository name: `Nexora-Build` · **Private** · do NOT add README.
3. In CMD:
```
cd C:\PROJECTS\Nexora_Build
git init
git add .
git commit -m "Phase 0: project skeleton + images"
git branch -M main
git remote add origin https://github.com/Nishanth091123/Nexora-Build.git
git push -u origin main
```

### 3.2 Neon (database)
1. https://neon.com → Sign up with GitHub/Google.
2. Create project → Name `nexora-build` · Postgres 17 · Region **AWS Asia Pacific (Singapore)**.
3. Dashboard → **Connect** → copy the **pooled** connection string (starts with `postgresql://...`).
4. Paste it into `.env` as `DATABASE_URL` (Step 4).

### 3.3 Cloudflare R2 (files) – ⚠ needs a payment method
Cloudflare asks for a **card or PayPal** only to activate R2 (identity check; nothing is charged within the free 10 GB).
1. https://dash.cloudflare.com → sign up → left menu **R2 Object Storage** → activate.
2. Create bucket → `nexora-build-files` · Location: Automatic.
3. R2 → **Manage API tokens** → Create token → permission **Object Read & Write** → bucket `nexora-build-files`.
4. Copy: Account ID, Access Key ID, Secret Access Key → into `.env`.

👉 If you have **no card / PayPal**, tell me. The backend storage is S3-compatible, so I'll switch to another free provider without changing anything else.

### 3.4 Hugging Face (backend hosting)
1. https://huggingface.co/join
2. Settings → **Access Tokens** → New token → type **Write** → name `nexora-deploy` → copy into `.env` as `HF_TOKEN`.
3. Don't create the Space yet – I'll give exact steps in Phase 1.

### 3.5 Vercel (frontend hosting)
1. https://vercel.com/signup → **Continue with GitHub**.
2. Nothing else now – we'll import the repo in Phase 1.

### 3.6 LLM keys (all free)
| Key | Where | `.env` name |
|---|---|---|
| Gemini | https://aistudio.google.com/apikey → Create API key | `GEMINI_API_KEY` |
| Groq (LLM + Whisper voice) | https://console.groq.com/keys → Create API Key | `GROQ_API_KEY` |
| OpenRouter | https://openrouter.ai/keys → Create Key | `OPENROUTER_API_KEY` |

## Step 4 – Create your `.env`
```
cd C:\PROJECTS\Nexora_Build
copy .env.example .env
notepad .env
```
Fill every value, save. **Never upload `.env` to GitHub or send it in chat** – it's already in `.gitignore`.
For me, just reply with which keys are ready (✅/❌), not the keys themselves.

## Step 5 – Images (already done ✅)
| File | Used in |
|---|---|
| sidebar_main.jpg | Sidebar – Home, Design, Estimate, Projects, AI, Settings |
| sidebar_site.jpg | Sidebar – Site page |
| sidebar_vastu.jpg | Sidebar – Vastu page |
| proj_residential / proj_commercial / proj_warehouse / proj_road / proj_villa .jpg | Project cards |
| company_building.jpg | Settings → Company info |
| site_current.jpg | Site → Current status |
| site_column_rebar / site_rcc_casting / site_brickwork / site_material_stock / site_slab_formwork / site_electrical .jpg | Site photos |
| estimate_house.jpg | Estimate → Project overview (laptop with fake numbers cropped out) |

## Phase 0 checklist – reply with this
```
[ ] check_setup.bat – all versions shown
[ ] GitHub repo pushed
[ ] Neon DATABASE_URL in .env
[ ] R2 bucket + keys in .env   (or: "no card – use alternative")
[ ] HF write token in .env
[ ] Vercel account linked to GitHub
[ ] Gemini / Groq / OpenRouter keys in .env
```
