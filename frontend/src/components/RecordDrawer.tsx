import { useEffect, useState } from "react";
import { Check, X, Lock, PencilLine } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusBadge } from "./StatusBadge";
import { AnomalyIcon } from "./AnomalyIcon";
import { RawPayloadViewer } from "./RawPayloadViewer";
import { AuditTimeline } from "./AuditTimeline";
import { EditRecordForm } from "./EditRecordForm";
import { api } from "@/api/api";
import { useAuth } from "@/context/AuthContext";
import { formatDate, formatDateTime } from "@/lib/utils";
import type { EmissionRecord, AuditLogEntry, EditRecordPayload } from "@/types";

interface Props {
  recordId: string | null;
  onClose: () => void;
  onActionComplete: () => void;
}

type ActionType = "approve" | "reject" | "lock";

export function RecordDrawer({ recordId, onClose, onActionComplete }: Props) {
  const { isAdmin } = useAuth();
  const [record, setRecord]     = useState<EmissionRecord | null>(null);
  const [audit, setAudit]       = useState<AuditLogEntry[]>([]);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [editMode, setEditMode] = useState(false);
  const [notes, setNotes]       = useState("");
  const [actionError, setActionError] = useState("");

  // Confirm dialog state
  const [confirmAction, setConfirmAction] = useState<ActionType | null>(null);

  useEffect(() => {
    if (!recordId) { setRecord(null); return; }
    setLoading(true);
    setError("");
    setEditMode(false);
    setNotes("");
    setActionError("");

    Promise.all([api.records.get(recordId), api.records.audit(recordId)])
      .then(([rec, log]) => { setRecord(rec); setAudit(log); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [recordId]);

  const isLocked = record?.review_status === "LOCKED";

  async function executeAction(action: ActionType) {
    if (!record) return;
    setActionError("");
    try {
      if (action === "approve") await api.records.approve(record.id, notes);
      else if (action === "reject") await api.records.reject(record.id, notes);
      else await api.records.lock(record.id);

      const [rec, log] = await Promise.all([
        api.records.get(record.id),
        api.records.audit(record.id),
      ]);
      setRecord(rec);
      setAudit(log);
      setNotes("");
      onActionComplete();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setConfirmAction(null);
    }
  }

  async function handleEdit(data: EditRecordPayload) {
    if (!record) return;
    const updated = await api.records.patch(record.id, data);
    const log     = await api.records.audit(record.id);
    setRecord(updated);
    setAudit(log);
    setEditMode(false);
    onActionComplete();
  }

  return (
    <>
      <Sheet open={!!recordId} onOpenChange={(open) => { if (!open) onClose(); }}>
        <SheetContent className="w-full sm:max-w-2xl flex flex-col p-0 gap-0">
          {/* Header */}
          <SheetHeader className="px-6 py-4 border-b border-border">
            <div className="flex items-center gap-3 flex-wrap">
              <SheetTitle className="text-base">Emission Record</SheetTitle>
              {record && <StatusBadge status={record.review_status} />}
              {record?.anomaly_flag && <AnomalyIcon reason={record.anomaly_reason} />}
              {isLocked && (
                <Badge variant="outline" className="gap-1 text-muted-foreground">
                  <Lock className="h-3 w-3" /> Locked
                </Badge>
              )}
            </div>
          </SheetHeader>

          {/* Body */}
          <ScrollArea className="flex-1">
            <div className="px-6 py-5 space-y-6">
              {loading && (
                <div className="space-y-3 animate-pulse">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="h-4 bg-muted rounded w-full" />
                  ))}
                </div>
              )}

              {error && (
                <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded px-4 py-3 text-sm">
                  {error}
                </div>
              )}

              {record && !loading && (
                <>
                  {/* Section A — Normalized Data */}
                  <section className="space-y-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
                      Normalized Data
                    </p>
                    <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
                      <DataRow label="Period">
                        {formatDate(record.period_start)}
                        {record.period_start !== record.period_end &&
                          ` → ${formatDate(record.period_end)}`}
                      </DataRow>
                      <DataRow label="Year">{record.reporting_year}</DataRow>
                      <DataRow label="Source">{record.source_type}</DataRow>
                      <DataRow label="Scope">{record.scope.replace("_", " ")}</DataRow>
                      <DataRow label="Category">{record.category}</DataRow>
                      <DataRow label="Raw">
                        {record.quantity_raw}{" "}
                        <span className="text-muted-foreground">{record.unit_raw}</span>
                      </DataRow>
                      <DataRow label="Normalized">
                        {record.quantity_normalized}{" "}
                        <span className="text-muted-foreground">{record.unit_normalized}</span>
                      </DataRow>
                      <DataRow label="Factor">
                        {record.emission_factor} kg CO₂e/{record.unit_normalized}
                      </DataRow>
                      <DataRow label="Source">{record.emission_factor_source}</DataRow>
                      <DataRow label="CO₂e">
                        <strong>{parseFloat(record.co2e_kg).toLocaleString()} kg</strong>
                      </DataRow>
                      <DataRow label="Confidence">
                        <ConfidencePill score={record.confidence_score} />
                      </DataRow>
                      {record.anomaly_flag && (
                        <DataRow label="Anomaly" className="col-span-2">
                          <span className="text-red-600 text-sm">{record.anomaly_reason}</span>
                        </DataRow>
                      )}
                    </dl>
                  </section>

                  {/* Review meta */}
                  {(record.reviewed_by_email || record.locked_by_email) && (
                    <>
                      <Separator />
                      <section className="bg-muted/40 rounded-lg px-4 py-3 text-sm space-y-1">
                        {record.reviewed_by_email && (
                          <p className="text-foreground">
                            Reviewed by <strong>{record.reviewed_by_email}</strong>
                            {record.reviewed_at && (
                              <span className="text-muted-foreground"> · {formatDateTime(record.reviewed_at)}</span>
                            )}
                          </p>
                        )}
                        {record.review_notes && (
                          <p className="text-muted-foreground italic">"{record.review_notes}"</p>
                        )}
                        {record.locked_by_email && (
                          <p className="text-foreground">
                            Locked by <strong>{record.locked_by_email}</strong>
                            {record.locked_at && (
                              <span className="text-muted-foreground"> · {formatDateTime(record.locked_at)}</span>
                            )}
                          </p>
                        )}
                      </section>
                    </>
                  )}

                  {/* Edit form */}
                  {editMode && (
                    <>
                      <Separator />
                      <section className="space-y-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
                          Edit Record
                        </p>
                        <EditRecordForm
                          record={record}
                          onSave={handleEdit}
                          onCancel={() => setEditMode(false)}
                        />
                      </section>
                    </>
                  )}

                  {/* Section B — Raw Payload */}
                  {record.raw_payload && (
                    <>
                      <Separator />
                      <RawPayloadViewer payload={record.raw_payload} />
                    </>
                  )}

                  {/* Section C — Audit History */}
                  <Separator />
                  <section className="space-y-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
                      Audit History
                    </p>
                    <AuditTimeline entries={audit} />
                  </section>
                </>
              )}
            </div>
          </ScrollArea>

          {/* Action bar */}
          {record && !loading && !editMode && (
            <div className="border-t border-border px-6 py-4 space-y-3">
              {actionError && (
                <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded px-3 py-2">
                  {actionError}
                </p>
              )}

              {!isLocked && (
                <div className="space-y-1">
                  <Label htmlFor="action-notes" className="text-xs">
                    Note (optional)
                  </Label>
                  <Input
                    id="action-notes"
                    placeholder="Add a note for this action…"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="h-8 text-sm"
                  />
                </div>
              )}

              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  className="bg-green-600 hover:bg-green-700 text-white"
                  disabled={isLocked}
                  onClick={() => setConfirmAction("approve")}
                >
                  <Check className="h-4 w-4 mr-1" /> Approve
                </Button>

                <Button
                  size="sm"
                  variant="destructive"
                  disabled={isLocked}
                  onClick={() => setConfirmAction("reject")}
                >
                  <X className="h-4 w-4 mr-1" /> Reject
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  disabled={isLocked}
                  onClick={() => setEditMode(true)}
                >
                  <PencilLine className="h-4 w-4 mr-1" /> Edit
                </Button>

                {isAdmin && (
                  <Button
                    size="sm"
                    variant="secondary"
                    className="ml-auto"
                    disabled={record.review_status !== "APPROVED"}
                    onClick={() => setConfirmAction("lock")}
                    title={
                      record.review_status !== "APPROVED"
                        ? "Must be APPROVED before locking"
                        : "Lock for audit"
                    }
                  >
                    <Lock className="h-4 w-4 mr-1" /> Lock
                  </Button>
                )}
              </div>

              {isLocked && (
                <p className="text-xs text-muted-foreground text-center">
                  This record is locked and cannot be modified.
                </p>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Confirm Dialog */}
      <Dialog open={!!confirmAction} onOpenChange={(open) => { if (!open) setConfirmAction(null); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {confirmAction === "approve" && "Approve this record?"}
              {confirmAction === "reject"  && "Reject this record?"}
              {confirmAction === "lock"    && "Lock this record?"}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {confirmAction === "approve" && "This record will be marked as Approved and available for locking."}
            {confirmAction === "reject"  && "This record will be returned to Needs Review status."}
            {confirmAction === "lock"    && "This record will be permanently locked and cannot be edited or unlocked."}
          </p>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setConfirmAction(null)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant={confirmAction === "reject" ? "destructive" : "default"}
              onClick={() => confirmAction && executeAction(confirmAction)}
            >
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DataRow({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="text-xs text-muted-foreground mb-0.5">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  );
}

function ConfidencePill({ score }: { score: number }) {
  const className =
    score >= 80
      ? "border-green-200 bg-green-50 text-green-700"
      : score >= 50
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-red-200 bg-red-50 text-red-700";

  return (
    <Badge variant="outline" className={`text-xs font-semibold ${className}`}>
      {score}/100
    </Badge>
  );
}
