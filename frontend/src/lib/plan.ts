// Shared types & helpers for the Design Studio (all sizes in feet).
export type Room = { id: string; type: string; name: string; x: number; y: number; w: number; d: number; parent?: string };
export type Wall = { kind: "ext" | "int230" | "int115" | "parapet"; x1: number; y1: number; x2: number; y2: number; a?: string | null; b?: string | null };
export type Opening = { id: string; room: string; type: string; x1: number; y1: number; x2: number; y2: number; w: number; h: number };
export type LevelSummary = {
  width_ft: number; depth_ft: number; builtup_sqft: number; carpet_sqft: number; terrace_sqft?: number;
  ext_wall_ft: number; int230_wall_ft: number; int115_wall_ft: number; parapet_ft?: number;
  bedrooms: number; toilets: number; kitchens: number; halls: number; main_doors: number; doors: number;
  toilet_doors: number; windows: number; window_area_sqft: number;
  rooms: { id: string; name: string; type: string; size: string; area_sqft: number }[];
};
export type Level = { name: string; stilt: boolean; rooms: Room[]; openings: Opening[]; walls: Wall[]; summary: LevelSummary; warnings: string[] };
export type Setbacks = {
  rule: string; area_type: string; road_width_m: number; corner: boolean; height_m: number; max_height_m: number;
  m: Record<string, number>; ft: Record<string, number>; buildable: { x: number; y: number; w: number; d: number };
  coverage_pct: number; notes: string[];
};
export type Plan = {
  version: number; units: string; plot: { w: number; d: number }; facing: string;
  compass: { up: [number, number]; right: [number, number] }; setbacks: Setbacks;
  building: { x: number; y: number; w: number; d: number }; floor_height_ft: number; levels: Level[];
  notes: string[]; requirements: any; warnings: string[];
  summary: { levels: number; builtup_sqft: number; carpet_sqft: number; bedrooms: number; toilets: number; kitchens: number };
};

export const ROOM_FILL: Record<string, string> = {
  bedroom: "#dbeafe", toilet: "#cffafe", common_toilet: "#cffafe", kitchen: "#fef3c7", hall: "#ffedd5", lounge: "#ffedd5",
  dining: "#fef9c3", pooja: "#fce7f3", stair: "#e2e8f0", parking: "#f1f5f9", passage: "#f8fafc", dress: "#ede9fe",
  terrace: "#ecfccb", balcony: "#ecfccb", sitout: "#ecfccb", utility: "#f5f5f4", store: "#f5f5f4",
};

export const ROOM_TYPES: [string, string][] = [
  ["bedroom", "Bedroom"], ["toilet", "Toilet"], ["common_toilet", "Common Toilet"], ["kitchen", "Kitchen"], ["hall", "Living / Hall"],
  ["lounge", "Family Lounge"], ["dining", "Dining"], ["pooja", "Pooja"], ["stair", "Staircase"], ["parking", "Parking"],
  ["passage", "Passage"], ["dress", "Dress"], ["utility", "Utility"], ["store", "Store"], ["sitout", "Sit-out"],
  ["balcony", "Balcony"], ["terrace", "Open Terrace"],
];

export const WALL_T: Record<string, number> = { ext: 0.755, int230: 0.755, int115: 0.377, parapet: 0.5 };

export const snap = (v: number, g: number) => Math.round(v / g) * g;
export const ft = (v: number) => `${Math.round(v * 100) / 100}'`;
export const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

/** Screen direction (svg units, y down) of north, from the plan compass. */
export function northVector(p: Plan): [number, number] {
  const [re, rn] = p.compass.right;
  const [ue, un] = p.compass.up;
  void re; void ue;
  return [rn, -un];
}

export const FACINGS = ["east", "west", "north", "south", "north-east", "north-west", "south-east", "south-west"];
