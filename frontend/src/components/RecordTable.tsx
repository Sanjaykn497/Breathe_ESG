import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "./StatusBadge";
import { AnomalyIcon }  from "./AnomalyIcon";
import { formatDate }   from "@/lib/utils";
import type { EmissionRecord } from "@/types";

interface Props {
  records: EmissionRecord[];
  loading: boolean;
  onRowClick: (id: string) => void;
}

export function RecordTable({ records, loading, onRowClick }: Props) {
  if (loading) {
    return (
      <div className="divide-y divide-border">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-4 px-4 py-3 animate-pulse">
            {Array.from({ length: 7 }).map((_, j) => (
              <div key={j} className="h-4 bg-muted rounded flex-1" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="py-16 text-center text-muted-foreground text-sm">
        No records found.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="bg-muted/40 hover:bg-muted/40">
          <TableHead>Period</TableHead>
          <TableHead>Scope</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Raw Qty</TableHead>
          <TableHead>CO₂e (kg)</TableHead>
          <TableHead>Confidence</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="w-8"></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {records.map((r) => (
          <TableRow
            key={r.id}
            className="cursor-pointer"
            onClick={() => onRowClick(r.id)}
          >
            <TableCell className="text-muted-foreground whitespace-nowrap">
              {formatDate(r.period_start)}
              {r.period_start !== r.period_end && (
                <span className="text-muted-foreground/60"> → {formatDate(r.period_end)}</span>
              )}
            </TableCell>

            <TableCell className="font-mono text-xs">
              {r.scope.replace("SCOPE_", "S")}
            </TableCell>

            <TableCell className="font-medium">
              {r.category}
            </TableCell>

            <TableCell className="text-muted-foreground whitespace-nowrap">
              {r.quantity_raw}{" "}
              <span className="text-muted-foreground/60 text-xs">{r.unit_raw}</span>
            </TableCell>

            <TableCell className="font-mono">
              {parseFloat(r.co2e_kg).toLocaleString()}
            </TableCell>

            <TableCell>
              <ConfidenceBar score={r.confidence_score} />
            </TableCell>

            <TableCell>
              <StatusBadge status={r.review_status} />
            </TableCell>

            <TableCell>
              {r.anomaly_flag && <AnomalyIcon reason={r.anomaly_reason} />}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ConfidenceBar({ score }: { score: number }) {
  const color =
    score >= 80 ? "bg-green-500" : score >= 50 ? "bg-amber-500" : "bg-red-500";

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs text-muted-foreground">{score}</span>
    </div>
  );
}
