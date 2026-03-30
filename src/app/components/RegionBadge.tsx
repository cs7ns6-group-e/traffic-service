import { cn } from "../components/ui/utils";

interface RegionBadgeProps {
  region: "EU" | "US" | "APAC";
  className?: string;
}

export function RegionBadge({ region, className }: RegionBadgeProps) {
  const variants = {
    EU: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    US: "bg-purple-500/10 text-purple-600 border-purple-500/20",
    APAC: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border",
        variants[region],
        className
      )}
    >
      {region}
    </span>
  );
}
