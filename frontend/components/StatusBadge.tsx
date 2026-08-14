import clsx from "clsx";

const statusStyles: Record<string, string> = {
  active: "badge-green",
  approved: "badge-green",
  valid: "badge-green",
  confirmed: "badge-green",
  applied: "badge-green",

  pending: "badge-yellow",
  review: "badge-yellow",

  revoked: "badge-red",
  rejected: "badge-red",
  denied: "badge-red",
  blocked: "badge-red",
  invalid: "badge-red",
  expired: "badge-red",

  suspended: "badge-gray",
};

export default function StatusBadge({ status }: { status: string }) {
  const key = status?.toLowerCase?.() ?? "";
  const style = statusStyles[key] || "badge-gray";
  return <span className={clsx(style)}>{status}</span>;
}
