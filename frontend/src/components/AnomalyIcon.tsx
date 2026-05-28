import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  reason?: string;
  className?: string;
}

export function AnomalyIcon({ reason, className }: Props) {
  return (
    <span title={reason || "Anomaly detected"} className={cn("inline-flex", className)}>
      <AlertTriangle className="h-4 w-4 text-red-500" />
    </span>
  );
}
