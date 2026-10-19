import { Fragment, type ReactNode } from "react";

/** Tiny, safe markdown renderer for assistant answers: headings, bullets, numbers, bold, italics, code, [n] citations. */
function inline(text: string, onCite?: (n: number) => void): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[\d+\](?:\[\d+\])*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const s = m[0];
    if (s.startsWith("**")) out.push(<strong key={k++} className="font-semibold text-navy-ink">{s.slice(2, -2)}</strong>);
    else if (s.startsWith("`")) out.push(<code key={k++} className="rounded bg-slate-100 px-1 text-[0.85em]">{s.slice(1, -1)}</code>);
    else if (s.startsWith("[")) {
      for (const n of s.match(/\d+/g) || []) {
        out.push(
          <button key={k++} type="button" onClick={() => onCite?.(Number(n))}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-brand-50 px-1 align-text-top text-[10px] font-bold text-brand-700 hover:bg-brand-100">{n}</button>);
      }
    } else out.push(<em key={k++}>{s.slice(1, -1)}</em>);
    last = m.index + s.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  const lines = (text || "").replace(/\r/g, "").split("\n");
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let para: string[] = [];
  const flushPara = () => {
    if (para.length) blocks.push(<p key={blocks.length} className="leading-relaxed">{inline(para.join(" "), onCite)}</p>);
    para = [];
  };
  const flushList = () => {
    if (!list) return;
    const L = list;
    const cls = L.ordered ? "list-decimal" : "list-disc";
    blocks.push(
      <ul key={blocks.length} className={`${cls} space-y-1 pl-5 marker:text-brand-600`}>
        {L.items.map((it, i) => <li key={i} className="leading-relaxed">{inline(it, onCite)}</li>)}
      </ul>);
    list = null;
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const h = line.match(/^#{1,4}\s+(.*)/);
    const b = line.match(/^\s*[-*•]\s+(.*)/);
    const n = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (!line.trim()) { flushPara(); flushList(); continue; }
    if (h) { flushPara(); flushList(); blocks.push(<div key={blocks.length} className="pt-1 font-bold text-navy-ink">{inline(h[1], onCite)}</div>); continue; }
    if (b || n) {
      flushPara();
      const ordered = !!n;
      if (!list || list.ordered !== ordered) { flushList(); list = { ordered, items: [] }; }
      list.items.push((b || n)![1]);
      continue;
    }
    if (list && /^\s{2,}/.test(raw)) { list.items[list.items.length - 1] += " " + line.trim(); continue; }
    flushList();
    para.push(line.trim());
  }
  flushPara(); flushList();
  return <div className="space-y-2 text-[14px] text-slate-700">{blocks.map((b, i) => <Fragment key={i}>{b}</Fragment>)}</div>;
}
