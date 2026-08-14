import Navbar from "@/components/Navbar";
import { UserPlus, FileCheck2, KeyRound, ShieldCheck } from "lucide-react";

const steps = [
  {
    icon: UserPlus,
    title: "1. Create your identity wallet",
    body: "Register and DecentraID generates a Decentralized Identifier (DID) and keypair for you. Your private key never leaves your control.",
  },
  {
    icon: FileCheck2,
    title: "2. Get a credential issued",
    body: "A trusted issuer (a university, employer, or KYC provider) verifies your information — assisted by our AI document and face-matching pipeline — and issues a cryptographically signed credential to your wallet.",
  },
  {
    icon: KeyRound,
    title: "3. Generate a zero-knowledge proof",
    body: "When a verifier needs to confirm a claim (e.g. 'is this person 18+?'), your wallet generates a zero-knowledge proof answering only that question — nothing else about your credential is revealed.",
  },
  {
    icon: ShieldCheck,
    title: "4. Verifier checks the proof, not your data",
    body: "The verifier checks the proof's validity and the credential's on-chain revocation status. They receive a boolean result and never see your date of birth, ID number, or documents.",
  },
];

export default function HowItWorksPage() {
  return (
    <main>
      <Navbar />
      <div className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">How It Works</h1>
        <p className="text-gray-500 mb-12">
          A four-step flow that keeps your raw personal data out of every verifier's hands.
        </p>

        <div className="space-y-8">
          {steps.map((step) => (
            <div key={step.title} className="flex gap-4">
              <div className="w-11 h-11 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                <step.icon className="w-5 h-5 text-brand-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 mb-1">{step.title}</h3>
                <p className="text-sm text-gray-500">{step.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
