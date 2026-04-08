import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import { Calendar, AlertTriangle, Route as RouteIcon, Zap, CheckCircle2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { RegionBadge } from "../components/RegionBadge";
import { RoadSegmentChip } from "../components/RoadSegmentChip";
import { Modal } from "../components/Modal";
import { SlotGrid, TimeSlot } from "../components/SlotGrid";
import { PlaceSearch, Place } from "../components/PlaceSearch";
import { RouteMap } from "../components/RouteMap";
import { StatusBadge } from "../components/StatusBadge";
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

interface RouteData {
  segments: string[];
  distance_km: number;
  duration_mins: number;
  coordinates: [number, number][];
}

interface BookingResult {
  id: string;
  origin: string;
  destination: string;
  start_time: string;
  status: string;
  region: string;
  distance_km?: number;
  duration_mins?: number;
}

function tomorrow(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().split("T")[0];
}

const EU_KEYWORDS = ["dublin", "london", "paris", "berlin", "cork", "belfast", "manchester", "amsterdam", "brussels", "lyon", "frankfurt", "madrid", "rome", "vienna", "ireland", "uk", "france", "germany", "spain", "italy", "austria", "netherlands", "belgium"];
const US_KEYWORDS = ["new york", "los angeles", "chicago", "boston", "houston", "seattle", "miami", "san francisco", "washington", "usa", "united states", "california", "texas", "florida"];
const APAC_KEYWORDS = ["singapore", "tokyo", "osaka", "sydney", "melbourne", "kuala lumpur", "bangkok", "hong kong", "seoul", "japan", "australia", "malaysia", "thailand", "korea"];

function detectRegion(name: string): "EU" | "US" | "APAC" | null {
  const l = name.toLowerCase();
  if (US_KEYWORDS.some(k => l.includes(k))) return "US";
  if (APAC_KEYWORDS.some(k => l.includes(k))) return "APAC";
  if (EU_KEYWORDS.some(k => l.includes(k))) return "EU";
  if (l.length > 2) return "EU";
  return null;
}

export default function BookJourney() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [originPlace, setOriginPlace] = useState<Place | null>(null);
  const [destinationPlace, setDestinationPlace] = useState<Place | null>(null);
  const [date, setDate] = useState(tomorrow());
  const [slots, setSlots] = useState<TimeSlot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [routeData, setRouteData] = useState<RouteData | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [successModal, setSuccessModal] = useState<BookingResult | null>(null);
  const [conflictModal, setConflictModal] = useState(false);
  const [famousRoutes, setFamousRoutes] = useState<FamousRoute[]>([]);
  const [activeTab, setActiveTab] = useState<"EU" | "US" | "APAC">("EU");

  const isEmergency = user?.vehicle_type === "EMERGENCY";

  // Fetch famous routes on mount
  useEffect(() => {
    apiGet<FamousRoute[]>(ENDPOINTS.FAMOUS_ROUTES).then(setFamousRoutes).catch(() => {});
  }, []);

  // Fetch slots when origin + destination + date all set
  const fetchSlots = useCallback(() => {
    if (!originPlace || !destinationPlace || !date) return;
    setSlotsLoading(true);
    apiGet<TimeSlot[]>(
      `${ENDPOINTS.CONFLICTS_SLOTS}?origin=${encodeURIComponent(originPlace.name)}&destination=${encodeURIComponent(destinationPlace.name)}&date=${date}`
    )
      .then(setSlots)
      .catch(() => {
        // Fall back to all slots available
        const fallback: TimeSlot[] = [];
        for (let h = 6; h <= 22; h++) {
          for (const m of [0, 30]) {
            if (h === 22 && m === 30) break;
            fallback.push({ slot: `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`, available: true });
          }
        }
        setSlots(fallback);
      })
      .finally(() => setSlotsLoading(false));
  }, [originPlace, destinationPlace, date]);

  useEffect(() => {
    if (originPlace && destinationPlace && date) {
      setSelectedSlot(null);
      fetchSlots();
    } else {
      setSlots([]);
    }
  }, [originPlace, destinationPlace, date, fetchSlots]);

  // Auto-refresh slots every 30s
  useEffect(() => {
    if (!originPlace || !destinationPlace || !date) return;
    const id = setInterval(fetchSlots, 30000);
    return () => clearInterval(id);
  }, [originPlace, destinationPlace, date, fetchSlots]);

  // Fetch route when origin + destination set
  useEffect(() => {
    if (!originPlace || !destinationPlace) { setRouteData(null); return; }
    setRouteLoading(true);
    apiPost<RouteData>(ENDPOINTS.ROUTE, { origin: originPlace.name, destination: destinationPlace.name })
      .then(setRouteData)
      .catch(() => setRouteData(null))
      .finally(() => setRouteLoading(false));
  }, [originPlace, destinationPlace]);

  const originRegion = originPlace ? detectRegion(originPlace.name) : null;
  const destinationRegion = destinationPlace ? detectRegion(destinationPlace.name) : null;
  const isCrossRegion = originRegion && destinationRegion && originRegion !== destinationRegion;

  function handleRouteCardClick(route: FamousRoute) {
    setOriginPlace({ name: route.origin, lat: 0, lon: 0 });
    setDestinationPlace({ name: route.destination, lat: 0, lon: 0 });
    setSelectedSlot(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!originPlace || !destinationPlace) { toast.error("Please select origin and destination"); return; }
    if (!selectedSlot) { toast.error("Please select a time slot"); return; }

    const start_time = `${date}T${selectedSlot}:00`;
    setSubmitting(true);
    try {
      const result = await apiPost<BookingResult>(ENDPOINTS.JOURNEYS, {
        origin: originPlace.name,
        destination: destinationPlace.name,
        start_time,
      });
      setSuccessModal(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Booking failed";
      if (msg.includes("409") || msg.toLowerCase().includes("conflict") || msg.toLowerCase().includes("already")) {
        setConflictModal(true);
      } else {
        toast.error("Booking failed", { description: msg });
      }
    } finally {
      setSubmitting(false);
    }
  }

  const routesByRegion = famousRoutes.filter(r => r.region === activeTab);

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Book a Journey</h1>
          <p className="text-gray-600 text-sm mt-0.5">Plan your route and request approval from traffic authorities.</p>
        </div>
      </div>

      {/* EMERGENCY Banner */}
      {isEmergency && (
        <div className="bg-red-50 border border-red-300 rounded-lg p-3 flex items-center gap-3">
          <Zap className="w-5 h-5 text-red-600 flex-shrink-0" />
          <div>
            <span className="font-semibold text-red-900 text-sm">🚨 Emergency Vehicle — All slots available. </span>
            <span className="text-sm text-red-800">Your journeys bypass conflict detection.</span>
          </div>
        </div>
      )}

      {/* Famous Routes — compact horizontal strip */}
      {famousRoutes.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-sm font-semibold text-gray-700 flex-shrink-0">Popular Routes</span>
            <div className="flex gap-1.5">
              {(["EU", "US", "APAC"] as const).map(region => (
                <button
                  key={region}
                  type="button"
                  onClick={() => setActiveTab(region)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    activeTab === region ? "bg-[#2563EB] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {region}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
            {routesByRegion.map(route => (
              <button
                key={route.id}
                type="button"
                onClick={() => handleRouteCardClick(route)}
                className="flex-shrink-0 w-48 text-left p-2.5 rounded-lg border border-gray-200 hover:border-[#2563EB] hover:bg-blue-50 transition-all"
              >
                <p className="font-medium text-gray-900 text-xs truncate">{route.name}</p>
                <p className="text-xs text-gray-500 truncate">{route.origin} → {route.destination}</p>
                <p className="text-xs text-gray-400 mt-1">{route.distance_km} km · ~{route.duration_mins} min</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main 2-column grid */}
      <form onSubmit={handleSubmit} className="grid lg:grid-cols-2 gap-4 items-start">

        {/* LEFT: Journey Details */}
        <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
          <h2 className="font-semibold text-gray-900">Journey Details</h2>

          {/* Origin */}
          <div className="space-y-1.5">
            <Label className="text-xs">Origin</Label>
            <PlaceSearch
              value={originPlace}
              onChange={(p) => { setOriginPlace(p); setSelectedSlot(null); }}
              placeholder="Enter starting location"
              pinColor="green"
            />
            {originRegion && (
              <div className="flex items-center gap-1.5">
                <RegionBadge region={originRegion} />
                <span className="text-xs text-gray-500">Detected region</span>
              </div>
            )}
          </div>

          {/* Destination */}
          <div className="space-y-1.5">
            <Label className="text-xs">Destination</Label>
            <PlaceSearch
              value={destinationPlace}
              onChange={(p) => { setDestinationPlace(p); setSelectedSlot(null); }}
              placeholder="Enter destination"
              pinColor="red"
            />
            {destinationRegion && (
              <div className="flex items-center gap-1.5">
                <RegionBadge region={destinationRegion} />
                <span className="text-xs text-gray-500">Detected region</span>
              </div>
            )}
          </div>

          {/* Cross-Region Banner */}
          {isCrossRegion && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-900 text-sm">Cross-region: {originRegion} → {destinationRegion}</p>
                <p className="text-xs text-amber-800 mt-0.5">Both regions will be notified via RabbitMQ</p>
              </div>
            </div>
          )}

          {/* Date */}
          <div className="space-y-1.5">
            <Label htmlFor="date" className="text-xs">Date</Label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                id="date"
                type="date"
                value={date}
                onChange={(e) => { setDate(e.target.value); setSelectedSlot(null); }}
                className="pl-10 h-10"
                required
                min={new Date().toISOString().split("T")[0]}
              />
            </div>
          </div>

          {/* How it works */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <ul className="text-xs text-blue-800 space-y-1">
              <li>• Journey checked for conflicts with road closures</li>
              <li>• Traffic authorities review and approve your request</li>
              <li>• Notification sent once approved</li>
              <li>• Cross-region requires approval from both regions</li>
            </ul>
          </div>

          {/* Submit buttons */}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="outline" onClick={() => navigate("/driver")} className="flex-1 h-10" disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting || !selectedSlot}
              className={`flex-1 h-10 ${isEmergency ? "bg-red-600 hover:bg-red-700" : "bg-[#2563EB] hover:bg-[#1d4ed8]"}`}
            >
              {submitting ? "Booking…" : isEmergency ? "Book Emergency Journey" : "Request Approval"}
            </Button>
          </div>
        </div>

        {/* RIGHT: Map + Time Slots */}
        <div className="space-y-4">
          {/* Route Map */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                <RouteIcon className="w-4 h-4 text-[#2563EB]" />
                Route Preview
              </h3>
              {routeData && (
                <div className="flex gap-3 text-xs text-gray-600">
                  <span className="font-medium">{routeData.distance_km} km</span>
                  <span className="font-medium">{routeData.duration_mins} min</span>
                </div>
              )}
            </div>
            {routeLoading ? (
              <div className="h-[200px] bg-gray-100 rounded-lg animate-pulse flex items-center justify-center text-gray-400 text-sm">
                Loading map…
              </div>
            ) : routeData?.coordinates?.length ? (
              <>
                <RouteMap coordinates={routeData.coordinates} height={200} />
                {routeData.segments.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {routeData.segments.slice(0, 6).map((seg, i) => (
                      <RoadSegmentChip key={i} roadName={seg} />
                    ))}
                    {routeData.segments.length > 6 && (
                      <span className="text-xs text-gray-500 self-center">+{routeData.segments.length - 6} more</span>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="h-[200px] bg-gray-100 rounded-lg flex items-center justify-center text-gray-400 text-sm">
                {originPlace && destinationPlace ? "Map unavailable — you can still book" : "Select origin & destination to preview route"}
              </div>
            )}
          </div>

          {/* Time Slots */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <Label className="text-sm font-semibold text-gray-900">Select Time Slot</Label>
              {selectedSlot && (
                <span className="text-sm font-medium text-[#2563EB]">✓ {selectedSlot}</span>
              )}
            </div>
            {!originPlace || !destinationPlace || !date ? (
              <p className="text-sm text-gray-400 text-center py-6">Complete origin, destination &amp; date to see available slots</p>
            ) : slotsLoading ? (
              <SlotGrid slots={[]} selectedSlot={null} onSelect={() => {}} loading />
            ) : slots.length > 0 ? (
              <SlotGrid slots={slots} selectedSlot={selectedSlot} onSelect={setSelectedSlot} forceAllAvailable={isEmergency} />
            ) : (
              <p className="text-sm text-gray-500 text-center py-4">No slots available</p>
            )}
          </div>
        </div>
      </form>

      {/* Success Modal */}
      <Modal isOpen={!!successModal} onClose={() => { setSuccessModal(null); navigate("/driver"); }}>
        {successModal && (
          <div className="text-center space-y-4">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto" />
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Journey Booked ✅</h2>
              <p className="text-sm text-gray-500 mt-1 font-mono">ID: {successModal.id.slice(0, 8)}</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 text-left space-y-2">
              <p className="text-sm text-gray-700">
                <span className="font-medium">{successModal.origin}</span>
                <span className="text-gray-400 mx-2">→</span>
                <span className="font-medium">{successModal.destination}</span>
              </p>
              <p className="text-sm text-gray-600">
                {new Date(successModal.start_time).toLocaleString("en-GB", {
                  weekday: "short", day: "numeric", month: "short", year: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })}
              </p>
              <div className="flex items-center gap-2 mt-2">
                <StatusBadge status={(successModal.status === "EMERGENCY_CONFIRMED" ? "CONFIRMED" : successModal.status) as "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED"} />
                <RegionBadge region={successModal.region as "EU" | "US" | "APAC"} />
              </div>
              {(successModal.distance_km || successModal.duration_mins) && (
                <p className="text-xs text-gray-500 mt-1">
                  {successModal.distance_km} km · {successModal.duration_mins} min
                </p>
              )}
            </div>
            <p className="text-sm text-gray-500">📱 Telegram notification sent</p>
            <Button
              onClick={() => { setSuccessModal(null); navigate("/driver"); }}
              className="w-full bg-[#2563EB] hover:bg-[#1d4ed8]"
            >
              View Dashboard
            </Button>
          </div>
        )}
      </Modal>

      {/* Conflict Modal */}
      <Modal isOpen={conflictModal} onClose={() => setConflictModal(false)}>
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
            <span className="text-3xl">❌</span>
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Slot Already Booked</h2>
            <p className="text-sm text-gray-600 mt-2">You already have a journey at this time</p>
          </div>
          <Button
            onClick={() => setConflictModal(false)}
            variant="outline"
            className="w-full"
          >
            Choose a Different Slot
          </Button>
        </div>
      </Modal>
    </div>
  );
}
