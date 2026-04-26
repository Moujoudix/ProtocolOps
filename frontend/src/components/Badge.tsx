import type { ReactNode } from "react";

type Tone = "neutral" | "green" | "amber" | "red" | "blue";

const toneClasses: Record<Tone, string> = {
  neutral: "border-zinc-200 bg-zinc-50 text-zinc-700",
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-rose-200 bg-rose-50 text-rose-800",
  blue: "border-cyan-200 bg-cyan-50 text-cyan-800",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex max-w-full items-center rounded-md border px-2.5 py-1 text-xs font-medium ${toneClasses[tone]}`}>
      <span className="truncate">{children}</span>
    </span>
  );
}

export function ConfidenceBadge({ value }: { value: number }) {
  const tone: Tone = value >= 0.7 ? "green" : value >= 0.45 ? "amber" : "red";
  return <Badge tone={tone}>{Math.round(value * 100)}% confidence</Badge>;
}
