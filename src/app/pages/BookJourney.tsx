import { useState } from "react";
import { useNavigate } from "react-router";
import { MapPin, Calendar, Clock, AlertTriangle, Route as RouteIcon, ChevronDown } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { RegionBadge } from "../components/RegionBadge";
import { RoadSegmentChip } from "../components/RoadSegmentChip";
import { toast } from "sonner";

export default function BookJourney() {
  const navigate = useNavigate();
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [showRoutePreview, setShowRoutePreview] = useState(false);

  // Mock region detection
  const originRegion = origin.toLowerCase().includes("paris") || origin.toLowerCase().includes("berlin") || origin.toLowerCase().includes("amsterdam") 
    ? "EU" 
    : origin.toLowerCase().includes("new york") || origin.toLowerCase().includes("chicago")
    ? "US"
    : origin.toLowerCase().includes("tokyo") || origin.toLowerCase().includes("singapore")
    ? "APAC"
    : null;

  const destinationRegion = destination.toLowerCase().includes("paris") || destination.toLowerCase().includes("berlin") || destination.toLowerCase().includes("amsterdam")
    ? "EU"
    : destination.toLowerCase().includes("new york") || destination.toLowerCase().includes("chicago")
    ? "US"
    : destination.toLowerCase().includes("tokyo") || destination.toLowerCase().includes("singapore")
    ? "APAC"
    : null;

  const isCrossRegion = originRegion && destinationRegion && originRegion !== destinationRegion;

  // Mock route data
  const routePreview = {
    distance: "584 km",
    duration: "5h 45min",
    segments: [
      "A1 - Berlin Ring",
      "A9 - Munich Autobahn",
      "B12 - Inner Munich Route",
      "A95 - Southern Bypass",
    ],
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success("Journey booking submitted!", {
      description: "Your journey request is being processed.",
    });
    setTimeout(() => {
      navigate("/driver");
    }, 1500);
  };

  const handleShowRoutePreview = () => {
    if (origin && destination) {
      setShowRoutePreview(true);
    } else {
      toast.error("Please enter both origin and destination");
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Book a Journey</h1>
        <p className="text-gray-600 mt-1">Plan your route and request approval from traffic authorities.</p>
      </div>

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
                onChange={(e) => setOrigin(e.target.value)}
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
                onChange={(e) => setDestination(e.target.value)}
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
                  This is a cross-region journey. The destination region ({destinationRegion}) will be notified
                  and must approve this journey.
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
            >
              <RouteIcon className="w-4 h-4 mr-2" />
              Preview Route
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

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500 uppercase font-medium">Distance</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{routePreview.distance}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase font-medium">Duration</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{routePreview.duration}</p>
                </div>
              </div>

              <div>
                <button
                  type="button"
                  onClick={() => {}}
                  className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3 hover:text-gray-900"
                >
                  Road Segments ({routePreview.segments.length})
                  <ChevronDown className="w-4 h-4" />
                </button>
                <div className="flex flex-wrap gap-2">
                  {routePreview.segments.map((segment, index) => (
                    <RoadSegmentChip key={index} roadName={segment} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate("/driver")}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="flex-1 bg-[#2563EB] hover:bg-[#1d4ed8]"
            >
              Request Journey Approval
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
