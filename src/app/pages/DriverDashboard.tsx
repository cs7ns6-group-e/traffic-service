import { useState } from "react";
import { useNavigate } from "react-router";
import { MapPin, Plus, Search, Filter } from "lucide-react";
import { StatCard } from "../components/StatCard";
import { JourneyCard } from "../components/JourneyCard";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

export default function DriverDashboard() {
  const navigate = useNavigate();

  // Mock data
  const stats = {
    total: 127,
    confirmed: 98,
    pending: 15,
    cancelled: 14,
  };

  const recentJourneys = [
    {
      id: "J2024-0847",
      origin: "Berlin, Germany",
      destination: "Munich, Germany",
      date: "2026-04-02",
      time: "14:30",
      status: "CONFIRMED" as const,
      region: "EU" as const,
    },
    {
      id: "J2024-0846",
      origin: "Hamburg, Germany",
      destination: "Frankfurt, Germany",
      date: "2026-03-31",
      time: "09:15",
      status: "PENDING" as const,
      region: "EU" as const,
    },
    {
      id: "J2024-0845",
      origin: "Paris, France",
      destination: "Brussels, Belgium",
      date: "2026-03-28",
      time: "16:45",
      status: "CONFIRMED" as const,
      region: "EU" as const,
    },
    {
      id: "J2024-0844",
      origin: "Amsterdam, Netherlands",
      destination: "Rotterdam, Netherlands",
      date: "2026-03-25",
      time: "11:00",
      status: "CANCELLED" as const,
      region: "EU" as const,
    },
    {
      id: "J2024-0843",
      origin: "Vienna, Austria",
      destination: "Salzburg, Austria",
      date: "2026-03-20",
      time: "08:30",
      status: "AUTHORITY_CANCELLED" as const,
      region: "EU" as const,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
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
        <StatCard
          label="Total Journeys"
          value={stats.total}
          icon={MapPin}
        />
        <StatCard
          label="Confirmed"
          value={stats.confirmed}
          trend={{ value: 12, direction: "up" }}
        />
        <StatCard
          label="Pending"
          value={stats.pending}
        />
        <StatCard
          label="Cancelled"
          value={stats.cancelled}
        />
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
              />
            </div>
            <Button variant="outline" size="icon" className="h-10 w-10">
              <Filter className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          {recentJourneys.map((journey) => (
            <JourneyCard
              key={journey.id}
              journey={journey}
              variant="compact"
              onViewDetails={() => navigate(`/driver/journey/${journey.id}`)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
