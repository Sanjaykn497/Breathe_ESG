import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ReviewStatus } from "@/types";

const config: Record<ReviewStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline"; className: string }> = {
  AUTO_APPROVED: {
    label: "Auto Approved",
    variant: "outline",
    className: "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-50",
  },
  NEEDS_REVIEW: {
    label: "Needs Review",
    variant: "outline",
    className: "border-yellow-200 bg-yellow-50 text-yellow-800 hover:bg-yellow-50",
  },
  APPROVED: {
    label: "Approved",
    variant: "outline",
    className: "border-green-200 bg-green-50 text-green-700 hover:bg-green-50",
  },
  REJECTED: {
    label: "Rejected",
    variant: "outline",
    className: "border-red-200 bg-red-50 text-red-700 hover:bg-red-50",
  },
  LOCKED: {
    label: "Locked",
    variant: "outline",
    className: "border-neutral-200 bg-neutral-100 text-neutral-500 hover:bg-neutral-100",
  },
};

interface Props {
  status: ReviewStatus;
  className?: string;
}

export function StatusBadge({ status, className }: Props) {
  const { label, variant, className: base } = config[status];
  return (
    <Badge variant={variant} className={cn("text-xs font-medium", base, className)}>
      {label}
    </Badge>
  );
}
