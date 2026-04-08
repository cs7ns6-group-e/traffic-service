import { Outlet, useNavigate, useLocation } from "react-router";
import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  MapPin,
  Route,
  Bell,
  Settings,
  Menu,
  X,
  LogOut,
  User,
  Shield,
  UserCog,
} from "lucide-react";
import { RegionBadge } from "../components/RegionBadge";
import { Button } from "../components/ui/button";
import { cn } from "../components/ui/utils";
import { useAuth } from "../context/AuthContext";

export default function DashboardLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [notificationCount] = useState(3);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!user) navigate("/login", { replace: true });
  }, [user, navigate]);

  // Derive role from JWT user; fallback to path for initial render
  const role: "driver" | "traffic_authority" | "admin" =
    user?.role ??
    (location.pathname.startsWith("/driver")
      ? "driver"
      : location.pathname.startsWith("/authority")
      ? "traffic_authority"
      : "admin");

  const roleConfig = {
    driver: {
      icon: User,
      label: "Driver",
      links: [
        { path: "/driver", icon: LayoutDashboard, label: "Dashboard" },
        { path: "/driver/book-journey", icon: MapPin, label: "Book Journey" },
        { path: "/driver/notifications", icon: Bell, label: "Notifications" },
        { path: "/driver/settings", icon: Settings, label: "Settings" },
      ],
    },
    traffic_authority: {
      icon: Shield,
      label: "Traffic Authority",
      links: [
        { path: "/authority", icon: LayoutDashboard, label: "Control Panel" },
        { path: "/authority/notifications", icon: Bell, label: "Notifications" },
        { path: "/authority/settings", icon: Settings, label: "Settings" },
      ],
    },
    admin: {
      icon: UserCog,
      label: "Admin",
      links: [
        { path: "/admin", icon: LayoutDashboard, label: "System Dashboard" },
        { path: "/admin/notifications", icon: Bell, label: "Notifications" },
        { path: "/admin/settings", icon: Settings, label: "Settings" },
      ],
    },
  };

  const config = roleConfig[role];
  const RoleIcon = config.icon;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-[#0F1B2D] text-white p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Route className="w-6 h-6 text-[#2563EB]" />
          <span className="font-bold">TrafficBook</span>
        </div>
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="p-2 hover:bg-white/10 rounded-lg transition-colors"
        >
          {isSidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-0 left-0 h-full w-64 bg-[#0F1B2D] text-white z-40 transition-transform duration-300",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full",
          "lg:translate-x-0"
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-white/10">
            <div className="flex items-center gap-3 mb-1">
              <Route className="w-8 h-8 text-[#2563EB]" />
              <div>
                <h1 className="text-xl font-bold">TrafficBook</h1>
                <p className="text-xs text-gray-400">Every journey, approved before it starts</p>
              </div>
            </div>
          </div>

          {/* User Info */}
          <div className="p-4 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-[#2563EB] flex items-center justify-center">
                <RoleIcon className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user.name}</p>
                <p className="text-xs text-gray-400 truncate">{user.email}</p>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <RegionBadge region={user.region} />
              <span className="text-xs text-gray-400">{config.label}</span>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            {config.links.map((link) => {
              const Icon = link.icon;
              const isActive =
                location.pathname === link.path ||
                (link.path !== `/${role}` && location.pathname.startsWith(link.path));
              return (
                <button
                  key={link.path}
                  onClick={() => {
                    navigate(link.path);
                    setIsSidebarOpen(false);
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-left",
                    isActive
                      ? "bg-[#2563EB] text-white"
                      : "text-gray-300 hover:bg-white/5"
                  )}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-sm font-medium">{link.label}</span>
                  {link.icon === Bell && notificationCount > 0 && (
                    <span className="ml-auto bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                      {notificationCount}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Logout */}
          <div className="p-4 border-t border-white/10">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 hover:bg-white/5 transition-colors"
            >
              <LogOut className="w-5 h-5" />
              <span className="text-sm font-medium">Logout</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="lg:ml-64 pt-20 lg:pt-0">
        <div className="p-4 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
