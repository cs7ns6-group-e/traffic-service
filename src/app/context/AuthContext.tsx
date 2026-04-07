import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { getToken, setTokens, clearTokens } from "../api/client";
import { ENDPOINTS } from "../api/config";

export interface User {
  id: string;
  email: string;
  name: string;
  role: "driver" | "traffic_authority" | "admin";
  vehicle_type: "STANDARD" | "EMERGENCY" | "AUTHORITY";
  region: "EU" | "US" | "APAC";
}

interface AuthContextValue {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

function decodeJwt(token: string): Partial<User> | null {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const decoded = JSON.parse(atob(payload));
    return {
      id:           decoded.sub,
      email:        decoded.email,
      name:         decoded.name,
      role:         decoded.role,
      vehicle_type: decoded.vehicle_type ?? "STANDARD",
      region:       decoded.region ?? "EU",
    };
  } catch {
    return null;
  }
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const token = getToken();
    if (!token) return null;
    const decoded = decodeJwt(token);
    if (!decoded?.id) return null;
    return decoded as User;
  });

  async function login(email: string, password: string) {
    const res = await fetch(ENDPOINTS.LOGIN, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail ?? "Login failed");
    }
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    const decoded = decodeJwt(data.access_token);
    if (decoded?.id) setUser(decoded as User);
  }

  function logout() {
    clearTokens();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
