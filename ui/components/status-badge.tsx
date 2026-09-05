import { Badge } from "@/components/ui/badge";
import {
  SEVERITY_LABELS,
  STATUS_LABELS,
  type ReportStatus,
  type Severity,
} from "@/lib/reports-api";

type BadgeVariant = React.ComponentProps<typeof Badge>["variant"];

const STATUS_VARIANT: Record<ReportStatus, BadgeVariant> = {
  SUBMITTED: "secondary",
  TRIAGING: "info",
  PENDING_REVIEW: "warning",
  APPROVED: "success",
  REJECTED: "destructive",
  PUBLISHED: "success",
  FAILED: "destructive",
};

const SEVERITY_VARIANT: Record<Severity, BadgeVariant> = {
  LOW: "secondary",
  MEDIUM: "info",
  HIGH: "warning",
  CRITICAL: "destructive",
};

export function StatusBadge({ status }: { status: ReportStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABELS[status]}</Badge>;
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant={SEVERITY_VARIANT[severity]}>{SEVERITY_LABELS[severity]}</Badge>
  );
}
