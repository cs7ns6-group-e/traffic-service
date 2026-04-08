import { useState } from "react";
import { useNavigate } from "react-router";
import { Route, User, Shield, UserCog } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { cn } from "../components/ui/utils";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { login, register } = useAuth();

  const [isLogin, setIsLogin] = useState(true);
  const [selectedRole, setSelectedRole] = useState<"driver" | "traffic_authority" | "admin">("driver");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roles = [
    { value: "driver" as const, icon: User, label: "Driver" },
    { value: "traffic_authority" as const, icon: Shield, label: "Traffic Authority" },
    { value: "admin" as const, icon: UserCog, label: "Admin" },
  ];

  const demoCredentials = [
    { label: "Driver", email: "driver@trafficbook.com", password: "Driver123!" },
    { label: "Emergency", email: "emergency@trafficbook.com", password: "Emergency123!" },
    { label: "Authority", email: "authority@trafficbook.com", password: "Authority123!" },
    { label: "Admin", email: "admin@trafficbook.com", password: "Admin123!" },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (isLogin) {
        await login(email, password);
        // role comes from JWT via AuthContext — read it back
        const token = localStorage.getItem("tb_access_token");
        if (token) {
          const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
          const role = payload.role as string;
          if (role === "driver") navigate("/driver");
          else if (role === "traffic_authority") navigate("/authority");
          else navigate("/admin");
        }
      } else {
        await register(email, name, password, selectedRole, selectedRole === "driver" ? "STANDARD" : "AUTHORITY");
        if (selectedRole === "driver") navigate("/driver");
        else if (selectedRole === "traffic_authority") navigate("/authority");
        else navigate("/admin");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-br from-[#0F1B2D] via-[#1a2942] to-[#0F1B2D]">
      {/* Animated Background Pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute inset-0" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M54.627 0l.83.828-1.415 1.415L51.8 0h2.827zM5.373 0l-.83.828L5.96 2.243 8.2 0H5.374zM48.97 0l3.657 3.657-1.414 1.414L46.143 0h2.828zM11.03 0L7.372 3.657 8.787 5.07 13.857 0H11.03zm32.284 0L49.8 6.485 48.384 7.9l-7.9-7.9h2.83zM16.686 0L10.2 6.485 11.616 7.9l7.9-7.9h-2.83zm20.97 0l9.315 9.314-1.414 1.414L34.828 0h2.83zM22.344 0L13.03 9.314l1.414 1.414L25.172 0h-2.83zM32 0l12.142 12.142-1.414 1.414L30 .828 17.272 13.556 15.858 12.14 28 0h4zm5.656 0l14.142 14.142-1.414 1.414L32.828 0h4.83zM8.485 0l16.97 16.97-1.414 1.415L7.07 1.414 8.485 0zm-5.656 0l19.8 19.799-1.415 1.414L0 2.828V0h2.83zM60 0v2.83l-22.627 22.627-1.414-1.414L57.172 2.828 60 0zM56.97 0L34.344 22.627l-1.414-1.414L54.142 0h2.828zM22.344 0L0 22.343v-2.828L19.516 0h2.828z' fill='%232563EB' fill-opacity='1' fill-rule='evenodd'/%3E%3C/svg%3E")`,
        }} />
      </div>

      <div className="relative z-10 min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          {/* Logo & Tagline */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-3">
              <Route className="w-12 h-12 text-[#2563EB]" />
              <h1 className="text-4xl font-bold text-white">TrafficBook</h1>
            </div>
            <p className="text-gray-400 italic">"Every journey, approved before it starts"</p>
          </div>

          {/* Login Form Card */}
          <div className="bg-white rounded-2xl shadow-2xl p-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
              {isLogin ? "Welcome Back" : "Create Account"}
            </h2>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Name (register only) */}
              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="h-11"
                  />
                </div>
              )}

              {/* Email */}
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-11"
                />
              </div>

              {/* Password */}
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-11"
                />
              </div>

              {/* Role Selector */}
              <div className="space-y-2">
                <Label>Select Role</Label>
                <div className="grid grid-cols-3 gap-2">
                  {roles.map((role) => {
                    const Icon = role.icon;
                    return (
                      <button
                        key={role.value}
                        type="button"
                        onClick={() => setSelectedRole(role.value)}
                        className={cn(
                          "flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all",
                          selectedRole === role.value
                            ? "border-[#2563EB] bg-blue-50 text-[#2563EB]"
                            : "border-gray-200 hover:border-gray-300 text-gray-600"
                        )}
                      >
                        <Icon className="w-6 h-6" />
                        <span className="text-xs font-medium text-center">{role.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                disabled={loading}
                className="w-full h-11 bg-[#2563EB] hover:bg-[#1d4ed8] text-white font-semibold"
              >
                {loading ? (isLogin ? "Signing in..." : "Creating account...") : (isLogin ? "Login" : "Register")}
              </Button>
            </form>

            {/* Toggle Login/Register */}
            <div className="mt-6 text-center">
              <button
                type="button"
                onClick={() => { setIsLogin(!isLogin); setError(null); }}
                className="text-sm text-[#2563EB] hover:underline"
              >
                {isLogin ? "Don't have an account? Register" : "Already have an account? Login"}
              </button>
            </div>

            {/* Demo Credentials */}
            {isLogin && (
              <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
                <p className="text-xs font-semibold text-gray-600 mb-2">Demo Credentials</p>
                <div className="space-y-1">
                  {demoCredentials.map((cred) => (
                    <button
                      key={cred.email}
                      type="button"
                      onClick={() => { setEmail(cred.email); setPassword(cred.password); }}
                      className="w-full text-left text-xs text-gray-600 hover:text-[#2563EB] py-0.5 flex justify-between"
                    >
                      <span className="font-medium">{cred.label}</span>
                      <span className="font-mono">{cred.email}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer Note */}
          <p className="text-center text-gray-400 text-xs mt-6">
            Powered by Keycloak OAuth2 · Azure Cloud Infrastructure
          </p>
        </div>
      </div>
    </div>
  );
}
