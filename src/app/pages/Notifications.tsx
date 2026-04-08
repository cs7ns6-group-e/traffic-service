import { useState, useEffect } from "react";
import { Bell, Check } from "lucide-react";
import { Button } from "../components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { cn } from "../components/ui/utils";
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
  cancelled_reason?: string;
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
  const ts = j.created_at ?? j.start_time;

  switch (j.status) {
    case "EMERGENCY_CONFIRMED":
      return {
        id: j.id,
        type: "emergency",
        title: `🚨 Emergency journey approved: ${route}`,
        body: "Emergency vehicle journey instantly approved. Conflict detection bypassed.",
        timestamp: ts,
        unread: true,
        category: "journey",
      };
    case "CONFIRMED":
      return {
        id: j.id,
        type: "success",
        title: `Journey CONFIRMED: ${route}`,
        body: "Your journey has been approved by traffic authorities.",
        timestamp: ts,
        unread: false,
        category: "journey",
      };
    case "PENDING":
      return {
        id: j.id,
        type: "info",
        title: `Journey processing: ${route}`,
        body: "Awaiting conflict check and authority approval.",
        timestamp: ts,
        unread: true,
        category: "journey",
      };
    case "CANCELLED":
      return {
        id: j.id,
        type: "warning",
        title: `Journey cancelled: ${route}`,
        body: "You cancelled this journey.",
        timestamp: ts,
        unread: false,
        category: "journey",
      };
    case "AUTHORITY_CANCELLED":
      return {
        id: j.id,
        type: "error",
        title: `Journey cancelled by Traffic Authority: ${route}`,
        body: j.cancelled_reason ? `Reason: ${j.cancelled_reason}` : "Reason: No reason given",
        timestamp: ts,
        unread: true,
        category: "authority",
      };
    default:
      return {
        id: j.id,
        type: "info",
        title: `Journey update: ${route}`,
        body: j.status,
        timestamp: ts,
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
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  } catch { return iso; }
}

function getTypeStyle(type: string) {
  switch (type) {
    case "success":   return { bg: "bg-green-100", text: "text-green-700", dot: "bg-green-500", icon: "✅" };
    case "emergency": return { bg: "bg-red-100",   text: "text-red-700",   dot: "bg-red-500",   icon: "🚨" };
    case "error":     return { bg: "bg-red-100",   text: "text-red-700",   dot: "bg-red-500",   icon: "🚫" };
    case "warning":   return { bg: "bg-gray-100",  text: "text-gray-600",  dot: "bg-gray-400",  icon: "❌" };
    default:          return { bg: "bg-yellow-100",text: "text-yellow-700",dot: "bg-yellow-400",icon: "⏳" };
  }
}

export default function Notifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "journey" | "authority">("all");

  useEffect(() => {
    apiGet<ApiJourney[]>(ENDPOINTS.JOURNEYS)
      .then((journeys) => {
        const notifs = journeys
          .sort((a, b) =>
            new Date(b.created_at ?? b.start_time).getTime() -
            new Date(a.created_at ?? a.start_time).getTime()
          )
          .map(journeyToNotification);
        setNotifications(notifs);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleMarkAllRead = () =>
    setNotifications(notifications.map(n => ({ ...n, unread: false })));
  const handleMarkRead = (id: string) =>
    setNotifications(notifications.map(n => n.id === id ? { ...n, unread: false } : n));

  const filteredNotifications = notifications.filter(
    n => filter === "all" || n.category === filter
  );
  const unreadCount = notifications.filter(n => n.unread).length;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Notifications</h1>
          <p className="text-gray-600 mt-1">
            {loading
              ? "Loading…"
              : unreadCount > 0
              ? `You have ${unreadCount} unread notification${unreadCount > 1 ? "s" : ""}`
              : "All caught up!"}
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
              <p className="text-gray-600">No journey history yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredNotifications.map((n) => {
                const style = getTypeStyle(n.type);
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
                      <div className={cn("w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0", style.bg)}>
                        <span className="text-base leading-none">{style.icon}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <h3 className="font-semibold text-gray-900 text-sm">{n.title}</h3>
                          {n.unread && (
                            <div className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0 mt-1.5" />
                          )}
                        </div>
                        <p className="text-sm text-gray-700 mb-1">{n.body}</p>
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
