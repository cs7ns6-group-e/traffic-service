import { useState } from "react";
import { User, Mail, Bell, MessageCircle, Shield, Lock, Trash2, ExternalLink, LogOut } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router";

export default function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [emailNotifications, setEmailNotifications] = useState(true);
  const [telegramNotifications, setTelegramNotifications] = useState(false);
  const [selectedRegion, setSelectedRegion] = useState(user?.region ?? "EU");
  const [isTelegramConnected, setIsTelegramConnected] = useState(false);

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success("Profile updated successfully");
  };

  const handleChangePassword = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success("Password changed successfully");
  };

  const handleConnectTelegram = () => {
    window.open("https://t.me/trafficbook_bot?start=connect", "_blank");
    toast.info("Opening Telegram bot...", {
      description: "Click /start to connect your account",
    });
    // Simulate connection after a delay
    setTimeout(() => {
      setIsTelegramConnected(true);
      setTelegramNotifications(true);
      toast.success("Telegram connected successfully!");
    }, 3000);
  };

  const handleDeleteAccount = () => {
    if (confirm("Are you sure you want to delete your account? This action cannot be undone.")) {
      toast.error("Account deletion initiated", {
        description: "Your account will be deleted within 24 hours",
      });
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">Manage your account preferences and notifications.</p>
      </div>

      {/* Profile Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <User className="w-5 h-5 text-gray-600" />
          <h2 className="text-xl font-bold text-gray-900">Profile Information</h2>
        </div>
        <form onSubmit={handleSaveProfile} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input id="name" defaultValue={user?.name ?? ""} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" defaultValue={user?.email ?? ""} />
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Role</Label>
              <div className="flex items-center gap-2 h-11 px-3 bg-gray-50 rounded border border-gray-200">
                <Shield className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-gray-700 capitalize">{user?.role?.replace("_", " ") ?? "—"}</span>
                <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded">Active</span>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Vehicle Type</Label>
              <div className="flex items-center gap-2 h-11 px-3 bg-gray-50 rounded border border-gray-200">
                <span className="text-sm text-gray-700">{user?.vehicle_type ?? "—"}</span>
              </div>
            </div>
          </div>
          <Button type="submit" className="bg-[#2563EB] hover:bg-[#1d4ed8]">
            Save Changes
          </Button>
        </form>
      </div>

      {/* Notification Preferences */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Bell className="w-5 h-5 text-gray-600" />
          <h2 className="text-xl font-bold text-gray-900">Notification Preferences</h2>
        </div>
        <div className="space-y-6">
          {/* Email Notifications */}
          <div className="flex items-center justify-between">
            <div className="flex items-start gap-3">
              <Mail className="w-5 h-5 text-gray-600 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900">Email Notifications</p>
                <p className="text-sm text-gray-600">Receive journey updates and alerts via email</p>
              </div>
            </div>
            <Switch
              checked={emailNotifications}
              onCheckedChange={setEmailNotifications}
            />
          </div>

          {/* Telegram Notifications */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-start gap-3">
                <MessageCircle className="w-5 h-5 text-gray-600 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Telegram Notifications</p>
                  <p className="text-sm text-gray-600">Receive instant notifications on Telegram</p>
                </div>
              </div>
              <Switch
                checked={telegramNotifications}
                onCheckedChange={setTelegramNotifications}
                disabled={!isTelegramConnected}
              />
            </div>

            {!isTelegramConnected && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 ml-8">
                <h4 className="font-semibold text-blue-900 mb-2">Connect Telegram Bot</h4>
                <ol className="text-sm text-blue-800 space-y-1 mb-4">
                  <li>1. Click the button below to open the TrafficBook bot</li>
                  <li>2. Send the /start command to connect your account</li>
                  <li>3. Your account will be linked automatically</li>
                </ol>
                <Button
                  type="button"
                  onClick={handleConnectTelegram}
                  variant="outline"
                  className="border-blue-600 text-blue-600 hover:bg-blue-50"
                >
                  <MessageCircle className="w-4 h-4 mr-2" />
                  Connect to Telegram Bot
                  <ExternalLink className="w-3 h-3 ml-2" />
                </Button>
              </div>
            )}

            {isTelegramConnected && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 ml-8">
                <div className="flex items-center gap-2 text-green-700">
                  <MessageCircle className="w-4 h-4" />
                  <span className="text-sm font-medium">Telegram account connected</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Region Preference */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Shield className="w-5 h-5 text-gray-600" />
          <h2 className="text-xl font-bold text-gray-900">Region Preference</h2>
        </div>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Primary Region</Label>
            <Select value={selectedRegion} onValueChange={setSelectedRegion} disabled>
              <SelectTrigger className="w-full sm:w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="EU">EU - Europe</SelectItem>
                <SelectItem value="US">US - United States</SelectItem>
                <SelectItem value="APAC">APAC - Asia Pacific</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-sm text-gray-600">
              Region is assigned by the system and cannot be changed here.
            </p>
          </div>
        </div>
      </div>

      {/* Logout */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <LogOut className="w-5 h-5 text-gray-600" />
          <h2 className="text-xl font-bold text-gray-900">Session</h2>
        </div>
        <Button variant="outline" onClick={handleLogout} className="border-gray-300">
          <LogOut className="w-4 h-4 mr-2" />
          Logout
        </Button>
      </div>

      {/* Change Password */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Lock className="w-5 h-5 text-gray-600" />
          <h2 className="text-xl font-bold text-gray-900">Change Password</h2>
        </div>
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="current-password">Current Password</Label>
            <Input id="current-password" type="password" />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input id="new-password" type="password" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm New Password</Label>
              <Input id="confirm-password" type="password" />
            </div>
          </div>
          <Button type="submit" className="bg-[#2563EB] hover:bg-[#1d4ed8]">
            Update Password
          </Button>
        </form>
      </div>

      {/* Danger Zone */}
      <div className="bg-white rounded-lg border border-red-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Trash2 className="w-5 h-5 text-red-600" />
          <h2 className="text-xl font-bold text-red-900">Danger Zone</h2>
        </div>
        <div className="space-y-4">
          <p className="text-sm text-gray-700">
            Once you delete your account, there is no going back. This will permanently delete your
            account, journey history, and all associated data.
          </p>
          <Button
            variant="destructive"
            onClick={handleDeleteAccount}
            className="bg-red-600 hover:bg-red-700"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete Account
          </Button>
        </div>
      </div>
    </div>
  );
}
