import type { Plan } from "../../lib/plan";

export type Field = { key: string; label: string; type: "num" | "select"; options?: string[]; labels?: string[]; value?: any; length?: boolean };
export type Source = { n: number; kind: "kb" | "doc"; title: string; ref?: string; snippet: string; file_id?: number; page?: number; category?: string };
export type Card =
  | { type: "plan"; title: string; subtitle: string; plan: Plan; features: string[]; request: string; spec_level: string; state: string; notes: string[]; warnings: string[]; estimate?: EstimateCardT; links?: Links }
  | EstimateCardT
  | { type: "questions"; tool: string; kind?: string; questions: string[]; understood?: string[]; fields: Field[]; options?: { label: string; requirements: any; notes: string[] }[]; unit?: string }
  | CalcCardT
  | { type: "vastu"; title: string; summary: { matched: number; partly: number; not_matched: number; total: number; label: string }; checks: any[]; overview: Record<string, any>; design_id: number | null; suggestions: string[] }
  | { type: "site"; title: string; date: string; progress: any; cards: any; insights: { kind: string; text: string }[]; activities: any[] }
  | { type: "drawing"; analysis_id: number; file_name: string; method: string; rooms: any[]; questions: string[] }
  | { type: "photo"; file_id: number; file_name: string; result: any }
  | { type: "setback"; rule: string; ft: Record<string, number>; m: Record<string, number>; buildable: { w: number; d: number }; plot: { w: number; d: number }; coverage_pct: number; height_m: number; notes: string[]; road_width_m: number };
export type Links = { design_id?: number; estimate_id?: number };
export type EstimateCardT = {
  type: "estimate"; title: string; source: string; spec_level: string; rates_state: string; state: string; inputs: any; design_id?: number; links?: Links;
  totals: { grand_total: number; cost_per_sqft: number; builtup_sqft: number; materials: number; labour: number; equipment: number; extras: number; duration_months: number; cement_bags: number; steel_kg: number };
  materials: { label: string; qty: number; unit: string }[]; breakdown: { group: string; amount: number; pct: number }[]; floors: any[]; warnings: string[]; assumptions: string[];
};
export type CalcCardT = { type: "calc"; kind: string; title: string; inputs: [string, string][]; steps: string[]; results: { label: string; value: any; unit: string }[]; assumptions: string[]; missing: string[]; note?: string };
export type Msg = {
  id: number; conversation_id: number; role: "user" | "assistant"; content: string; cards: Card[]; sources: Source[]; tool: string; provider: string;
  language: string; feedback: number; chips: string[]; notes: string[]; attachment: { id: number; name: string; url: string } | null; created_at: string;
  pending?: boolean;
};
export type Conv = { id: number; project_id: number | null; title: string; agent: string; is_pinned: boolean; created_at: string; updated_at: string; preview: string; pending: boolean };
export type Meta = {
  agents: { key: string; name: string; name_ta: string; desc: string }[];
  calculators: { key: string; name: string; name_ta: string; params: Field[] }[];
  material_guide: { key: string; name: string; name_ta: string; rate_code: string; items: { name: string; standard: string; use: string; pros: string; cons: string }[]; tips: string[]; kb: string; rate: any }[];
  rates_state: string;
  kb: { id: string; category: string; title: string; title_ta: string; source: string }[];
};
export type SendOpts = { text?: string; form?: any; attachment?: { id: number; name: string } | null; agent?: string };
