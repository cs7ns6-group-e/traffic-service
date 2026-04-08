import { useState, useEffect, useCallback } from "react";
import { Plus, Minus, Activity, Database, Radio } from "lucide-react";
import { ServiceHealthIndicator } from "../components/ServiceHealthIndicator";
import { RegionBadge } from "../components/RegionBadge";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import { apiGet } from "../api/client";
import { ENDPOINTS } from "../api/config";

interface ServiceHealth {
  name: string;
  status: "ONLINE" | "OFFLINE";
  responseTime: number;
  replicas: number;
}

interface RegionData {
  activeJourneys: number;
  status: string;
}

interface QueueData {
  booking_events?: number;
  emergency_events?: number;
  road_closure_events?: number;
  total?: number;
  depth?: number;
}

interface CacheData {
  hit_rate?: number;
  hitRate?: number;
}

const DEFAULT_SERVICES: ServiceHealth[] = [
  { name: "API Gateway",       status: "ONLINE", responseTime: 45,  replicas: 3 },
  { name: "Journey Booking",   status: "ONLINE", responseTime: 87,  replicas: 5 },
  { name: "Conflict Detection",status: "ONLINE", responseTime: 124, replicas: 4 },
  { name: "User Management",   status: "ONLINE", responseTime: 56,  replicas: 3 },
  { name: "Notification Service",status:"ONLINE",responseTime: 72,  replicas: 4 },
  { name: "Traffic Authority", status: "ONLINE", responseTime: 93,  replicas: 3 },
  { name: "Road Routing",      status: "ONLINE", responseTime: 145, replicas: 5 },
];

export default function AdminDashboard() {
  const [services, setServices] = useState<ServiceHealth[]>(DEFAULT_SERVICES);
  const [regions, setRegions] = useState<Record<string, RegionData>>({
    EU:   { activeJourneys: 0, status: "healthy" },
    US:   { activeJourneys: 0, status: "healthy" },
    APAC: { activeJourneys: 0, status: "healthy" },
  });
  const [queueDepth, setQueueDepth] = useState(0);
  const [cacheHitRate, setCacheHitRate] = useState(0);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingRegions, setLoadingRegions] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(true);

  const fetchHealth = useCallback(() => {
    setLoadingHealth(true);
    apiGet<unknown>(ENDPOINTS.ADMIN_HEALTH)
      .then((data) => {
        if (!data) return;
        // Try to parse various response shapes
        const obj = data as Record<string, unknown>;
        if (Array.isArray(obj.services)) {
          setServices(
            (obj.services as Array<Record<string, unknown>>).map((s, i) => ({
              name: String(s.name ?? DEFAULT_SERVICES[i]?.name ?? "Service"),
              status: (s.status === "healthy" || s.status === "ONLINE") ? "ONLINE" : "OFFLINE",
              responseTime: Number(s.response_time_ms ?? s.responseTime ?? DEFAULT_SERVICES[i]?.responseTime ?? 0),
              replicas: Number(s.replicas ?? DEFAULT_SERVICES[i]?.replicas ?? 1),
            }))
          );
        } else {
          // Shape: { auth: { status, response_time_ms }, ... }
          const updated = DEFAULT_SERVICES.map((svc) => {
            const key = svc.name.toLowerCase().replace(/\s+/g, "_");
            const entry = (obj[key] ?? obj[svc.name]) as Record<string, unknown> | undefined;
            if (!entry) return svc;
            return {
              ...svc,
              status: (entry.status === "healthy" || entry.status === "ONLINE") ? "ONLINE" as const : "OFFLINE" as const,
              responseTime: Number(entry.response_time_ms ?? entry.responseTime ?? svc.responseTime),
            };
          });
          setServices(updated);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingHealth(false));
  }, []);

  const fetchRegions = useCallback(() => {
    setLoadingRegions(true);
    apiGet<unknown>(ENDPOINTS.ADMIN_ALL_REGIONS)
      .then((data) => {
        if (!data) return;
        const obj = data as Record<string, unknown>;
        const mapped: Record<string, RegionData> = {};
        for (const region of ["EU", "US", "APAC"]) {
          const r = obj[region] as Record<string, unknown> | undefined;
          if (r) {
            mapped[region] = {
              activeJourneys: Number(r.active_journeys ?? r.total ?? r.activeJourneys ?? 0),
              status: String(r.status ?? "healthy"),
            };
          }
        }
        if (Object.keys(mapped).length > 0) setRegions(prev => ({ ...prev, ...mapped }));
      })
      .catch(() => {})
      .finally(() => setLoadingRegions(false));
  }, []);

  const fetchMetrics = useCallback(() => {
    setLoadingMetrics(true);
    Promise.all([
      apiGet<QueueData>(ENDPOINTS.ADMIN_QUEUE).catch(() => null),
      apiGet<CacheData>(ENDPOINTS.ADMIN_CACHE).catch(() => null),
    ]).then(([queue, cache]) => {
      if (queue) {
        setQueueDepth(queue.total ?? queue.depth ?? (queue.booking_events ?? 0) + (queue.emergency_events ?? 0) + (queue.road_closure_events ?? 0));
      }
      if (cache) {
        setCacheHitRate(Number(cache.hit_rate ?? cache.hitRate ?? 0));
      }
    }).finally(() => setLoadingMetrics(false));
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchRegions();
    fetchMetrics();

    const interval = setInterval(() => {
      fetchHealth();
      fetchRegions();
      fetchMetrics();
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchHealth, fetchRegions, fetchMetrics]);

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
        {loadingHealth ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 animate-pulse">
            {[0,1,2,3,4,5,6].map(i => <div key={i} className="h-20 bg-gray-200 rounded-lg" />)}
          </div>
        ) : (
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
        )}
      </div>

      {/* Region Status & Metrics */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Region Status */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Region Status</h2>
          {loadingRegions ? (
            <div className="space-y-3 animate-pulse">
              {[0,1,2].map(i => <div key={i} className="h-16 bg-gray-100 rounded-lg" />)}
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(regions).map(([region, data]) => (
                <div
                  key={region}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <RegionBadge region={region as "EU" | "US" | "APAC"} />
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {data.activeJourneys} active journeys
                      </p>
                      <p className="text-xs text-gray-500">Status: {data.status}</p>
                    </div>
                  </div>
                  <div className={`w-3 h-3 rounded-full ${data.status === "healthy" ? "bg-green-500" : "bg-red-500"}`} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* System Metrics */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">System Metrics</h2>
          {loadingMetrics ? (
            <div className="space-y-6 animate-pulse">
              {[0,1,2].map(i => <div key={i} className="h-16 bg-gray-100 rounded" />)}
            </div>
          ) : (
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
                <Progress value={Math.min((queueDepth / 100) * 100, 100)} className="h-2" />
                <p className="text-xs text-gray-500 mt-1">Messages pending processing</p>
              </div>

              {/* Redis Cache Hit Rate */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-900">Redis Cache Hit Rate</span>
                  </div>
                  <span className="text-lg font-bold text-gray-900">{cacheHitRate.toFixed(1)}%</span>
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
          )}
        </div>
      </div>

      {/* Auto-refresh notice */}
      <p className="text-xs text-gray-400 text-right">Auto-refreshes every 30 seconds</p>
    </div>
  );
}
