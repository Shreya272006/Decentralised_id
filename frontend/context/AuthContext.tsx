"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiClient, setStoredTokens, clearStoredTokens, extractErrorMessage } from "@/lib/api";

export type Role = "user" | "issuer" | "verifier" | "admin";

interface AuthUser {
  userId: string;
  email: string;
  role: Role;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ otpRequired: boolean; challengeToken?: string }>;
  verifyOtp: (challengeToken: string, code: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, role: Role) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function decodeJwt(token: string): any {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const infoStr = typeof window !== "undefined" ? window.sessionStorage.getItem("user_info") : null;
    if (infoStr) {
      setUser(JSON.parse(infoStr));
    }
    setLoading(false);
  }, []);

  const applyUser = useCallback((userInfo: AuthUser) => {
    setUser(userInfo);
    window.sessionStorage.setItem("user_info", JSON.stringify(userInfo));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post("/auth/login", { email, password });
    if (data.otp_required) {
      return { otpRequired: true, challengeToken: data.otp_challenge_token };
    }
    applyUser({ userId: data.user_id, email: data.email, role: data.role });
    return { otpRequired: false };
  }, [applyUser]);

  const verifyOtp = useCallback(async (challengeToken: string, code: string) => {
    const { data } = await apiClient.post("/auth/verify-otp", {
      otp_challenge_token: challengeToken,
      otp_code: code,
    });
    applyUser({ userId: data.user_id, email: data.email, role: data.role });
  }, [applyUser]);

  const register = useCallback(async (email: string, password: string, fullName: string, role: Role) => {
    await apiClient.post("/auth/register", { email, password, full_name: fullName, role });
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch {}
    window.sessionStorage.removeItem("user_info");
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, verifyOtp, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export { extractErrorMessage };
