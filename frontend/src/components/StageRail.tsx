import { CheckCircle2, ClipboardList, FileSearch, FlaskConical } from "lucide-react";

type Stage = "input" | "qc" | "plan";

interface StageRailProps {
  active: Stage;
  hasQc: boolean;
  hasPlan: boolean;
}

const stages = [
  { id: "input", label: "Hypothesis", shortLabel: "Hypothesis", icon: ClipboardList },
  { id: "qc", label: "Literature QC", shortLabel: "QC", icon: FileSearch },
  { id: "plan", label: "Plan", shortLabel: "Plan", icon: FlaskConical },
] as const;

export function StageRail({ active, hasQc, hasPlan }: StageRailProps) {
  return (
    <div className="grid grid-cols-3 gap-2 rounded-lg border border-zinc-200 bg-white p-1" aria-label="Workflow stages">
      {stages.map((stage) => {
        const Icon = stage.icon;
        const complete = (stage.id === "qc" && hasQc) || (stage.id === "plan" && hasPlan);
        const selected = active === stage.id;
        return (
          <div
            key={stage.id}
            className={`flex min-h-12 items-center gap-2 rounded-md px-3 text-sm transition ${
              selected ? "bg-zinc-950 text-white" : complete ? "bg-zinc-100 text-zinc-900" : "text-zinc-500"
            }`}
          >
            {complete ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <Icon className="h-4 w-4 shrink-0" />}
            <span className="hidden truncate sm:inline">{stage.label}</span>
            <span className="truncate sm:hidden">{stage.shortLabel}</span>
          </div>
        );
      })}
    </div>
  );
}
