import type { ConceptLinkedVideo } from "@/api/concepts";

export function formatConceptSegment(v: ConceptLinkedVideo): string {
  const s = v.start_time_seconds;
  const e = v.end_time_seconds;
  if (s == null && e == null) return "—";
  const fmt = (sec: number) => {
    const m = Math.floor(sec / 60);
    const r = sec % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  };
  if (s != null && e != null) return `${fmt(s)} – ${fmt(e)}`;
  if (s != null) return `${fmt(s)} 起`;
  return `至 ${fmt(e!)}`;
}
