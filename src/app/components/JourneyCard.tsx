import { cn } from "../components/ui/utils";
import { StatusBadge } from "./StatusBadge";
import { RegionBadge } from "./RegionBadge";
import { MapPin, Calendar, ArrowRight, ChevronRight } from "lucide-react";
import { Button } from "./ui/button";

interface JourneyCardProps {
  journey: {
    id: string;
    origin: string;
    destination: string;
    date: string;
    time: string;
    status: "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED";
    region: "EU" | "US" | "APAC";
  };
  variant?: "compact" | "expanded";
  onViewDetails?: () => void;
  className?: string;
}

export function JourneyCard({
  journey,
  variant = "compact",
  onViewDetails,
  className,
}: JourneyCardProps) {
  if (variant === "compact") {
    return (
      <div className={cn("bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow", className)}>
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-gray-500 font-mono">#{journey.id}</span>
              <RegionBadge region={journey.region} />
            </div>
            <div className="flex items-center gap-2 text-sm">
              <MapPin className="w-4 h-4 text-gray-400" />
              <span className="font-medium text-gray-900">{journey.origin}</span>
              <ArrowRight className="w-4 h-4 text-gray-400" />
              <span className="font-medium text-gray-900">{journey.destination}</span>
            </div>
          </div>
          <StatusBadge status={journey.status} />
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <Calendar className="w-3.5 h-3.5" />
            <span>{journey.date} at {journey.time}</span>
          </div>
          {onViewDetails && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onViewDetails}
              className="text-blue-600 hover:text-blue-700"
            >
              View <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("bg-white rounded-lg border border-gray-200 p-6", className)}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm text-gray-500 font-mono">Journey #{journey.id}</span>
            <RegionBadge region={journey.region} />
          </div>
          <h3 className="text-lg font-semibold text-gray-900">Journey Details</h3>
        </div>
        <StatusBadge status={journey.status} />
      </div>
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase">Route</label>
          <div className="flex items-center gap-3 mt-1">
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
        <div>
          <label className="text-xs font-medium text-gray-500 uppercase">Scheduled Time</label>
          <div className="flex items-center gap-2 mt-1">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span className="text-gray-900">{journey.date} at {journey.time}</span>
          </div>
        </div>
      </div>
      {onViewDetails && (
        <Button
          onClick={onViewDetails}
          className="w-full mt-4 bg-blue-600 hover:bg-blue-700"
        >
          View Full Details <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
      )}
    </div>
  );
}
