import { cn } from "./ui/utils";

export interface TimeSlot {
  slot: string;
  available: boolean;
}

interface SlotGridProps {
  slots: TimeSlot[];
  selectedSlot: string | null;
  onSelect: (slot: string) => void;
  forceAllAvailable?: boolean;
  loading?: boolean;
}

export function SlotGrid({ slots, selectedSlot, onSelect, forceAllAvailable = false, loading = false }: SlotGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-4 gap-2 animate-pulse">
        {Array.from({ length: 32 }).map((_, i) => (
          <div key={i} className="h-10 bg-gray-200 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-4 gap-2">
      {slots.map(({ slot, available }) => {
        const isAvailable = forceAllAvailable || available;
        const isSelected = selectedSlot === slot;
        return (
          <button
            key={slot}
            type="button"
            disabled={!isAvailable}
            onClick={() => isAvailable && onSelect(slot)}
            className={cn(
              "h-10 rounded-lg text-sm font-medium transition-all border-2",
              isSelected
                ? "border-[#2563EB] bg-blue-50 text-[#2563EB]"
                : isAvailable
                ? "border-green-200 bg-green-50 text-green-700 hover:border-green-400 hover:bg-green-100"
                : "border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed"
            )}
          >
            {slot}
          </button>
        );
      })}
    </div>
  );
}
