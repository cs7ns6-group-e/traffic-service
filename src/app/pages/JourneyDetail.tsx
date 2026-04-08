import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router";
import { MapPin, Calendar, ArrowRight, CheckCircle2, Clock, XCircle, Zap } from "lucide-react";
import { Button } from "../components/ui/button";
import { StatusBadge } from "../components/StatusBadge";
import { RegionBadge } from "../components/RegionBadge";
import { RoadSegmentChip } from "../components/RoadSegmentChip";
import { RouteMap } from "../components/RouteMap";
import { Modal } from "../components/Modal";
import { toast } from "sonner";
import { apiGet, apiDelete, apiPost } from "../api/client";
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
  created_at?: string;
}

interface RouteData {
  coordinates: [number, number][];
  segments?: string[];
  distance_km?: number;
  duration_mins?: number;
}

function buildTimeline(status: ApiJourney["status"]) {
  if (status === "EMERGENCY_CONFIRMED") {
    return [
      { label: "Submitted", done: true, icon: CheckCircle2, green: true },
      { label: "Emergency bypass — Instantly approved", done: true, icon: Zap, green: false, red: true },
    ];
  }
  return [
    { label: "Submitted", done: true, icon: CheckCircle2, green: true },
    { label: "Conflict Check", done: status !== "PENDING", icon: status !== "PENDING" ? CheckCircle2 : Clock, green: status !== "PENDING" },
    { label: "Authority Review", done: status === "CONFIRMED" || status === "AUTHORITY_CANCELLED", icon: status === "AUTHORITY_CANCELLED" ? XCircle : (status === "CONFIRMED" ? CheckCircle2 : Clock), green: status === "CONFIRMED" },
    {
      label: status === "AUTHORITY_CANCELLED" ? "Authority Cancelled" : status === "CANCELLED" ? "Cancelled" : "Approved",
      done: status === "CONFIRMED" || status === "AUTHORITY_CANCELLED" || status === "CANCELLED",
      icon: (status === "CONFIRMED") ? CheckCircle2 : (status === "CANCELLED" || status === "AUTHORITY_CANCELLED") ? XCircle : Clock,
      green: status === "CONFIRMED",
    },
  ];
}

function fmt(iso: string) {
  try {
    return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export default function JourneyDetail() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [journey, setJourney] = useState<ApiJourney | null>(null);
  const [routeData, setRouteData] = useState<RouteData | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelModal, setCancelModal] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!id) return;
    apiGet<ApiJourney>(ENDPOINTS.JOURNEY(id))
      .then((j) => {
        setJourney(j);
        // Fetch route for map
        apiPost<RouteData>(ENDPOINTS.ROUTE, { origin: j.origin, destination: j.destination })
          .then(setRouteData)
          .catch(() => {});
      })
      .catch(() => toast.error("Failed to load journey"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleCancel() {
    if (!id) return;
    setCancelling(true);
    try {
      await apiDelete(ENDPOINTS.JOURNEY(id));
      toast.success("Journey cancelled");
      navigate("/driver");
    } catch (err: unknown) {
      toast.error("Cancel failed", { description: err instanceof Error ? err.message : "Unknown" });
    } finally {
      setCancelling(false);
      setCancelModal(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto space-y-6 animate-pulse">
        <div className="h-10 bg-gray-200 rounded w-1/3" />
        <div className="h-64 bg-gray-200 rounded" />
      </div>
    );
  }

  if (!journey) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center text-gray-500">
          Journey not found.
          <div className="mt-4">
            <Button variant="outline" onClick={() => navigate("/driver")}>Back to Dashboard</Button>
          </div>
        </div>
      </div>
    );
  }

  const isEmergency = journey.vehicle_type === "EMERGENCY" || journey.status === "EMERGENCY_CONFIRMED";
  const canCancel = (journey.status === "CONFIRMED" || journey.status === "EMERGENCY_CONFIRMED") && new Date(journey.start_time) > new Date();
  const displayStatus = journey.status === "EMERGENCY_CONFIRMED" ? "CONFIRMED" : journey.status;
  const timeline = buildTimeline(journey.status);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Journey Details</h1>
          <p className="text-gray-600 mt-1 font-mono">#{journey.id}</p>
        </div>
        <Button variant="outline" onClick={() => navigate("/driver")}>
          Back to Dashboard
        </Button>
      </div>

      {/* EMERGENCY Banner */}
      {isEmergency && (
        <div className="bg-red-50 border border-red-300 rounded-lg p-4 flex items-start gap-3">
          <Zap className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-red-900">🚨 EMERGENCY VEHICLE — Instant Approval</h4>
            <p className="text-sm text-red-800 mt-1">This journey was instantly approved, bypassing conflict detection.</p>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">

          {/* Info Card */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-2">Journey Information</h2>
                <div className="flex items-center gap-2 flex-wrap">
                  <RegionBadge region={journey.region} />
                  <StatusBadge status={displayStatus as "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED"} />
                  {journey.is_cross_region && (
                    <span className="text-xs font-medium px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full border border-blue-200">Cross-Region</span>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {/* Route */}
              <div>
                <label className="text-xs font-medium text-gray-500 uppercase">Route</label>
                <div className="flex items-center gap-3 mt-2">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-green-600" />
                    <span className="font-medium text-gray-900">{journey.origin}</span>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-400" />
                  <div className="flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-red-600" />
                    <span className="font-medium text-gray-900">{journey.destination}</span>
                  </div>
                </div>
              </div>

              {/* Scheduled Time */}
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase">Scheduled Time</label>
                  <div className="flex items-center gap-2 mt-2">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-900">{fmt(journey.start_time)}</span>
                  </div>
                </div>
                {journey.created_at && (
                  <div>
                    <label className="text-xs font-medium text-gray-500 uppercase">Created</label>
                    <div className="flex items-center gap-2 mt-2">
                      <Clock className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-900">{fmt(journey.created_at)}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Distance & Duration */}
              {(journey.distance_km || journey.duration_mins) && (
                <div className="grid sm:grid-cols-2 gap-4 pt-4 border-t">
                  {journey.distance_km && (
                    <div>
                      <label className="text-xs font-medium text-gray-500 uppercase">Distance</label>
                      <p className="text-lg font-bold text-gray-900 mt-1">{journey.distance_km} km</p>
                    </div>
                  )}
                  {journey.duration_mins && (
                    <div>
                      <label className="text-xs font-medium text-gray-500 uppercase">Est. Duration</label>
                      <p className="text-lg font-bold text-gray-900 mt-1">{journey.duration_mins} min</p>
                    </div>
                  )}
                </div>
              )}

              {/* Road Segments */}
              {journey.route_segments && journey.route_segments.length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-xs font-medium text-gray-500 uppercase">Road Segments</label>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {journey.route_segments.map((seg, i) => (
                      <RoadSegmentChip key={i} roadName={seg} />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Cancel Button */}
            {canCancel && (
              <div className="mt-6 pt-6 border-t">
                <Button
                  variant="destructive"
                  onClick={() => setCancelModal(true)}
                  className="w-full sm:w-auto"
                >
                  Cancel Journey
                </Button>
              </div>
            )}
          </div>

          {/* Timeline */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-6">Status Timeline</h3>
            <div className="space-y-4">
              {timeline.map((item, index) => {
                const Icon = item.icon;
                const colorClass = "red" in item && item.red ? "text-red-600" : item.green ? "text-green-600" : "text-gray-400";
                const bgClass = "red" in item && item.red ? "bg-red-100" : item.green ? "bg-green-100" : "bg-gray-100";
                return (
                  <div key={index} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className={`w-10 h-10 rounded-full ${bgClass} flex items-center justify-center`}>
                        <Icon className={`w-5 h-5 ${colorClass}`} />
                      </div>
                      {index < timeline.length - 1 && <div className="w-0.5 h-8 bg-gray-200 my-1" />}
                    </div>
                    <div className="flex-1 pb-4">
                      <p className="font-medium text-gray-900">{item.label}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Map */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Route Map</h3>
            {routeData?.coordinates?.length ? (
              <RouteMap coordinates={routeData.coordinates} />
            ) : (
              <div className="h-[220px] bg-gray-100 rounded-lg flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <MapPin className="w-10 h-10 mx-auto mb-2 text-gray-400" />
                  <p className="text-sm">Map Preview</p>
                </div>
              </div>
            )}
          </div>

          {/* Summary */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Summary</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between pb-2 border-b">
                <span className="text-gray-500">Status</span>
                <StatusBadge status={displayStatus as "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED"} />
              </div>
              <div className="flex justify-between pb-2 border-b">
                <span className="text-gray-500">Region</span>
                <RegionBadge region={journey.region} />
              </div>
              {journey.is_cross_region && journey.dest_region && (
                <div className="flex justify-between pb-2 border-b">
                  <span className="text-gray-500">Dest. Region</span>
                  <RegionBadge region={journey.dest_region} />
                </div>
              )}
              <div>
                <span className="text-gray-500">Journey ID</span>
                <p className="font-mono text-xs text-gray-700 mt-1 break-all">{journey.id}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Cancel Modal */}
      <Modal isOpen={cancelModal} onClose={() => setCancelModal(false)} title="Cancel Journey">
        <div className="space-y-4">
          <p className="text-gray-700">
            Cancel your journey from <span className="font-medium">{journey.origin}</span> to <span className="font-medium">{journey.destination}</span>?
          </p>
          <p className="text-sm text-gray-500">{fmt(journey.start_time)}</p>
          <div className="flex gap-3 pt-2">
            <Button variant="outline" onClick={() => setCancelModal(false)} disabled={cancelling} className="flex-1">Keep Journey</Button>
            <Button variant="destructive" onClick={handleCancel} disabled={cancelling} className="flex-1">
              {cancelling ? "Cancelling…" : "Yes, Cancel"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
