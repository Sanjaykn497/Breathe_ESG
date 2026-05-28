import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { EmissionRecord, EditRecordPayload, Scope } from "@/types";

interface Props {
  record: EmissionRecord;
  onSave: (data: EditRecordPayload) => Promise<void>;
  onCancel: () => void;
}

const SCOPE_OPTIONS: { value: Scope; label: string }[] = [
  { value: "SCOPE_1", label: "Scope 1 — Direct" },
  { value: "SCOPE_2", label: "Scope 2 — Indirect (Energy)" },
  { value: "SCOPE_3", label: "Scope 3 — Value Chain" },
];

export function EditRecordForm({ record, onSave, onCancel }: Props) {
  const [form, setForm] = useState<EditRecordPayload>({
    category:        record.category,
    quantity_raw:    record.quantity_raw,
    unit_raw:        record.unit_raw,
    emission_factor: record.emission_factor,
    scope:           record.scope,
    review_notes:    record.review_notes,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  const set = (key: keyof EditRecordPayload, val: string) =>
    setForm((f) => ({ ...f, [key]: val }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSave(form);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="edit-category">Category</Label>
          <Input
            id="edit-category"
            value={form.category ?? ""}
            onChange={(e) => set("category", e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="edit-scope">Scope</Label>
          <Select
            value={form.scope ?? ""}
            onValueChange={(v) => set("scope", v)}
          >
            <SelectTrigger id="edit-scope">
              <SelectValue placeholder="Select scope" />
            </SelectTrigger>
            <SelectContent>
              {SCOPE_OPTIONS.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="edit-qty">Raw Quantity</Label>
          <Input
            id="edit-qty"
            value={form.quantity_raw ?? ""}
            onChange={(e) => set("quantity_raw", e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="edit-unit">Raw Unit</Label>
          <Input
            id="edit-unit"
            value={form.unit_raw ?? ""}
            onChange={(e) => set("unit_raw", e.target.value)}
          />
        </div>

        <div className="space-y-1 col-span-2">
          <Label htmlFor="edit-factor">Emission Factor</Label>
          <Input
            id="edit-factor"
            value={form.emission_factor ?? ""}
            onChange={(e) => set("emission_factor", e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-1">
        <Label htmlFor="edit-notes">Review Notes</Label>
        <Textarea
          id="edit-notes"
          rows={3}
          className="resize-none"
          value={form.review_notes ?? ""}
          onChange={(e) => set("review_notes", e.target.value)}
        />
      </div>

      {error && (
        <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded px-3 py-2">
          {error}
        </p>
      )}

      <Separator />

      <div className="flex gap-2">
        <Button type="submit" disabled={saving} size="sm">
          {saving ? "Saving…" : "Save Changes"}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Auto-Approved records will reset to Needs Review after any edit.
      </p>
    </form>
  );
}
