"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import ProtectedRoute from "@/components/ProtectedRoute";
import StatusBadge from "@/components/StatusBadge";
import { apiClient, extractErrorMessage } from "@/lib/api";
import { SendHorizontal, ScanLine, History } from "lucide-react";

interface VerificationHistoryItem {
  id: string;
  subject_id: string | null;
  claim_scope: string;
  result: string;
  created_at: string;
}

const SCOPE_OPTIONS = ["age_gte_18", "age_gte_21", "is_student_eq_true", "is_employee_eq_true", "kyc_valid_eq_true"];

function VerifierDashboardContent() {
  const [tab, setTab] = useState<"request" | "verify" | "history">("request");
  const [history, setHistory] = useState<VerificationHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [subjectEmail, setSubjectEmail] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [purpose, setPurpose] = useState("");
  const [creatingRequest, setCreatingRequest] = useState(false);
  const [lastConsentId, setLastConsentId] = useState("");

  const [consentId, setConsentId] = useState("");
  const [zkProofId, setZkProofId] = useState("");
  const [verifyResult, setVerifyResult] = useState<any>(null);
  const [verifying, setVerifying] = useState(false);

  async function loadHistory() {
    try {
      const { data } = await apiClient.get("/verifier/history");
      setHistory(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  function toggleScope(scope: string) {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  }

  async function handleCreateRequest(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setCreatingRequest(true);
    try {
      const { data } = await apiClient.post("/verifier/proof-request", {
        subject_email: subjectEmail,
        requested_scopes: scopes,
        purpose,
      });
      setSuccess(`Proof request created. Consent ID: ${data.consent_id}`);
      setLastConsentId(data.consent_id);
      setConsentId(data.consent_id);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setCreatingRequest(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setVerifyResult(null);
    setVerifying(true);
    try {
      const { data } = await apiClient.post("/verifier/verify-proof", {
        consent_id: consentId,
        zk_proof_id: zkProofId,
      });
      setVerifyResult(data);
      loadHistory();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setVerifying(false);
    }
  }

  const tabs = [
    { id: "request", label: "Proof Request Builder", icon: SendHorizontal },
    { id: "verify", label: "Verification Terminal", icon: ScanLine },
    { id: "history", label: "Audit History", icon: History },
  ] as const;

  return (
    <main>
      <Navbar />
      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-semibold text-gray-900 mb-1">Verifier Terminal</h1>
        <p className="text-gray-500 mb-8">Request and verify zero-knowledge proofs from users.</p>

        {error && <div className="bg-red-50 text-red-700 text-sm rounded-lg px-3 py-2 mb-6">{error}</div>}
        {success && <div className="bg-green-50 text-green-700 text-sm rounded-lg px-3 py-2 mb-6">{success}</div>}

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

        {tab === "request" && (
          <form onSubmit={handleCreateRequest} className="card max-w-xl space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject email</label>
              <input
                type="email"
                required
                className="input-field"
                value={subjectEmail}
                onChange={(e) => setSubjectEmail(e.target.value)}
                placeholder="user@example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Requested scopes</label>
              <div className="space-y-2">
                {SCOPE_OPTIONS.map((scope) => (
                  <label key={scope} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={scopes.includes(scope)} onChange={() => toggleScope(scope)} />
                    {scope}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Purpose</label>
              <input
                required
                className="input-field"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="e.g. Age verification for venue entry"
              />
            </div>
            <button type="submit" disabled={creatingRequest || scopes.length === 0} className="btn-primary w-full">
              {creatingRequest ? "Sending..." : "Send Proof Request"}
            </button>
          </form>
        )}

        {tab === "verify" && (
          <form onSubmit={handleVerify} className="card max-w-xl space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Consent ID</label>
              <input required className="input-field font-mono text-sm" value={consentId} onChange={(e) => setConsentId(e.target.value)} />
              {lastConsentId && (
                <button
                  type="button"
                  onClick={() => setConsentId(lastConsentId)}
                  className="text-xs text-brand-600 mt-1"
                >
                  Use last created: {lastConsentId.slice(0, 8)}...
                </button>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ZK Proof ID</label>
              <input required className="input-field font-mono text-sm" value={zkProofId} onChange={(e) => setZkProofId(e.target.value)} />
              <p className="text-xs text-gray-400 mt-1">The subject provides this after generating a proof in their wallet.</p>
            </div>
            <button type="submit" disabled={verifying} className="btn-primary w-full">
              {verifying ? "Verifying..." : "Verify Proof"}
            </button>

            {verifyResult && (
              <div className="bg-gray-50 border border-gray-100 rounded-lg p-4 flex items-center justify-between">
                <span className="text-sm text-gray-600">Result</span>
                <StatusBadge status={verifyResult.result} />
              </div>
            )}
          </form>
        )}

        {tab === "history" && (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-100">
                  <th className="pb-2">Scope</th>
                  <th className="pb-2">Result</th>
                  <th className="pb-2">Subject</th>
                  <th className="pb-2">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-b border-gray-50 last:border-0">
                    <td className="py-3">{h.claim_scope}</td>
                    <td className="py-3">
                      <StatusBadge status={h.result} />
                    </td>
                    <td className="py-3 font-mono text-xs text-gray-400">{h.subject_id?.slice(0, 8) || "—"}</td>
                    <td className="py-3 text-gray-500">{new Date(h.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {history.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-gray-400">
                      No verification history yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

export default function VerifierDashboardPage() {
  return (
    <ProtectedRoute allowedRoles={["verifier"]}>
      <VerifierDashboardContent />
    </ProtectedRoute>
  );
}
