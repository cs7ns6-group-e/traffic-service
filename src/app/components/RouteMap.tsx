import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix Leaflet default icons (known Vite/webpack issue)
delete (L.Icon.Default.prototype as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface RouteMapProps {
  /** GeoJSON-style [lon, lat] coordinate pairs */
  coordinates: [number, number][];
  height?: number;
  className?: string;
}

export function RouteMap({ coordinates, height = 200, className = "" }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  // mapReady triggers the coordinate-render effect once the map is initialised
  const [mapReady, setMapReady] = useState(false);

  // ── Initialise map (once) ──────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Guard: if a prior Leaflet instance left state on this node, remove it
    if ((el as Element & { _leaflet_id?: unknown })._leaflet_id !== undefined) {
      try { L.map(el).remove(); } catch { /* ignore */ }
    }

    const map = L.map(el, { zoomControl: true }).setView([53.35, -6.26], 7);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);

    const layer = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;
    setMapReady(true);

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      setMapReady(false);
    };
  }, []); // run once on mount

  // ── Render route whenever coordinates change (or map becomes ready) ────
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!mapReady || !map || !layer) return;

    layer.clearLayers();

    if (!coordinates?.length) return;

    // API returns [lon, lat] (GeoJSON); Leaflet needs [lat, lon]
    const lls: [number, number][] = coordinates.map(([lon, lat]) => [lat, lon]);

    // Route polyline
    L.polyline(lls, { color: "#2563EB", weight: 4, opacity: 0.85 }).addTo(layer);

    // Origin → green dot
    const gIcon = L.divIcon({
      className: "",
      html: `<div style="width:14px;height:14px;background:#16A34A;border:3px solid #fff;border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,.45)"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });
    // Destination → red dot
    const rIcon = L.divIcon({
      className: "",
      html: `<div style="width:14px;height:14px;background:#DC2626;border:3px solid #fff;border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,.45)"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });

    L.marker(lls[0], { icon: gIcon }).addTo(layer);
    L.marker(lls[lls.length - 1], { icon: rIcon }).addTo(layer);

    // Fit all points with padding
    map.fitBounds(L.latLngBounds(lls), { padding: [24, 24] });
    // Invalidate size in case container was hidden during mount
    setTimeout(() => { map.invalidateSize(); }, 80);
  }, [mapReady, coordinates]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ height: `${height}px`, borderRadius: "8px", overflow: "hidden", background: "#e5e7eb" }}
    />
  );
}
