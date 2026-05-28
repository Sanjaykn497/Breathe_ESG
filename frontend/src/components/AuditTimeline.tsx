import { Separator } from "@/components/ui/separator";
import { formatDateTime } from "@/lib/utils";
import type { AuditLogEntry } from "@/types";

interface Props {
  entries: AuditLogEntry[];
}

const ACTION_COLORS: Record<string, string> = {
  STATUS_CHANGE: "bg-blue-500",
  FIELD_EDIT:    "bg-amber-500",
  LOCK:          "bg-neutral-500",
  REJECT:        "bg-red-500",
  INGEST:        "bg-green-500",
};

export function AuditTimeline({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic py-4 text-center">
        No audit history yet.
      </p>
    );
  }

  return (
    <ol className="relative border-l border-border ml-3 space-y-5">
      {entries.map((entry, idx) => (
        <li key={entry.id} className="ml-5">
          <span
            className={`absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-background
                        ${ACTION_COLORS[entry.action] ?? "bg-neutral-400"}`}
          />

          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-foreground uppercase tracking-wide">
                {entry.action.replace("_", " ")}
              </span>
              {entry.field_name && (
                <span className="text-xs text-muted-foreground">
                  — <code className="font-mono">{entry.field_name}</code>
                </span>
              )}
            </div>

            {entry.before_value !== null && entry.after_value !== null && (
              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="line-through text-red-400">{entry.before_value}</span>
                <span className="text-muted-foreground">→</span>
                <span className="text-green-600">{entry.after_value}</span>
              </div>
            )}

            {entry.note && (
              <p className="text-xs text-muted-foreground italic">"{entry.note}"</p>
            )}

            <p className="text-xs text-muted-foreground">
              {entry.changed_by_email ?? "System"} · {formatDateTime(entry.changed_at)}
            </p>
          </div>

          {idx < entries.length - 1 && <Separator className="mt-4" />}
        </li>
      ))}
    </ol>
  );
}
