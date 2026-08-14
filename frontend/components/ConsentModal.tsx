"use client";

import { X, ShieldAlert } from "lucide-react";

interface ConsentModalProps {
  open: boolean;
  requesterName: string;
  purpose: string;
  requestedScopes: string[];
  onApprove: (approvedScopes: string[]) => void;
  onDeny: () => void;
  onClose: () => void;
}

const scopeLabels: Record<string, string> = {
  age_gte_18: "Confirm you are 18 or older",
  age_gte_21: "Confirm you are 21 or older",
  is_student_eq_true: "Confirm active student status",
  is_employee_eq_true: "Confirm active employment status",
  kyc_valid_eq_true: "Confirm valid KYC status",
};

export default function ConsentModal({
  open,
  requesterName,
  purpose,
  requestedScopes,
  onApprove,
  onDeny,
  onClose,
}: ConsentModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-xl2 shadow-xl max-w-md w-full p-6 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600">
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 text-brand-700 mb-2">
          <ShieldAlert className="w-5 h-5" />
          <h2 className="text-lg font-semibold">Consent Request</h2>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          <span className="font-medium">{requesterName}</span> is requesting to verify the following, for:{" "}
          <span className="italic">&ldquo;{purpose}&rdquo;</span>
        </p>

        <div className="bg-gray-50 border border-gray-100 rounded-lg p-4 mb-6 space-y-2">
          {requestedScopes.map((scope) => (
            <div key={scope} className="flex items-start gap-2 text-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 mt-1.5 flex-shrink-0" />
              <span>{scopeLabels[scope] || scope}</span>
            </div>
          ))}
        </div>

        <p className="text-xs text-gray-400 mb-6">
          Only the exact boolean result of each item above will be shared. No underlying personal data
          (e.g. your date of birth or ID number) is ever disclosed.
        </p>

        <div className="flex gap-3">
          <button onClick={onDeny} className="btn-secondary flex-1">
            Deny
          </button>
          <button onClick={() => onApprove(requestedScopes)} className="btn-primary flex-1">
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
