import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { MapPin, Calendar, Clock, AlertTriangle, Route as RouteIcon, ChevronDown, Zap } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { RegionBadge } from "../components/RegionBadge";
import { RoadSegmentChip } from "../components/RoadSegmentChip";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { apiGet, apiPost } from "../api/client";
import { ENDPOINTS } from "../api/config";

interface FamousRoute {
  id: string;
  name: string;
  origin: string;
  destination: string;
  region: "EU" | "US" | "APAC";
  distance_km: number;
  duration_mins: number;
}

interface RoutePreview {
  segments: string[];
  distance_m: number;
  duration_s: number;
  distance_km: number;
  duration_mins: number;
}

export default function BookJourney() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [showRoutePreview, setShowRoutePreview] = useState(false);
  const [routePreview, setRoutePreview] = useState<RoutePreview | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [famousRoutes, setFamousRoutes] = useState<FamousRoute[]>([]);
  const [activeTab, setActiveTab] = useState<"EU" | "US" | "APAC">("EU");

  const isEmergency = user?.vehicle_type === "EMERGENCY";

  // Fetch famous routes on mount
  useEffect(() => {
    apiGet<FamousRoute[]>(ENDPOINTS.FAMOUS_ROUTES)
      .then(setFamousRoutes)
      .catch(() => {}); // non-blocking — silently ignore if unavailable
  }, []);

  // Simple region detection (mirrors backend logic)
  function detectRegion(loc: string): "EU" | "US" | "APAC" | null {
    const l = loc.toLowerCase();
    const us = ['usa','united states','new york','los angeles','chicago','houston','boston','toronto','canada','california','texas','florida','washington','san francisco','detroit'];
    const apac = ['singapore','tokyo','japan','beijing','china','sydney','australia','mumbai','india','seoul','korea','kuala lumpur','malaysia','bangkok','thailand','osaka','melbourne'];
    if (us.some(k => l.includes(k))) return "US";
    if (apac.some(k => l.includes(k))) return "APAC";
    if (l.length > 2) return "EU"; // default EU for non-empty strings
    return null;
  }

  const originRegion = detectRegion(origin);
  const destinationRegion = detectRegion(destination);
  const isCrossRegion = originRegion && destinationRegion && originRegion !== destinationRegion;

  const routesByRegion = famousRoutes.filter(r => r.region === activeTab);

  function handleRouteCardClick(route: FamousRoute) {
    setOrigin(route.origin);
    setDestination(route.destination);
    setShowRoutePreview(false);
    setRoutePreview(null);
  }

  async function handleShowRoutePreview() {
    if (!origin || !destination) {
      toast.error("Please enter both origin and destination");
      return;
    }
    setRouteLoading(true);
    setShowRoutePreview(true);
    try {
      const data = await apiPost<RoutePreview>(ENDPOINTS.ROUTE, { origin, destination });
      setRoutePreview({
        segments: data.segments ?? [],
        distance_m: data.distance_m ?? 0,
        duration_s: data.duration_s ?? 0,
        distance_km: data.distance_km ?? Math.round((data.distance_m ?? 0) / 100) / 10,
        duration_mins: data.duration_mins ?? Math.round((data.duration_s ?? 0) / 60),
      });
    } catch {
      setRoutePreview(null);
    } finally {
      setRouteLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!date || !time) { toast.error("Please select a date and time"); return; }

    const start_time = `${date}T${time}:00`;
    setSubmitting(true);
    try {
      const result = await apiPost<{ id: string; status: string }>(ENDPOINTS.JOURNEYS, {
        origin,
        destination,
        start_time,
      });

      if (result.status === "EMERGENCY_CONFIRMED") {
        toast.success("🚨 Emergency journey instantly approved!", {
          description: `Journey ID: ${result.id.slice(0, 8)} — Conflict detection bypassed.`,
        });
      } else {
        toast.success("Journey booking confirmed!", {
          description: `Journey ID: ${result.id.slice(0, 8)} — Status: ${result.status}`,
        });
      }
      setTimeout(() => navigate("/driver"), 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Booking failed";
      toast.error("Booking failed", { description: msg });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Book a Journey</h1>
        <p className="text-gray-600 mt-1">Plan your route and request approval from traffic authorities.</p>
      </div>

      {/* EMERGENCY Banner */}
      {isEmergency && (
        <div className="bg-red-50 border border-red-300 rounded-lg p-4 flex items-start gap-3">
          <Zap className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-red-900">🚨 EMERGENCY VEHICLE — Instant Approval</h4>
            <p className="text-sm text-red-800 mt-1">
              All journeys are instantly approved. Conflict detection and authority approval are bypassed.
            </p>
          </div>
        </div>
      )}

      {/* Famous Routes */}
      {famousRoutes.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Popular Routes</h2>

          {/* Region Tabs */}
          <div className="flex gap-2 mb-4">
            {(["EU", "US", "APAC"] as const).map(region => (
              <button
                key={region}
                type="button"
                onClick={() => setActiveTab(region)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  activeTab === region
                    ? "bg-[#2563EB] text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {region}
              </button>
            ))}
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            {routesByRegion.map(route => (
              <button
                key={route.id}
                type="button"
                onClick={() => handleRouteCardClick(route)}
                className="text-left p-3 rounded-lg border border-gray-200 hover:border-[#2563EB] hover:bg-blue-50 transition-all"
              >
                <p className="font-medium text-gray-900 text-sm">{route.name}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {route.origin} → {route.destination}
                </p>
                <div className="flex gap-3 mt-2 text-xs text-gray-600">
                  <span>{route.distance_km} km</span>
                  <span>~{route.duration_mins} min</span>
                  <RegionBadge region={route.region} />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Form Card */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Origin */}
          <div className="space-y-2">
            <Label htmlFor="origin">Origin</Label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-green-600" />
              <Input
                id="origin"
                placeholder="Enter starting location"
                value={origin}
                onChange={(e) => { setOrigin(e.target.value); setShowRoutePreview(false); setRoutePreview(null); }}
                className="pl-11 h-12"
                required
              />
              {originRegion && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <RegionBadge region={originRegion} />
                </div>
              )}
            </div>
          </div>

          {/* Destination */}
          <div className="space-y-2">
            <Label htmlFor="destination">Destination</Label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-red-600" />
              <Input
                id="destination"
                placeholder="Enter destination"
                value={destination}
                onChange={(e) => { setDestination(e.target.value); setShowRoutePreview(false); setRoutePreview(null); }}
                className="pl-11 h-12"
                required
              />
              {destinationRegion && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <RegionBadge region={destinationRegion} />
                </div>
              )}
            </div>
          </div>

          {/* Cross-Region Warning */}
          {isCrossRegion && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-amber-900">Cross-Region Journey</h4>
                <p className="text-sm text-amber-800 mt-1">
                  This journey crosses into {destinationRegion}. The destination region will be notified and must approve this journey.
                </p>
              </div>
            </div>
          )}

          {/* Date & Time */}
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="date">Date</Label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <Input
                  id="date"
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="pl-11 h-12"
                  required
                  min={new Date().toISOString().split('T')[0]}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="time">Time</Label>
              <div className="relative">
                <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <Input
                  id="time"
                  type="time"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  className="pl-11 h-12"
                  required
                />
              </div>
            </div>
          </div>

          {/* Route Preview Button */}
          {!showRoutePreview && origin && destination && (
            <Button
              type="button"
              variant="outline"
              onClick={handleShowRoutePreview}
              className="w-full"
              disabled={routeLoading}
            >
              <RouteIcon className="w-4 h-4 mr-2" />
              {routeLoading ? "Loading route..." : "Preview Route"}
            </Button>
          )}

          {/* Route Preview */}
          {showRoutePreview && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <RouteIcon className="w-5 h-5 text-[#2563EB]" />
                  Estimated Route
                </h3>
              </div>

              {routeLoading ? (
                <div className="animate-pulse space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-1/2" />
                  <div className="h-4 bg-gray-200 rounded w-1/3" />
                </div>
              ) : routePreview ? (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Distance</p>
                      <p className="text-lg font-bold text-gray-900 mt-1">{routePreview.distance_km} km</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase font-medium">Duration</p>
                      <p className="text-lg font-bold text-gray-900 mt-1">{routePreview.duration_mins} min</p>
                    </div>
                  </div>
                  {routePreview.segments.length > 0 && (
                    <div>
                      <button
                        type="button"
                        className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3 hover:text-gray-900"
                      >
                        Road Segments ({routePreview.segments.length})
                        <ChevronDown className="w-4 h-4" />
                      </button>
                      <div className="flex flex-wrap gap-2">
                        {routePreview.segments.slice(0, 10).map((segment, index) => (
                          <RoadSegmentChip key={index} roadName={typeof segment === "string" ? segment : (segment as { name?: string })?.name ?? ""} />
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-gray-500">Route preview unavailable — you can still book.</p>
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate("/driver")}
              className="flex-1"
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              className={`flex-1 ${isEmergency ? "bg-red-600 hover:bg-red-700" : "bg-[#2563EB] hover:bg-[#1d4ed8]"}`}
            >
              {submitting
                ? "Booking..."
                : isEmergency
                ? "Book Emergency Journey"
                : "Request Journey Approval"}
            </Button>
          </div>
        </form>
      </div>

      {/* Info Card */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900 mb-2">How it works</h4>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• Your journey will be checked for conflicts with road closures</li>
          <li>• Traffic authorities will review and approve your request</li>
          <li>• You'll receive a notification once approved or if action is needed</li>
          <li>• Cross-region journeys require approval from both regions</li>
        </ul>
      </div>
    </div>
  );
}
