import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router";
import { MapPin, Calendar, ArrowRight, CheckCircle2, Clock, XCircle, AlertCircle, Zap } from "lucide-react";
import { Button } from "../components/ui/button";
import { StatusBadge } from "../components/StatusBadge";
import { RegionBadge } from "../components/RegionBadge";
import { RoadSegmentChip } from "../components/RoadSegmentChip";
import { toast } from "sonner";
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
  vehicle_type?: "STANDARD" | "EMERGENCY" | "AUTHORITY";
  distance_km?: number;
  duration_mins?: number;
  road_segments?: string[];
  created_at?: string;
}

function buildTimeline(status: ApiJourney["status"]) {
  if (status === "EMERGENCY_CONFIRMED") {
    return [
      { status: "Submitted", icon: CheckCircle2, color: "text-green-600", bgColor: "bg-green-100", completed: true },
      { status: "Emergency Bypass — Instantly Approved", icon: Zap, color: "text-red-600", bgColor: "bg-red-100", completed: true },
    ];
  }
  const steps = [
    { status: "Submitted", completed: true },
    { status: "Conflict Check", completed: status !== "PENDING" },
    { status: "Authority Review", completed: status === "CONFIRMED" || status === "AUTHORITY_CANCELLED" },
    { status: status === "AUTHORITY_CANCELLED" ? "Authority Cancelled" : status === "CANCELLED" ? "Cancelled" : "Approved", completed: status === "CONFIRMED" || status === "AUTHORITY_CANCELLED" || status === "CANCELLED" },
  ];
  return steps.map(s => ({
    ...s,
    icon: s.completed ? (s.status.includes("Cancelled") ? XCircle : CheckCircle2) : Clock,
    color: s.completed ? (s.status.includes("Cancelled") ? "text-red-600" : "text-green-600") : "text-gray-400",
    bgColor: s.completed ? (s.status.includes("Cancelled") ? "bg-red-100" : "bg-green-100") : "bg-gray-100",
  }));
}

function parseStartTime(start_time: string) {
  try {
    const d = new Date(start_time);
    return { date: d.toISOString().split("T")[0], time: d.toTimeString().slice(0, 5) };
  } catch { return { date: start_time, time: "" }; }
}

export default function JourneyDetail() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [journey, setJourney] = useState<ApiJourney | null>(null);
  const [loading, setLoading] = useState(true);
  const [isCancelling, setIsCancelling] = useState(false);

  useEffect(() => {
    if (!id) return;
    apiGet<ApiJourney>(ENDPOINTS.JOURNEY(id))
      .then(setJourney)
      .catch(() => toast.error("Failed to load journey"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleCancelJourney = async () => {
    if (!id) return;
    setIsCancelling(true);
    try {
      await apiDelete(ENDPOINTS.JOURNEY(id));
      toast.success("Journey cancelled successfully");
      navigate("/driver");
    } catch (err: unknown) {
      toast.error("Cancel failed", { description: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setIsCancelling(false);
    }
  };

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
        </div>
      </div>
    );
  }

  const { date, time } = parseStartTime(journey.start_time);
  const createdAt = journey.created_at ? parseStartTime(journey.created_at) : null;
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
          <p className="text-gray-600 mt-1">#{journey.id}</p>
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
          {/* Journey Info Card */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-2">Journey Information</h2>
                <div className="flex items-center gap-2">
                  <RegionBadge region={journey.region} />
                  <StatusBadge status={displayStatus as "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED"} />
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

              {/* Date & Time */}
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase">Scheduled Time</label>
                  <div className="flex items-center gap-2 mt-2">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-900">{date} at {time}</span>
                  </div>
                </div>
                {createdAt && (
                  <div>
                    <label className="text-xs font-medium text-gray-500 uppercase">Created</label>
                    <div className="flex items-center gap-2 mt-2">
                      <Clock className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-900">{createdAt.date} at {createdAt.time}</span>
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
              {journey.road_segments && journey.road_segments.length > 0 && (
                <div className="pt-4 border-t">
                  <label className="text-xs font-medium text-gray-500 uppercase">Road Segments</label>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {journey.road_segments.map((segment, index) => (
                      <RoadSegmentChip key={index} roadName={segment} />
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
                  onClick={handleCancelJourney}
                  disabled={isCancelling}
                  className="w-full sm:w-auto"
                >
                  {isCancelling ? "Cancelling..." : "Cancel Journey"}
                </Button>
              </div>
            )}
          </div>

          {/* Status Timeline */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-6">Status Timeline</h3>
            <div className="space-y-4">
              {timeline.map((item, index) => {
                const Icon = item.icon;
                return (
                  <div key={index} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className={`w-10 h-10 rounded-full ${item.bgColor} flex items-center justify-center`}>
                        <Icon className={`w-5 h-5 ${item.color}`} />
                      </div>
                      {index < timeline.length - 1 && (
                        <div className="w-0.5 h-8 bg-gray-200 my-1" />
                      )}
                    </div>
                    <div className="flex-1 pb-4">
                      <p className="font-medium text-gray-900">{item.status}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Map Placeholder */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Route Map</h3>
            <div className="aspect-square bg-gray-100 rounded-lg flex items-center justify-center">
              <div className="text-center text-gray-500">
                <MapPin className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                <p className="text-sm">Map Preview</p>
                <p className="text-xs">Route visualization</p>
              </div>
            </div>
          </div>

          {/* Journey Info Summary */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Summary</h3>
            <div className="space-y-3">
              <div className="pb-3 border-b">
                <p className="text-sm font-medium text-gray-900">Status</p>
                <p className="text-xs text-gray-600 mt-1">{journey.status}</p>
              </div>
              <div className="pb-3 border-b">
                <p className="text-sm font-medium text-gray-900">Region</p>
                <p className="text-xs text-gray-600 mt-1">{journey.region}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Journey ID</p>
                <p className="text-xs font-mono text-gray-600 mt-1">{journey.id}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
