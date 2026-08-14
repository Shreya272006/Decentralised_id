import Link from "next/link";
import Navbar from "@/components/Navbar";
import { ShieldCheck, Fingerprint, EyeOff, Link as LinkIcon, ScanFace, Blocks } from "lucide-react";

const features = [
  {
    icon: EyeOff,
    title: "Zero-Knowledge Proofs",
    description: "Prove you're over 18, a verified student, or KYC-valid — without revealing your date of birth, ID number, or any other raw data.",
  },
  {
    icon: Fingerprint,
    title: "Decentralized Identity",
    description: "You hold your own DID and credentials in a personal wallet. No central database of your documents to breach.",
  },
  {
    icon: ScanFace,
    title: "AI Fraud Detection",
    description: "Document tamper analysis, face-match verification, and liveness detection stop spoofed or forged identities before they're issued a credential.",
  },
  {
    icon: Blocks,
    title: "On-Chain Integrity",
    description: "Every credential and revocation is anchored on-chain as a cryptographic hash — publicly verifiable, never containing personal data.",
  },
];

export default function LandingPage() {
  return (
    <main>
      <Navbar />

      <section className="max-w-5xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 text-brand-700 bg-brand-50 px-3 py-1 rounded-full text-xs font-medium mb-6">
          <ShieldCheck className="w-3.5 h-3.5" />
          Privacy-first identity verification
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-gray-900 mb-6">
          Prove who you are.<br />Without giving it away.
        </h1>
        <p className="text-lg text-gray-500 max-w-2xl mx-auto mb-10">
          DecentraID lets you prove sensitive claims — your age, student status, employment,
          or KYC validity — using zero-knowledge proofs. Verifiers learn only the answer, never
          your underlying personal data.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link href="/register" className="btn-primary px-6 py-3 text-base">
            Create your wallet
          </Link>
          <Link href="/how-it-works" className="btn-secondary px-6 py-3 text-base">
            See how it works
          </Link>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((f) => (
            <div key={f.title} className="card">
              <f.icon className="w-8 h-8 text-brand-600 mb-4" />
              <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-500">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-white border-t border-gray-100">
        <div className="max-w-4xl mx-auto px-6 py-16 text-center">
          <LinkIcon className="w-8 h-8 text-brand-600 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-gray-900 mb-3">Built for issuers, verifiers, and everyone in between</h2>
          <p className="text-gray-500 mb-8">
            Universities, employers, and KYC providers issue tamper-evident credentials.
            Bars, apps, and platforms verify claims instantly — with your explicit, granular consent every time.
          </p>
          <Link href="/register" className="btn-primary px-6 py-3 text-base inline-block">
            Get started for free
          </Link>
        </div>
      </section>

      <footer className="text-center text-xs text-gray-400 py-8">
        DecentraID — hackathon reference implementation. Not for production use without a full security audit.
      </footer>
    </main>
  );
}
