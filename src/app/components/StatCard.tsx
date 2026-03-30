import { cn } from "../components/ui/utils";
import { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  trend?: {
    value: number;
    direction: "up" | "down";
  };
  className?: string;
}

export function StatCard({ label, value, icon: Icon, trend, className }: StatCardProps) {
  return (
    <div className={cn("bg-white rounded-lg border border-gray-200 p-4", className)}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-600">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {trend && (
            <div className="flex items-center mt-2 text-xs">
              {trend.direction === "up" ? (
                <TrendingUp className="w-3 h-3 text-green-600 mr-1" />
              ) : (
                <TrendingDown className="w-3 h-3 text-red-600 mr-1" />
              )}
              <span
                className={cn(
                  "font-medium",
                  trend.direction === "up" ? "text-green-600" : "text-red-600"
                )}
              >
                {trend.value}%
              </span>
            </div>
          )}
        </div>
        {Icon && (
          <div className="ml-4">
            <Icon className="w-8 h-8 text-blue-600" />
          </div>
        )}
      </div>
    </div>
  );
}
