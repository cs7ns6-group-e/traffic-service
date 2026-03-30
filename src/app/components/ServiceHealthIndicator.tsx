import { cn } from "../components/ui/utils";
import { Circle } from "lucide-react";

interface ServiceHealthIndicatorProps {
  serviceName: string;
  status: "ONLINE" | "OFFLINE";
  responseTime?: number;
  className?: string;
}

export function ServiceHealthIndicator({
  serviceName,
  status,
  responseTime,
  className,
}: ServiceHealthIndicatorProps) {
  return (
    <div className={cn("bg-white rounded-lg border border-gray-200 p-4", className)}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h3 className="text-sm font-medium text-gray-900">{serviceName}</h3>
          {responseTime && status === "ONLINE" && (
            <p className="text-xs text-gray-500 mt-1">{responseTime}ms</p>
          )}
        </div>
        <div className="flex items-center">
          <Circle
            className={cn(
              "w-3 h-3 mr-2",
              status === "ONLINE" ? "fill-green-500 text-green-500" : "fill-red-500 text-red-500"
            )}
          />
          <span
            className={cn(
              "text-xs font-semibold",
              status === "ONLINE" ? "text-green-600" : "text-red-600"
            )}
          >
            {status}
          </span>
        </div>
      </div>
    </div>
  );
}
