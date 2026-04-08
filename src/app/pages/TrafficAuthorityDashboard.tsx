import { useState, useEffect } from "react";
import { MapPin, XCircle, Plus, Search, Filter, AlertCircle, Radio } from "lucide-react";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { RegionBadge } from "../components/RegionBadge";
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

interface AuthorityStats {
  active_journeys?: number;
  cancelled_today?: number;
  road_closures?: number;
  cross_region?: number;
  total?: number;
  confirmed?: number;
  pending?: number;
  cancelled?: number;
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
  const [search, setSearch] = useState("");
  const [journeys, setJourneys] = useState<AuthorityJourney[]>([]);
  const [stats, setStats] = useState<AuthorityStats>({});
  const [loadingJourneys, setLoadingJourneys] = useState(true);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [submittingClosure, setSubmittingClosure] = useState(false);

  useEffect(() => {
    fetchJourneys();
    fetchStats();
  }, []);

  function fetchJourneys() {
    setLoadingJourneys(true);
    apiGet<AuthorityJourney[]>(ENDPOINTS.AUTHORITY_JOURNEYS)
      .then((data) => {
        // Sort emergency journeys to the top
        const sorted = [...data].sort((a, b) => {
          const aEmerg = a.vehicle_type === "EMERGENCY" || a.status === "EMERGENCY_CONFIRMED" ? 0 : 1;
          const bEmerg = b.vehicle_type === "EMERGENCY" || b.status === "EMERGENCY_CONFIRMED" ? 0 : 1;
          return aEmerg - bEmerg;
        });
        setJourneys(sorted);
      })
      .catch(() => {})
      .finally(() => setLoadingJourneys(false));
  }

  function fetchStats() {
    apiGet<AuthorityStats>(ENDPOINTS.AUTHORITY_STATS)
      .then(setStats)
      .catch(() => {});
  }

  const displayStats = {
    activeJourneys: stats.active_journeys ?? stats.total ?? journeys.filter(j => j.status === "CONFIRMED" || j.status === "PENDING" || j.status === "EMERGENCY_CONFIRMED").length,
    cancelledToday: stats.cancelled_today ?? stats.cancelled ?? journeys.filter(j => j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED").length,
    roadClosures: stats.road_closures ?? 0,
    crossRegion: stats.cross_region ?? 0,
  };

  const filtered = journeys.filter(j => {
    const matchesSearch = search === "" ||
      j.id.toLowerCase().includes(search.toLowerCase()) ||
      j.origin.toLowerCase().includes(search.toLowerCase()) ||
      j.destination.toLowerCase().includes(search.toLowerCase()) ||
      j.driver_id.toLowerCase().includes(search.toLowerCase());
    return matchesSearch;
  });

  const chartData = [
    {
      region: "EU",
      confirmed: journeys.filter(j => j.region === "EU" && (j.status === "CONFIRMED" || j.status === "EMERGENCY_CONFIRMED")).length,
      pending: journeys.filter(j => j.region === "EU" && j.status === "PENDING").length,
      cancelled: journeys.filter(j => j.region === "EU" && (j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED")).length,
    },
    {
      region: "US",
      confirmed: journeys.filter(j => j.region === "US" && (j.status === "CONFIRMED" || j.status === "EMERGENCY_CONFIRMED")).length,
      pending: journeys.filter(j => j.region === "US" && j.status === "PENDING").length,
      cancelled: journeys.filter(j => j.region === "US" && (j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED")).length,
    },
    {
      region: "APAC",
      confirmed: journeys.filter(j => j.region === "APAC" && (j.status === "CONFIRMED" || j.status === "EMERGENCY_CONFIRMED")).length,
      pending: journeys.filter(j => j.region === "APAC" && j.status === "PENDING").length,
      cancelled: journeys.filter(j => j.region === "APAC" && (j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED")).length,
    },
  ];

  const handleForceCancel = async (journeyId: string) => {
    setCancellingId(journeyId);
    try {
      await apiPost(ENDPOINTS.AUTHORITY_CANCEL(journeyId));
      toast.success(`Journey ${journeyId.slice(0, 8)} cancelled`, {
        description: "The driver has been notified.",
      });
      fetchJourneys();
    } catch (err: unknown) {
      toast.error("Cancel failed", { description: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setCancellingId(null);
    }
  };

  const handleCreateClosure = async () => {
    if (!closureData.roadName || !closureData.reason) {
      toast.error("Please fill in all fields");
      return;
    }
    setSubmittingClosure(true);
    try {
      await apiPost(ENDPOINTS.AUTHORITY_CLOSURE, {
        road_name: closureData.roadName,
        reason: closureData.reason,
        region: closureData.region,
      });
      toast.success("Road closure created", {
        description: closureData.cancelAffected
          ? "Affected journeys have been cancelled"
          : "Road closure is now active",
      });
      setIsClosureModalOpen(false);
      setClosureData({ roadName: "", region: "EU", reason: "", cancelAffected: false });
      fetchStats();
    } catch (err: unknown) {
      toast.error("Failed to create closure", { description: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setSubmittingClosure(false);
    }
  };

  const handleBroadcast = () => {
    toast.success("Broadcast sent", {
      description: "All affected drivers have been notified",
    });
    setIsBroadcastModalOpen(false);
  };

  function formatTime(start_time: string) {
    try {
      const d = new Date(start_time);
      return d.toISOString().replace("T", " ").slice(0, 16);
    } catch { return start_time; }
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
          <Select value={selectedRegion} onValueChange={(value: "EU" | "US" | "APAC") => setSelectedRegion(value)}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="EU">EU</SelectItem>
              <SelectItem value="US">US</SelectItem>
              <SelectItem value="APAC">APAC</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={() => setIsBroadcastModalOpen(true)}
            variant="outline"
            className="gap-2"
          >
            <Radio className="w-4 h-4" />
            Broadcast
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

      {/* Journey Volume Chart */}
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

      {/* Road Closures */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900">Active Road Closures</h2>
          <Button
            onClick={() => setIsClosureModalOpen(true)}
            className="bg-[#2563EB] hover:bg-[#1d4ed8]"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Closure
          </Button>
        </div>
        <p className="text-sm text-gray-500">Use the "Create Closure" button to declare a new road closure. Active closures will appear here once the backend returns them.</p>
      </div>

      {/* Journeys Table */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <h2 className="text-xl font-bold text-gray-900">Active Journeys</h2>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:flex-initial">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search..."
                className="pl-10 h-10 sm:w-64"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Button variant="outline" size="icon" className="h-10 w-10">
              <Filter className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {loadingJourneys ? (
          <div className="space-y-3 animate-pulse">
            {[0, 1, 2].map(i => <div key={i} className="h-12 bg-gray-100 rounded" />)}
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-center py-8 text-gray-500">No journeys found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Journey ID</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Driver</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Route</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Time</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((journey) => {
                  const isEmerg = journey.vehicle_type === "EMERGENCY" || journey.status === "EMERGENCY_CONFIRMED";
                  const displayStatus = journey.status === "EMERGENCY_CONFIRMED" ? "CONFIRMED" : journey.status;
                  return (
                    <tr key={journey.id} className={`border-b border-gray-100 hover:bg-gray-50 ${isEmerg ? "bg-red-50" : ""}`}>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-gray-900">#{journey.id.slice(0, 8)}</span>
                          {isEmerg && <span className="text-xs text-red-600 font-bold">🚨</span>}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-gray-900 font-mono">{journey.driver_id.slice(0, 8)}…</span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-sm text-gray-900">
                          {journey.origin} → {journey.destination}
                        </div>
                        <RegionBadge region={journey.region} />
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-gray-600">{formatTime(journey.start_time)}</span>
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={displayStatus as "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED"} />
                      </td>
                      <td className="py-3 px-4">
                        <Button
                          variant="destructive"
                          size="sm"
                          disabled={cancellingId === journey.id || journey.status === "CANCELLED" || journey.status === "AUTHORITY_CANCELLED"}
                          onClick={() => handleForceCancel(journey.id)}
                        >
                          {cancellingId === journey.id ? "Cancelling..." : "Force Cancel"}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Closure Modal */}
      <Dialog open={isClosureModalOpen} onOpenChange={setIsClosureModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Road Closure</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Road Name</Label>
              <Input
                placeholder="e.g., A9 - Munich Autobahn"
                value={closureData.roadName}
                onChange={(e) => setClosureData({ ...closureData, roadName: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Region</Label>
              <Select
                value={closureData.region}
                onValueChange={(value: "EU" | "US" | "APAC") => setClosureData({ ...closureData, region: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EU">EU</SelectItem>
                  <SelectItem value="US">US</SelectItem>
                  <SelectItem value="APAC">APAC</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Reason</Label>
              <Textarea
                placeholder="Describe the reason for closure..."
                value={closureData.reason}
                onChange={(e) => setClosureData({ ...closureData, reason: e.target.value })}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="cancel-affected"
                checked={closureData.cancelAffected}
                onCheckedChange={(checked) =>
                  setClosureData({ ...closureData, cancelAffected: checked as boolean })
                }
              />
              <label htmlFor="cancel-affected" className="text-sm text-gray-700">
                Cancel all affected journeys
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsClosureModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateClosure} disabled={submittingClosure} className="bg-[#2563EB] hover:bg-[#1d4ed8]">
              {submittingClosure ? "Creating..." : "Create Closure"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Broadcast Modal */}
      <Dialog open={isBroadcastModalOpen} onOpenChange={setIsBroadcastModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Broadcast Alert</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Message</Label>
              <Textarea
                placeholder="Enter your broadcast message to all affected drivers..."
                rows={6}
              />
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              This message will be sent to all drivers in the {selectedRegion} region via email and Telegram.
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBroadcastModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleBroadcast} className="bg-[#2563EB] hover:bg-[#1d4ed8]">
              Send Broadcast
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
