/** 1.15 – Material Library: built-in colours / materials, the "slots" of the house they can go on, and turning a
 *  pick (built-in "b:id" or your own "c:id") into what the 3D view draws. */
import * as THREE from "three";
import * as T from "./textures";

export type Cat = "paint" | "cladding" | "flooring" | "wall_tile" | "roof" | "door" | "frame" | "counter" | "plinth";
export type Item = {
  ref: string; cat: Cat; name: string; color: string; brand?: string; code?: string;
  tex?: "stone" | "wood" | "tiles" | "marble" | "granite" | "brick" | "floor" | "mosaic" | "roof" | "pavers";
  tile?: number; rough?: number; metal?: number; n?: number;  // n = tiles per texture (floor / wall tiles)
  image?: string | null; custom?: boolean; finish?: string; rate?: number | null; unit?: string; id?: number;
};
export type Look = { color: string; map: THREE.Texture | null; tile: number; rough: number; metal: number };

const P = (id: string, name: string, color: string): Item => ({ ref: `b:${id}`, cat: "paint", name, color });
export const BUILTIN: Item[] = [
  // paints (walls, ceiling, compound)
  P("ivory", "Ivory cream", "#efe7d8"), P("offwhite", "Off-white", "#f5f3ee"), P("white", "Pure white", "#ffffff"),
  P("lgrey", "Light grey", "#d9d9d6"), P("dgrey", "Charcoal grey", "#4a4e55"), P("beige", "Warm beige", "#e9d7b9"),
  P("sandal", "Sandal", "#f2deb0"), P("peach", "Peach", "#f6d5c3"), P("sky", "Sky blue", "#cfe3f2"), P("mint", "Mint", "#d9eedf"),
  P("lilac", "Lilac", "#e6dff0"), P("blush", "Blush pink", "#f7e1e1"), P("terracotta", "Terracotta", "#b5654a"),
  P("olive", "Olive", "#8a8f5a"), P("mustard", "Mustard", "#d9a441"), P("sage", "Sage green", "#b7c4a8"), P("navy", "Navy", "#2b3a55"),
  // cladding
  { ref: "b:stone", cat: "cladding", name: "Natural stone (stacked)", color: "#9a8f7b", tex: "stone", tile: 4 },
  { ref: "b:slate", cat: "cladding", name: "Dark slate stone", color: "#5d5a55", tex: "stone", tile: 4 },
  { ref: "b:woodclad", cat: "cladding", name: "Wood panels (teak)", color: "#8c5a33", tex: "wood", tile: 4, rough: 0.6 },
  { ref: "b:woodlight", cat: "cladding", name: "Wood panels (light)", color: "#b98a5a", tex: "wood", tile: 4, rough: 0.6 },
  { ref: "b:greytile", cat: "cladding", name: "Grey large tiles", color: "#7d8188", tex: "tiles", tile: 4, rough: 0.55 },
  { ref: "b:brick", cat: "cladding", name: "Exposed brick", color: "#a8553a", tex: "brick", tile: 3 },
  { ref: "b:marbleclad", cat: "cladding", name: "White marble", color: "#f2f0eb", tex: "marble", tile: 4, rough: 0.25 },
  // flooring
  { ref: "b:vitbeige", cat: "flooring", name: "Vitrified 2'x2' beige", color: "#e7e0d3", tex: "floor", n: 2, tile: 4, rough: 0.3 },
  { ref: "b:vitwhite", cat: "flooring", name: "Vitrified 2'x2' white", color: "#f4f2ee", tex: "floor", n: 2, tile: 4, rough: 0.25 },
  { ref: "b:vitgrey", cat: "flooring", name: "Vitrified 4'x2' grey", color: "#b9b9b5", tex: "floor", n: 1, tile: 4, rough: 0.3 },
  { ref: "b:marble", cat: "flooring", name: "White marble", color: "#f2f0eb", tex: "marble", tile: 4, rough: 0.2 },
  { ref: "b:granblack", cat: "flooring", name: "Black granite", color: "#2f2f2f", tex: "granite", tile: 2, rough: 0.25 },
  { ref: "b:grangrey", cat: "flooring", name: "Grey granite", color: "#8a8a88", tex: "granite", tile: 2, rough: 0.3 },
  { ref: "b:woodfloor", cat: "flooring", name: "Wooden flooring", color: "#a7774b", tex: "wood", tile: 4, rough: 0.45 },
  { ref: "b:redoxide", cat: "flooring", name: "Red oxide", color: "#b5523a", rough: 0.4 },
  { ref: "b:kota", cat: "flooring", name: "Kota stone", color: "#9faa8f", tex: "floor", n: 2, tile: 4, rough: 0.5 },
  { ref: "b:antiskid", cat: "flooring", name: "Anti-skid (toilet)", color: "#c9c4ba", tex: "floor", n: 4, tile: 4, rough: 0.8 },
  // wall tiles
  { ref: "b:wtwhite", cat: "wall_tile", name: "White glossy tiles", color: "#f7f7f5", tex: "floor", n: 4, tile: 4, rough: 0.15 },
  { ref: "b:wtbeige", cat: "wall_tile", name: "Beige ceramic tiles", color: "#e6dccb", tex: "floor", n: 4, tile: 4, rough: 0.2 },
  { ref: "b:wtgrey", cat: "wall_tile", name: "Grey ceramic tiles", color: "#a9adb2", tex: "floor", n: 3, tile: 4, rough: 0.2 },
  { ref: "b:wtblue", cat: "wall_tile", name: "Blue mosaic", color: "#5b8fc9", tex: "mosaic", tile: 2, rough: 0.2 },
  // roof / terrace
  { ref: "b:concrete", cat: "roof", name: "Concrete", color: "#cfcac2" },
  { ref: "b:weathering", cat: "roof", name: "Weathering tiles", color: "#b9473a", tex: "floor", n: 4, tile: 4 },
  { ref: "b:whitecoat", cat: "roof", name: "White heat-reflective coat", color: "#eceae6" },
  // doors
  { ref: "b:teak", cat: "door", name: "Teak wood", color: "#9a6a3f", tex: "wood", tile: 4, rough: 0.5 },
  { ref: "b:walnut", cat: "door", name: "Walnut", color: "#5b3a1e", tex: "wood", tile: 4, rough: 0.5 },
  { ref: "b:oak", cat: "door", name: "Oak", color: "#d2b48c", tex: "wood", tile: 4, rough: 0.5 },
  { ref: "b:rosewood", cat: "door", name: "Rosewood", color: "#6b3f1f", tex: "wood", tile: 4, rough: 0.45 },
  { ref: "b:whitelam", cat: "door", name: "White laminate", color: "#eceae6", rough: 0.4 },
  { ref: "b:greylam", cat: "door", name: "Grey laminate", color: "#8b9097", rough: 0.4 },
  // window frames
  { ref: "b:blackalu", cat: "frame", name: "Black aluminium", color: "#1d2024", rough: 0.4, metal: 0.3 },
  { ref: "b:greyalu", cat: "frame", name: "Grey aluminium", color: "#3a3f46", rough: 0.4, metal: 0.3 },
  { ref: "b:whiteupvc", cat: "frame", name: "White UPVC", color: "#f8fafc", rough: 0.4 },
  { ref: "b:woodframe", cat: "frame", name: "Wooden frame", color: "#6b3f1f", tex: "wood", tile: 4 },
  // kitchen counter
  { ref: "b:cblack", cat: "counter", name: "Black granite top", color: "#1f2328", tex: "granite", tile: 2, rough: 0.2 },
  { ref: "b:cgrey", cat: "counter", name: "Grey granite top", color: "#7d7d7b", tex: "granite", tile: 2, rough: 0.25 },
  { ref: "b:cwhite", cat: "counter", name: "White quartz top", color: "#f1f0ec", tex: "marble", tile: 4, rough: 0.2 },
  // plinth
  { ref: "b:pcharcoal", cat: "plinth", name: "Charcoal", color: "#3b3a38" }, { ref: "b:pgrey", cat: "plinth", name: "Grey", color: "#8d8d8d" },
  { ref: "b:pmaroon", cat: "plinth", name: "Maroon", color: "#7a2e1f" }, { ref: "b:pgranite", cat: "plinth", name: "Black granite", color: "#2f2f2f", tex: "granite", tile: 2 },
  { ref: "b:pstone", cat: "plinth", name: "Natural stone", color: "#9a8f7b", tex: "stone", tile: 4 },
];

export type Slot = "ext_wall" | "cladding" | "plinth" | "roof" | "door" | "frame" | "compound" | "int_wall" | "ceiling" | "floor" | "wet_floor" | "wet_wall" | "counter";
export const SLOTS: { key: Slot; label: string; cats: Cat[]; group: "Exterior" | "Interior" }[] = [
  { key: "ext_wall", label: "Exterior walls", cats: ["paint", "cladding"], group: "Exterior" },
  { key: "cladding", label: "Feature walls (front)", cats: ["cladding", "paint"], group: "Exterior" },
  { key: "plinth", label: "Plinth", cats: ["plinth", "cladding", "paint"], group: "Exterior" },
  { key: "roof", label: "Terrace / roof", cats: ["roof"], group: "Exterior" },
  { key: "door", label: "Doors", cats: ["door"], group: "Exterior" },
  { key: "frame", label: "Window frames", cats: ["frame"], group: "Exterior" },
  { key: "compound", label: "Compound wall", cats: ["paint", "cladding"], group: "Exterior" },
  { key: "int_wall", label: "Interior walls", cats: ["paint", "wall_tile", "cladding"], group: "Interior" },
  { key: "ceiling", label: "Ceiling", cats: ["paint"], group: "Interior" },
  { key: "floor", label: "Flooring", cats: ["flooring"], group: "Interior" },
  { key: "wet_floor", label: "Toilet floor", cats: ["flooring"], group: "Interior" },
  { key: "wet_wall", label: "Toilet wall tiles (to 7 ft)", cats: ["wall_tile"], group: "Interior" },
  { key: "counter", label: "Kitchen counter top", cats: ["counter"], group: "Interior" },
];
export const CAT_LABEL: Record<Cat, string> = { paint: "Paint", cladding: "Cladding", flooring: "Flooring", wall_tile: "Wall tiles", roof: "Roof", door: "Door", frame: "Frame", counter: "Counter top", plinth: "Plinth" };

export function procTex(it: Item): THREE.Texture | null {
  switch (it.tex) {
    case "stone": return T.stone();
    case "wood": return T.wood(it.color);
    case "tiles": return T.tiles();
    case "marble": return T.marble(it.color);
    case "granite": return T.granite(it.color);
    case "brick": return T.brick(it.color);
    case "floor": return T.floorTiles(it.color, it.n || 2);
    case "mosaic": return T.mosaic(it.color);
    case "pavers": return T.pavers();
    default: return null;
  }
}

/** pick → what to draw. custom = your own items (photo textures already loaded) */
export function lookOf(it: Item | undefined, photos: Map<string, THREE.Texture>): Look | null {
  if (!it) return null;
  const photo = it.custom ? photos.get(it.ref) || null : null;
  const base = photo || procTex(it);
  let map: THREE.Texture | null = null;
  const tile = it.tile || 4;
  if (base) {
    map = base.clone();  // own repeat per material; the picture itself is shared
    map.wrapS = map.wrapT = THREE.RepeatWrapping;
    map.repeat.set(4 / tile, 4 / tile);  // geometry UVs are "1 = 4 ft"
    map.colorSpace = THREE.SRGBColorSpace;
    map.needsUpdate = true;
  }
  const rough = it.rough ?? (it.finish === "gloss" ? 0.15 : it.finish === "satin" ? 0.45 : 0.85);
  // a textured / photo item keeps its own colours; a plain colour is drawn with the light plaster grain
  return { color: map && (photo || it.tex === "stone" || it.tex === "tiles" || it.tex === "brick" || it.tex === "mosaic" || it.tex === "floor" || it.tex === "marble" || it.tex === "granite" || it.tex === "wood") ? "#ffffff" : it.color,
           map: map || T.plaster(), tile, rough, metal: it.metal ?? 0 };
}

export type Picks = { mat?: Partial<Record<Slot, string>>; rooms?: Record<string, { wall?: string; floor?: string }> };
