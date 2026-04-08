import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";

interface RouteMapProps {
  coordinates: [number, number][]; // GeoJSON [lon, lat] pairs
  className?: string;
}

// Defer Leaflet import to avoid SSR issues
let L: typeof import("leaflet") | null = null;

async function getLeaflet() {
  if (!L) {
    L = await import("leaflet");
    // Fix default icon
    delete (L.Icon.Default.prototype as Record<string, unknown>)._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
      shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    });
  }
  return L;
}

export function RouteMap({ coordinates, className = "" }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const layersRef = useRef<import("leaflet").LayerGroup | null>(null);

  // Initialize map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let mounted = true;
    getLeaflet().then((Leaflet) => {
      if (!mounted || !containerRef.current || mapRef.current) return;

      const map = Leaflet.map(containerRef.current, { zoomControl: true }).setView([53.35, -6.26], 7);
      Leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap",
        maxZoom: 18,
      }).addTo(map);

      const layers = Leaflet.layerGroup().addTo(map);
      mapRef.current = map;
      layersRef.current = layers;
    });

    return () => {
      mounted = false;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        layersRef.current = null;
      }
    };
  }, []);

  // Update route when coordinates change
  useEffect(() => {
    const map = mapRef.current;
    const layers = layersRef.current;
    if (!map || !layers || !coordinates?.length) return;

    let mounted = true;
    getLeaflet().then((Leaflet) => {
      if (!mounted || !map || !layers) return;

      layers.clearLayers();

      // Convert GeoJSON [lon, lat] → Leaflet [lat, lon]
      const latLngs = coordinates.map(([lon, lat]) => [lat, lon] as [number, number]);

      // Polyline
      Leaflet.polyline(latLngs, { color: "#2563EB", weight: 4, opacity: 0.8 }).addTo(layers);

      // Origin (green circle)
      const greenIcon = Leaflet.divIcon({
        className: "",
        html: '<div style="width:14px;height:14px;background:#16A34A;border:3px solid white;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,0.5)"></div>',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });

      // Destination (red circle)
      const redIcon = Leaflet.divIcon({
        className: "",
        html: '<div style="width:14px;height:14px;background:#DC2626;border:3px solid white;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,0.5)"></div>',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });

      Leaflet.marker(latLngs[0], { icon: greenIcon }).addTo(layers);
      Leaflet.marker(latLngs[latLngs.length - 1], { icon: redIcon }).addTo(layers);

      // Fit bounds
      const bounds = Leaflet.latLngBounds(latLngs);
      map.fitBounds(bounds, { padding: [30, 30] });

      // Invalidate size after layout
      setTimeout(() => map.invalidateSize(), 100);
    });

    return () => { mounted = false; };
  }, [coordinates]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ height: "220px", borderRadius: "8px", overflow: "hidden" }}
    />
  );
}
