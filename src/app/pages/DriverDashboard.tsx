import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { MapPin, Plus, Search, Filter } from "lucide-react";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { RegionBadge } from "../components/RegionBadge";
import { RoadSegmentChip } from "../components/RoadSegmentChip";
import { Modal } from "../components/Modal";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { apiGet, apiDelete } from "../api/client";
import { ENDPOINTS } from "../api/config";

interface ApiJourney {
  id: string;
  driver_id: string;
  origin: string;
  destination: string;
  start_time: string;
  status: "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED" | "EMERGENCY_CONFIRMED";
  region: "EU" | "US" | "APAC";
  dest_region?: "EU" | "US" | "APAC";
  is_cross_region?: boolean;
  vehicle_type?: "STANDARD" | "EMERGENCY" | "AUTHORITY";
  route_segments?: string[];
  distance_km?: number;
  duration_mins?: number;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-GB", {
      weekday: "short", day: "numeric", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function normaliseStatus(status: ApiJourney["status"]): "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED" {
  if (status === "EMERGENCY_CONFIRMED") return "CONFIRMED";
  return status;
}

export default function DriverDashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [journeys, setJourneys] = useState<ApiJourney[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [cancelTarget, setCancelTarget] = useState<ApiJourney | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const isEmergency = user?.vehicle_type === "EMERGENCY";

  function fetchJourneys() {
    if (!user?.email) { setLoading(false); return; }
    setLoading(true);
    apiGet<ApiJourney[]>(`${ENDPOINTS.JOURNEYS}?driver_id=${encodeURIComponent(user.email)}`)
      .then(setJourneys)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => { fetchJourneys(); }, [user?.email]);

  const stats = {
    total: journeys.length,
    confirmed: journeys.filter(j => j.status === "CONFIRMED" || j.status === "EMERGENCY_CONFIRMED").length,
    pending: journeys.filter(j => j.status === "PENDING").length,
    cancelled: journeys.filter(j => j.status === "CANCELLED" || j.status === "AUTHORITY_CANCELLED").length,
  };

  const filtered = journeys.filter(j =>
    search === "" ||
    j.origin.toLowerCase().includes(search.toLowerCase()) ||
    j.destination.toLowerCase().includes(search.toLowerCase()) ||
    j.id.toLowerCase().includes(search.toLowerCase())
  );

  async function handleCancel() {
    if (!cancelTarget) return;
    setCancelling(true);
    try {
      await apiDelete(ENDPOINTS.JOURNEY(cancelTarget.id));
      setJourneys(prev => prev.filter(j => j.id !== cancelTarget.id));
      toast.success("Journey cancelled");
    } catch (err: unknown) {
      toast.error("Cancel failed", { description: err instanceof Error ? err.message : "Unknown" });
    } finally {
      setCancelling(false);
      setCancelTarget(null);
    }
  }

  function canCancel(j: ApiJourney) {
    return (j.status === "CONFIRMED" || j.status === "EMERGENCY_CONFIRMED") && new Date(j.start_time) > new Date();
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Dashboard
            {isEmergency && (
              <span className="ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-red-100 text-red-800 border border-red-300">
                🚨 EMERGENCY VEHICLE
              </span>
            )}
          </h1>
          <p className="text-gray-600 mt-1">Welcome back! Here's an overview of your journeys.</p>
        </div>
        <Button
          onClick={() => navigate("/driver/book-journey")}
          className="bg-[#2563EB] hover:bg-[#1d4ed8] h-11 px-6"
        >
          <Plus className="w-5 h-5 mr-2" />
          Book a Journey
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          [0, 1, 2, 3].map(i => (
            <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
              <div className="h-3 bg-gray-200 rounded w-1/2 mb-3" />
              <div className="h-8 bg-gray-200 rounded w-1/3" />
            </div>
          ))
        ) : (
          <>
            <StatCard label="Total Journeys" value={stats.total} icon={MapPin} />
            <StatCard label="Confirmed" value={stats.confirmed} />
            <StatCard label="Pending" value={stats.pending} />
            <StatCard label="Cancelled" value={stats.cancelled} />
          </>
        )}
      </div>

      {/* Journey List */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <h2 className="text-xl font-bold text-gray-900">Recent Journeys</h2>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:flex-initial">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search journeys..."
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

        {loading ? (
          <div className="space-y-4">
            {[0, 1, 2].map(i => (
              <div key={i} className="bg-gray-50 rounded-lg border border-gray-200 p-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-1/3 mb-2" />
                <div className="h-4 bg-gray-200 rounded w-2/3" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            {journeys.length === 0 ? "No journeys yet. Book your first journey!" : "No journeys match your search."}
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((journey) => (
              <div key={journey.id} className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center flex-wrap gap-2 mb-1">
                      <span className="text-xs text-gray-500 font-mono">#{journey.id.slice(0, 8)}</span>
                      <RegionBadge region={journey.region} />
                      {journey.is_cross_region && (
                        <span className="text-xs font-medium px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full border border-blue-200">Cross-Region</span>
                      )}
                      {(journey.vehicle_type === "EMERGENCY" || journey.status === "EMERGENCY_CONFIRMED") && (
                        <span className="text-xs font-medium px-2 py-0.5 bg-red-100 text-red-700 rounded-full border border-red-200">🚨 EMERGENCY</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                      <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <span>{journey.origin}</span>
                      <span className="text-gray-400">→</span>
                      <span>{journey.destination}</span>
                    </div>
                    {(journey.distance_km || journey.duration_mins) && (
                      <p className="text-xs text-gray-500 mt-1">
                        {journey.distance_km ? `${journey.distance_km} km` : ""}
                        {journey.distance_km && journey.duration_mins ? " · " : ""}
                        {journey.duration_mins ? `${journey.duration_mins} min` : ""}
                      </p>
                    )}
                    {journey.route_segments && journey.route_segments.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {journey.route_segments.slice(0, 3).map((seg, i) => (
                          <RoadSegmentChip key={i} roadName={seg} />
                        ))}
                        {journey.route_segments.length > 3 && (
                          <span className="text-xs text-gray-400 self-center">+{journey.route_segments.length - 3}</span>
                        )}
                      </div>
                    )}
                  </div>
                  <StatusBadge status={normaliseStatus(journey.status)} />
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-600">{formatDate(journey.start_time)}</p>
                  <div className="flex gap-2">
                    {canCancel(journey) && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-red-600 border-red-200 hover:bg-red-50 h-8"
                        onClick={() => setCancelTarget(journey)}
                      >
                        Cancel
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate(`/driver/journey/${journey.id}`)}
                      className="text-blue-600 hover:text-blue-700 h-8"
                    >
                      View →
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Cancel Confirm Modal */}
      <Modal
        isOpen={!!cancelTarget}
        onClose={() => setCancelTarget(null)}
        title="Cancel Journey"
      >
        {cancelTarget && (
          <div className="space-y-4">
            <p className="text-gray-700">
              Cancel journey from <span className="font-medium">{cancelTarget.origin}</span> to <span className="font-medium">{cancelTarget.destination}</span>?
            </p>
            <p className="text-sm text-gray-500">{formatDate(cancelTarget.start_time)}</p>
            <div className="flex gap-3 pt-2">
              <Button variant="outline" onClick={() => setCancelTarget(null)} className="flex-1" disabled={cancelling}>
                Keep Journey
              </Button>
              <Button
                variant="destructive"
                onClick={handleCancel}
                disabled={cancelling}
                className="flex-1"
              >
                {cancelling ? "Cancelling…" : "Yes, Cancel"}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
