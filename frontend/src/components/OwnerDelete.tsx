import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Modal, toast } from "./ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

/** Owner-only delete: moves the item to the Recycle Bin (Settings → Recycle Bin) where it can be restored. */
export default function OwnerDelete({ entity, id, title, onDone, label, className = "" }: {
  entity: string; id: number; title: string; onDone?: () => void; label?: string; className?: string;
}) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  if (user?.role !== "owner") return null;
  const go = async () => {
    setBusy(true);
    try {
      await api(`/api/trash/${entity}/${id}`, { method: "POST" });
      toast("Moved to the Recycle Bin");
      setOpen(false);
      onDone?.();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <>
      <button type="button" title="Delete (owner)" aria-label="Delete"
        onClick={(e) => { e.stopPropagation(); e.preventDefault(); setOpen(true); }}
        className={`inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 ${className}`}>
        <Trash2 size={14} />{label}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Delete?">
        <p className="text-sm text-slate-700">Move <b>{title}</b> to the Recycle Bin?</p>
        <p className="mt-1 text-xs text-slate-500">You can restore it, or delete it permanently, from Settings → Recycle Bin.
          {entity === "project" && " Everything inside this project goes with it."}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
          <button className="btn bg-red-600 text-white hover:bg-red-700" onClick={go} disabled={busy}><Trash2 size={16} />{busy ? "Deleting…" : "Delete"}</button>
        </div>
      </Modal>
    </>
  );
}
