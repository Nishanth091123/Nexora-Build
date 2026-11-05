/** 1.16 – Trees & plants around the house: ON/OFF, count and place for each type. Saved with the design. */
import { Trees } from "lucide-react";
import { DEFAULT_PLANTS, PLACE_LABEL, PLANT_LABEL, PLANT_MAX, plantsOf, type PlantKind, type Place, type Plants } from "./house3d/plants";

const KINDS: PlantKind[] = ["coconut", "neem", "mango", "areca", "shrubs", "potted"];

export function plantSummary(p?: Plants | null): string[] {
  const P = plantsOf(p);
  const out = KINDS.filter((k) => P[k]?.on && (P[k]?.count ?? 0) > 0)
    .map((k) => `${PLANT_LABEL[k]} × ${P[k]!.count}${k === "potted" ? "" : ` – ${PLACE_LABEL[(P[k]!.place || "edge") as Place]}`}`);
  if (P.lawn?.on) out.push(PLANT_LABEL.lawn);
  return out;
}

export default function PlantsPanel({ plants, onChange, disabled }: { plants?: Plants; onChange: (p: Plants) => void; disabled?: boolean }) {
  const P = plantsOf(plants);
  const set = (k: PlantKind | "lawn", v: Partial<{ on: boolean; count: number; place: Place }>) => onChange({ ...P, [k]: { ...P[k], ...v } });
  return (
    <div className="rounded-lg border border-line p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-navy-ink"><Trees size={13} className="mr-1 inline" />Trees & plants around the house</span>
        <span className="text-[11px] text-slate-500">Always outside the house and roof overhang. If the yard is too small, big trees go just outside the compound.</span>
        <span className="flex-1" />
        <button className="btn-ghost btn-sm" disabled={disabled} onClick={() => onChange(DEFAULT_PLANTS)}>Reset</button>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {KINDS.map((k) => {
          const o = P[k]!;
          return (
            <div key={k} className={`rounded-lg border p-2 ${o.on ? "border-emerald-300 bg-emerald-50/40" : "border-line"}`}>
              <label className="flex items-center gap-2 text-xs font-semibold text-navy-ink">
                <input type="checkbox" className="accent-emerald-600" disabled={disabled} checked={o.on} onChange={(e) => set(k, { on: e.target.checked })} />{PLANT_LABEL[k]}
              </label>
              {o.on && (
                <div className="mt-1.5 flex items-center gap-2 text-xs">
                  <span className="text-slate-500">How many</span>
                  <input type="number" min={1} max={PLANT_MAX[k]} className="input w-16 py-1 text-xs" disabled={disabled} value={o.count ?? 1}
                    onChange={(e) => set(k, { count: Math.max(1, Math.min(PLANT_MAX[k], Number(e.target.value) || 1)) })} />
                  {k !== "potted" ? (
                    <select className="input py-1 text-xs" disabled={disabled} value={o.place || "edge"} onChange={(e) => set(k, { place: e.target.value as Place })}>
                      {(Object.keys(PLACE_LABEL) as Place[]).map((pl) => <option key={pl} value={pl}>{PLACE_LABEL[pl]}</option>)}
                    </select>
                  ) : <span className="text-slate-500">at the entrance path</span>}
                </div>
              )}
            </div>
          );
        })}
        <div className={`rounded-lg border p-2 ${P.lawn.on ? "border-emerald-300 bg-emerald-50/40" : "border-line"}`}>
          <label className="flex items-center gap-2 text-xs font-semibold text-navy-ink">
            <input type="checkbox" className="accent-emerald-600" disabled={disabled} checked={P.lawn.on} onChange={(e) => set("lawn", { on: e.target.checked })} />{PLANT_LABEL.lawn}
          </label>
          <p className="mt-1 text-[11px] text-slate-500">Off = plain earth around the house.</p>
        </div>
      </div>
    </div>
  );
}
