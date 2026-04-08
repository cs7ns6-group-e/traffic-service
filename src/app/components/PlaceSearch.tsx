import { useState, useEffect, useRef, useCallback } from "react";
import { MapPin, X, Loader2 } from "lucide-react";
import { cn } from "./ui/utils";

export interface Place {
  name: string;
  lat: number;
  lon: number;
}

interface PlaceSearchProps {
  value: Place | null;
  onChange: (place: Place | null) => void;
  placeholder?: string;
  pinColor?: "green" | "red";
  className?: string;
}

export function PlaceSearch({ value, onChange, placeholder = "Search location...", pinColor = "green", className }: PlaceSearchProps) {
  const [query, setQuery] = useState(value?.name ?? "");
  const [results, setResults] = useState<Place[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Sync when value changes externally (e.g. famous route click)
  useEffect(() => {
    setQuery(value?.name ?? "");
  }, [value]);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    setLoading(true);
    try {
      const res = await fetch(`/search?q=${encodeURIComponent(q)}&limit=5`);
      if (!res.ok) { setResults([]); return; }
      const data: Place[] = await res.json();
      setResults(data);
      setOpen(data.length > 0);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    // Clear selection when typing
    if (value) onChange(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(q), 400);
  }

  function handleSelect(place: Place) {
    onChange(place);
    setQuery(place.name);
    setOpen(false);
    setResults([]);
  }

  function handleClear() {
    onChange(null);
    setQuery("");
    setResults([]);
    setOpen(false);
  }

  const pinClass = pinColor === "green" ? "text-green-600" : "text-red-600";

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <div className="relative">
        <MapPin className={cn("absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5", pinClass)} />
        <input
          type="text"
          value={query}
          onChange={handleInput}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder={placeholder}
          className="w-full pl-11 pr-10 h-12 rounded-md border border-input bg-background text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          autoComplete="off"
        />
        {loading && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 animate-spin" />
        )}
        {!loading && query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <ul className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          {results.map((place, i) => (
            <li key={i}>
              <button
                type="button"
                onClick={() => handleSelect(place)}
                className="w-full text-left px-4 py-3 hover:bg-blue-50 flex items-center gap-3 transition-colors"
              >
                <MapPin className={cn("w-4 h-4 flex-shrink-0", pinClass)} />
                <span className="text-sm text-gray-900 truncate">{place.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
