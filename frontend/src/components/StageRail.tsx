import { CheckCircle2, ClipboardList, FileSearch, FlaskConical } from "lucide-react";

type Stage = "input" | "qc" | "plan";

interface StageRailProps {
  active: Stage;
  hasQc: boolean;
  hasPlan: boolean;
}

const stages = [
  { id: "input", label: "Hypothesis", icon: ClipboardList },
  { id: "qc", label: "Literature QC", icon: FileSearch },
  { id: "plan", label: "Plan", icon: FlaskConical },
] as const;

export function StageRail({ active, hasQc, hasPlan }: StageRailProps) {
  return (
    <div className="grid grid-cols-3 gap-2" aria-label="Workflow stages">
      {stages.map((stage) => {
        const Icon = stage.icon;
        const complete = (stage.id === "qc" && hasQc) || (stage.id === "plan" && hasPlan);
        const selected = active === stage.id;
        return (
          <div
            key={stage.id}
            className={`flex min-h-12 items-center gap-2 rounded-md border px-3 text-sm transition ${
              selected ? "border-zinc-900 bg-zinc-950 text-white" : "border-zinc-200 bg-white text-zinc-700"
            }`}
          >
            {complete ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <Icon className="h-4 w-4 shrink-0" />}
            <span className="truncate">{stage.label}</span>
          </div>
        );
      })}
    </div>
  );
}

