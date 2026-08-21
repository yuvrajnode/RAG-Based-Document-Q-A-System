export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? Math.round(value) : value.toFixed(1)} ${units[exponent]}`;
}

export function formatCount(value: number): string {
  return value >= 10_000 ? `${(value / 1000).toFixed(0)}k` : value.toLocaleString();
}

export function formatDuration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const TYPE_LABELS: Record<string, string> = {
  pdf: "PDF",
  docx: "DOCX",
  md: "MD",
  markdown: "MD",
  txt: "TXT",
  html: "HTML",
  htm: "HTML",
  csv: "CSV",
  json: "JSON",
};

export function typeLabel(sourceType: string): string {
  return TYPE_LABELS[sourceType] ?? sourceType.toUpperCase().slice(0, 4);
}

const TYPE_TONES: Record<string, string> = {
  pdf: "bg-rose-500/15 text-rose-600 dark:text-rose-300",
  docx: "bg-sky-500/15 text-sky-600 dark:text-sky-300",
  md: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
  markdown: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
  html: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
  htm: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
  csv: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
  json: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
  txt: "bg-ink-500/15 text-ink-600 dark:text-ink-300",
};

export function typeTone(sourceType: string): string {
  return TYPE_TONES[sourceType] ?? "bg-ink-500/15 text-ink-600 dark:text-ink-300";
}
