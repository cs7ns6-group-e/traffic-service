import { useState, useEffect } from "react";
import { MapPin, XCircle, Plus, Search, Filter, AlertCircle, Radio, Lock } from "lucide-react";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { RegionBadge } from "../components/RegionBadge";
import { Modal } from "../components/Modal";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Checkbox } from "../components/ui/checkbox";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { toast } from "sonner";
import { apiGet, apiPost } from "../api/client";
import { ENDPOINTS } from "../api/config";

interface AuthorityJourney {
  id: string;
  driver_id: string;
  origin: string;
  destination: string;
  start_time: string;
  status: "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED" | "EMERGENCY_CONFIRMED";
  region: "EU" | "US" | "APAC";
  vehicle_type?: "STANDARD" | "EMERGENCY" | "AUTHORITY";
}

interface Closure {
  closure_id?: string;
  id?: string;
  road_name: string;
  reason: string;
  region?: string;
  created_at?: string;
  affected_journeys?: number;
}

interface ClosurePreview {
  road_name: string;
  affected_journeys: number;
  emergency_skipped: number;
  affected_routes?: Array<string | { origin: string; destination: string }>;
}

interface ClosureResult {
  closure_id: string;
  road_name: string;
  affected_journeys: number;
  emergency_skipped: number;
  cancelled_journey_ids?: string[];
}

interface AuthorityStats {
  active_journeys?: number;
  cancelled_today?: number;
  road_closures?: number;
  cross_region?: number;
}

function routeLabel(r: string | { origin: string; destination: string }): string {
  return typeof r === "string" ? r : `${r.origin} → ${r.destination}`;
}

export default function TrafficAuthorityDashboard() {
  const [selectedRegion, setSelectedRegion] = useState<"EU" | "US" | "APAC">("EU");
  const [isClosureModalOpen, setIsClosureModalOpen] = useState(false);
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [closureData, setClosureData] = useState({
    roadName: "",
    region: "EU" as "EU" | "US" | "APAC",
    reason: "",
    cancelAffected: false,
  });

  // Segments dropdown state
  const [availableSegments, setAvailableSegments] = useState<string[]>([]);

  // Preview state
  const [closurePreview, setClosurePreview] = useState<ClosurePreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"All" | "Confirmed" | "Pending" | "Cancelled">("All");

  const [journeys, setJourneys] = useState<AuthorityJourney[]>([]);
  const [closures, setClosures] = useState<Closure[]>([]);
  const [stats, setStats] = useState<AuthorityStats>({});
  const [loadingJourneys, setLoadingJourneys] = useState(true);
  const [submittingClosure, setSubmittingClosure] = useState(false);
  const [closureResult, setClosureResult] = useState<ClosureResult | null>(null);

  const [cancelTarget, setCancelTarget] = useState<AuthorityJourney | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    fetchAll();
    apiGet<unknown>(ENDPOINTS.AUTHORITY_SEGMENTS)
      .then((res) => {
        const obj = res as { segments?: unknown };
        setAvailableSegments(
          Array.isArray(obj?.segments) ? (obj.segments as string[]) :
          Array.isArray(res) ? (res as string[]) : []
        );
      })
      .catch(() => {});
  }, []);

  function fetchAll() {
    setLoadingJourneys(true);
    apiGet<AuthorityJourney[]>(ENDPOINTS.AUTHORITY_JOURNEYS)
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        const sorted = [...list].sort((a, b) => {
          const ae = a.vehicle_type === "EMERGENCY" || a.status === "EMERGENCY_CONFIRMED" ? 0 : 1;
          const be = b.vehicle_type === "EMERGENCY" || b.status === "EMERGENCY_CONFIRMED" ? 0 : 1;
          return ae - be;
        });
        setJourneys(sorted);
      })
      .catch(() => {})
      .finally(() => setLoadingJourneys(false));

    apiGet<Closure[]>(ENDPOINTS.AUTHORITY_CLOSURES).then((data) => setClosures(Array.isArray(data) ? data : [])).catch(() => {});
    apiGet<AuthorityStats>(ENDPOINTS.AUTHORITY_STATS).then(setStats).catch(() => {});
  }

  const displayStats = {
    activeJourneys: stats.active_journeys ?? journeys.filter(j => j.status === "CONFIRMED" || j.status === "PENDING" || j.status === "EMERGENCY_CONFIRMED").length,
    cancelledToday: stats.cancelled_today ?? journeys.filter(j => j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED").length,
    roadClosures: stats.road_closures ?? closures.length,
    crossRegion: stats.cross_region ?? 0,
  };

  const filtered = journeys.filter(j => {
    const matchSearch = search === "" ||
      j.id.toLowerCase().includes(search.toLowerCase()) ||
      j.origin.toLowerCase().includes(search.toLowerCase()) ||
      j.destination.toLowerCase().includes(search.toLowerCase());
    const matchStatus =
      statusFilter === "All" ||
      (statusFilter === "Confirmed" && (j.status === "CONFIRMED" || j.status === "EMERGENCY_CONFIRMED")) ||
      (statusFilter === "Pending" && j.status === "PENDING") ||
      (statusFilter === "Cancelled" && (j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED"));
    return matchSearch && matchStatus;
  });

  const chartData = ["EU", "US", "APAC"].map(r => ({
    region: r,
    confirmed: journeys.filter(j => j.region === r && (j.status === "CONFIRMED" || j.status === "EMERGENCY_CONFIRMED")).length,
    pending: journeys.filter(j => j.region === r && j.status === "PENDING").length,
    cancelled: journeys.filter(j => j.region === r && (j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED")).length,
  }));

  async function handleForceCancel() {
    if (!cancelTarget || !cancelReason.trim()) { toast.error("Please enter a reason"); return; }
    setCancelling(true);
    try {
      await apiPost(ENDPOINTS.AUTHORITY_CANCEL(cancelTarget.id), { reason: cancelReason });
      toast.success(`Journey ${cancelTarget.id.slice(0, 8)} force-cancelled`);
      setCancelTarget(null);
      setCancelReason("");
      fetchAll();
    } catch (err: unknown) {
      toast.error("Cancel failed", { description: err instanceof Error ? err.message : "Unknown" });
    } finally {
      setCancelling(false);
    }
  }

  async function handlePreviewClosure() {
    if (!closureData.roadName || !closureData.reason) {
      toast.error("Enter a road name and reason first");
      return;
    }
    setLoadingPreview(true);
    try {
      const preview = await apiGet<ClosurePreview>(
        ENDPOINTS.AUTHORITY_CLOSURE_PREVIEW(closureData.roadName)
      );
      setClosurePreview(preview);
    } catch (err: unknown) {
      toast.error("Preview failed", { description: err instanceof Error ? err.message : "Unknown" });
    } finally {
      setLoadingPreview(false);
    }
  }

  async function handleConfirmClosure() {
    setSubmittingClosure(true);
    try {
      const result = await apiPost<ClosureResult>(ENDPOINTS.AUTHORITY_CLOSURE, {
        road_name: closureData.roadName,
        reason: closureData.reason,
        region: closureData.region,
      });
      setClosurePreview(null);
      setIsClosureModalOpen(false);
      setClosureData({ roadName: "", region: "EU", reason: "", cancelAffected: false });
      setClosureResult(result);
      fetchAll();
    } catch (err: unknown) {
      toast.error("Closure failed", { description: err instanceof Error ? err.message : "Unknown" });
    } finally {
      setSubmittingClosure(false);
    }
  }

  function resetClosureModal() {
    setIsClosureModalOpen(false);
    setClosureData({ roadName: "", region: "EU", reason: "", cancelAffected: false });
    setClosurePreview(null);
  }

  function formatTime(t: string) {
    try { return new Date(t).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
    catch { return t; }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Traffic Authority Control Panel</h1>
          <p className="text-gray-600 mt-1">Monitor and manage road journeys in your region.</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={selectedRegion} onValueChange={(v: "EU" | "US" | "APAC") => setSelectedRegion(v)}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="EU">EU</SelectItem>
              <SelectItem value="US">US</SelectItem>
              <SelectItem value="APAC">APAC</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => setIsBroadcastModalOpen(true)} variant="outline" className="gap-2">
            <Radio className="w-4 h-4" />Broadcast
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Active Journeys" value={displayStats.activeJourneys} icon={MapPin} />
        <StatCard label="Cancelled Today" value={displayStats.cancelledToday} icon={XCircle} />
        <StatCard label="Road Closures" value={displayStats.roadClosures} icon={AlertCircle} />
        <StatCard label="Cross-Region" value={displayStats.crossRegion} />
      </div>

      {/* Chart */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-6">Journey Volume by Region</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="region" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="confirmed" fill="#16A34A" name="Confirmed" />
            <Bar dataKey="pending" fill="#F59E0B" name="Pending" />
            <Bar dataKey="cancelled" fill="#DC2626" name="Cancelled" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Active Closures */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900">Active Road Closures</h2>
          <Button onClick={() => setIsClosureModalOpen(true)} className="bg-[#2563EB] hover:bg-[#1d4ed8]">
            <Plus className="w-4 h-4 mr-2" />Create Closure
          </Button>
        </div>
        {closures.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">No active road closures</p>
        ) : (
          <div className="space-y-4">
            {closures.map((c, i) => (
              <div key={c.closure_id ?? c.id ?? i} className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-1">
                  <AlertCircle className="w-4 h-4 text-red-600" />
                  <h3 className="font-semibold text-gray-900">{c.road_name}</h3>
                  {c.region && <RegionBadge region={c.region as "EU" | "US" | "APAC"} />}
                </div>
                <p className="text-sm text-gray-700">{c.reason}</p>
                {(c.created_at || c.affected_journeys !== undefined) && (
                  <div className="flex gap-4 text-xs text-gray-500 mt-1">
                    {c.created_at && <span>Created: {formatTime(c.created_at)}</span>}
                    {c.affected_journeys !== undefined && <span>Affected: {c.affected_journeys}</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Journeys Table */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
          <h2 className="text-xl font-bold text-gray-900">Active Journeys</h2>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:flex-initial">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input placeholder="Search..." className="pl-10 h-10 sm:w-64" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <Button variant="outline" size="icon" className="h-10 w-10"><Filter className="w-4 h-4" /></Button>
          </div>
        </div>

        <div className="flex gap-2 mb-4">
          {(["All", "Confirmed", "Pending", "Cancelled"] as const).map(f => (
            <button
              key={f}
              type="button"
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${statusFilter === f ? "bg-[#2563EB] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
            >
              {f}
            </button>
          ))}
        </div>

        {loadingJourneys ? (
          <div className="space-y-3 animate-pulse">{[0,1,2].map(i => <div key={i} className="h-12 bg-gray-100 rounded" />)}</div>
        ) : filtered.length === 0 ? (
          <p className="text-center py-8 text-gray-500">No journeys found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Journey ID</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Route</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Time</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((j) => {
                  const isEmerg = j.vehicle_type === "EMERGENCY" || j.status === "EMERGENCY_CONFIRMED";
                  const displayStatus = j.status === "EMERGENCY_CONFIRMED" ? "CONFIRMED" : j.status;
                  const isCancelled = j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED";
                  return (
                    <tr key={j.id} className={`border-b border-gray-100 hover:bg-gray-50 ${isEmerg ? "bg-red-50" : ""}`}>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-gray-900">#{j.id.slice(0, 8)}</span>
                          {isEmerg && <span className="text-xs text-red-600 font-bold">🚨 EMERGENCY</span>}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-sm text-gray-900">{j.origin} → {j.destination}</div>
                        <RegionBadge region={j.region} />
                      </td>
                      <td className="py-3 px-4 text-sm text-gray-600">{formatTime(j.start_time)}</td>
                      <td className="py-3 px-4">
                        <StatusBadge status={displayStatus as "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED"} />
                      </td>
                      <td className="py-3 px-4">
                        {isEmerg ? (
                          <div className="flex items-center gap-1 text-gray-400 text-sm">
                            <Lock className="w-4 h-4" />
                            <span>Protected</span>
                          </div>
                        ) : (
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={isCancelled}
                            onClick={() => { setCancelTarget(j); setCancelReason(""); }}
                          >
                            Force Cancel
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Create Closure Dialog ──────────────────────────────────────── */}
      <Dialog open={isClosureModalOpen} onOpenChange={(open) => { if (!open) resetClosureModal(); }}>
        <DialogContent>
          <DialogHeader><DialogTitle>Create Road Closure</DialogTitle></DialogHeader>
          <div className="space-y-4 py-4">

            {/* Region */}
            <div className="space-y-2">
              <Label>Region</Label>
              <Select
                value={closureData.region}
                onValueChange={(v: "EU" | "US" | "APAC") => setClosureData({ ...closureData, region: v, roadName: "" })}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="EU">EU</SelectItem>
                  <SelectItem value="US">US</SelectItem>
                  <SelectItem value="APAC">APAC</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Road Name — pure select dropdown */}
            <div className="space-y-2">
              <Label>Road Name</Label>
              <select
                value={closureData.roadName}
                onChange={(e) => setClosureData(d => ({ ...d, roadName: e.target.value }))}
                className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              >
                <option value="">Select a road segment...</option>
                {(Array.isArray(availableSegments) ? availableSegments : []).map(seg => (
                  <option key={seg} value={seg}>{seg}</option>
                ))}
                {(!Array.isArray(availableSegments) || availableSegments.length === 0) && (
                  <option disabled>No active journeys — book journeys first</option>
                )}
              </select>
              <p className="text-xs text-gray-500">
                {(Array.isArray(availableSegments) ? availableSegments : []).length} road segments available from active journeys
              </p>
            </div>

            {/* Reason */}
            <div className="space-y-2">
              <Label>Reason</Label>
              <Textarea
                placeholder="Describe reason for closure..."
                value={closureData.reason}
                onChange={(e) => setClosureData(d => ({ ...d, reason: e.target.value }))}
              />
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="cancel-affected"
                checked={closureData.cancelAffected}
                onCheckedChange={(c) => setClosureData(d => ({ ...d, cancelAffected: c as boolean }))}
              />
              <label htmlFor="cancel-affected" className="text-sm text-gray-700">Cancel all affected journeys</label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={resetClosureModal}>Cancel</Button>
            <Button
              onClick={handlePreviewClosure}
              disabled={!closureData.roadName || !closureData.reason || loadingPreview}
              className="bg-[#2563EB] hover:bg-[#1d4ed8]"
            >
              {loadingPreview ? "Loading…" : "Preview & Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Closure Preview Modal ──────────────────────────────────────── */}
      <Modal isOpen={!!closurePreview} onClose={() => setClosurePreview(null)} title="Closure Preview">
        {closurePreview && (
          <div className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <p className="font-semibold text-amber-900">
                Closing <span className="font-bold">{closurePreview.road_name}</span> will cancel:
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-2xl font-bold text-gray-900">{closurePreview.affected_journeys}</p>
                <p className="text-xs text-gray-500 mt-1">Journeys affected</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-2xl font-bold text-red-600">{closurePreview.emergency_skipped}</p>
                <p className="text-xs text-gray-500 mt-1">Emergency vehicles skipped</p>
              </div>
            </div>

            {closurePreview.affected_routes && closurePreview.affected_routes.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-2">Affected Routes</p>
                <div className="space-y-1 max-h-32 overflow-y-auto bg-gray-50 rounded-lg p-3">
                  {closurePreview.affected_routes.map((r, i) => (
                    <p key={i} className="text-sm text-gray-700">• {routeLabel(r)}</p>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button variant="outline" onClick={() => setClosurePreview(null)} className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={handleConfirmClosure}
                disabled={submittingClosure}
                className="flex-1 bg-red-600 hover:bg-red-700"
              >
                {submittingClosure ? "Creating…" : "Confirm Closure"}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Closure Result Modal ───────────────────────────────────────── */}
      <Modal isOpen={!!closureResult} onClose={() => setClosureResult(null)} title="Road Closure Created">
        {closureResult && (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="font-semibold text-green-900">Road closed: {closureResult.road_name}</p>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-2 border-b">
                <span className="text-gray-600">Journeys cancelled</span>
                <span className="font-bold text-gray-900">{closureResult.affected_journeys}</span>
              </div>
              <div className="flex justify-between py-2 border-b">
                <span className="text-gray-600">Emergency vehicles skipped</span>
                <span className="font-bold text-red-600">{closureResult.emergency_skipped}</span>
              </div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
              📱 Telegram notifications sent to all affected drivers
            </div>
            {closureResult.cancelled_journey_ids && closureResult.cancelled_journey_ids.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-2">Cancelled Journey IDs</p>
                <div className="space-y-1 max-h-28 overflow-y-auto bg-gray-50 rounded p-2">
                  {closureResult.cancelled_journey_ids.map(id => (
                    <p key={id} className="text-xs font-mono text-gray-600">{id}</p>
                  ))}
                </div>
              </div>
            )}
            <Button onClick={() => setClosureResult(null)} className="w-full bg-[#2563EB] hover:bg-[#1d4ed8]">Done</Button>
          </div>
        )}
      </Modal>

      {/* ── Force Cancel Modal ─────────────────────────────────────────── */}
      <Modal isOpen={!!cancelTarget} onClose={() => setCancelTarget(null)} title="Force Cancel Journey">
        {cancelTarget && (
          <div className="space-y-4">
            <p className="text-sm text-gray-700">
              Cancel <span className="font-mono">#{cancelTarget.id.slice(0, 8)}</span>:{" "}
              {cancelTarget.origin} → {cancelTarget.destination}
            </p>
            <div className="space-y-2">
              <Label>Reason (required)</Label>
              <Textarea
                placeholder="Enter reason for force cancellation..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                rows={3}
              />
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setCancelTarget(null)} disabled={cancelling} className="flex-1">Back</Button>
              <Button variant="destructive" onClick={handleForceCancel} disabled={cancelling || !cancelReason.trim()} className="flex-1">
                {cancelling ? "Cancelling…" : "Confirm Cancel"}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Broadcast Dialog ───────────────────────────────────────────── */}
      <Dialog open={isBroadcastModalOpen} onOpenChange={setIsBroadcastModalOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Broadcast Alert</DialogTitle></DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Message</Label>
              <Textarea placeholder="Enter broadcast message..." rows={6} />
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              This message will be sent to all drivers in the {selectedRegion} region.
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBroadcastModalOpen(false)}>Cancel</Button>
            <Button onClick={() => { toast.success("Broadcast sent"); setIsBroadcastModalOpen(false); }} className="bg-[#2563EB] hover:bg-[#1d4ed8]">
              Send Broadcast
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
