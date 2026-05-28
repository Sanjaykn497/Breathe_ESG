import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Upload, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { api } from "@/api/api";
import type { DataSource } from "@/types";

interface CardState {
  loading: boolean;
  result:  DataSource | null;
  error:   string;
}

const EMPTY: CardState = { loading: false, result: null, error: "" };
const CURRENT_YEAR = new Date().getFullYear();

export default function IngestionPage() {
  const navigate = useNavigate();

  const [sapState, setSapState]         = useState(EMPTY);
  const [utilityState, setUtilityState] = useState(EMPTY);
  const [travelState, setTravelState]   = useState(EMPTY);

  // SAP
  const [sapCsv, setSapCsv]   = useState("");
  const [sapName, setSapName] = useState("SAP Upload");
  const [sapYear, setSapYear] = useState(CURRENT_YEAR);

  // Utility
  const [utilityCsv, setUtilityCsv]   = useState("");
  const [utilityName, setUtilityName] = useState("Utility Upload");
  const [utilityYear, setUtilityYear] = useState(CURRENT_YEAR);

  // Travel
  const [travelJson, setTravelJson]   = useState("");
  const [travelName, setTravelName]   = useState("Travel Upload");
  const [travelYear, setTravelYear]   = useState(CURRENT_YEAR);

  async function ingestSap(e: React.FormEvent) {
    e.preventDefault();
    setSapState({ loading: true, result: null, error: "" });
    try {
      const result = await api.ingest.sap({ csv_text: sapCsv, name: sapName, reporting_year: sapYear });
      setSapState({ loading: false, result, error: "" });
    } catch (err: unknown) {
      setSapState({ loading: false, result: null, error: err instanceof Error ? err.message : "Failed" });
    }
  }

  async function ingestUtility(e: React.FormEvent) {
    e.preventDefault();
    setUtilityState({ loading: true, result: null, error: "" });
    try {
      const result = await api.ingest.utility({ csv_text: utilityCsv, name: utilityName, reporting_year: utilityYear });
      setUtilityState({ loading: false, result, error: "" });
    } catch (err: unknown) {
      setUtilityState({ loading: false, result: null, error: err instanceof Error ? err.message : "Failed" });
    }
  }

  async function ingestTravel(e: React.FormEvent) {
    e.preventDefault();
    let records: Record<string, unknown>[] = [];
    try {
      const parsed = JSON.parse(travelJson);
      records = Array.isArray(parsed) ? parsed : (parsed.records ?? []);
    } catch {
      setTravelState({ loading: false, result: null, error: "Invalid JSON format" });
      return;
    }
    setTravelState({ loading: true, result: null, error: "" });
    try {
      const result = await api.ingest.travel({ records, name: travelName, reporting_year: travelYear });
      setTravelState({ loading: false, result, error: "" });
    } catch (err: unknown) {
      setTravelState({ loading: false, result: null, error: err instanceof Error ? err.message : "Failed" });
    }
  }

  return (
    <div className="min-h-screen bg-muted/20">
      <header className="bg-background border-b border-border">
        <div className="page-container flex items-center gap-4 py-3">
          <Button variant="outline" size="sm" onClick={() => navigate("/dashboard")} className="gap-1.5">
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <div>
            <p className="text-sm font-semibold leading-none">Ingest Data</p>
            <p className="text-xs text-muted-foreground mt-0.5">Upload emission source data</p>
          </div>
        </div>
      </header>

      <main className="page-container mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* SAP */}
        <IngestionCard
          title="SAP"
          subtitle="Fuel & Procurement CSV"
          state={sapState}
          onSubmit={ingestSap}
        >
          <FormRow label="Feed Name" id="sap-name">
            <Input id="sap-name" value={sapName} onChange={(e) => setSapName(e.target.value)} />
          </FormRow>
          <FormRow label="Reporting Year" id="sap-year">
            <Input id="sap-year" type="number" value={sapYear} onChange={(e) => setSapYear(+e.target.value)} />
          </FormRow>
          <FormRow label="CSV Data" id="sap-csv">
            <Textarea
              id="sap-csv"
              className="font-mono text-xs resize-none"
              rows={8}
              placeholder={`plant_code,quantity,unit,document_date\nPLT001,500,L,2024-01-15`}
              value={sapCsv}
              onChange={(e) => setSapCsv(e.target.value)}
            />
          </FormRow>
        </IngestionCard>

        {/* Utility */}
        <IngestionCard
          title="Utility"
          subtitle="Electricity Bills CSV"
          state={utilityState}
          onSubmit={ingestUtility}
        >
          <FormRow label="Feed Name" id="util-name">
            <Input id="util-name" value={utilityName} onChange={(e) => setUtilityName(e.target.value)} />
          </FormRow>
          <FormRow label="Reporting Year" id="util-year">
            <Input id="util-year" type="number" value={utilityYear} onChange={(e) => setUtilityYear(+e.target.value)} />
          </FormRow>
          <FormRow label="CSV Data" id="util-csv">
            <Textarea
              id="util-csv"
              className="font-mono text-xs resize-none"
              rows={8}
              placeholder={`kwh_usage,period_start,period_end\n12500,2024-01-01,2024-01-31`}
              value={utilityCsv}
              onChange={(e) => setUtilityCsv(e.target.value)}
            />
          </FormRow>
        </IngestionCard>

        {/* Travel */}
        <IngestionCard
          title="Corporate Travel"
          subtitle="Flights, Hotels & Ground JSON"
          state={travelState}
          onSubmit={ingestTravel}
        >
          <FormRow label="Feed Name" id="travel-name">
            <Input id="travel-name" value={travelName} onChange={(e) => setTravelName(e.target.value)} />
          </FormRow>
          <FormRow label="Reporting Year" id="travel-year">
            <Input id="travel-year" type="number" value={travelYear} onChange={(e) => setTravelYear(+e.target.value)} />
          </FormRow>
          <FormRow label="JSON Payload" id="travel-json">
            <Textarea
              id="travel-json"
              className="font-mono text-xs resize-none"
              rows={8}
              placeholder={`[\n  {"travel_type":"FLIGHT","distance_km":850,"travel_date":"2024-03-10"},\n  {"travel_type":"HOTEL","nights":2,"travel_date":"2024-03-10"}\n]`}
              value={travelJson}
              onChange={(e) => setTravelJson(e.target.value)}
            />
          </FormRow>
        </IngestionCard>
      </main>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────

interface IngestionCardProps {
  title: string;
  subtitle: string;
  state: CardState;
  onSubmit: (e: React.FormEvent) => void;
  children: React.ReactNode;
}

function IngestionCard({ title, subtitle, state, onSubmit, children }: IngestionCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-sm">{title}</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
          </div>
          <Upload className="h-4 w-4 text-muted-foreground/40" />
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 flex-1">
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          {children}
          <Button type="submit" disabled={state.loading} className="w-full gap-2">
            {state.loading
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Processing…</>
              : "Ingest"
            }
          </Button>
        </form>

        {state.result && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-green-700">
                <CheckCircle2 className="h-4 w-4" />
                <span className="font-medium">
                  {state.result.ingestion_status === "COMPLETED" ? "Completed" : state.result.ingestion_status}
                </span>
                <Badge variant="outline" className="ml-auto border-green-200 text-green-700 bg-green-50">
                  {state.result.row_count} rows
                </Badge>
              </div>

              {state.result.error_summary && state.result.error_summary.length > 0 && (
                <details className="text-xs text-amber-700">
                  <summary className="cursor-pointer font-medium">
                    {state.result.error_summary.length} row error{state.result.error_summary.length !== 1 ? "s" : ""}
                  </summary>
                  <ul className="mt-1 space-y-0.5 font-mono">
                    {state.result.error_summary.map((e, i) => (
                      <li key={i}>Row {e.row}: {e.error}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </>
        )}

        {state.error && (
          <>
            <Separator />
            <div className="flex gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{state.error}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function FormRow({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}
