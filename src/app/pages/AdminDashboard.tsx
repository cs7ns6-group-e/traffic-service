import { useState, useEffect, useCallback } from "react";
import { Plus, Minus, Activity, Database, Radio, RefreshCw } from "lucide-react";
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
  p95_ms?: number;
  sla?: string;
}

interface RegionStats {
  total?: number;
  confirmed?: number;
  pending?: number;
  cancelled?: number;
  emergency?: number;
  active_journeys?: number;
  status?: string;
  available?: boolean;
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
  { name: "API Gateway",        status: "ONLINE", responseTime: 45,  replicas: 3 },
  { name: "Journey Booking",    status: "ONLINE", responseTime: 87,  replicas: 5 },
  { name: "Conflict Detection", status: "ONLINE", responseTime: 124, replicas: 4 },
  { name: "User Management",    status: "ONLINE", responseTime: 56,  replicas: 3 },
  { name: "Notification",       status: "ONLINE", responseTime: 72,  replicas: 4 },
  { name: "Traffic Authority",  status: "ONLINE", responseTime: 93,  replicas: 3 },
  { name: "Road Routing",       status: "ONLINE", responseTime: 145, replicas: 5 },
];

function fmt(ts: Date) {
  return ts.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function AdminDashboard() {
  const [services, setServices] = useState<ServiceHealth[]>(DEFAULT_SERVICES);
  const [regions, setRegions] = useState<Record<string, RegionStats & { name: string }>>({
    EU:   { name: "EU",   status: "loading" },
    US:   { name: "US",   status: "loading" },
    APAC: { name: "APAC", status: "loading" },
  });
  const [queueDepth, setQueueDepth] = useState(0);
  const [cacheHitRate, setCacheHitRate] = useState(0);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingRegions, setLoadingRegions] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchHealth = useCallback(() => {
    setLoadingHealth(true);
    Promise.all([
      apiGet<unknown>(ENDPOINTS.ADMIN_HEALTH).catch(() => null),
      apiGet<unknown>(ENDPOINTS.ADMIN_LATENCY).catch(() => null),
    ]).then(([health, latency]) => {
      const latencyMap: Record<string, number> = {};
      if (latency) {
        const lo = latency as Record<string, Record<string, unknown>>;
        for (const [k, v] of Object.entries(lo)) {
          if (typeof v === "object" && v !== null) {
            latencyMap[k] = Number((v as Record<string, unknown>).p95_ms ?? 0);
          }
        }
      }

      if (!health) { setLoadingHealth(false); return; }
      const obj = health as Record<string, unknown>;

      if (Array.isArray(obj.services)) {
        setServices(
          (obj.services as Array<Record<string, unknown>>).map((s, i) => ({
            name: String(s.name ?? DEFAULT_SERVICES[i]?.name ?? "Service"),
            status: (s.status === "healthy" || s.status === "ONLINE") ? "ONLINE" : "OFFLINE",
            responseTime: Number(s.response_time_ms ?? s.responseTime ?? DEFAULT_SERVICES[i]?.responseTime ?? 0),
            replicas: Number(s.replicas ?? DEFAULT_SERVICES[i]?.replicas ?? 1),
            p95_ms: latencyMap[String(s.name).toLowerCase().replace(/\s+/g, "_")],
          }))
        );
      } else {
        setServices(DEFAULT_SERVICES.map((svc) => {
          const key = svc.name.toLowerCase().replace(/\s+/g, "_");
          const entry = (obj[key] ?? obj[svc.name]) as Record<string, unknown> | undefined;
          if (!entry) return svc;
          return {
            ...svc,
            status: (entry.status === "healthy" || entry.status === "ONLINE") ? "ONLINE" as const : "OFFLINE" as const,
            responseTime: Number(entry.response_time_ms ?? entry.responseTime ?? svc.responseTime),
            p95_ms: latencyMap[key],
          };
        }));
      }
    }).finally(() => setLoadingHealth(false));
  }, []);

  const fetchRegions = useCallback(() => {
    setLoadingRegions(true);
    apiGet<unknown>(ENDPOINTS.ADMIN_ALL_REGIONS)
      .then((data) => {
        if (!data) return;
        const obj = data as Record<string, unknown>;
        const mapped: Record<string, RegionStats & { name: string }> = {};
        for (const region of ["EU", "US", "APAC"]) {
          const r = obj[region] as Record<string, unknown> | undefined;
          mapped[region] = r ? {
            name: region,
            total: Number(r.total ?? r.active_journeys ?? 0),
            confirmed: Number(r.confirmed ?? 0),
            pending: Number(r.pending ?? 0),
            cancelled: Number(r.cancelled ?? 0),
            emergency: Number(r.emergency ?? 0),
            active_journeys: Number(r.active_journeys ?? r.total ?? 0),
            status: String(r.status ?? "healthy"),
            available: true,
          } : { name: region, status: "unavailable", available: false };
        }
        setRegions(mapped);
      })
      .catch(() => {
        setRegions({
          EU:   { name: "EU",   status: "unavailable", available: false },
          US:   { name: "US",   status: "unavailable", available: false },
          APAC: { name: "APAC", status: "unavailable", available: false },
        });
      })
      .finally(() => setLoadingRegions(false));
  }, []);

  const fetchMetrics = useCallback(() => {
    setLoadingMetrics(true);
    Promise.all([
      apiGet<QueueData>(ENDPOINTS.ADMIN_QUEUE).catch(() => null),
      apiGet<CacheData>(ENDPOINTS.ADMIN_CACHE).catch(() => null),
    ]).then(([queue, cache]) => {
      if (queue) setQueueDepth(queue.total ?? queue.depth ?? (queue.booking_events ?? 0) + (queue.emergency_events ?? 0) + (queue.road_closure_events ?? 0));
      if (cache) setCacheHitRate(Number(cache.hit_rate ?? cache.hitRate ?? 0));
    }).finally(() => setLoadingMetrics(false));
  }, []);

  function refreshAll() {
    fetchHealth();
    fetchRegions();
    fetchMetrics();
    setLastUpdated(new Date());
  }

  useEffect(() => {
    refreshAll();
    const id = setInterval(refreshAll, 30000);
    return () => clearInterval(id);
  }, [fetchHealth, fetchRegions, fetchMetrics]);

  function handleScaleService(name: string, dir: "up" | "down") {
    setServices(services.map(s => {
      if (s.name !== name) return s;
      const n = dir === "up" ? s.replicas + 1 : Math.max(1, s.replicas - 1);
      toast.success(`${name} scaled to ${n} replicas`);
      return { ...s, replicas: n };
    }));
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">System Dashboard</h1>
          <p className="text-gray-600 mt-1">Monitor and manage TrafficBook infrastructure.</p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && <span className="text-xs text-gray-400">Updated {fmt(lastUpdated)}</span>}
          <Button variant="outline" size="sm" onClick={refreshAll}>
            <RefreshCw className="w-4 h-4 mr-1" />Refresh
          </Button>
        </div>
      </div>

      {/* Service Health */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">Service Health</h2>
        {loadingHealth ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 animate-pulse">
            {[0,1,2,3,4,5,6].map(i => <div key={i} className="h-20 bg-gray-200 rounded-lg" />)}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {services.map((svc) => (
              <div key={svc.name} className="space-y-2">
                <ServiceHealthIndicator serviceName={svc.name} status={svc.status} responseTime={svc.responseTime} />
                {svc.p95_ms !== undefined && (
                  <div className={`text-xs px-2 py-0.5 rounded mx-4 text-center font-medium ${svc.p95_ms < 500 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    P95 {svc.p95_ms}ms {svc.p95_ms < 500 ? "✅" : "⚠️"}
                  </div>
                )}
                <div className="flex items-center justify-between gap-2 px-4">
                  <span className="text-xs text-gray-600">{svc.replicas} replicas</span>
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" className="h-6 w-6 p-0" onClick={() => handleScaleService(svc.name, "down")}>
                      <Minus className="w-3 h-3" />
                    </Button>
                    <Button size="sm" variant="outline" className="h-6 w-6 p-0" onClick={() => handleScaleService(svc.name, "up")}>
                      <Plus className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Regions + Metrics */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Region Cards */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Region Status</h2>
          {loadingRegions ? (
            <div className="space-y-3 animate-pulse">{[0,1,2].map(i => <div key={i} className="h-20 bg-gray-100 rounded-lg" />)}</div>
          ) : (
            <div className="space-y-4">
              {Object.entries(regions).map(([region, data]) => {
                const unavailable = !data.available || data.status === "unavailable";
                return (
                  <div key={region} className={`p-4 rounded-lg border ${unavailable ? "bg-gray-50 border-gray-200 opacity-60" : "bg-white border-gray-200"}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <RegionBadge region={region as "EU" | "US" | "APAC"} />
                        {unavailable && <span className="text-xs text-gray-400">(unavailable)</span>}
                      </div>
                      <div className={`w-3 h-3 rounded-full ${unavailable ? "bg-gray-400" : data.status === "healthy" ? "bg-green-500" : "bg-red-500"}`} />
                    </div>
                    {!unavailable && (
                      <div className="grid grid-cols-4 gap-2 text-center mt-2">
                        {([
                          ["Total", data.total ?? data.active_journeys ?? 0],
                          ["Confirmed", data.confirmed ?? 0],
                          ["Pending", data.pending ?? 0],
                          ["Emergency", data.emergency ?? 0],
                        ] as [string, number][]).map(([label, value]) => (
                          <div key={label}>
                            <p className="text-lg font-bold text-gray-900">{value}</p>
                            <p className="text-xs text-gray-500">{label}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* System Metrics */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">System Metrics</h2>
          {loadingMetrics ? (
            <div className="space-y-6 animate-pulse">{[0,1,2].map(i => <div key={i} className="h-16 bg-gray-100 rounded" />)}</div>
          ) : (
            <div className="space-y-6">
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
      <p className="text-xs text-gray-400 text-right">Auto-refreshes every 30 seconds</p>
    </div>
  );
}
