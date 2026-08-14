"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import ProtectedRoute from "@/components/ProtectedRoute";
import StatusBadge from "@/components/StatusBadge";
import SearchFilterToolbar from "@/components/SearchFilterToolbar";
import { apiClient, extractErrorMessage } from "@/lib/api";
import { Users, Building2, ScrollText, ActivitySquare } from "lucide-react";

interface AdminUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  is_blocked: boolean;
  created_at: string;
}

interface AdminIssuer {
  id: string;
  user_id: string;
  organization_name: string;
  is_approved: boolean;
  is_blocked: boolean;
  created_at: string;
}

interface AdminAuditLog {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  created_at: string;
}

function AdminDashboardContent() {
  const [tab, setTab] = useState<"users" | "issuers" | "logs" | "health">("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [issuers, setIssuers] = useState<AdminIssuer[]>([]);
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [integrity, setIntegrity] = useState<{ intact: boolean; first_broken_record_id: string | null } | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function loadAll() {
    setError(null);
    try {
      const [usersRes, issuersRes, logsRes, integrityRes] = await Promise.all([
        apiClient.get("/admin/users"),
        apiClient.get("/admin/issuers"),
        apiClient.get("/admin/logs"),
        apiClient.get("/admin/logs/integrity"),
      ]);
      setUsers(usersRes.data);
      setIssuers(issuersRes.data);
      setLogs(logsRes.data);
      setIntegrity(integrityRes.data);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function approveIssuer(issuerProfileId: string) {
    try {
      await apiClient.post("/admin/approve-issuer", { issuer_profile_id: issuerProfileId });
      loadAll();
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  async function blockIssuer(issuerProfileId: string) {
    const reason = window.prompt("Reason for blocking this issuer:");
    if (!reason) return;
    try {
      await apiClient.post("/admin/block-issuer", { issuer_profile_id: issuerProfileId, reason });
      loadAll();
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  const filteredUsers = users.filter((u) => u.email.toLowerCase().includes(search.toLowerCase()));

  const tabs = [
    { id: "users", label: "Users", icon: Users },
    { id: "issuers", label: "Issuers", icon: Building2 },
    { id: "logs", label: "Audit Logs", icon: ScrollText },
    { id: "health", label: "System Health", icon: ActivitySquare },
  ] as const;

  return (
    <main>
      <Navbar />
      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-semibold text-gray-900 mb-1">Admin Console</h1>
        <p className="text-gray-500 mb-8">Platform-wide oversight of users, issuers, and system integrity.</p>

        {error && <div className="bg-red-50 text-red-700 text-sm rounded-lg px-3 py-2 mb-6">{error}</div>}

        <div className="flex gap-2 mb-8 flex-wrap">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium ${
                tab === t.id ? "bg-brand-600 text-white" : "bg-white border border-gray-200 text-gray-600"
              }`}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </div>

        {tab === "users" && (
          <div className="card">
            <SearchFilterToolbar searchValue={search} onSearchChange={setSearch} searchPlaceholder="Search by email..." />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-100">
                    <th className="pb-2">Email</th>
                    <th className="pb-2">Role</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Joined</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((u) => (
                    <tr key={u.id} className="border-b border-gray-50 last:border-0">
                      <td className="py-3">{u.email}</td>
                      <td className="py-3 capitalize">{u.role}</td>
                      <td className="py-3">
                        <StatusBadge status={u.is_blocked ? "blocked" : u.is_active ? "active" : "suspended"} />
                      </td>
                      <td className="py-3 text-gray-500">{new Date(u.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "issuers" && (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-100">
                  <th className="pb-2">Organization</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Registered</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {issuers.map((i) => (
                  <tr key={i.id} className="border-b border-gray-50 last:border-0">
                    <td className="py-3">{i.organization_name}</td>
                    <td className="py-3">
                      <StatusBadge status={i.is_blocked ? "blocked" : i.is_approved ? "approved" : "pending"} />
                    </td>
                    <td className="py-3 text-gray-500">{new Date(i.created_at).toLocaleDateString()}</td>
                    <td className="py-3 flex gap-3">
                      {!i.is_approved && !i.is_blocked && (
                        <button onClick={() => approveIssuer(i.id)} className="text-xs text-brand-600 font-medium">
                          Approve
                        </button>
                      )}
                      {!i.is_blocked && (
                        <button onClick={() => blockIssuer(i.id)} className="text-xs text-red-500 font-medium">
                          Block
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "logs" && (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-100">
                  <th className="pb-2">Action</th>
                  <th className="pb-2">Resource</th>
                  <th className="pb-2">Actor</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-b border-gray-50 last:border-0">
                    <td className="py-3 font-mono text-xs">{l.action}</td>
                    <td className="py-3 text-gray-500">
                      {l.resource_type} {l.resource_id ? `(${l.resource_id.slice(0, 8)}...)` : ""}
                    </td>
                    <td className="py-3 font-mono text-xs text-gray-400">{l.actor_id?.slice(0, 8) || "system"}</td>
                    <td className="py-3 text-gray-500">{new Date(l.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "health" && (
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="card">
              <p className="text-xs text-gray-400 mb-1">Audit Log Chain Integrity</p>
              <div className="flex items-center gap-2 mt-2">
                <StatusBadge status={integrity?.intact ? "valid" : "invalid"} />
                {!integrity?.intact && integrity?.first_broken_record_id && (
                  <span className="text-xs text-red-500 font-mono">
                    First tampered record: {integrity.first_broken_record_id.slice(0, 8)}...
                  </span>
                )}
              </div>
            </div>
            <div className="card">
              <p className="text-xs text-gray-400 mb-1">Total Users</p>
              <p className="text-2xl font-semibold">{users.length}</p>
            </div>
            <div className="card">
              <p className="text-xs text-gray-400 mb-1">Total Issuers</p>
              <p className="text-2xl font-semibold">{issuers.length}</p>
            </div>
            <div className="card">
              <p className="text-xs text-gray-400 mb-1">Audit Events Logged</p>
              <p className="text-2xl font-semibold">{logs.length}</p>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default function AdminDashboardPage() {
  return (
    <ProtectedRoute allowedRoles={["admin"]}>
      <AdminDashboardContent />
    </ProtectedRoute>
  );
}
