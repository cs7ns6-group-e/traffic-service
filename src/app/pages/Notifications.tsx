import { useState } from "react";
import { Bell, CheckCircle, XCircle, AlertTriangle, Info, Check } from "lucide-react";
import { Button } from "../components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { cn } from "../components/ui/utils";

export default function Notifications() {
  const [notifications, setNotifications] = useState([
    {
      id: 1,
      type: "success",
      icon: CheckCircle,
      title: "Journey Approved",
      body: "Your journey from Berlin to Munich has been approved by the EU Traffic Authority.",
      timestamp: "2 hours ago",
      unread: true,
      category: "journey",
    },
    {
      id: 2,
      type: "warning",
      icon: AlertTriangle,
      title: "Road Closure Alert",
      body: "A9 - Munich Autobahn is closed due to emergency maintenance. Your upcoming journey may be affected.",
      timestamp: "5 hours ago",
      unread: true,
      category: "authority",
    },
    {
      id: 3,
      type: "error",
      icon: XCircle,
      title: "Journey Cancelled by Authority",
      body: "Your journey #J2024-0844 has been cancelled by the traffic authority due to road closure.",
      timestamp: "1 day ago",
      unread: true,
      category: "authority",
    },
    {
      id: 4,
      type: "success",
      icon: CheckCircle,
      title: "Conflict Check Passed",
      body: "Your journey request has passed the automated conflict detection system.",
      timestamp: "2 days ago",
      unread: false,
      category: "journey",
    },
    {
      id: 5,
      type: "info",
      icon: Info,
      title: "System Maintenance",
      body: "Scheduled system maintenance will occur on April 5th from 2:00 AM to 4:00 AM UTC.",
      timestamp: "3 days ago",
      unread: false,
      category: "journey",
    },
    {
      id: 6,
      type: "success",
      icon: CheckCircle,
      title: "Journey Completed",
      body: "Your journey from Paris to Brussels has been marked as completed.",
      timestamp: "4 days ago",
      unread: false,
      category: "journey",
    },
  ]);

  const [filter, setFilter] = useState<"all" | "journey" | "authority">("all");

  const handleMarkAllRead = () => {
    setNotifications(notifications.map(n => ({ ...n, unread: false })));
  };

  const handleMarkRead = (id: number) => {
    setNotifications(notifications.map(n => 
      n.id === id ? { ...n, unread: false } : n
    ));
  };

  const filteredNotifications = notifications.filter(n => 
    filter === "all" || n.category === filter
  );

  const unreadCount = notifications.filter(n => n.unread).length;

  const getIconColor = (type: string) => {
    switch (type) {
      case "success":
        return "text-green-600 bg-green-100";
      case "error":
        return "text-red-600 bg-red-100";
      case "warning":
        return "text-amber-600 bg-amber-100";
      default:
        return "text-blue-600 bg-blue-100";
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Notifications</h1>
          <p className="text-gray-600 mt-1">
            {unreadCount > 0 ? `You have ${unreadCount} unread notification${unreadCount > 1 ? 's' : ''}` : 'All caught up!'}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button onClick={handleMarkAllRead} variant="outline">
            <Check className="w-4 h-4 mr-2" />
            Mark all as read
          </Button>
        )}
      </div>

      {/* Filters */}
      <Tabs value={filter} onValueChange={(value: any) => setFilter(value)}>
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
          <div className="space-y-3">
            {filteredNotifications.length === 0 ? (
              <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
                <Bell className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">No notifications to display</p>
              </div>
            ) : (
              filteredNotifications.map((notification) => {
                const Icon = notification.icon;
                return (
                  <div
                    key={notification.id}
                    className={cn(
                      "bg-white rounded-lg border p-4 cursor-pointer transition-all hover:shadow-md",
                      notification.unread ? "border-blue-200 bg-blue-50/50" : "border-gray-200"
                    )}
                    onClick={() => handleMarkRead(notification.id)}
                  >
                    <div className="flex items-start gap-4">
                      <div className={cn("p-2 rounded-full", getIconColor(notification.type))}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <h3 className="font-semibold text-gray-900">{notification.title}</h3>
                          {notification.unread && (
                            <div className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0 mt-1.5" />
                          )}
                        </div>
                        <p className="text-sm text-gray-700 mb-2">{notification.body}</p>
                        <p className="text-xs text-gray-500">{notification.timestamp}</p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
