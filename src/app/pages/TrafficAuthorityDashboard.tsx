import { useState } from "react";
import { MapPin, XCircle, Plus, Search, Filter, AlertCircle, Radio } from "lucide-react";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/StatusBadge";
import { RegionBadge } from "../components/RegionBadge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Checkbox } from "../components/ui/checkbox";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { toast } from "sonner";

export default function TrafficAuthorityDashboard() {
  const [selectedRegion, setSelectedRegion] = useState<"EU" | "US" | "APAC">("EU");
  const [isClosureModalOpen, setIsClosureModalOpen] = useState(false);
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [closureData, setClosureData] = useState({
    roadName: "",
    region: "EU" as const,
    reason: "",
    cancelAffected: false,
  });

  // Mock data
  const stats = {
    activeJourneys: 1247,
    cancelledToday: 23,
    roadClosures: 8,
    crossRegion: 45,
  };

  const journeys = [
    {
      id: "J2024-0847",
      driver: "John Driver",
      origin: "Berlin, Germany",
      destination: "Munich, Germany",
      time: "2026-04-02 14:30",
      status: "CONFIRMED" as const,
      region: "EU" as const,
    },
    {
      id: "J2024-0846",
      driver: "Sarah Smith",
      origin: "Hamburg, Germany",
      destination: "Frankfurt, Germany",
      time: "2026-03-31 09:15",
      status: "PENDING" as const,
      region: "EU" as const,
    },
    {
      id: "J2024-0845",
      driver: "Mike Johnson",
      origin: "Paris, France",
      destination: "Brussels, Belgium",
      time: "2026-03-28 16:45",
      status: "CONFIRMED" as const,
      region: "EU" as const,
    },
    {
      id: "J2024-0844",
      driver: "Emma Brown",
      origin: "Amsterdam, Netherlands",
      destination: "Paris, France",
      time: "2026-04-05 11:00",
      status: "PENDING" as const,
      region: "EU" as const,
    },
  ];

  const roadClosures = [
    {
      id: "RC-001",
      roadName: "A9 - Munich Autobahn",
      region: "EU" as const,
      reason: "Emergency maintenance",
      createdAt: "2026-03-29 14:20",
      affectedJourneys: 15,
    },
    {
      id: "RC-002",
      roadName: "B12 - Inner Munich Route",
      region: "EU" as const,
      reason: "Accident investigation",
      createdAt: "2026-03-30 08:45",
      affectedJourneys: 8,
    },
  ];

  const chartData = [
    { region: "EU", confirmed: 847, pending: 123, cancelled: 45 },
    { region: "US", confirmed: 654, pending: 89, cancelled: 32 },
    { region: "APAC", confirmed: 543, pending: 67, cancelled: 28 },
  ];

  const handleForceCancel = (journeyId: string) => {
    toast.success(`Journey ${journeyId} has been cancelled`, {
      description: "The driver has been notified.",
    });
  };

  const handleCreateClosure = () => {
    if (!closureData.roadName || !closureData.reason) {
      toast.error("Please fill in all fields");
      return;
    }
    toast.success("Road closure created", {
      description: closureData.cancelAffected 
        ? "Affected journeys have been cancelled"
        : "Road closure is now active",
    });
    setIsClosureModalOpen(false);
    setClosureData({ roadName: "", region: "EU", reason: "", cancelAffected: false });
  };

  const handleBroadcast = () => {
    toast.success("Broadcast sent", {
      description: "All affected drivers have been notified",
    });
    setIsBroadcastModalOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Traffic Authority Control Panel</h1>
          <p className="text-gray-600 mt-1">Monitor and manage road journeys in your region.</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={selectedRegion} onValueChange={(value: any) => setSelectedRegion(value)}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="EU">EU</SelectItem>
              <SelectItem value="US">US</SelectItem>
              <SelectItem value="APAC">APAC</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={() => setIsBroadcastModalOpen(true)}
            variant="outline"
            className="gap-2"
          >
            <Radio className="w-4 h-4" />
            Broadcast
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Active Journeys" value={stats.activeJourneys} icon={MapPin} />
        <StatCard label="Cancelled Today" value={stats.cancelledToday} icon={XCircle} />
        <StatCard label="Road Closures" value={stats.roadClosures} icon={AlertCircle} />
        <StatCard label="Cross-Region" value={stats.crossRegion} />
      </div>

      {/* Journey Volume Chart */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-6">Journey Volume by Region</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="region" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="confirmed" fill="#16A34A" name="Confirmed" />
            <Bar dataKey="pending" fill="#F59E0B" name="Pending" />
            <Bar dataKey="cancelled" fill="#DC2626" name="Cancelled" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Road Closures */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900">Active Road Closures</h2>
          <Button
            onClick={() => setIsClosureModalOpen(true)}
            className="bg-[#2563EB] hover:bg-[#1d4ed8]"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Closure
          </Button>
        </div>
        <div className="space-y-4">
          {roadClosures.map((closure) => (
            <div
              key={closure.id}
              className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start justify-between gap-4"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="w-5 h-5 text-red-600" />
                  <h3 className="font-semibold text-gray-900">{closure.roadName}</h3>
                  <RegionBadge region={closure.region} />
                </div>
                <p className="text-sm text-gray-700 mb-2">{closure.reason}</p>
                <div className="flex items-center gap-4 text-xs text-gray-600">
                  <span>Created: {closure.createdAt}</span>
                  <span>Affected journeys: {closure.affectedJourneys}</span>
                </div>
              </div>
              <Button variant="outline" size="sm" className="text-red-600 border-red-600 hover:bg-red-50">
                Remove
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Journeys Table */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
          <h2 className="text-xl font-bold text-gray-900">Active Journeys</h2>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:flex-initial">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input placeholder="Search..." className="pl-10 h-10 sm:w-64" />
            </div>
            <Button variant="outline" size="icon" className="h-10 w-10">
              <Filter className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Journey ID</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Driver</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Route</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Time</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase">Action</th>
              </tr>
            </thead>
            <tbody>
              {journeys.map((journey) => (
                <tr key={journey.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-3 px-4">
                    <span className="text-sm font-mono text-gray-900">#{journey.id}</span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-sm text-gray-900">{journey.driver}</span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="text-sm text-gray-900">
                      {journey.origin} → {journey.destination}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-sm text-gray-600">{journey.time}</span>
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={journey.status} />
                  </td>
                  <td className="py-3 px-4">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleForceCancel(journey.id)}
                    >
                      Force Cancel
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Closure Modal */}
      <Dialog open={isClosureModalOpen} onOpenChange={setIsClosureModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Road Closure</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Road Name</Label>
              <Input
                placeholder="e.g., A9 - Munich Autobahn"
                value={closureData.roadName}
                onChange={(e) => setClosureData({ ...closureData, roadName: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Region</Label>
              <Select
                value={closureData.region}
                onValueChange={(value: any) => setClosureData({ ...closureData, region: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EU">EU</SelectItem>
                  <SelectItem value="US">US</SelectItem>
                  <SelectItem value="APAC">APAC</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Reason</Label>
              <Textarea
                placeholder="Describe the reason for closure..."
                value={closureData.reason}
                onChange={(e) => setClosureData({ ...closureData, reason: e.target.value })}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="cancel-affected"
                checked={closureData.cancelAffected}
                onCheckedChange={(checked) =>
                  setClosureData({ ...closureData, cancelAffected: checked as boolean })
                }
              />
              <label htmlFor="cancel-affected" className="text-sm text-gray-700">
                Cancel all affected journeys
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsClosureModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateClosure} className="bg-[#2563EB] hover:bg-[#1d4ed8]">
              Create Closure
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Broadcast Modal */}
      <Dialog open={isBroadcastModalOpen} onOpenChange={setIsBroadcastModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Broadcast Alert</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Message</Label>
              <Textarea
                placeholder="Enter your broadcast message to all affected drivers..."
                rows={6}
              />
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              This message will be sent to all drivers in the {selectedRegion} region via email and Telegram.
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBroadcastModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleBroadcast} className="bg-[#2563EB] hover:bg-[#1d4ed8]">
              Send Broadcast
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
