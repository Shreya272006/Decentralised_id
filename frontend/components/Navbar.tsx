"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { ShieldCheck, LogOut, LayoutDashboard } from "lucide-react";
import clsx from "clsx";

const roleHome: Record<string, string> = {
  user: "/dashboard/user",
  issuer: "/dashboard/issuer",
  verifier: "/dashboard/verifier",
  admin: "/dashboard/admin",
};

export default function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <header className="border-b border-gray-100 bg-white/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold text-brand-700">
          <ShieldCheck className="w-6 h-6" />
          <span>DecentraID</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm text-gray-600">
          <Link href="/how-it-works" className={clsx(pathname === "/how-it-works" && "text-brand-600 font-medium")}>
            How It Works
          </Link>
          <Link href="/privacy" className={clsx(pathname === "/privacy" && "text-brand-600 font-medium")}>
            Privacy
          </Link>
          {user && (
            <Link
              href={roleHome[user.role] || "/dashboard/user"}
              className={clsx("flex items-center gap-1", pathname.startsWith("/dashboard") && "text-brand-600 font-medium")}
            >
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="hidden sm:inline text-sm text-gray-500">{user.email}</span>
              <button onClick={logout} className="btn-secondary flex items-center gap-1 text-sm">
                <LogOut className="w-4 h-4" />
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="btn-secondary text-sm">
                Log in
              </Link>
              <Link href="/register" className="btn-primary text-sm">
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
