import { cn } from "../components/ui/utils";

interface RoadSegmentChipProps {
  roadName: string;
  className?: string;
}

export function RoadSegmentChip({ roadName, className }: RoadSegmentChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200",
        className
      )}
    >
      {roadName}
    </span>
  );
}
