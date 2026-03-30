import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { MapPin, Calendar, ArrowRight, CheckCircle2, Clock, XCircle, AlertCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { StatusBadge } from "../components/StatusBadge";
import { RegionBadge } from "../components/RegionBadge";
import { RoadSegmentChip } from "../components/RoadSegmentChip";
import { toast } from "sonner";

export default function JourneyDetail() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [isCancelling, setIsCancelling] = useState(false);

  // Mock journey data
  const journey = {
    id: id || "J2024-0847",
    origin: "Berlin, Germany",
    destination: "Munich, Germany",
    date: "2026-04-02",
    time: "14:30",
    status: "CONFIRMED" as const,
    region: "EU" as const,
    createdAt: "2026-03-25 10:30",
    distance: "584 km",
    duration: "5h 45min",
    roadSegments: [
      "A1 - Berlin Ring",
      "A9 - Munich Autobahn",
      "B12 - Inner Munich Route",
      "A95 - Southern Bypass",
    ],
  };

  const timeline = [
    {
      status: "Submitted",
      timestamp: "2026-03-25 10:30",
      icon: CheckCircle2,
      color: "text-green-600",
      bgColor: "bg-green-100",
      completed: true,
    },
    {
      status: "Conflict Check",
      timestamp: "2026-03-25 10:31",
      icon: CheckCircle2,
      color: "text-green-600",
      bgColor: "bg-green-100",
      completed: true,
    },
    {
      status: "Authority Review",
      timestamp: "2026-03-25 11:15",
      icon: CheckCircle2,
      color: "text-green-600",
      bgColor: "bg-green-100",
      completed: true,
    },
    {
      status: "Approved",
      timestamp: "2026-03-25 11:20",
      icon: CheckCircle2,
      color: "text-green-600",
      bgColor: "bg-green-100",
      completed: true,
    },
  ];

  const notifications = [
    {
      title: "Journey Approved",
      message: "Your journey has been approved by the EU Traffic Authority",
      timestamp: "2026-03-25 11:20",
    },
    {
      title: "Conflict Check Passed",
      message: "No conflicts detected with road closures or other journeys",
      timestamp: "2026-03-25 10:31",
    },
    {
      title: "Journey Submitted",
      message: "Your journey request has been submitted for review",
      timestamp: "2026-03-25 10:30",
    },
  ];

  const handleCancelJourney = () => {
    setIsCancelling(true);
    setTimeout(() => {
      toast.success("Journey cancelled successfully");
      navigate("/driver");
    }, 1000);
  };

  const canCancel = journey.status === "CONFIRMED" && new Date(journey.date) > new Date();

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
                  <StatusBadge status={journey.status} />
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
                    <span className="text-gray-900">{journey.date} at {journey.time}</span>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase">Created</label>
                  <div className="flex items-center gap-2 mt-2">
                    <Clock className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-900">{journey.createdAt}</span>
                  </div>
                </div>
              </div>

              {/* Distance & Duration */}
              <div className="grid sm:grid-cols-2 gap-4 pt-4 border-t">
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase">Distance</label>
                  <p className="text-lg font-bold text-gray-900 mt-1">{journey.distance}</p>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 uppercase">Est. Duration</label>
                  <p className="text-lg font-bold text-gray-900 mt-1">{journey.duration}</p>
                </div>
              </div>

              {/* Road Segments */}
              <div className="pt-4 border-t">
                <label className="text-xs font-medium text-gray-500 uppercase">Road Segments</label>
                <div className="flex flex-wrap gap-2 mt-2">
                  {journey.roadSegments.map((segment, index) => (
                    <RoadSegmentChip key={index} roadName={segment} />
                  ))}
                </div>
              </div>
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
                      <p className="text-sm text-gray-500">{item.timestamp}</p>
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

          {/* Notification History */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Notifications</h3>
            <div className="space-y-3">
              {notifications.map((notif, index) => (
                <div key={index} className="pb-3 border-b last:border-0 last:pb-0">
                  <p className="text-sm font-medium text-gray-900">{notif.title}</p>
                  <p className="text-xs text-gray-600 mt-1">{notif.message}</p>
                  <p className="text-xs text-gray-400 mt-1">{notif.timestamp}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
