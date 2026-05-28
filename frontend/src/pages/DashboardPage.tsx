import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, Upload, RefreshCw } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { RecordTable } from "@/components/RecordTable";
import { RecordDrawer } from "@/components/RecordDrawer";
import { api } from "@/api/api";
import { useAuth } from "@/context/AuthContext";
import type { EmissionRecord, ReviewStatus, Scope, RecordFilters } from "@/types";

const TAB_STATUSES: { label: string; value: ReviewStatus | "ALL" }[] = [
  { label: "Needs Review", value: "NEEDS_REVIEW" },
  { label: "All Records",  value: "ALL" },
  { label: "Approved",     value: "APPROVED" },
  { label: "Locked",       value: "LOCKED" },
];

const SCOPES: { label: string; value: Scope | "" }[] = [
  { label: "All Scopes", value: "" },
  { label: "Scope 1",    value: "SCOPE_1" },
  { label: "Scope 2",    value: "SCOPE_2" },
  { label: "Scope 3",    value: "SCOPE_3" },
];

const YEARS = ["", "2024", "2023", "2022"];

export default function DashboardPage() {
  const { user, setUser, isAdmin } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab]     = useState<ReviewStatus | "ALL">("NEEDS_REVIEW");
  const [records, setRecords]         = useState<EmissionRecord[]>([]);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");
  const [selectedId, setSelectedId]   = useState<string | null>(null);
  const [scope, setScope]             = useState<Scope | "">("");
  const [year, setYear]               = useState("");
  const [anomalyOnly, setAnomalyOnly] = useState(false);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const filters: RecordFilters = {
        scope:          scope || undefined,
        review_status:  activeTab === "ALL" ? undefined : activeTab,
        reporting_year: year || undefined,
        anomaly_flag:   anomalyOnly || undefined,
      };
      const data = await api.records.list(filters);
      setRecords(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load records");
    } finally {
      setLoading(false);
    }
  }, [activeTab, scope, year, anomalyOnly]);

  useEffect(() => { fetchRecords(); }, [fetchRecords]);

  function handleLogout() {
    setUser(null);
    navigate("/");
  }

  return (
    <div className="min-h-screen bg-muted/20">
      {/* Top nav */}
      <header className="bg-background border-b border-border sticky top-0 z-30">
        <div className="page-container flex items-center justify-between py-3">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded bg-neutral-900 text-white flex items-center
                            justify-center text-sm font-bold shrink-0">
              B
            </div>
            <div>
              <p className="text-sm font-semibold leading-none">breathe ESG</p>
              <p className="text-xs text-muted-foreground mt-0.5">Emissions Review</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/ingest")}
              className="gap-1.5"
            >
              <Upload className="h-4 w-4" /> Ingest Data
            </Button>

            <Separator orientation="vertical" className="h-6" />

            <div className="flex items-center gap-2 text-sm">
              <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center
                              text-xs font-semibold text-muted-foreground">
                {user?.email?.[0]?.toUpperCase()}
              </div>
              <span className="text-foreground hidden sm:block">{user?.email}</span>
              {isAdmin && (
                <Badge variant="secondary" className="text-xs">Admin</Badge>
              )}
            </div>

            <Button variant="ghost" size="icon" onClick={handleLogout} className="h-8 w-8">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="page-container mt-4 space-y-4">
        <div className="flex items-center justify-between">
          <h1>Emission Records</h1>
          <span className="text-sm text-muted-foreground">
            {records.length} record{records.length !== 1 ? "s" : ""}
          </span>
        </div>

        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as ReviewStatus | "ALL")}>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <TabsList>
              {TAB_STATUSES.map((t) => (
                <TabsTrigger key={t.value} value={t.value}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {/* Filter bar */}
            <div className="flex items-center gap-3 flex-wrap">
              <Select value={scope} onValueChange={(v) => setScope(v as Scope | "")}>
                <SelectTrigger className="w-36 h-8 text-sm">
                  <SelectValue placeholder="All Scopes" />
                </SelectTrigger>
                <SelectContent>
                  {SCOPES.map((s) => (
                    <SelectItem key={s.value} value={s.value || "__all__"}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={year} onValueChange={setYear}>
                <SelectTrigger className="w-32 h-8 text-sm">
                  <SelectValue placeholder="All Years" />
                </SelectTrigger>
                <SelectContent>
                  {YEARS.map((y) => (
                    <SelectItem key={y} value={y || "__all__"}>
                      {y || "All Years"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <div className="flex items-center gap-2">
                <Switch
                  id="anomaly-toggle"
                  checked={anomalyOnly}
                  onCheckedChange={setAnomalyOnly}
                />
                <Label htmlFor="anomaly-toggle" className="text-sm cursor-pointer">
                  Anomalies only
                </Label>
              </div>

              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={fetchRecords}
                title="Refresh"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {error && (
            <div className="mt-3 bg-destructive/10 border border-destructive/20 text-destructive rounded px-4 py-3 text-sm">
              {error}
            </div>
          )}

          {TAB_STATUSES.map((t) => (
            <TabsContent key={t.value} value={t.value} className="mt-3">
              <div className="rounded-lg border border-border bg-background shadow-sm overflow-hidden">
                <RecordTable
                  records={records}
                  loading={loading}
                  onRowClick={setSelectedId}
                />
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </main>

      <RecordDrawer
        recordId={selectedId}
        onClose={() => setSelectedId(null)}
        onActionComplete={fetchRecords}
      />
    </div>
  );
}
