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

CLEANUP: list[dict] = []  # test items in the Recycle Bin, purged together at the end (one safety backup)
FULL = "--full" in sys.argv  # also test the live AI providers (slow: free AI services can take minutes)
T_START = time.perf_counter()
TIMES: list[tuple[float, str]] = []


class Client(httpx.Client):
    """Slow answers (database waking up) are retried once; a second timeout becomes a FAIL line
    instead of stopping the whole test. AI calls are never retried (that only doubled the wait)."""
    def request(self, method, url, **kw):
        t0 = time.perf_counter()
        try:
            return self._request(method, url, **kw)
        finally:
            TIMES.append((time.perf_counter() - t0, f"{method} {str(url).split('?')[0]}"))

    def _request(self, method, url, **kw):
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
                if attempt == 1 and not str(url).startswith("/api/ai/"):
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
_v = tuple(int(x) for x in (r.json().get("version", "0.0").split("-")[0].split(".") + ["0", "0"])[:3] if x.isdigit())
check("backend is the 1.18 version (not an old one still running)", _v >= (1, 18, 0), r.text)

login = input("Owner username [nishanth_s]: ").strip() or "nishanth_s"
pw = getpass.getpass("Owner password (hidden): ")
r = c.post("/api/auth/login", json={"login": login, "password": pw})
check("owner login", r.status_code == 200, r.text)
if r.status_code != 200:
    sys.exit("Cannot continue without login.")
c.headers["Authorization"] = "Bearer " + r.json()["token"]
_lat = []
for _ in range(3):
    _t = time.perf_counter()
    c.get("/api/auth/me")
    _lat.append((time.perf_counter() - _t) * 1000)
_ms = min(_lat)
print(f"       Database speed: one simple request = {_ms:.0f} ms" + (
      "  (slow internet to the online database – the whole test will take longer)" if _ms > 800 else ""))
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
check("1.16 separate Approval + Material Rates permissions", r.status_code == 200 and {"approval", "rates"} <= set(r.json().get("modules", [])), r.text[:200])
pp = c.get("/api/projects").json()["projects"]
mine = next((x for x in pp if x["id"] == pid), {})
check("1.16 owner has Approval + Rates", (mine.get("permissions") or {}).get("approval") is True and (mine.get("permissions") or {}).get("rates") is True, str(mine.get("permissions")))
check("1.16 no client record made for a typed client name", mine.get("client_id") in (None, 0), str(mine.get("client_id")))

_bk = c.get("/api/admin/backups").json().get("backups", [])
before = _bk[0]["id"] if _bk else 0  # the list shows only the newest 60, so compare the newest id (not the count)
r = c.post("/api/admin/backups")
check("backup started", r.status_code == 200, r.text)
print("       waiting for the backup to finish (runs in the background)...")
done = False
for _ in range(100):
    time.sleep(3)
    bl = c.get("/api/admin/backups").json()
    _new = bl.get("backups", [])
    if not (bl.get("running") or {}).get("running") and _new and _new[0]["id"] != before:
        done = True
        break
check("backup finished", done, str((bl.get("running") or {}).get("error", "")) if not done else "")
r = c.get("/api/admin/audit?per_page=5")
check("audit log", r.status_code == 200 and r.json()["total"] > 0)

# ---------------- Phase 2: estimate ----------------
r = c.get("/api/rates?state=Tamil Nadu")
check("rate library (TN)", r.status_code == 200 and len(r.json()["items"]) > 50, r.text[:200])
check("1.16 owner sees the rupee values", r.status_code == 200 and r.json().get("locked") is False and r.json()["items"][0].get("standard") is not None, r.text[:200])
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
# ---------------- 1.8 Part 2: estimate upgrade ----------------
r = c.post(f"/api/projects/{pid}/estimates", json={"inputs": inp, "title": "SMOKE estimate 1.8"})
e18 = r.json() if r.status_code == 200 else {}
res18 = e18.get("result") or {}
check("floor-wise BOQ", len(res18.get("floor_boq", {}).get("rows", [])) > 10, str(res18.get("floor_boq"))[:200])
check("area statement", len(res18.get("area_statement", [])) == len(inp.get("floor_areas_sqft", [])) and
      all(0 < a["carpet_sqft"] < a["builtup_sqft"] for a in res18.get("area_statement", [])), str(res18.get("area_statement"))[:200])
ps18 = res18.get("payment_schedule", [])
check("payment schedule = 100%", abs(sum(x["pct"] for x in ps18) - 100) < 0.01 and all("amount" in x for x in ps18), str(ps18)[:200])
check("key quantities", len(res18.get("key_quantities", [])) >= 6, str(res18.get("key_quantities"))[:200])
for fmt in ("bank", "client"):
    r = c.get(f"/api/estimates/{e18.get('id')}/pdf?fmt={fmt}")
    check(f"{fmt} PDF", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
r = c.get(f"/api/estimates/{e18.get('id')}/excel")
check("Excel has floor-wise BOQ", r.status_code == 200 and b"Floor-wise BOQ" in __import__("zipfile").ZipFile(__import__("io").BytesIO(r.content)).read("xl/workbook.xml"),
      r.text[:200] if r.status_code != 200 else "")
# ---------------- 1.13: estimate download without saving + old estimates get the floor-wise BOQ ----------------
for kind, magic in (("bank", b"%PDF"), ("excel", b"PK")):
    r = c.post(f"/api/projects/{pid}/estimate/export?kind={kind}", json={"inputs": inp, "state": "Tamil Nadu"})
    check(f"1.13 estimate {kind} download without saving", r.status_code == 200 and r.content[:len(magic)] == magic, r.text[:200] if r.status_code != 200 else "")
# ---------------- 1.16: download under every tab + part estimate ----------------
for tab, fmt, magic in (("overview", "pdf", b"%PDF"), ("floorboq", "excel", b"PK"), ("takeoff", "pdf", b"%PDF"), ("material", "excel", b"PK"),
                        ("cost", "pdf", b"%PDF"), ("boq", "pdf", b"%PDF"), ("payment", "pdf", b"%PDF"), ("compare", "excel", b"PK")):
    r = c.post(f"/api/projects/{pid}/estimate/tab-export?tab={tab}&fmt={fmt}", json={"inputs": inp, "state": "Tamil Nadu"}, timeout=120)
    check(f"1.16 estimate tab download ({tab} {fmt})", r.status_code == 200 and r.content[:len(magic)] == magic, r.text[:200] if r.status_code != 200 else "")
r = c.post(f"/api/projects/{pid}/estimate/part", json={"inputs": inp, "state": "Tamil Nadu", "floor": "Ground Floor", "work": "slab"})
pt = r.json() if r.status_code == 200 else {}
check("1.16 part estimate (Ground Floor slab)", bool(pt.get("items")) and all(i["floor"] == "Ground Floor" for i in pt["items"])
      and any(k["name"] == "Cement" for k in pt.get("key_materials", [])) and pt["totals"]["total"] > 0, r.text[:300])
r = c.post(f"/api/projects/{pid}/estimate/part?fmt=pdf", json={"inputs": inp, "state": "Tamil Nadu", "floor": "Ground Floor", "work": "slab"})
check("1.16 part estimate PDF", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
check("1.16 file name has project code + name", "Ground_Floor_Slab_Estimate.pdf" in r.headers.get("content-disposition", ""), r.headers.get("content-disposition", ""))
r = c.post(f"/api/projects/{pid}/estimate/part", json={"inputs": inp, "state": "Tamil Nadu", "floor": "all", "work": "bad"})
check("1.16 part estimate refuses an unknown work", r.status_code == 400, r.text[:200])
r = c.get(f"/api/estimates/{eid}")
check("1.13 saved estimate shows floor-wise BOQ + payment schedule", r.status_code == 200 and r.json()["result"].get("floor_boq") and r.json()["result"].get("payment_schedule"), r.text[:200])
custom = [{"stage": "Advance", "pct": 20}, {"stage": "Structure", "pct": 50}, {"stage": "Finishing", "pct": 30}]
r = c.post(f"/api/projects/{pid}/estimate/calculate", json={"inputs": {**inp, "payment_schedule": custom}, "state": "Tamil Nadu"})
check("custom payment schedule", r.status_code == 200 and [x["pct"] for x in r.json()["payment_schedule"]] == [20, 50, 30], r.text[:200])
# ---------------- 1.18: my own quantity wins (Manual), the auto value is kept ----------------
it0 = (r.json().get("items") or [{}])[0] if r.status_code == 200 else {}
r = c.post(f"/api/projects/{pid}/estimate/calculate", json={"inputs": {**inp, "qty_overrides": {it0.get("key", "?"): 12.5}}, "state": "Tamil Nadu"})
m0 = next((i for i in r.json().get("items", []) if i.get("key") == it0.get("key")), {}) if r.status_code == 200 else {}
check("1.18 manual quantity used, auto kept", m0.get("manual") and m0.get("qty") == 12.5 and m0.get("auto_qty") == it0.get("qty"), str(m0)[:200])
r = c.post(f"/api/projects/{pid}/estimate/quick", json={"builtup_sqft": 2400, "floors": 2, "bedrooms": 3, "toilets": 3})
qk = r.json() if r.status_code == 200 else {}
check("quick estimate: Economy < Standard < Premium", bool(qk) and qk["specs"]["basic"]["grand_total"] < qk["specs"]["standard"]["grand_total"]
      < qk["specs"]["premium"]["grand_total"], r.text[:200])
r = c.post(f"/api/projects/{pid}/estimate/quick", json={"builtup_sqft": 2400, "floors": 2, "bedrooms": 0, "toilets": 0})
check("quick estimate asks for rooms", r.status_code == 422, r.text[:200])
was_es = c.get("/api/estimate-settings").json()
r = c.put("/api/estimate-settings", json={"gst_pct": 12, "contractor_margin_pct": 10, "contingency_pct": None})
check("estimate defaults saved", r.status_code == 200 and r.json()["gst_pct"] == 12, r.text[:200])
r = c.get(f"/api/projects/{pid}/estimate-defaults")
check("defaults used for new estimate", r.status_code == 200 and r.json()["inputs"]["gst_pct"] == 12, r.text[:200])
c.put("/api/estimate-settings", json={k: was_es.get(k) for k in ("gst_pct", "contractor_margin_pct", "contingency_pct")})
r = c.post(f"/api/files/project/{pid}", data={"category": "loan_boq"}, files={"file": ("boq.pdf", pdf, "application/pdf")})
check("loan document upload", r.status_code == 200, r.text[:200])
r = c.get(f"/api/projects/{pid}/loan-docs")
check("loan checklist shows it", r.status_code == 200 and any(i["key"] == "boq" and i["status"] == "uploaded" for i in r.json()["items"]), r.text[:200])

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
    # ---------------- 1.17: every room can be entered; never through another bedroom ----------------
    acc = [w for w in plan.get("warnings", []) if "cannot be reached" in w or "no access" in w]
    check("1.17 every room has a door / opening from a common area", not acc, "; ".join(acc)[:300])
    # ---------------- 1.17: roofing sheets ----------------
    top = plan["levels"][-1]
    st_ = next((q for q in top["rooms"] if q["type"] == "stair"), None)
    rp = json.loads(json.dumps(plan))
    rp["roof_sheets"] = [{"place": "on_terrace", "level": len(rp["levels"]) - 1, "x": 1, "y": 8, "w": 15, "d": 12, "sheet": "galvalume",
                          "thk_mm": 0.47, "shape": "gable", "ridge": "x", "slope_deg": 15, "height_ft": 9, "bogus": 1},
                         {"place": "nowhere", "sheet": "gi"}]
    if st_:
        rp["roof_sheets"].append({"place": "headroom", "level": len(rp["levels"]) - 1, "x": st_["x"], "y": st_["y"], "w": st_["w"], "d": st_["d"],
                                  "sheet": "acc", "shape": "mono", "high": "back", "slope_deg": 12})
    r = c.post(f"/api/projects/{pid}/design/recompute", json={"plan": rp})
    rp2 = r.json() if r.status_code == 200 else {}
    rs_ = rp2.get("roof_sheets") or []
    check("1.17 roof sheets saved with the design (and cleaned)", len(rs_) == (2 if st_ else 1) and "bogus" not in rs_[0]
          and rs_[0]["truss"]["purlin_ft"] == 4.0, str(rs_)[:300])
    if rs_:
        for q, magic in (("kind=sheets_pdf&page=roof", b"%PDF"), ("kind=sheets_pdf&page=truss", b"%PDF"), ("kind=sheets_dxf", b"SECTION")):
            r = c.post(f"/api/projects/{pid}/design/export?{q}", json={"plan": rp2}, timeout=180)
            check(f"1.17 roof sheet drawing ({q})", r.status_code == 200 and magic in r.content[:200], r.text[:200] if r.status_code != 200 else "")
        r = c.post(f"/api/projects/{pid}/design/quick-estimate", json={"plan": rp2})
        qi = r.json().get("inputs", {}) if r.status_code == 200 else {}
        check("1.17 estimate inputs carry the sheet roofs", len(qi.get("roof_sheets") or []) == len(rs_)
              and any(b_["group"] == "Roofing" for b_ in r.json().get("breakdown", [])), r.text[:200])
        r = c.post(f"/api/projects/{pid}/estimate/part", json={"inputs": qi, "state": "Tamil Nadu", "floor": "all", "work": "roofing"})
        its = r.json().get("items", []) if r.status_code == 200 else []
        check("1.17 part estimate: roofing sheet (sheet + steel)", any(i["unit"] == "kg" for i in its) and any(i["unit"] == "m²" for i in its), r.text[:200])
        r = c.post(f"/api/projects/{pid}/vastu/analyse", json={"plan": rp2})
        check("1.17 vastu checks the sheet roof slope", r.status_code == 200 and any(ch["rule"] == "roof_slope" for ch in r.json()["result"]["checks"]), r.text[:200])
        full = json.loads(json.dumps(plan))
        full["roof_sheets"] = [{"place": "full_roof", "level": len(full["levels"]) - 1, "x": 0, "y": 0, "w": full["building"]["w"], "d": full["building"]["d"],
                                "sheet": "galvalume", "shape": "gable", "ridge": "y", "slope_deg": 18}]
        r = c.post(f"/api/projects/{pid}/design/recompute", json={"plan": full})
        r = c.post(f"/api/projects/{pid}/design/quick-estimate", json={"plan": r.json() if r.status_code == 200 else full})
        qi = r.json().get("inputs", {}) if r.status_code == 200 else {}
        top_name = full["levels"][-1]["name"]
        r = c.post(f"/api/projects/{pid}/estimate/part", json={"inputs": qi, "state": "Tamil Nadu", "floor": top_name, "work": "slab"})
        its = r.json().get("items", []) if r.status_code == 200 else None
        check("1.17 full sheet roof: no RCC roof slab on the top floor", its is not None and not any("Roof slab" in i["description"] for i in its), r.text[:200])
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
    # ---------------- 1.18: one active drawing for every module ----------------
    r = c.get(f"/api/projects/{pid}/active-design")
    check("1.18 newest saved design is the active drawing", r.status_code == 200 and (r.json().get("design") or {}).get("id") == d2, r.text[:200])
    r = c.put(f"/api/projects/{pid}/active-design", json={"design_id": d1})
    check("1.18 owner picks the active drawing ('Use everywhere')", r.status_code == 200, r.text[:200])
    r = c.get(f"/api/projects/{pid}/estimate-defaults")
    check("1.18 estimate knows the active drawing (no manual sizes asked)", r.status_code == 200 and (r.json().get("active_design") or {}).get("id") == d1, r.text[:200])
    r = c.get(f"/api/projects/{pid}/designs")
    check("1.18 design list marks the active one", r.status_code == 200 and [x["id"] for x in r.json() if x.get("active")] == [d1], r.text[:200])
    c.put(f"/api/projects/{pid}/active-design", json={"design_id": d2})
    # ---------------- 1.18: staircase design ----------------
    r = c.post(f"/api/projects/{pid}/design/stair", json={"plan": plan, "opts": {}})
    sd = r.json() if r.status_code == 200 else {}
    check("1.18 staircase designed (risers, checks, waist slab, BBS)", sd.get("risers", 0) >= 15 and len(sd.get("checks", [])) >= 6
          and sd.get("structure", {}).get("waist_mm", 0) >= 150 and len(sd.get("bbs", [])) >= 4, r.text[:300])
    r = c.post(f"/api/projects/{pid}/design/stair", json={"plan": plan, "opts": {"type": "straight"}})
    check("1.18 staircase warns (long straight flight) – never blocks", r.status_code == 200 and any(not x["ok"] for x in r.json()["checks"]), r.text[:200])
    st_plan = json.loads(json.dumps(plan)); st_plan["stair"] = {"type": "dog_legged", "riser_mm": 999, "railing": "ss"}
    r = c.post(f"/api/projects/{pid}/design/recompute", json={"plan": st_plan})
    check("1.18 staircase values checked (riser 999 refused)", r.status_code == 422, r.text[:200])
    st_plan["stair"] = {"type": "dog_legged", "finish": "granite", "railing": "ss", "bogus": 1}
    r = c.post(f"/api/projects/{pid}/design/recompute", json={"plan": st_plan})
    check("1.18 staircase choices saved (and cleaned)", r.status_code == 200 and r.json().get("stair", {}).get("type") == "dog_legged"
          and "bogus" not in r.json().get("stair", {}), r.text[:200])
    r = c.post(f"/api/projects/{pid}/design/export?kind=sheets_pdf&page=stair", json={"plan": plan}, timeout=180)
    check("1.18 Staircase Detail sheet", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
    r = c.post(f"/api/projects/{pid}/design/quick-estimate", json={"plan": plan})
    qi = r.json().get("inputs", {}) if r.status_code == 200 else {}
    check("1.18 estimate inputs carry the designed staircase", (qi.get("stair") or {}).get("concrete_m3", 0) > 0, str(qi.get("stair"))[:200])
    r = c.post(f"/api/projects/{pid}/estimate/part", json={"inputs": qi, "state": "Tamil Nadu", "floor": "all", "work": "staircase"})
    its = r.json().get("items", []) if r.status_code == 200 else []
    check("1.18 staircase in the estimate (concrete, steel, railing)", any("railing" in i["description"].lower() for i in its)
          and any(i["unit"] == "kg" for i in its), r.text[:200])
    # ---------------- 1.18: irregular plot ----------------
    rq = dict(req, plot_shape={"mode": "quad", "sides": [30, 42, 34, 40]})
    r = c.post(f"/api/projects/{pid}/design/generate", json={"requirements": rq})
    check("1.18 irregular plot: asks the diagonal (never guesses the shape)", r.status_code == 422 and "diagonal" in r.text.lower(), r.text[:200])
    rq["plot_shape"]["diagonal"] = 52
    r = c.post(f"/api/projects/{pid}/design/generate", json={"requirements": rq})
    ip = r.json() if r.status_code == 200 else {}
    check("1.18 irregular plot planned (polygon + setbacks from every side)", len((ip.get("plot") or {}).get("poly") or []) == 4
          and ip.get("setbacks", {}).get("edge_kinds", [None])[0] == "road" and ip["building"]["w"] >= 10, r.text[:300])
    if ip:
        r = c.post(f"/api/projects/{pid}/design/export?kind=sheets_pdf&page=site", json={"plan": ip}, timeout=180)
        check("1.18 irregular plot site plan", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
        r = c.post(f"/api/projects/{pid}/vastu/analyse", json={"plan": ip})
        check("1.18 vastu reads the plot shape", r.status_code == 200, r.text[:200])
    # ---------------- 1.18: auto + manual ----------------
    r = c.post(f"/api/projects/{pid}/design/generate", json={"requirements": dict(req, setback_override={"front": 6})})
    mp = r.json() if r.status_code == 200 else {}
    check("1.18 manual setback used (auto kept for the check)", mp.get("setbacks", {}).get("ft", {}).get("front") == 6
          and "front" in mp.get("setbacks", {}).get("manual", []), r.text[:200])
    r = c.get(f"/api/designs/{d2}/pdf")
    check("plan PDF export", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
    r = c.get(f"/api/designs/{d2}/dxf")
    check("plan DXF export", r.status_code == 200 and b"ENTITIES" in r.content, r.text[:200] if r.status_code != 200 else "")
    # ---------------- 1.10 Part 3: drawing sheets ----------------
    r = c.post(f"/api/projects/{pid}/design/sheets-preview", json={"plan": plan})
    sv = r.json() if r.status_code == 200 else {}
    check("door & window schedule", any(x["mark"] == "D1" for x in sv.get("schedule", [])) and
          any(x["mark"].startswith("W") for x in sv.get("schedule", [])), r.text[:200])
    check("elevation + section drawings", all(k in sv.get("svgs", {}) for k in ("site", "elevation", "section", "plan_0")), r.text[:200])
    check("area details (FSI, coverage)", sv.get("area", {}).get("fsi", 0) > 0 and 0 < sv.get("area", {}).get("coverage_pct", 0) < 100, str(sv.get("area"))[:200])
    sp = json.loads(json.dumps(plan))
    sp["opening_specs"] = {"main_door": {"w_ft": 4, "h_ft": 7.5, "material": "Teak"}}
    r = c.post(f"/api/projects/{pid}/design/recompute", json={"plan": sp})
    md = [o for o in r.json()["levels"][0]["openings"] if o["type"] == "main_door"] if r.status_code == 200 else []
    check("door size from schedule", bool(md) and md[0]["w"] == 4 and md[0]["h"] == 7.5, r.text[:200])
    r = c.get(f"/api/designs/{d2}/sheets.pdf")
    check("A3 drawing set PDF", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
    r = c.get(f"/api/designs/{d2}/sheets.dxf")
    check("drawing set DXF", r.status_code == 200 and b"SECTION A-A" in r.content, r.text[:200] if r.status_code != 200 else "")
    # ---------------- 1.11 Part 4: 3D colours are kept with the design ----------------
    p3 = json.loads(json.dumps(plan))
    p3["finishes"] = {"ext": "#b5654a", "floor": "#f5f5f4", "bad": "red", "door": "javascript:x"}
    r = c.post(f"/api/projects/{pid}/designs", json={"plan": p3, "title": "SMOKE 3D colours"})
    f3 = (r.json().get("plan") or {}).get("finishes", {}) if r.status_code == 200 else {}
    check("3D colours saved (and cleaned)", f3 == {"ext": "#b5654a", "floor": "#f5f5f4"}, r.text[:200])
    # ---------------- 1.12 Part 5: structural (preliminary) + CAD colours ----------------
    r = c.get(f"/api/designs/{d2}/sheets.pdf?style=cad")
    check("drawing set PDF in CAD colours", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
    r = c.post(f"/api/projects/{pid}/structural/calculate", json={"design_id": d2, "inputs": {}})
    check("structural asks for soil SBC + seismic zone", r.status_code == 422 and "bearing" in r.text, r.text[:200])
    r = c.post(f"/api/projects/{pid}/structural", json={"design_id": d2, "inputs": {"sbc_kn_m2": 150, "seismic_zone": "III"}}, timeout=180)
    sd = r.json() if r.status_code == 200 else {}
    res5 = sd.get("result") or {}
    check("structural design (columns, beams, slabs, footings)", all(res5.get("summary", {}).get(k, 0) > 0 for k in ("columns", "beams", "slabs", "footings")), r.text[:200])
    check("structural drawings", "columns" in (sd.get("previews") or {}) and "foundation" in (sd.get("previews") or {}), r.text[:200])
    if sd.get("id"):
        for path, magic in (("pdf", b"%PDF"), ("pdf?style=cad", b"%PDF"), ("dxf", b"SECTION")):
            r = c.get(f"/api/structural/{sd['id']}/{path}", timeout=180)
            check(f"structural {path}", r.status_code == 200 and magic in r.content[:200], r.text[:200] if r.status_code != 200 else "")
    # ---------------- 1.13: downloads from the screen (no save), one sheet, 3D style ----------------
    for q, magic in (("kind=plan_pdf", b"%PDF"), ("kind=sheets_pdf&page=elevation", b"%PDF"), ("kind=sheets_pdf&page=plan_0&style=cad", b"%PDF"), ("kind=sheets_dxf", b"SECTION")):
        r = c.post(f"/api/projects/{pid}/design/export?{q}", json={"plan": plan}, timeout=180)
        check(f"1.13 design download ({q})", r.status_code == 200 and magic in r.content[:200], r.text[:200] if r.status_code != 200 else "")
    if sd.get("id"):
        for q in ("kind=pdf&page=columns", "kind=pdf&page=notes", "kind=dxf"):
            r = c.post(f"/api/projects/{pid}/structural/export?{q}", json={"design_id": d2, "inputs": {"sbc_kn_m2": 150, "seismic_zone": "III"}}, timeout=180)
            check(f"1.13 structural download ({q})", r.status_code == 200 and (b"%PDF" in r.content[:10] or b"SECTION" in r.content[:200]), r.text[:200] if r.status_code != 200 else "")
    # ---------------- 1.14 Part 6: approval drawing ----------------
    r = c.get(f"/api/projects/{pid}/approval")
    ap0 = r.json() if r.status_code == 200 else {}
    check("1.14 approval details load", r.status_code == 200 and len(ap0.get("stages", [])) == 7, r.text[:200])
    r = c.post(f"/api/projects/{pid}/approval/sheet?kind=pdf", json={"plan": plan, "site_info": {"owner_name": ""}}, timeout=180)
    check("1.14 approval drawing asks for owner / survey no. (never guesses)", r.status_code == 422 and "Survey" in r.text, r.text[:200])
    info = {"owner_name": "SMOKE OWNER", "survey_no": "123/4A", "village": "Keezhvelur", "taluk": "Kilvelur",
            "district": "Nagapattinam", "road_name": "Gandhi Street", "allowed_fsi": 1.5, "sump": True}
    r = c.put(f"/api/projects/{pid}/approval", json={"site_info": info, "authority": "panchayat"})
    check("1.14 approval details saved", r.status_code == 200 and r.json()["site_info"].get("survey_no") == "123/4A" and r.json()["authority"] == "panchayat", r.text[:200])
    r = c.post(f"/api/projects/{pid}/approval/check", json={"plan": plan}, timeout=120)
    ck = r.json() if r.status_code == 200 else {}
    check("1.14 rule check (setbacks / height / FSI / coverage)", len(ck.get("rows", [])) >= 8 and any("FSI" in x["item"] and x["status"] in ("ok", "fail") for x in ck["rows"]), r.text[:200])
    for q, magic in (("kind=pdf&size=A1", b"%PDF"), ("kind=pdf&size=A2&style=cad", b"%PDF"), ("kind=dxf", b"SECTION")):
        r = c.post(f"/api/projects/{pid}/approval/sheet?{q}", json={"plan": plan}, timeout=180)
        check(f"1.14 approval drawing ({q})", r.status_code == 200 and magic in r.content[:200], r.text[:200] if r.status_code != 200 else "")
    r = c.put(f"/api/projects/{pid}/approval/stage", json={"key": "applied", "done": True, "ref": "SMOKE/APP/1"})
    check("1.14 approval stage + application no.", r.status_code == 200 and r.json()["stages"][2]["ref"] == "SMOKE/APP/1", r.text[:200])
    r = c.get(f"/api/projects/{pid}/permit")
    check("1.14 application no. shown in the checklist", r.status_code == 200 and r.json().get("application_no") == "SMOKE/APP/1", r.text[:200])
    same = c.get(f"/api/projects/{pid}/approval").json().get("fee_rates", [])
    r = c.put("/api/approval/fee-rates", json={"authority": "panchayat", "rows": same})  # your own rates put back unchanged
    check("1.14 fee rates save (owner)", r.status_code == 200, r.text[:200])
    # ---------------- 1.15: material library (your own items + photos) and picks saved with the design ----------------
    import base64
    png1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    r = c.post("/api/materials", json={"category": "flooring", "name": "SMOKE tile", "brand": "Test", "code": "T-1", "color": "#aabbcc", "tile_ft": 2})
    li = r.json() if r.status_code == 200 else {}
    check("1.15 own material added", li.get("ref", "").startswith("c:"), r.text[:200])
    if li.get("id"):
        r = c.post(f"/api/materials/{li['id']}/image", files={"file": ("tile.png", png1, "image/png")})
        check("1.15 material photo upload", r.status_code == 200 and r.json().get("image_url"), r.text[:200])
        if r.status_code == 200:
            r2 = c.get(r.json()["image_url"])
            check("1.15 material photo opens", r2.status_code == 200 and r2.content[:4] == b"\x89PNG", str(r2.status_code))
        r = c.get("/api/materials")
        check("1.15 library lists your item", r.status_code == 200 and any(x["id"] == li["id"] for x in r.json()["items"]), r.text[:200])
        p5 = json.loads(json.dumps(plan))
        p5["finishes"] = {"style": "modern", "mat": {"ext_wall": "b:sky", "floor": li["ref"], "bad": "b:x", "door": "javascript:1"},
                          "rooms": {"0:hall_1": {"wall": "b:peach", "floor": "b:marble"}, "bad room": {"wall": "b:sky"}}}
        r = c.post(f"/api/projects/{pid}/designs", json={"plan": p5, "title": "SMOKE materials"})
        f5 = (r.json().get("plan") or {}).get("finishes", {}) if r.status_code == 200 else {}
        check("1.15 material picks saved (and cleaned)", f5.get("mat") == {"ext_wall": "b:sky", "floor": li["ref"]} and list(f5.get("rooms", {})) == ["0:hall_1"], str(f5)[:200])
        p6 = json.loads(json.dumps(plan))
        p6["finishes"] = {"style": "modern", "plants": {"coconut": {"on": True, "count": 99, "place": "rear"}, "lawn": {"on": False}, "palm_x": {"on": True}, "neem": {"on": True, "count": 2, "place": "roof"}}}
        r = c.post(f"/api/projects/{pid}/designs", json={"plan": p6, "title": "SMOKE plants"})
        f6 = (r.json().get("plan") or {}).get("finishes", {}).get("plants", {}) if r.status_code == 200 else {}
        check("1.16 trees & plants saved (and cleaned)", f6.get("coconut") == {"on": True, "count": 12, "place": "rear"} and f6.get("lawn") == {"on": False}
              and "palm_x" not in f6 and f6.get("neem", {}).get("place") == "edge", str(f6)[:200])
        r = c.post(f"/api/trash/library_item/{li['id']}")
        check("1.15 own material to Recycle Bin", r.status_code == 200, r.text[:200])
        CLEANUP.append({"entity": "library_item", "id": li["id"]})
    # ---------------- 1.18: Material Library (brands, A/B/C grades, rates, project choice) ----------------
    r = c.get("/api/market")
    mk = r.json() if r.status_code == 200 else {}
    check("1.18 material library: every material of a house with brands", len(mk.get("categories", [])) >= 30
          and any(b["name"] == "Ramco" and b["category"] == "cement" for b in mk.get("brands", [])), r.text[:200])
    r = c.post("/api/market/brands", json={"category": "cement", "name": "SMOKE TEST BRAND", "tier": "A"})
    tb = r.json() if r.status_code == 200 else {}
    check("1.18 add a brand (grade A)", tb.get("tier") == "A", r.text[:200])
    if tb:
        r = c.post("/api/market/variants", json={"brand_id": tb["id"], "name": "PPC", "code": "SMK-01", "unit": "bag", "rate": 777, "gst_pct": 28})
        tv = r.json() if r.status_code == 200 else {}
        check("1.18 add a variant with my rate", tv.get("rate") == 777 and tv.get("rate_code") == "cement", r.text[:200])
        r = c.get("/api/market")
        prem = ((r.json().get("tiers") or {}).get("cement") or {}).get("premium") or {}
        check("1.18 grade A brands → Premium rate", "SMOKE TEST BRAND" in prem.get("names", []), str(prem)[:200])
        r = c.put(f"/api/projects/{pid}/brand-choices", json={"category": "cement", "variant_id": tv.get("id")})
        check("1.18 brand chosen for this project", r.status_code == 200 and r.json()["choices"].get("cement") == tv.get("id"), r.text[:200])
        r = c.post(f"/api/projects/{pid}/estimate/calculate", json={"inputs": inp, "state": "Tamil Nadu"})
        check("1.18 estimate uses the chosen brand's rate", r.status_code == 200 and any("SMOKE TEST BRAND" in n for n in r.json().get("material_notes", [])), r.text[:200])
        c.put(f"/api/projects/{pid}/brand-choices", json={"category": "cement", "variant_id": None})
        buf = "category,brand,name,code,colour,unit,rate,gst_pct\npaint_interior,SMOKE TEST BRAND,Smoke shade,0951,#efe3cf,litre,,18\n"
        r = c.post("/api/market/import", files={"file": ("smoke.csv", buf.encode(), "text/csv")})
        check("1.18 import a shade list (CSV)", r.status_code == 200 and r.json().get("added", 0) >= 1, r.text[:200])
        r = c.get("/api/market")
        check("1.18 shade code searchable (0951)", any(v["code"] == "0951" and v["color"] == "#efe3cf" for v in r.json().get("variants", [])), "")
        for b_ in [b for b in r.json().get("brands", []) if b["name"] == "SMOKE TEST BRAND"]:
            c.post(f"/api/trash/market_brand/{b_['id']}")
            CLEANUP.append({"entity": "market_brand", "id": b_["id"]})
    p4 = json.loads(json.dumps(plan)); p4["finishes"] = {"style": "traditional", "ext": "#f2deb0"}
    r = c.post(f"/api/projects/{pid}/designs", json={"plan": p4, "title": "SMOKE 3D style"})
    check("1.13 3D elevation style saved", r.status_code == 200 and (r.json().get("plan") or {}).get("finishes", {}).get("style") == "traditional", r.text[:200])
    r = c.get(f"/api/projects/{pid}/project-pdf?design_id={d2}", timeout=180)
    check("one complete PDF (drawings + estimate)", r.status_code == 200 and r.content[:4] == b"%PDF" and r.content.count(b"/Type /Page") > 8,
          r.text[:200] if r.status_code != 200 else "")
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
            r = c.get(f"/api/projects/{pid}/active-design")
            check("1.18 uploaded drawing becomes the active drawing", (r.json().get("design") or {}).get("id") == up.get("id"), r.text[:200])
        if up:
            r = c.post(f"/api/projects/{pid}/vastu/analyse", json={"design_id": up["id"]})
            ok = r.status_code == 200 and r.json()["result"]["summary"]["total"] >= 8
            check("vastu analysis", ok, r.text[:300])
            vr = r.json()["result"] if ok else {}
            check("1.16 vastu score + floor-wise scores", isinstance(vr.get("score"), int) and len(vr.get("floors", [])) >= 2, str(vr.get("floors"))[:200])
            check("1.16 vastu 16-zone mandala + door pada", len(vr.get("mandala", [])) == 16 and (vr.get("door") or {}).get("code", "")[:1] in "NESW", str(vr.get("door"))[:200])
            check("1.16 vastu asks site details (never guesses)", any(q["key"] == "sump" for q in vr.get("questions", [])), str(vr.get("questions"))[:200])
            check("1.16 vastu 8-direction overview", set(vr.get("overview8", {})) == {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}, str(vr.get("overview8"))[:200])
            was_site = c.get(f"/api/projects/{pid}/vastu/site").json().get("site", {})
            r = c.put(f"/api/projects/{pid}/vastu/site", json={"sump": "NE", "oh_tank": "SW", "gate": "XX", "bogus": 1})
            check("1.16 vastu site answers saved (and cleaned)", r.status_code == 200 and r.json()["site"] == {"sump": "NE", "oh_tank": "SW"}, r.text[:200])
            r = c.post(f"/api/projects/{pid}/vastu/analyse", json={"design_id": up["id"], "lang": "ta"})
            vt = r.json()["result"] if r.status_code == 200 else {}
            check("1.16 vastu in Tamil + sump checked", any(ch["rule"] == "sump" and ch["status"] == "matched" for ch in vt.get("checks", []))
                  and "வாஸ்து" in vt.get("note", ""), r.text[:200])
            c.put(f"/api/projects/{pid}/vastu/site", json=was_site)
            r = c.post(f"/api/projects/{pid}/vastu/options", json={"design_id": up["id"]}, timeout=180)
            check("1.16 vastu improved options (max 3, never worse)", r.status_code == 200 and len(r.json()["options"]) <= 3
                  and all(o["score"] >= r.json()["current"]["score"] for o in r.json()["options"]), r.text[:200])
            r = c.post(f"/api/projects/{pid}/vastu/report-html", json={"design_id": up["id"], "lang": "ta"}, timeout=180)
            check("1.16 vastu Tamil report (print)", r.status_code == 200 and "வாஸ்து அறிக்கை" in r.text and "<svg" in r.text, r.text[:200])
            was_rules = c.get("/api/vastu/rules").json().get("own", {})
            r = c.put("/api/vastu/rules", json={"kitchen": {"good": ["SE", "NW"], "ok": ["E"]}, "nonsense": {"good": ["N"]}})
            check("1.16 owner's own Vastu rules", r.status_code == 200 and list(r.json()["own"]) == ["kitchen"], r.text[:200])
            c.put("/api/vastu/rules", json=was_rules)  # back as it was
            r = c.post(f"/api/projects/{pid}/vastu/apply", json={"design_id": up["id"]})
            check("vastu apply suggestions", r.status_code == 200 and "after" in r.json(), r.text[:200])
            r = c.post(f"/api/projects/{pid}/vastu/report-pdf", json={"design_id": up["id"], "north_deg": 90})
            check("1.13 vastu report download without saving", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
            r = c.post(f"/api/projects/{pid}/vastu/reports", json={"design_id": up["id"], "north_deg": 90})
            rid = r.json().get("id") if r.status_code == 200 else None
            check("vastu report saved", bool(rid), r.text[:200])
            r = c.get(f"/api/vastu/reports/{rid}/pdf")
            check("vastu report PDF", r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:200] if r.status_code != 200 else "")
    pdfp = c.get(f"/api/designs/{d2}/pdf").content
    r = c.post(f"/api/projects/{pid}/drawings/upload", files={"file": ("smoke_plan.pdf", pdfp, "application/pdf")})
    check("vector PDF drawing read", r.status_code == 200 and r.json().get("method") == "pdf" and r.json().get("rooms", 0) >= 4,
          r.text[:300])
    try:  # 1.18: the plan is on page 2 (cover sheet first) – found automatically
        import io as _io
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas as _cv
        cb = _io.BytesIO(); cv_ = _cv.Canvas(cb); cv_.drawString(100, 700, "COVER SHEET"); cv_.save()
        w_ = PdfWriter(); w_.add_page(PdfReader(_io.BytesIO(cb.getvalue())).pages[0])
        for pg_ in PdfReader(_io.BytesIO(pdfp)).pages:
            w_.add_page(pg_)
        out_ = _io.BytesIO(); w_.write(out_)
        r = c.post(f"/api/projects/{pid}/drawings/upload", files={"file": ("smoke_two_pages.pdf", out_.getvalue(), "application/pdf")})
        check("1.18 PDF: plan page found automatically", r.status_code == 200 and r.json().get("method") == "pdf" and r.json().get("rooms", 0) >= 4
              and (((r.json().get("info") or {}).get("info") or {}).get("page") or 0) >= 1, r.text[:300])  # any plan page, never the cover
    except ImportError as e:
        check("1.18 PDF: plan page found automatically", False, f"needs pypdf + reportlab: {e}")

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
check("1.18 weather tips get today's work", r.status_code == 200 and "today_work" in r.json(), r.text[:200])

# ---------------- Phase 7.8: weather alerts (bell + phone push)
r = c.get("/api/push/key")
check("push key ready", r.status_code == 200 and len(r.json().get("public_key", "")) > 80, r.text[:200])
r = c.get("/api/alerts/cron-key")
key = r.json().get("key") if r.status_code == 200 else ""
check("daily alert link key", bool(key), r.text[:200])
r = c.get("/api/alerts/run", params={"key": "wrong"})
check("daily alert link refuses a wrong key", r.status_code == 403, r.text[:200])
r = c.post("/api/notifications/mark", json={"keys": ["smoke:test"], "action": "read"})
check("notification mark read", r.status_code == 200, r.text[:200])
r = c.post("/api/notifications/mark", json={"keys": ["smoke:test"], "action": "delete"})
check("notification delete", r.status_code == 200, r.text[:200])
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
        CLEANUP.append({"entity": "task", "id": tid})  # cleaned up at the end, in one go
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
r = c.post(f"/api/projects/{pid}/bbs/export/excel", json={"title": "SMOKE BBS", "members": [col]})
check("1.13 BBS download without saving", r.status_code == 200 and r.content[:2] == b"PK", r.text[:200] if r.status_code != 200 else "")
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
    rr = c.post("/api/ai/chat", json=body, timeout=120)
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
if st6.get("any") and not FULL:
    print("       (live AI provider test skipped – quick mode. For it run:  scripts\\update.bat --full)")
if st6.get("any") and FULL:
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

# ---------------- company (1.16: the Clients section is removed – client name stays on the project) ----------------
r = c.get("/api/settings/company")
check("company name + proprietor", r.status_code == 200 and "proprietor" in r.json(), r.text[:200])
r = c.get("/api/clients")
check("1.16 Clients section removed", r.status_code in (404, 405), str(r.status_code))
r0 = c.get("/api/owner-only")
check("owner-only switches load", r0.status_code == 200, f"{r0.status_code} {r0.text[:120]}")
was = r0.json().get("modules", []) if r0.status_code == 200 else []
r = c.put("/api/owner-only", json={"modules": sorted(set(was) | {"vastu"})})
check("owner-only module switch", r.status_code == 200 and "vastu" in r.json()["modules"], r.text[:200])
c.put("/api/owner-only", json={"modules": was})  # back as it was

r = c.patch(f"/api/projects/{pid}", json={"status": "archived"})
check("archive test project", r.status_code == 200, r.text)
lst = c.get("/api/projects").json()["projects"]
check("archived project hidden from list", all(p["id"] != pid for p in lst))

if CLEANUP:
    r = c.post("/api/trash/purge-many", json={"items": CLEANUP}, timeout=300)
    check("test items removed from the Recycle Bin (one backup)", r.status_code == 200, r.text[:200])
print()
total = time.perf_counter() - T_START
print(f"Test time: {total / 60:.1f} min, {len(TIMES)} requests. Slowest:")
for secs, what in sorted(TIMES, reverse=True)[:8]:
    print(f"   {secs:6.1f} s  {what}")
print(f"{ok_count} passed, {len(fail)} failed")
if fail:
    print("Failed:", ", ".join(fail), "\nSend this output to Claude.")
    sys.exit(1)
else:
    print("NEXORA 1.18 API: ALL GOOD")
