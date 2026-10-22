"""Nexora Build – Phase 1 automatic API test.
Start the app first (scripts\\start.bat), then in another CMD:
    cd /d C:\\PROJECTS\\Nexora_Build
    backend\\.venv\\Scripts\\activate
    python scripts\\smoke_test.py

It creates ONE test project named "SMOKE TEST" and archives it at the end
(data is never deleted, archived projects are hidden from lists).
"""
import getpass
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000"
ok_count, fail = 0, []


def check(name, cond, info=""):
    global ok_count
    if cond:
        ok_count += 1
        print(f"[OK]   {name}")
    else:
        fail.append(name)
        print(f"[FAIL] {name}  {info}")


import atexit
import subprocess
import time
from pathlib import Path

class Client(httpx.Client):
    """Slow answers (database waking up, AI providers) are retried once; a second timeout becomes a FAIL line
    instead of stopping the whole test."""
    def request(self, method, url, **kw):
        for attempt in (1, 2, 3):
            try:
                return super().request(method, url, **kw)
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                # the server closed an idle connection just as we reused it – simply send again on a new one
                if attempt < 3:
                    time.sleep(1)
                    continue
                return httpx.Response(599, json={"detail": f"connection dropped: {method} {url} ({type(e).__name__})"},
                                      request=httpx.Request(method, BASE + str(url)))
            except httpx.TimeoutException:
                if attempt == 1:
                    print(f"       (slow answer from {method} {url} – trying once more...)")
                    continue
                return httpx.Response(599, json={"detail": f"timed out: {method} {url}"}, request=httpx.Request(method, BASE + str(url)))
            except httpx.ConnectError:
                if server is not None and server.poll() is not None:
                    print("[FAIL] The test backend stopped. Its error is printed above – send it to Claude.")
                    sys.exit(1)
                if attempt < 3:
                    time.sleep(2)
                    continue
                raise


c = Client(base_url=BASE, timeout=90)
server = None
try:
    r = c.get("/api/health")
except httpx.ConnectError:
    # backend not running -> start it just for this test, stop it at the end
    print("Starting backend for the test (takes ~20 s)...")
    backend = Path(__file__).resolve().parent.parent / "backend"
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000", "--log-level", "warning", "--timeout-keep-alive", "30"],
                              cwd=str(backend))
    atexit.register(server.terminate)
    for _ in range(60):
        time.sleep(2)
        try:
            r = c.get("/api/health")
            break
        except httpx.ConnectError:
            if server.poll() is not None:
                sys.exit("[ERROR] Backend failed to start – see the error above.")
    else:
        sys.exit("[ERROR] Backend did not start in 2 minutes.")
check("health", r.status_code == 200 and r.json().get("status") == "ok", r.text)
check("backend is the Phase 7 version (not an old one still running)", "phase7" in r.json().get("version", ""), r.text)

login = input("Owner username [nishanth_s]: ").strip() or "nishanth_s"
pw = getpass.getpass("Owner password (hidden): ")
r = c.post("/api/auth/login", json={"login": login, "password": pw})
check("owner login", r.status_code == 200, r.text)
if r.status_code != 200:
    sys.exit("Cannot continue without login.")
c.headers["Authorization"] = "Bearer " + r.json()["token"]

r = c.post("/api/auth/login", json={"login": login, "password": "wrong-password-123"})
check("wrong password rejected", r.status_code == 401)

me = c.get("/api/auth/me").json()
check("me = owner + protected", me.get("role") == "owner" and me.get("is_protected") is True, str(me))

r = c.patch(f"/api/users/{me['id']}", json={"status": "deactivated"})
check("owner cannot be deactivated", r.status_code == 400, r.text)

s = c.get("/api/settings")
check("settings load", s.status_code == 200 and "units" in s.json(), s.text[:200])
r = c.put("/api/settings/section/units", json={"decimal_places": 2})
check("settings save", r.status_code == 200, r.text)

# leftovers from an earlier test that stopped half-way → archive them (hidden, never deleted)
for old in c.get("/api/projects?status=all&q=SMOKE").json().get("projects", []):
    if old.get("name") == "SMOKE TEST" and old.get("status") != "archived":
        c.patch(f"/api/projects/{old['id']}", json={"status": "archived"})

r = c.post("/api/projects", json={"name": "SMOKE TEST", "project_type": "residential", "location": "Thanjavur",
                                  "district": "Thanjavur", "plot_width": 30, "plot_length": 40, "unit": "ft",
                                  "facing": "east", "floors": "G+1", "start_date": "2026-10-20", "end_date": "2027-04-30"})
check("create project", r.status_code == 200, r.text)
pid = r.json().get("id")


def _archive_test_project():
    """Always hide the test project, even if the test stops half-way."""
    try:
        c.patch(f"/api/projects/{pid}", json={"status": "archived"})
    except Exception:
        pass


if pid:
    atexit.register(_archive_test_project)

r = c.post("/api/projects", json={"name": "Bad dates", "start_date": "2027-01-01", "end_date": "2026-01-01"})
check("bad dates rejected", r.status_code == 400, r.text)

r = c.patch(f"/api/projects/{pid}", json={"progress": 10, "client_name": "Test Client"})
check("update project", r.status_code == 200 and r.json().get("progress") == 10, r.text)

pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
r = c.post(f"/api/files/project/{pid}", data={"category": "drawing"}, files={"file": ("smoke_plan.pdf", pdf, "application/pdf")})
check("upload PDF", r.status_code == 200, r.text)
fid = r.json().get("id")
r = c.post(f"/api/files/project/{pid}", data={"category": "drawing"}, files={"file": ("house.dwg", b"AC1032xxxx", "application/octet-stream")})
check("DWG gives convert message", r.status_code == 415 and "DXF" in r.text, r.text)
r = c.get(f"/api/files/{fid}/download")
check("download file", r.status_code == 200 and r.content == pdf)

d = c.get(f"/api/projects/{pid}").json()
check("project detail + activity", d["project"]["id"] == pid and len(d["activity"]) >= 2, str(d)[:200])

r = c.get("/api/users/access/matrix")
check("access matrix", r.status_code == 200, r.text[:200])

before = len(c.get("/api/admin/backups").json().get("backups", []))
r = c.post("/api/admin/backups")
check("backup started", r.status_code == 200, r.text)
print("       waiting for the backup to finish (runs in the background)...")
done = False
for _ in range(100):
    time.sleep(3)
    bl = c.get("/api/admin/backups").json()
    if not (bl.get("running") or {}).get("running") and len(bl.get("backups", [])) > before:
        done = True
        break
check("backup finished", done, str((bl.get("running") or {}).get("error", "")) if not done else "")
r = c.get("/api/admin/audit?per_page=5")
check("audit log", r.status_code == 200 and r.json()["total"] > 0)

# ---------------- Phase 2: estimate ----------------
r = c.get("/api/rates?state=Tamil Nadu")
check("rate library (TN)", r.status_code == 200 and len(r.json()["items"]) > 50, r.text[:200])
r = c.get("/api/rates?state=Kerala")
check("other state falls back to TN", r.status_code == 200 and r.json()["using_fallback"] is True)
r = c.get(f"/api/projects/{pid}/estimate-defaults")
check("estimate defaults", r.status_code == 200 and len(r.json()["inputs"]["floor_areas_sqft"]) == 2, r.text[:200])
inp = r.json()["inputs"]
r = c.post(f"/api/projects/{pid}/estimate/calculate", json={"inputs": {**inp, "floor_areas_sqft": [0, 0]}})
check("missing info asks questions", r.status_code == 422 and "questions" in r.text, r.text[:200])
inp.update({"floor_areas_sqft": [1000, 1000], "bedrooms": 3, "toilets": 3})
r = c.post(f"/api/projects/{pid}/estimate/calculate", json={"inputs": inp})
ok = r.status_code == 200
check("quick estimate calculates", ok, r.text[:300])
if ok:
    t = r.json()["totals"]
    print(f"       -> Rs {t['grand_total']:,.0f} | Rs {t['cost_per_sqft']:,.0f}/sqft | cement {t['cement_bags']} bags | steel {t['steel_kg']} kg")
    check("cost per sqft in sane range (1200-4000)", 1200 <= t["cost_per_sqft"] <= 4000, str(t["cost_per_sqft"]))
r = c.post(f"/api/projects/{pid}/estimates", json={"inputs": inp, "title": "SMOKE estimate"})
check("save estimate version", r.status_code == 200 and r.json().get("version", 0) >= 1, r.text[:200])
eid = r.json().get("id")
r = c.get(f"/api/projects/{pid}/estimates")
check("list versions", r.status_code == 200 and len(r.json()) >= 1)
r = c.get(f"/api/estimates/{eid}/excel")
check("Excel export", r.status_code == 200 and r.content[:2] == b"PK", r.text[:200] if r.status_code != 200 else "")
r = c.get(f"/api/estimates/{eid}/pdf")
check("PDF export", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")

# ---------------- Phase 3: design studio ----------------
r = c.post(f"/api/projects/{pid}/design/parse", json={"text": "20x40 4 rooms north facing"})
check("design asks when info is missing", r.status_code == 200 and len(r.json()["questions"]) >= 2 and r.json()["requirements"] is None, r.text[:200])
r = c.post(f"/api/projects/{pid}/design/parse", json={"text": "30x40 east facing 2BHK, car parking, G+1, 30 ft road"})
req = r.json().get("requirements") if r.status_code == 200 else None
check("design understands the request", bool(req) and len(req["levels"]) == 2, r.text[:200])
r = c.post(f"/api/projects/{pid}/design/generate", json={"requirements": req})
plan = r.json() if r.status_code == 200 else None
check("plan generated", bool(plan) and plan["summary"]["bedrooms"] == 2, r.text[:300])
if plan:
    check("TN setbacks applied (front 3 m for 30 ft road)", plan["setbacks"]["m"]["front"] == 3.0, str(plan["setbacks"]["m"]))
    check("walls, doors, windows derived", all(l["walls"] and l["openings"] for l in plan["levels"]))
    r = c.post(f"/api/projects/{pid}/design/quick-estimate", json={"plan": plan})
    check("quick estimate from drawing", r.status_code == 200 and r.json()["totals"]["grand_total"] > 0, r.text[:200])
    edited = json.loads(json.dumps(plan))
    rm = edited["levels"][0]["rooms"][0]
    rm["d"] = max(4, rm["d"] - 1)
    r = c.post(f"/api/projects/{pid}/design/recompute", json={"plan": edited})
    check("edited plan recomputed", r.status_code == 200 and "summary" in r.json(), r.text[:200])
    r = c.post(f"/api/projects/{pid}/designs", json={"plan": plan, "title": "SMOKE design"})
    d1 = r.json().get("id") if r.status_code == 200 else None
    check("save design version", bool(d1), r.text[:200])
    r = c.post(f"/api/projects/{pid}/designs", json={"plan": edited, "title": "SMOKE design edited", "source": "edited", "parent_id": d1})
    d2 = r.json().get("id") if r.status_code == 200 else None
    check("save second version", bool(d2), r.text[:200])
    r = c.get(f"/api/designs/compare?a={d1}&b={d2}")
    check("compare revisions", r.status_code == 200 and "totals" in r.json(), r.text[:200])
    r = c.get(f"/api/designs/{d2}/pdf")
    check("plan PDF export", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
    r = c.get(f"/api/designs/{d2}/dxf")
    check("plan DXF export", r.status_code == 200 and b"ENTITIES" in r.content, r.text[:200] if r.status_code != 200 else "")
    r = c.get(f"/api/designs/{d2}/estimate-inputs")
    ok = r.status_code == 200 and "geometry" in r.json()["inputs"]
    check("estimate inputs from design", ok, r.text[:200])
    if ok:
        r = c.post(f"/api/projects/{pid}/estimate/calculate", json={"inputs": r.json()["inputs"]})
        check("full estimate from design", r.status_code == 200 and r.json()["totals"]["grand_total"] > 0, r.text[:200])
# ---------------- Phase 4: drawing upload + vastu ----------------
if plan and d2:
    dxf = c.get(f"/api/designs/{d2}/dxf").content
    r = c.post(f"/api/projects/{pid}/drawings/upload", files={"file": ("smoke_plan.dxf", dxf, "image/vnd.dxf")})
    an = r.json() if r.status_code == 200 else {}
    check("DXF drawing read (rooms found)", r.status_code == 200 and an.get("rooms", 0) >= 6, r.text[:300])
    if an:
        check("north arrow read from the DXF (90 = east facing)", an["result"].get("north_deg") == 90, str(an["result"].get("north_deg")))
    if an:
        r = c.post(f"/api/analyses/{an['id']}/rescale", json={"units": "ft"})
        check("DXF units confirmed", r.status_code == 200, r.text[:200])
        res = r.json()["result"] if r.status_code == 200 else an["result"]
        levels = [{"name": g["name"], "rooms": [x for x in res["rooms"] if x.get("group") == g["id"] and x["placed"]]}
                  for g in res.get("groups", [])]
        check("floors detected on the sheet", len(levels) == 2, str(res.get("groups")))
        r = c.post(f"/api/analyses/{an['id']}/confirm", json={"levels": levels, "title": "SMOKE upload",
                   "opts": {"north_deg": 90, "plot_w_ft": 30, "plot_d_ft": 40, "road_width_m": 9.14}})
        up = r.json() if r.status_code == 200 else {}
        check("drawing confirmed -> design", bool(up.get("id")) and up["plan"]["facing"] == "east", r.text[:300])
        if up:
            r = c.post(f"/api/projects/{pid}/vastu/analyse", json={"design_id": up["id"]})
            ok = r.status_code == 200 and r.json()["result"]["summary"]["total"] >= 8
            check("vastu analysis", ok, r.text[:300])
            r = c.post(f"/api/projects/{pid}/vastu/apply", json={"design_id": up["id"]})
            check("vastu apply suggestions", r.status_code == 200 and "after" in r.json(), r.text[:200])
            r = c.post(f"/api/projects/{pid}/vastu/reports", json={"design_id": up["id"], "north_deg": 90})
            rid = r.json().get("id") if r.status_code == 200 else None
            check("vastu report saved", bool(rid), r.text[:200])
            r = c.get(f"/api/vastu/reports/{rid}/pdf")
            check("vastu report PDF", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
    pdfp = c.get(f"/api/designs/{d2}/pdf").content
    r = c.post(f"/api/projects/{pid}/drawings/upload", files={"file": ("smoke_plan.pdf", pdfp, "application/pdf")})
    check("vector PDF drawing read", r.status_code == 200 and r.json().get("method") == "pdf" and r.json().get("rooms", 0) >= 4,
          r.text[:300])

# ---------------- Phase 5: schedule, tasks, approvals, site ----------------
import base64
from datetime import date as _date
r = c.post(f"/api/projects/{pid}/schedule/template")
sch = r.json() if r.status_code == 200 else {}
check("schedule from template", len(sch.get("stages", [])) >= 10, r.text[:300])
if sch.get("stages"):
    st0 = sch["stages"][0]["id"]
    r = c.patch(f"/api/schedule/stages/{st0}", json={"progress": 100})
    check("stage progress update", r.status_code == 200 and r.json()["status"] == "completed", r.text[:200])
    pr = c.get(f"/api/projects/{pid}").json()["project"]["progress"]
    check("project progress follows schedule", pr > 0, str(pr))
r = c.post(f"/api/projects/{pid}/tasks", json={"title": "SMOKE task", "due_date": str(_date.today())})
tid = r.json().get("id") if r.status_code == 200 else None
check("task created", bool(tid), r.text[:200])
r = c.patch(f"/api/tasks/{tid}", json={"status": "completed"})
check("task completed", r.status_code == 200 and r.json()["status"] == "completed", r.text[:200])
r = c.post(f"/api/projects/{pid}/approvals", json={"title": "SMOKE floor plan", "item_type": "drawing"})
aid = r.json().get("id") if r.status_code == 200 else None
check("approval requested", bool(aid), r.text[:200])
r = c.post(f"/api/approvals/{aid}/decide", json={"status": "approved", "comment": "ok"})
check("approval decided", r.status_code == 200 and r.json()["status"] == "approved", r.text[:200])
today = str(_date.today())
r = c.put(f"/api/projects/{pid}/site/report", json={"report_date": today, "weather": "Sunny", "work_done": "Column casting"})
check("daily report saved", r.status_code == 200 and r.json()["saved"], r.text[:200])
stage_id = sch["stages"][3]["id"] if len(sch.get("stages", [])) > 3 else None
r = c.post(f"/api/projects/{pid}/site/activities", json={"title": "RCC Column Casting", "status": "in_progress",
           "progress": 60, "stage_id": stage_id, "stage_progress": 60})
check("site activity added", r.status_code == 200, r.text[:200])
png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
r = c.post(f"/api/projects/{pid}/site/photos", files={"file": ("smoke.png", png, "image/png")}, data={"caption": "Column rebar"})
check("site photo uploaded", r.status_code == 200 and r.json().get("url"), r.text[:200])
r = c.post(f"/api/projects/{pid}/site/materials", json={"code": "cement", "qty": 100, "kind": "received", "supplier": "ABC"})
check("material received", r.status_code == 200, r.text[:200])
r = c.get(f"/api/projects/{pid}/site/materials")
cem = next((m for m in r.json().get("items", []) if m.get("code") == "cement"), None) if r.status_code == 200 else None
check("material vs estimate", bool(cem) and cem["received"] >= 100 and cem["planned"] > 0, r.text[:300])
w1 = c.post(f"/api/projects/{pid}/site/workers", json={"name": "Ramesh", "trade": "mason"}).json()
w2 = c.post(f"/api/projects/{pid}/site/workers", json={"name": "Kumar", "trade": "helper_m"}).json()
r = c.post(f"/api/projects/{pid}/site/attendance", json={"work_date": today, "entries": [
    {"worker_id": w1.get("id"), "status": "present"}, {"worker_id": w2.get("id"), "status": "half"}]})
check("attendance saved", r.status_code == 200 and r.json()["summary"]["present"] == 1.5, r.text[:300])
r = c.get(f"/api/projects/{pid}/site/quality")
qc = r.json() if r.status_code == 200 else []
check("quality checklist", len(qc) >= 10, r.text[:200])
if qc:
    r = c.patch(f"/api/site/quality/{qc[0]['id']}", json={"status": "checked", "remarks": "ok"})
    check("quality check marked", r.status_code == 200 and r.json()["status"] == "checked", r.text[:200])
r = c.post(f"/api/projects/{pid}/site/safety", json={"kind": "delay", "title": "Steel delivery late", "delay_days": 2})
check("issue recorded", r.status_code == 200 and r.json()["status"] == "open", r.text[:200])
r = c.get(f"/api/projects/{pid}/site/overview")
ov = r.json() if r.status_code == 200 else {}
check("site overview", ov.get("cards", {}).get("issues") == 1 and ov["cards"]["workers"] == 1.5 and len(ov.get("gantt", [])) >= 10,
      r.text[:300])
r = c.get(f"/api/projects/{pid}/site/dpr.pdf")
check("DPR PDF", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
r = c.get(f"/api/projects/{pid}/site/report.xlsx")
check("site Excel report", r.status_code == 200 and r.content[:2] == b"PK", r.text[:200] if r.status_code != 200 else "")
r = c.put(f"/api/projects/{pid}/site/location", json={"latitude": 11.0168, "longitude": 76.9558})
check("site location saved", r.status_code == 200, r.text[:200])

r = c.post(f"/api/projects/{pid}/estimate/excel-template", json={"inputs": {"floor_areas_sqft": [1000, 1000], "bedrooms": 3, "toilets": 3}})
check("Excel input template", r.status_code == 200 and r.content[:2] == b"PK", r.text[:200] if r.status_code != 200 else "")
if r.status_code == 200:
    r2 = c.post(f"/api/projects/{pid}/estimate/excel-import", files={"file": ("inputs.xlsx", r.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"state": "Tamil Nadu"})
    check("Excel input read back", r2.status_code == 200 and r2.json()["inputs"].get("floor_areas_sqft") == [1000, 1000]
          and r2.json()["rates_changed"] == 0, r2.text[:300])

# ---------------- Phase 6.6: Recycle Bin, invites, BBS, plan approval, photo check
r = c.post(f"/api/projects/{pid}/tasks", json={"title": "SMOKE bin test"})
tid = r.json().get("id") if r.status_code == 200 else None
r = c.post(f"/api/trash/task/{tid}")
check("delete -> Recycle Bin", r.status_code == 200, r.text[:200])
r = c.get("/api/trash")
check("item listed in the bin", r.status_code == 200 and any(i["entity"] == "task" and i["id"] == tid for i in r.json()["items"]), r.text[:200])
r = c.post(f"/api/trash/task/{tid}/restore")
ok_restore = r.status_code == 200 and any(t["id"] == tid for t in c.get(f"/api/projects/{pid}/tasks").json())
check("restore from bin", ok_restore, r.text[:200])
c.post(f"/api/trash/task/{tid}")
r = c.post(f"/api/trash/task/{tid}/purge", timeout=300)
check("delete permanently (backup taken first)", r.status_code == 200 and r.json().get("deleted") == 1, r.text[:300])

# ---------------- Phase 7.2: Home site-weather card data
r = c.get(f"/api/projects/{pid}/weather-context")
check("home weather card data", r.status_code == 200 and "stages" in r.json() and "curing" in r.json(), r.text[:200])

# ---------------- Phase 7.8: weather alerts (bell + phone push)
r = c.get("/api/push/key")
check("push key ready", r.status_code == 200 and len(r.json().get("public_key", "")) > 80, r.text[:200])
r = c.get("/api/alerts/cron-key")
key = r.json().get("key") if r.status_code == 200 else ""
check("daily alert link key", bool(key), r.text[:200])
r = c.get("/api/alerts/run", params={"key": "wrong"})
check("daily alert link refuses a wrong key", r.status_code == 403, r.text[:200])
r = c.get("/api/alerts/today", timeout=60)
check("today's weather alerts (bell)", r.status_code == 200 and "items" in r.json(), r.text[:200])

# ---------------- Phase 7: recover a permanently deleted item from its "predelete" backup
bk = [b for b in c.get("/api/admin/backups").json()["backups"] if b["kind"] == "predelete"]
check("predelete backup exists", bool(bk))
if bk:
    r = c.get(f"/api/admin/backups/{bk[0]['id']}/compare", timeout=300)
    miss = {t["table"]: t["missing"] for t in r.json().get("tables", [])} if r.status_code == 200 else {}
    check("backup compare finds the deleted task", miss.get("tasks", 0) >= 1, r.text[:300])
    r = c.post(f"/api/admin/backups/{bk[0]['id']}/recover", json={"tables": ["tasks"]}, timeout=300)
    check("recover from backup", r.status_code == 200 and r.json().get("restored", {}).get("tasks", 0) >= 1, r.text[:300])
    r = c.get("/api/trash")
    back = r.status_code == 200 and any(i["entity"] == "task" and i["id"] == tid for i in r.json()["items"])
    check("recovered task is back in the Recycle Bin", back, r.text[:200])
    if back:
        c.post(f"/api/trash/task/{tid}/purge", timeout=300)  # clean up again
r = c.post("/api/invites", json={"label": "SMOKE invite", "job_title": "Site Engineer", "access": {str(pid): {"view": True, "site": True}}})
inv = r.json() if r.status_code == 200 else {}
check("invite link created", bool(inv.get("token")), r.text[:200])
r = c.get(f"/api/invites/open/{inv.get('token')}")
check("invite link opens (no login)", r.status_code == 200 and r.json().get("job_title") == "Site Engineer", r.text[:200])
r = c.post(f"/api/invites/open/{inv.get('token')}/join", json={"full_name": "Smoke Tester", "username": "smoke_x", "password": "short"})
check("join form checks the password", r.status_code == 400, r.text[:200])
c.patch(f"/api/invites/{inv.get('id')}", json={"is_active": False})
r = c.get(f"/api/invites/open/{inv.get('token')}")
check("stopped invite link refused", r.status_code == 404, r.text[:200])
r = c.get("/api/notifications")
check("notifications", r.status_code == 200 and "items" in r.json(), r.text[:200])
col = {"type": "column", "mark": "C1", "count": 10, "b": 230, "d": 380, "height": 3000, "floors": 2, "cover": 40,
       "main": [{"dia": 16, "nos": 4}, {"dia": 12, "nos": 4}], "tie_dia": 8, "tie_spacing": 150, "footing_depth": 450, "bottom_bend": 300}
r = c.post(f"/api/projects/{pid}/bbs/calculate", json={"members": [{"type": "column", "mark": "C2", "b": 230}]})
check("BBS asks for missing sizes", r.status_code == 422 and "questions" in r.text, r.text[:200])
r = c.post(f"/api/projects/{pid}/bbs", json={"title": "SMOKE BBS", "members": [col]})
bb = r.json() if r.status_code == 200 else {}
check("BBS saved", bb.get("total_kg", 0) > 0, r.text[:200])
r = c.get(f"/api/bbs/{bb.get('id')}/pdf")
check("BBS PDF with drawings", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
r = c.get(f"/api/bbs/{bb.get('id')}/excel")
check("BBS Excel", r.status_code == 200 and r.content[:2] == b"PK", r.text[:200] if r.status_code != 200 else "")
r = c.get(f"/api/projects/{pid}/permit")
pm6 = r.json() if r.status_code == 200 else {}
check("plan approval checklist", len(pm6.get("items", [])) >= 10, r.text[:200])
if pm6.get("items"):
    items = pm6["items"]
    items[0]["status"] = "collected"
    r = c.put(f"/api/projects/{pid}/permit", json={"items": items, "application_no": "SMOKE-1"})
    check("checklist updated", r.status_code == 200 and r.json()["done"] >= 1, r.text[:200])
r = c.get(f"/api/projects/{pid}/permit/pack.zip")
check("document pack ZIP", r.status_code == 200 and r.content[:2] == b"PK", r.text[:200] if r.status_code != 200 else "")
r = c.post("/api/ai/photo-check", json={"file_id": fid})
check("photo check refuses non-photos", r.status_code == 415, r.text[:200])

# ---------------- Phase 6: AI assistant
r = c.get("/api/ai/status")
st6 = r.json() if r.status_code == 200 else {}
check("AI status", r.status_code == 200, r.text[:200])
if not st6.get("any"):
    print("       (no AI keys in .env – answers will use Nexora's calculated results only)")
r = c.get(f"/api/ai/meta?project_id={pid}")
m6 = r.json() if r.status_code == 200 else {}
check("AI agents + calculators + material guide", len(m6.get("agents", [])) == 8 and len(m6.get("calculators", [])) >= 10
      and len(m6.get("material_guide", [])) >= 8, r.text[:200])
r = c.post("/api/ai/calc", json={"kind": "concrete", "params": {"volume_m3": 1, "grade": "M20"}})
check("calculator: 1 m3 M20 = 9 bags", r.status_code == 200 and r.json()["results"][0]["value"] == 9, r.text[:200])

def chat6(body):
    rr = c.post("/api/ai/chat", json=body, timeout=180)
    return rr, (rr.json() if rr.status_code == 200 else {})

r, j = chat6({"project_id": pid, "agent": "quantity", "text": "", "form": {"tool": "calc", "kind": "concrete",
             "params": {"length": 10, "width": 12, "depth": 0.5, "unit": "ft"}, "label": "Concrete for slab"}})
conv6 = (j.get("conversation") or {}).get("id")
check("AI chat: calculator card", r.status_code == 200 and any(cd["type"] == "calc" for cd in j["assistant_message"]["cards"]),
      r.text[:300])
r, j = chat6({"conversation_id": conv6, "text": "", "form": {"tool": "plan", "label": "Plan details", "answers": {
    "plot_w_ft": 30, "plot_d_ft": 40, "facing": "east", "road_width_ft": 30, "floors": 2, "bedrooms": 2}}})
cards6 = j.get("assistant_message", {}).get("cards", [])
plan6 = next((cd for cd in cards6 if cd["type"] == "plan"), None)
check("AI chat: floor plan + quantities", bool(plan6) and plan6.get("estimate", {}).get("totals", {}).get("grand_total", 0) > 0,
      r.text[:300])
r, j = chat6({"conversation_id": conv6, "text": "", "form": {"tool": "vastu", "label": "Check Vastu"}})
check("AI chat: Vastu of that plan", any(cd["type"] == "vastu" for cd in j.get("assistant_message", {}).get("cards", [])), r.text[:300])
r, j = chat6({"conversation_id": conv6, "text": "", "form": {"tool": "estimate", "label": "Estimate", "answers": {
    "builtup_sqft": 1000, "floors": 1, "bedrooms": 2, "toilets": 2, "spec_level": "standard"}}})
check("AI chat: estimate from area", any(cd["type"] == "estimate" for cd in j.get("assistant_message", {}).get("cards", [])),
      r.text[:300])
r, j = chat6({"conversation_id": conv6, "text": "20x40, 4 rooms - cost?"})
qs6 = [cd for cd in j.get("assistant_message", {}).get("cards", []) if cd["type"] == "questions"]
check("AI asks instead of guessing ('4 rooms')", r.status_code == 200 and (bool(qs6) or "?" in j["assistant_message"]["content"]),
      r.text[:300])
mid6 = j.get("assistant_message", {}).get("id")
r = c.post(f"/api/ai/messages/{mid6}/feedback", json={"value": 1})
check("AI feedback saved", r.status_code == 200, r.text[:200])
r = c.post("/api/ai/upload", data={"project_id": str(pid)},
           files={"file": ("smoke_spec.txt", b"Specification: cement shall be PPC. Steel shall be Fe500D TMT. Curing 10 days.", "text/plain")})
check("AI document upload", r.status_code == 200, r.text[:200])
r = c.post(f"/api/ai/docs/index?project_id={pid}", timeout=180)
check("document indexed", r.status_code == 200 and any(f["name"] == "smoke_spec.txt" and f["status"] == "indexed"
                                                       for f in r.json().get("files", [])), r.text[:300])
r, j = chat6({"conversation_id": conv6, "text": "", "form": {"tool": "docs", "label": "Ask documents",
                                                            "args": {"query": "which steel grade"}}})
check("Document Q&A finds the answer", any(s.get("kind") == "doc" for s in j.get("assistant_message", {}).get("sources", [])),
      r.text[:300])
if st6.get("any"):
    t6 = c.get("/api/ai/status?test=true", timeout=180).json().get("test", {})
    for prov, res in t6.items():
        print(f"       AI {prov}: {res}")
    r, j = chat6({"conversation_id": conv6, "text": "OPC vs PPC for coastal area?"})
    am = j.get("assistant_message") or {}
    if am.get("provider"):
        check("AI provider answered", True)
    elif any("limit" in n for n in am.get("notes", [])) or any("429" in str(v) for v in t6.values()):
        print("[WARN] AI provider answered – free AI limit reached right now (many test questions in one minute). "
              "Not counted as a failure; try a question in the app after a minute.")
    else:
        check("AI provider answered", False, "; ".join(am.get("notes", [])) or r.text[:300])
r = c.get(f"/api/ai/conversations?project_id={pid}")
check("conversation history", r.status_code == 200 and any(x["id"] == conv6 for x in r.json()), r.text[:200])
r = c.post(f"/api/ai/conversations/{conv6}/hide")
check("conversation hidden (kept)", r.status_code == 200, r.text[:200])

r = c.post(f"/api/projects/{pid}/design/generate", json={"requirements": {**(req or {}), "plot_w_ft": 20, "plot_d_ft": 30,
           "levels": [{"name": "Ground Floor", "bedrooms": 3, "attached_toilets": 3, "common_toilets": 0, "kitchen": True, "hall": True, "dining": True}]}})
check("too many rooms -> options offered", r.status_code == 422 and "suggestions" in r.text, r.text[:200])

r = c.patch(f"/api/projects/{pid}", json={"status": "archived"})
check("archive test project", r.status_code == 200, r.text)
lst = c.get("/api/projects").json()["projects"]
check("archived project hidden from list", all(p["id"] != pid for p in lst))

print()
print(f"{ok_count} passed, {len(fail)} failed")
if fail:
    print("Failed:", ", ".join(fail), "\nSend this output to Claude.")
    sys.exit(1)
else:
    print("PHASE 1 - 7 API: ALL GOOD")
