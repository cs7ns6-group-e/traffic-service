// GCP Load Balancer IPs (stable across VM restarts)
export const API_REGIONS = {
  EU:   "http://35.240.110.205",
  US:   "http://34.26.94.36",
  APAC: "http://34.126.131.195",
} as const;

// In dev, Vite proxies these paths to the EU backend.
// In prod (nginx on VM), nginx routes them directly.
export const ENDPOINTS = {
  LOGIN:   "/auth/login",
  REGISTER: "/auth/register",
  REFRESH: "/auth/refresh",
  ME:      "/auth/me",

  JOURNEYS:      "/journeys",
  JOURNEY:       (id: string) => `/journeys/${id}`,

  ROUTE:         "/route",
  FAMOUS_ROUTES: "/routes/famous",

  AUTHORITY_JOURNEYS:        "/authority/journeys",
  AUTHORITY_CANCEL:          (id: string) => `/authority/cancel/${id}`,
  AUTHORITY_CLOSURE:         "/authority/closure",
  AUTHORITY_CLOSURES:        "/authority/closures",
  AUTHORITY_STATS:           "/authority/stats",
  AUTHORITY_SEGMENTS:        "/authority/segments",
  AUTHORITY_CLOSURE_PREVIEW: (road: string) => `/authority/closure-preview?road_name=${encodeURIComponent(road)}`,

  ADMIN_HEALTH:      "/admin/health",
  ADMIN_STATS:       "/admin/stats",
  ADMIN_ALL_REGIONS: "/admin/all-regions",
  ADMIN_LATENCY:     "/admin/latency",
  ADMIN_QUEUE:       "/admin/queue",
  ADMIN_CACHE:       "/admin/cache",
  ADMIN_REPLICATED:  "/admin/replicated",

  CONFLICTS_SLOTS: "/conflicts/slots",
  SEARCH:          "/search",
} as const;
