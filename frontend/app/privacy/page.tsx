import Navbar from "@/components/Navbar";

const principles = [
  {
    title: "Data minimization by design",
    body: "Verifiers only ever receive the boolean result of a specific claim predicate (e.g. 'age >= 18: true'). Raw values like your exact date of birth or ID number are never transmitted to a verifier.",
  },
  {
    title: "Encryption at rest",
    body: "Every sensitive field — document images, extracted claim values, MFA secrets — is encrypted with AES-256-GCM before it touches the database or disk.",
  },
  {
    title: "You control consent",
    body: "Every verification request requires your explicit, scoped approval. You can see exactly what's being asked, approve only part of it, or deny it outright — and revoke previously granted consent at any time.",
  },
  {
    title: "Tamper-evident audit trail",
    body: "Every security-relevant action is recorded in a hash-chained audit log. Any retroactive tampering with the log is cryptographically detectable.",
  },
  {
    title: "On-chain minimalism",
    body: "Smart contracts store only cryptographic hashes and boolean states — never names, dates of birth, document scans, or any other personal data.",
  },
];

export default function PrivacyPage() {
  return (
    <main>
      <Navbar />
      <div className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Privacy Overview</h1>
        <p className="text-gray-500 mb-12">
          Our core design commitment: verifiers learn only what you choose to prove, and never anything more.
        </p>

        <div className="space-y-8">
          {principles.map((p) => (
            <div key={p.title} className="border-b border-gray-100 pb-6 last:border-0">
              <h3 className="font-semibold text-gray-900 mb-2">{p.title}</h3>
              <p className="text-sm text-gray-500">{p.body}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
