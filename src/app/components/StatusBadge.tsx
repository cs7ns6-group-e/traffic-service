import { cn } from "../components/ui/utils";

interface StatusBadgeProps {
  status: "CONFIRMED" | "PENDING" | "CANCELLED" | "AUTHORITY_CANCELLED" | "CROSS_REGION";
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const variants = {
    CONFIRMED: "bg-green-500/10 text-green-600 border-green-500/20",
    PENDING: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    CANCELLED: "bg-red-500/10 text-red-600 border-red-500/20",
    AUTHORITY_CANCELLED: "bg-red-500/10 text-red-600 border-red-500/20",
    CROSS_REGION: "bg-blue-500/10 text-blue-600 border-blue-500/20",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
        variants[status],
        className
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
