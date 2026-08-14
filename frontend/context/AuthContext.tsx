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
    const token = typeof window !== "undefined" ? window.sessionStorage.getItem("access_token") : null;
    if (token) {
      const claims = decodeJwt(token);
      if (claims) {
        setUser({ userId: claims.sub, email: claims.email || "", role: claims.role });
      }
    }
    setLoading(false);
  }, []);

  const applyTokens = useCallback((accessToken: string, refreshToken: string) => {
    setStoredTokens(accessToken, refreshToken);
    const claims = decodeJwt(accessToken);
    if (claims) {
      setUser({ userId: claims.sub, email: claims.email || "", role: claims.role });
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post("/auth/login", { email, password });
    if (data.otp_required) {
      return { otpRequired: true, challengeToken: data.otp_challenge_token };
    }
    applyTokens(data.access_token, data.refresh_token);
    return { otpRequired: false };
  }, [applyTokens]);

  const verifyOtp = useCallback(async (challengeToken: string, code: string) => {
    const { data } = await apiClient.post("/auth/verify-otp", {
      otp_challenge_token: challengeToken,
      otp_code: code,
    });
    applyTokens(data.access_token, data.refresh_token);
  }, [applyTokens]);

  const register = useCallback(async (email: string, password: string, fullName: string, role: Role) => {
    await apiClient.post("/auth/register", { email, password, full_name: fullName, role });
  }, []);

  const logout = useCallback(() => {
    clearStoredTokens();
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
