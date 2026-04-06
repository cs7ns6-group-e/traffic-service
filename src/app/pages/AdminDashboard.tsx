import { useState } from "react";
import { Plus, Minus, Activity, Database, Radio } from "lucide-react";
import { ServiceHealthIndicator } from "../components/ServiceHealthIndicator";
import { RegionBadge } from "../components/RegionBadge";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";

export default function AdminDashboard() {
  const [services, setServices] = useState([
    { name: "API Gateway", status: "ONLINE" as const, responseTime: 45, replicas: 3 },
    { name: "Journey Booking", status: "ONLINE" as const, responseTime: 87, replicas: 5 },
    { name: "Conflict Detection", status: "ONLINE" as const, responseTime: 124, replicas: 4 },
    { name: "User Management", status: "ONLINE" as const, responseTime: 56, replicas: 3 },
    { name: "Notification Service", status: "ONLINE" as const, responseTime: 72, replicas: 4 },
    { name: "Traffic Authority", status: "ONLINE" as const, responseTime: 93, replicas: 3 },
    { name: "Road Routing", status: "ONLINE" as const, responseTime: 145, replicas: 5 },
  ]);

  const regions = [
    { name: "EU", activeJourneys: 1247, status: "healthy" },
    { name: "US", activeJourneys: 876, status: "healthy" },
    { name: "APAC", activeJourneys: 654, status: "healthy" },
  ];

  const systemEvents = [
    {
      timestamp: "2026-03-30 14:23:15",
      level: "INFO",
      service: "Journey Booking",
      message: "Journey J2024-0847 approved successfully",
    },
    {
      timestamp: "2026-03-30 14:22:08",
      level: "WARNING",
      service: "Conflict Detection",
      message: "High load detected - scaling up replicas",
    },
    {
      timestamp: "2026-03-30 14:21:45",
      level: "INFO",
      service: "Notification Service",
      message: "Telegram notification sent to user #8473",
    },
    {
      timestamp: "2026-03-30 14:20:32",
      level: "ERROR",
      service: "Road Routing",
      message: "External API timeout - retrying...",
    },
    {
      timestamp: "2026-03-30 14:19:18",
      level: "INFO",
      service: "API Gateway",
      message: "Health check completed - all services responding",
    },
    {
      timestamp: "2026-03-30 14:18:05",
      level: "INFO",
      service: "User Management",
      message: "New user registered - Driver role",
    },
    {
      timestamp: "2026-03-30 14:17:42",
      level: "INFO",
      service: "Traffic Authority",
      message: "Road closure created for A9 - Munich Autobahn",
    },
    {
      timestamp: "2026-03-30 14:16:28",
      level: "WARNING",
      service: "Conflict Detection",
      message: "15 journeys affected by road closure RC-001",
    },
  ];

  const queueDepth = 42;
  const cacheHitRate = 87.5;

  const handleScaleService = (serviceName: string, direction: "up" | "down") => {
    setServices(services.map(s => {
      if (s.name === serviceName) {
        const newReplicas = direction === "up" ? s.replicas + 1 : Math.max(1, s.replicas - 1);
        toast.success(`${serviceName} scaled to ${newReplicas} replicas`);
        return { ...s, replicas: newReplicas };
      }
      return s;
    }));
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case "ERROR":
        return "text-red-600 bg-red-50";
      case "WARNING":
        return "text-amber-600 bg-amber-50";
      default:
        return "text-blue-600 bg-blue-50";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">System Dashboard</h1>
        <p className="text-gray-600 mt-1">Monitor and manage TrafficBook infrastructure.</p>
      </div>

      {/* System Health */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">Service Health</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {services.map((service) => (
            <div key={service.name} className="space-y-2">
              <ServiceHealthIndicator
                serviceName={service.name}
                status={service.status}
                responseTime={service.responseTime}
              />
              <div className="flex items-center justify-between gap-2 px-4">
                <span className="text-xs text-gray-600">{service.replicas} replicas</span>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 w-6 p-0"
                    onClick={() => handleScaleService(service.name, "down")}
                  >
                    <Minus className="w-3 h-3" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 w-6 p-0"
                    onClick={() => handleScaleService(service.name, "up")}
                  >
                    <Plus className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Region Status & Metrics */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Region Status */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Region Status</h2>
          <div className="space-y-4">
            {regions.map((region) => (
              <div
                key={region.name}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <RegionBadge region={region.name as any} />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {region.activeJourneys} active journeys
                    </p>
                    <p className="text-xs text-gray-500">Status: {region.status}</p>
                  </div>
                </div>
                <div className="w-3 h-3 rounded-full bg-green-500" />
              </div>
            ))}
          </div>
        </div>

        {/* System Metrics */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">System Metrics</h2>
          <div className="space-y-6">
            {/* RabbitMQ Queue Depth */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Radio className="w-4 h-4 text-gray-600" />
                  <span className="text-sm font-medium text-gray-900">RabbitMQ Queue Depth</span>
                </div>
                <span className="text-lg font-bold text-gray-900">{queueDepth}</span>
              </div>
              <Progress value={(queueDepth / 100) * 100} className="h-2" />
              <p className="text-xs text-gray-500 mt-1">Messages pending processing</p>
            </div>

            {/* Redis Cache Hit Rate */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-gray-600" />
                  <span className="text-sm font-medium text-gray-900">Redis Cache Hit Rate</span>
                </div>
                <span className="text-lg font-bold text-gray-900">{cacheHitRate}%</span>
              </div>
              <Progress value={cacheHitRate} className="h-2" />
              <p className="text-xs text-gray-500 mt-1">Optimal cache performance</p>
            </div>

            {/* System Load */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-gray-600" />
                  <span className="text-sm font-medium text-gray-900">System Load</span>
                </div>
                <span className="text-lg font-bold text-gray-900">Moderate</span>
              </div>
              <Progress value={62} className="h-2" />
              <p className="text-xs text-gray-500 mt-1">62% resource utilization</p>
            </div>
          </div>
        </div>
      </div>

      {/* System Events Log */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Recent System Events</h2>
          <Button variant="outline" size="sm">
            Export Logs
          </Button>
        </div>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {systemEvents.map((event, index) => (
            <div
              key={index}
              className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <span
                className={`text-xs font-mono px-2 py-1 rounded ${getLevelColor(event.level)}`}
              >
                {event.level}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-gray-900">{event.service}</span>
                  <span className="text-xs text-gray-400">{event.timestamp}</span>
                </div>
                <p className="text-sm text-gray-700">{event.message}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
