import { cn } from "./ui/utils";

export interface TimeSlot {
  slot: string;
  available: boolean;
  reason?: string;       // "" | "booked" | "being_selected"
  held_by_you?: boolean;
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
      {slots.map((s) => {
        const { slot, available, reason = "", held_by_you = false } = s;
        const isSelected = selectedSlot === slot;
        const isBeingSelected = reason === "being_selected" && !held_by_you;
        const isTaken = reason === "booked";
        const isClickable = forceAllAvailable || held_by_you || (available && !isBeingSelected && !isTaken);

        let label = slot;
        if (held_by_you || isSelected) label = `${slot} ✓`;
        else if (isBeingSelected) label = `${slot} •`;
        else if (isTaken) label = `${slot} ✕`;

        let btnClass: string;
        if (held_by_you || isSelected) {
          btnClass = "border-[#2563EB] bg-[#2563EB] text-white hover:bg-[#1d4ed8]";
        } else if (isBeingSelected) {
          btnClass = "border-gray-300 bg-gray-100 text-gray-400 cursor-not-allowed";
        } else if (isTaken) {
          btnClass = "border-gray-400 bg-gray-300 text-gray-500 cursor-not-allowed";
        } else if (forceAllAvailable || available) {
          btnClass = "border-green-300 bg-green-50 text-green-700 hover:border-green-500 hover:bg-green-100";
        } else {
          btnClass = "border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed";
        }

        return (
          <button
            key={slot}
            type="button"
            disabled={!isClickable}
            onClick={() => isClickable && onSelect(slot)}
            title={isBeingSelected ? "Another user is selecting this slot" : undefined}
            className={cn(
              "h-10 rounded-lg text-xs font-medium transition-all border-2",
              btnClass
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
