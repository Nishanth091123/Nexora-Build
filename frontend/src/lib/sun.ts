// 1.19 Sun path for the 3D view + sunshade (chajja) suggestion per face of the building.
// Sun position: NOAA-style approximation (declination, equation of time), Indian Standard Time (82.5° E meridian).
// Accuracy about ±1° – enough to see shadows and size a sunshade.

const R = Math.PI / 180;

export type SunPos = { az: number; el: number }; // degrees; azimuth from north, clockwise

export function sunPosition(date: Date, hour: number, lat: number, lon: number, tzMeridian = 82.5): SunPos {
  const start = new Date(date.getFullYear(), 0, 0);
  const n = Math.floor((date.getTime() - start.getTime()) / 86400000);
  const decl = 23.44 * Math.sin(R * (360 / 365) * (284 + n));
  const B = R * (360 / 365) * (n - 81);
  const eot = 9.87 * Math.sin(2 * B) - 7.53 * Math.cos(B) - 1.5 * Math.sin(B); // minutes
  const solar = hour + (4 * (lon - tzMeridian) + eot) / 60;
  const H = 15 * (solar - 12);
  const phi = lat * R, d = decl * R, h = H * R;
  const sinEl = Math.sin(phi) * Math.sin(d) + Math.cos(phi) * Math.cos(d) * Math.cos(h);
  const el = Math.asin(Math.max(-1, Math.min(1, sinEl))) / R;
  let az = Math.atan2(Math.sin(h), Math.cos(h) * Math.sin(phi) - Math.tan(d) * Math.cos(phi)) / R + 180;
  az = ((az % 360) + 360) % 360;
  return { az, el };
}

/** Plan axes → compass. compass.up / right = (east, north) parts of the plan +y / +x axes. */
export function compassVectors(compass: { up: number[]; right: number[] } | undefined) {
  const up = compass?.up || [0, 1], right = compass?.right || [1, 0];
  return { east: [right[0], up[0]], north: [right[1], up[1]] }; // in plan (x, y)
}

/** Sun direction in plan coordinates (x, y) + height (z up), unit vector. */
export function sunVector(p: SunPos, compass: { up: number[]; right: number[] } | undefined): [number, number, number] {
  const { east, north } = compassVectors(compass);
  const c = Math.cos(p.el * R);
  const e = c * Math.sin(p.az * R), nn = c * Math.cos(p.az * R);
  return [e * east[0] + nn * north[0], e * east[1] + nn * north[1], Math.sin(p.el * R)];
}

const DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
export const dirName = (az: number) => DIRS[Math.round((((az % 360) + 360) % 360) / 45) % 8];

export type FaceShade = { face: string; facing: string; sunHours: number; depth_m: number | null; advice: string };

/** For each face of the building (front / back / left / right) in the hot months (March – June): hours of direct
 *  sun on the face (9 am – 5 pm) and the chajja depth that shades a 1.2 m tall window (sill 0.9 m, head 2.1 m). */
export function shadeAdvice(compass: { up: number[]; right: number[] } | undefined, lat: number, lon: number, year = new Date().getFullYear()): FaceShade[] {
  const faces: [string, [number, number]][] = [["Front (road side)", [0, -1]], ["Back", [0, 1]], ["Left", [-1, 0]], ["Right", [1, 0]]];
  const { east, north } = compassVectors(compass);
  const out: FaceShade[] = [];
  for (const [name, nrm] of faces) {
    // outward normal → compass azimuth
    const e = nrm[0] * east[0] + nrm[1] * east[1], n = nrm[0] * north[0] + nrm[1] * north[1];
    // (plan → compass: the component along east = dot(n, eastVec) since the axes are orthonormal)
    const wallAz = ((Math.atan2(e, n) / R) + 360) % 360;
    const need: number[] = [];
    let hrs = 0;
    for (let m = 2; m <= 5; m++) {
      for (const day of [5, 20]) {
        const dt = new Date(year, m, day);
        for (let h = 9; h <= 17; h += 0.5) {
          const s = sunPosition(dt, h, lat, lon);
          if (s.el <= 3) continue;
          const g = (s.az - wallAz) * R;
          if (Math.cos(g) <= 0.05) continue; // sun behind or grazing the wall
          hrs += 0.5 / 8; // average over the 8 sample days
          const prof = Math.atan(Math.tan(s.el * R) / Math.cos(g)); // vertical shadow angle
          need.push(1.2 / Math.tan(prof));
        }
      }
    }
    need.sort((a, b) => a - b);
    const p80 = need.length ? need[Math.floor(need.length * 0.8)] : 0;
    let depth: number | null = need.length ? Math.round(Math.max(0.45, p80) * 20) / 20 : null;
    let advice: string;
    if (!need.length || hrs < 0.75) { advice = "Little direct sun in summer – a normal 450 mm chajja is enough."; depth = 0.45; }
    else if (p80 > 0.9) { advice = "Low morning / evening sun – a chajja alone cannot shade it. Add vertical fins or louvres, a deep verandah, or keep windows small on this side."; depth = 0.9; }
    else advice = `Chajja ${Math.round((depth || 0.45) * 1000)} mm deep (full window width + 150 mm each side) shades the window in the hot months.`;
    out.push({ face: name, facing: dirName(wallAz), sunHours: Math.round(hrs * 10) / 10, depth_m: depth, advice });
  }
  return out;
}
