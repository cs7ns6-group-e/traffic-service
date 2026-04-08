import { useState, useEffect } from "react";
import { Bell, CheckCircle, XCircle, AlertTriangle, Info, Check, Zap } from "lucide-react";
import { Button } from "../components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { cn } from "../components/ui/utils";
import { useAuth } from "../context/AuthContext";
import { apiGet } from "../api/client";
import { ENDPOINTS } from "../api/config";

interface ApiJourney {
  id: string;
  origin: string;
  destination: string;
  start_time: string;
  status: "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED" | "EMERGENCY_CONFIRMED";
  region: "EU" | "US" | "APAC";
  vehicle_type?: string;
  is_cross_region?: boolean;
  created_at?: string;
}

interface Notification {
  id: string;
  type: "success" | "warning" | "error" | "info" | "emergency";
  title: string;
  body: string;
  timestamp: string;
  unread: boolean;
  category: "journey" | "authority" | "system";
}

function journeyToNotification(j: ApiJourney): Notification {
  const route = `${j.origin} → ${j.destination}`;
  const isEmerg = j.vehicle_type === "EMERGENCY" || j.status === "EMERGENCY_CONFIRMED";

  if (isEmerg) {
    return {
      id: j.id,
      type: "emergency",
      title: `🚨 Emergency Journey — ${route}`,
      body: "Emergency vehicle journey instantly approved. Conflict detection bypassed.",
      timestamp: j.created_at ?? j.start_time,
      unread: j.status === "EMERGENCY_CONFIRMED",
      category: "journey",
    };
  }

  switch (j.status) {
    case "CONFIRMED":
      return {
        id: j.id,
        type: "success",
        title: `Journey Approved`,
        body: `${route} — CONFIRMED`,
        timestamp: j.created_at ?? j.start_time,
        unread: false,
        category: "journey",
      };
    case "PENDING":
      return {
        id: j.id,
        type: "info",
        title: `Journey Pending Review`,
        body: `${route} — Awaiting authority approval`,
        timestamp: j.created_at ?? j.start_time,
        unread: true,
        category: "journey",
      };
    case "CANCELLED":
      return {
        id: j.id,
        type: "warning",
        title: `Journey Cancelled`,
        body: `${route} — You cancelled this journey`,
        timestamp: j.created_at ?? j.start_time,
        unread: false,
        category: "journey",
      };
    case "AUTHORITY_CANCELLED":
      return {
        id: j.id,
        type: "error",
        title: `Journey Cancelled by Authority`,
        body: `${route} — N7 closure — journey cancelled`,
        timestamp: j.created_at ?? j.start_time,
        unread: true,
        category: "authority",
      };
    default:
      return {
        id: j.id,
        type: "info",
        title: `Journey Update`,
        body: route,
        timestamp: j.created_at ?? j.start_time,
        unread: false,
        category: "journey",
      };
  }
}

function formatTs(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins} min ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  } catch { return iso; }
}

export default function Notifications() {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "journey" | "authority">("all");

  useEffect(() => {
    if (!user?.email) { setLoading(false); return; }
    apiGet<ApiJourney[]>(`${ENDPOINTS.JOURNEYS}?driver_id=${encodeURIComponent(user.email)}`)
      .then((journeys) => {
        const notifs = journeys
          .sort((a, b) => new Date(b.created_at ?? b.start_time).getTime() - new Date(a.created_at ?? a.start_time).getTime())
          .map(journeyToNotification);
        setNotifications(notifs);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user?.email]);

  const handleMarkAllRead = () => setNotifications(notifications.map(n => ({ ...n, unread: false })));
  const handleMarkRead = (id: string) => setNotifications(notifications.map(n => n.id === id ? { ...n, unread: false } : n));

  const filteredNotifications = notifications.filter(n => filter === "all" || n.category === filter);
  const unreadCount = notifications.filter(n => n.unread).length;

  function getIconColor(type: string) {
    switch (type) {
      case "success":   return "text-green-600 bg-green-100";
      case "error":     return "text-red-600 bg-red-100";
      case "warning":   return "text-amber-600 bg-amber-100";
      case "emergency": return "text-red-600 bg-red-100";
      default:          return "text-blue-600 bg-blue-100";
    }
  }

  function getIcon(type: string) {
    switch (type) {
      case "success":   return CheckCircle;
      case "error":     return XCircle;
      case "warning":   return AlertTriangle;
      case "emergency": return Zap;
      default:          return Info;
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Notifications</h1>
          <p className="text-gray-600 mt-1">
            {loading ? "Loading…" : unreadCount > 0 ? `You have ${unreadCount} unread notification${unreadCount > 1 ? "s" : ""}` : "All caught up!"}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button onClick={handleMarkAllRead} variant="outline">
            <Check className="w-4 h-4 mr-2" />Mark all as read
          </Button>
        )}
      </div>

      {/* Filters */}
      <Tabs value={filter} onValueChange={(v) => setFilter(v as typeof filter)}>
        <TabsList>
          <TabsTrigger value="all">
            All
            {unreadCount > 0 && (
              <span className="ml-2 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="journey">Journey Updates</TabsTrigger>
          <TabsTrigger value="authority">Authority Alerts</TabsTrigger>
        </TabsList>

        <TabsContent value={filter} className="mt-6">
          {loading ? (
            <div className="space-y-3 animate-pulse">
              {[0, 1, 2].map(i => <div key={i} className="h-20 bg-gray-100 rounded-lg" />)}
            </div>
          ) : filteredNotifications.length === 0 ? (
            <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
              <Bell className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No notifications to display</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredNotifications.map((n) => {
                const Icon = getIcon(n.type);
                return (
                  <div
                    key={n.id}
                    className={cn(
                      "bg-white rounded-lg border p-4 cursor-pointer transition-all hover:shadow-md",
                      n.unread ? "border-blue-200 bg-blue-50/50" : "border-gray-200"
                    )}
                    onClick={() => handleMarkRead(n.id)}
                  >
                    <div className="flex items-start gap-4">
                      <div className={cn("p-2 rounded-full", getIconColor(n.type))}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <h3 className="font-semibold text-gray-900">{n.title}</h3>
                          {n.unread && <div className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0 mt-1.5" />}
                        </div>
                        <p className="text-sm text-gray-700 mb-2">{n.body}</p>
                        <p className="text-xs text-gray-500">{formatTs(n.timestamp)}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
