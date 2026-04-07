import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { MapPin, Plus, Search, Filter } from "lucide-react";
import { StatCard } from "../components/StatCard";
import { JourneyCard } from "../components/JourneyCard";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { useAuth } from "../context/AuthContext";
import { apiGet } from "../api/client";
import { ENDPOINTS } from "../api/config";

interface ApiJourney {
  id: string;
  driver_id: string;
  origin: string;
  destination: string;
  start_time: string;
  status: "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED" | "EMERGENCY_CONFIRMED";
  region: "EU" | "US" | "APAC";
}

function parseStartTime(start_time: string): { date: string; time: string } {
  try {
    const d = new Date(start_time);
    const date = d.toISOString().split("T")[0];
    const time = d.toTimeString().slice(0, 5);
    return { date, time };
  } catch {
    return { date: start_time, time: "" };
  }
}

function normaliseStatus(
  status: ApiJourney["status"]
): "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED" {
  if (status === "EMERGENCY_CONFIRMED") return "CONFIRMED";
  return status;
}

export default function DriverDashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [journeys, setJourneys] = useState<ApiJourney[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const isEmergency = user?.vehicle_type === "EMERGENCY";

  useEffect(() => {
    if (!user?.id) { setLoading(false); return; }
    apiGet<ApiJourney[]>(`${ENDPOINTS.JOURNEYS}?driver_id=${user.id}`)
      .then(setJourneys)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user?.id]);

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
          <>
            {[0, 1, 2, 3].map(i => (
              <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-3" />
                <div className="h-8 bg-gray-200 rounded w-1/3" />
              </div>
            ))}
          </>
        ) : (
          <>
            <StatCard label="Total Journeys" value={stats.total} icon={MapPin} />
            <StatCard label="Confirmed" value={stats.confirmed} />
            <StatCard label="Pending" value={stats.pending} />
            <StatCard label="Cancelled" value={stats.cancelled} />
          </>
        )}
      </div>

      {/* Recent Journeys */}
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
            {journeys.length === 0
              ? "No journeys yet. Book your first journey!"
              : "No journeys match your search."}
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((journey) => {
              const { date, time } = parseStartTime(journey.start_time);
              return (
                <JourneyCard
                  key={journey.id}
                  journey={{
                    id: journey.id,
                    origin: journey.origin,
                    destination: journey.destination,
                    date,
                    time,
                    status: normaliseStatus(journey.status),
                    region: journey.region,
                  }}
                  variant="compact"
                  onViewDetails={() => navigate(`/driver/journey/${journey.id}`)}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
