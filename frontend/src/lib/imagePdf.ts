/** 1.21 – a picture → one-page PDF (A3 / A4, portrait or landscape to suit the picture). Made in the browser,
 *  works offline. The picture is stored as JPEG inside the PDF at full resolution. */
const PAGES: Record<string, [number, number]> = { A3: [841.89, 1190.55], A4: [595.28, 841.89] };

export function imagePdf(jpegDataUrl: string, wPx: number, hPx: number, page: "A3" | "A4" = "A3", title = "Drawing"): Blob {
  const bin = atob(jpegDataUrl.split(",")[1]);
  const jpg = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) jpg[i] = bin.charCodeAt(i);
  let [pw, ph] = PAGES[page];
  if (wPx > hPx) [pw, ph] = [ph, pw];
  const m = 22, k = Math.min((pw - 2 * m) / wPx, (ph - 2 * m) / hPx);
  const w = wPx * k, h = hPx * k, x = (pw - w) / 2, y = (ph - h) / 2;
  const enc = new TextEncoder();
  const parts: Uint8Array[] = [];
  const offs: number[] = [];
  let len = 0;
  const push = (d: string | Uint8Array) => { const u = typeof d === "string" ? enc.encode(d) : d; parts.push(u); len += u.length; };
  const obj = (n: number, body: string, stream?: Uint8Array) => {
    offs[n] = len;
    push(`${n} 0 obj\n${body}\n`);
    if (stream) { push("stream\n"); push(stream); push("\nendstream\n"); }
    push("endobj\n");
  };
  const content = enc.encode(`q ${w.toFixed(2)} 0 0 ${h.toFixed(2)} ${x.toFixed(2)} ${y.toFixed(2)} cm /Im0 Do Q`);
  const safe = title.replace(/[()\\]/g, " ");
  push("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
  obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
  obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
  obj(3, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pw.toFixed(2)} ${ph.toFixed(2)}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`);
  obj(4, `<< /Type /XObject /Subtype /Image /Width ${wPx} /Height ${hPx} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpg.length} >>`, jpg);
  obj(5, `<< /Length ${content.length} >>`, content);
  obj(6, `<< /Title (${safe}) /Producer (Praganya Construction) >>`);
  const xref = len;
  push(`xref\n0 7\n0000000000 65535 f \n${[1, 2, 3, 4, 5, 6].map((n) => `${String(offs[n]).padStart(10, "0")} 00000 n \n`).join("")}`);
  push(`trailer\n<< /Size 7 /Root 1 0 R /Info 6 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts as BlobPart[], { type: "application/pdf" });
}

export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
