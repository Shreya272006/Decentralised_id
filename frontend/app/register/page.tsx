"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { useAuth, Role, extractErrorMessage } from "@/context/AuthContext";
import { ShieldCheck } from "lucide-react";

const roles: { value: Role; label: string; description: string }[] = [
  { value: "user", label: "Individual", description: "Hold credentials and generate proofs" },
  { value: "issuer", label: "Issuer", description: "Issue credentials (requires admin approval)" },
  { value: "verifier", label: "Verifier", description: "Request and verify proofs from users" },
];

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("user");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, fullName, role);
      setSuccess(true);
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main>
      <Navbar />
      <div className="max-w-md mx-auto px-6 py-16">
        <div className="text-center mb-8">
          <ShieldCheck className="w-8 h-8 text-brand-600 mx-auto mb-3" />
          <h1 className="text-2xl font-semibold text-gray-900">Create your wallet</h1>
        </div>

        <div className="card">
          {error && <div className="bg-red-50 text-red-700 text-sm rounded-lg px-3 py-2 mb-4">{error}</div>}
          {success && (
            <div className="bg-green-50 text-green-700 text-sm rounded-lg px-3 py-2 mb-4">
              Account created! Redirecting to login...
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
              <input required className="input-field" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                required
                className="input-field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                required
                minLength={10}
                className="input-field"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="text-xs text-gray-400 mt-1">
                At least 10 characters, with uppercase, lowercase, a number, and a symbol.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Account type</label>
              <div className="space-y-2">
                {roles.map((r) => (
                  <label
                    key={r.value}
                    className={`flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer ${
                      role === r.value ? "border-brand-500 bg-brand-50" : "border-gray-200"
                    }`}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={r.value}
                      checked={role === r.value}
                      onChange={() => setRole(r.value)}
                    />
                    <div>
                      <div className="text-sm font-medium text-gray-800">{r.label}</div>
                      <div className="text-xs text-gray-500">{r.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "Creating account..." : "Create account"}
            </button>
          </form>

          <p className="text-sm text-gray-500 text-center mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-brand-600 font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
