/** 1.13 – exact outlines from room rectangles (no overlapping boxes → no flicker / z-fighting).
 *  Rooms are laid on a 0.25 ft grid; union, outer ring (overhang) and boundary edges come from it. */
export type R = { x: number; y: number; w: number; d: number };

const C = 0.25;

export class Grid {
  x0: number; y0: number; nx: number; ny: number; a: Uint8Array;
  constructor(rects: R[], pad: number) {
    const xs = rects.flatMap((r) => [r.x, r.x + r.w]), ys = rects.flatMap((r) => [r.y, r.y + r.d]);
    this.x0 = Math.floor((Math.min(...xs) - pad) / C) * C;
    this.y0 = Math.floor((Math.min(...ys) - pad) / C) * C;
    this.nx = Math.ceil((Math.max(...xs) + pad - this.x0) / C) + 1;
    this.ny = Math.ceil((Math.max(...ys) + pad - this.y0) / C) + 1;
    this.a = new Uint8Array(this.nx * this.ny);
  }
  fill(r: R, v = 1) {
    const i0 = Math.round((r.x - this.x0) / C), i1 = Math.round((r.x + r.w - this.x0) / C);
    const j0 = Math.round((r.y - this.y0) / C), j1 = Math.round((r.y + r.d - this.y0) / C);
    for (let j = Math.max(0, j0); j < Math.min(this.ny, j1); j++)
      for (let i = Math.max(0, i0); i < Math.min(this.nx, i1); i++) this.a[j * this.nx + i] = v;
  }
  get(i: number, j: number) { return i < 0 || j < 0 || i >= this.nx || j >= this.ny ? 0 : this.a[j * this.nx + i]; }
  /** cells within `dist` ft (square) of a filled cell */
  dilate(dist: number): Grid {
    const g = Object.assign(Object.create(Grid.prototype), this, { a: new Uint8Array(this.a.length) }) as Grid;
    const k = Math.round(dist / C);
    const tmp = new Uint8Array(this.a.length);
    for (let j = 0; j < this.ny; j++) for (let i = 0; i < this.nx; i++) {
      if (!this.a[j * this.nx + i]) continue;
      for (let q = Math.max(0, i - k); q <= Math.min(this.nx - 1, i + k); q++) tmp[j * this.nx + q] = 1;
    }
    for (let j = 0; j < this.ny; j++) for (let i = 0; i < this.nx; i++) {
      if (!tmp[j * this.nx + i]) continue;
      for (let q = Math.max(0, j - k); q <= Math.min(this.ny - 1, j + k); q++) g.a[q * this.nx + i] = 1;
    }
    return g;
  }
  minus(o: Grid): Grid {
    const g = Object.assign(Object.create(Grid.prototype), this, { a: new Uint8Array(this.a.length) }) as Grid;
    for (let k = 0; k < this.a.length; k++) g.a[k] = this.a[k] && !o.a[k] ? 1 : 0;
    return g;
  }
  /** merged rectangles covering the filled cells exactly (row runs, then equal runs stacked) */
  rects(): R[] {
    const out: R[] = [];
    let open = new Map<string, R>();
    for (let j = 0; j <= this.ny; j++) {
      const runs: [number, number][] = [];
      if (j < this.ny) {
        let i = 0;
        while (i < this.nx) {
          if (this.a[j * this.nx + i]) { const s = i; while (i < this.nx && this.a[j * this.nx + i]) i++; runs.push([s, i]); } else i++;
        }
      }
      const next = new Map<string, R>();
      for (const [s, e] of runs) {
        const key = `${s}:${e}`;
        const r = open.get(key);
        if (r) { r.d += C; next.set(key, r); open.delete(key); }
        else next.set(key, { x: this.x0 + s * C, y: this.y0 + j * C, w: (e - s) * C, d: C });
      }
      open.forEach((r) => out.push(r));
      open = next;
    }
    return out;
  }
  /** outline edges of the filled area: [x1, y1, x2, y2, side] side = outward direction (-1 / +1) */
  edges(): { h: boolean; c: number; s: number; e: number; out: number }[] {
    const res: { h: boolean; c: number; s: number; e: number; out: number }[] = [];
    for (let j = 0; j <= this.ny; j++) {  // horizontal edges between row j-1 and j
      for (const out of [-1, 1]) {
        let i = 0;
        while (i < this.nx) {
          const inside = out === -1 ? this.get(i, j) && !this.get(i, j - 1) : this.get(i, j - 1) && !this.get(i, j);
          if (inside) { const s = i; while (i < this.nx && (out === -1 ? this.get(i, j) && !this.get(i, j - 1) : this.get(i, j - 1) && !this.get(i, j))) i++;
            res.push({ h: true, c: this.y0 + j * C, s: this.x0 + s * C, e: this.x0 + i * C, out }); }
          else i++;
        }
      }
    }
    for (let i = 0; i <= this.nx; i++) {
      for (const out of [-1, 1]) {
        let j = 0;
        while (j < this.ny) {
          const inside = out === -1 ? this.get(i, j) && !this.get(i - 1, j) : this.get(i - 1, j) && !this.get(i, j);
          if (inside) { const s = j; while (j < this.ny && (out === -1 ? this.get(i, j) && !this.get(i - 1, j) : this.get(i - 1, j) && !this.get(i, j))) j++;
            res.push({ h: false, c: this.x0 + i * C, s: this.y0 + s * C, e: this.y0 + j * C, out }); }
          else j++;
        }
      }
    }
    return res;
  }
  bounds(): R | null {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let j = 0; j < this.ny; j++) for (let i = 0; i < this.nx; i++) if (this.a[j * this.nx + i]) {
      x0 = Math.min(x0, i); x1 = Math.max(x1, i + 1); y0 = Math.min(y0, j); y1 = Math.max(y1, j + 1);
    }
    return x0 === Infinity ? null : { x: this.x0 + x0 * C, y: this.y0 + y0 * C, w: (x1 - x0) * C, d: (y1 - y0) * C };
  }
}
