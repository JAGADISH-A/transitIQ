import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { TripStop } from '../../App';

interface TransitMapProps {
  sourcePosition?: [number, number];
  destinationPosition?: [number, number];
  sourceName?: string;
  destinationName?: string;
  routeShape?: [number, number][] | null;
  viewMode?: 'journey' | 'full';
  tripStops?: TripStop[];
}

const BoundsUpdater = ({ bounds }: { bounds: L.LatLngBoundsExpression | null }) => {
  const map = useMap();
  useEffect(() => {
    if (bounds) {
      const targetBounds = L.latLngBounds(bounds as any);
      const currentBounds = map.getBounds();
      
      if (currentBounds.contains(targetBounds)) {
        map.flyTo(targetBounds.getCenter(), map.getZoom(), { duration: 1.5 });
      } else {
        map.flyToBounds(bounds, { padding: [60, 60], maxZoom: 12, duration: 1.5 });
      }
    }
  }, [map, bounds]);
  return null;
};

const createCustomIcon = (color: string, radius: number = 16) => {
  return L.divIcon({
    className: 'custom-marker',
    html: `
      <div style="
        background-color: ${color};
        width: ${radius}px;
        height: ${radius}px;
        border-radius: 50%;
        border: 2px solid #1A1A1A;
        box-shadow: 0 0 10px ${color};
      "></div>
    `,
    iconSize: [radius, radius],
    iconAnchor: [radius / 2, radius / 2]
  });
};

export default function TransitMap({ 
  sourcePosition, 
  destinationPosition,
  sourceName = "Source",
  destinationName = "Destination",
  routeShape,
  viewMode = 'journey',
  tripStops = []
}: TransitMapProps) {
  // If neither is provided, center somewhere default (e.g., Chennai)
  const defaultCenter: [number, number] = [13.0827, 80.2707];
  
  const activePoints: [number, number][] = [];
  if (sourcePosition) activePoints.push(sourcePosition);
  if (destinationPosition) activePoints.push(destinationPosition);

  const routeSegments = useMemo(() => {
    if (!routeShape || routeShape.length === 0) return { full: null, journey: null };
    if (!sourcePosition || !destinationPosition) return { full: routeShape, journey: routeShape };

    let minSourceDist = Infinity;
    let sourceIdx = 0;
    let minDestDist = Infinity;
    let destIdx = 0;
    
    routeShape.forEach((pt, idx) => {
      const dSource = Math.pow(pt[0] - sourcePosition[0], 2) + Math.pow(pt[1] - sourcePosition[1], 2);
      const dDest = Math.pow(pt[0] - destinationPosition[0], 2) + Math.pow(pt[1] - destinationPosition[1], 2);
      if (dSource < minSourceDist) { minSourceDist = dSource; sourceIdx = idx; }
      if (dDest < minDestDist) { minDestDist = dDest; destIdx = idx; }
    });
    
    const start = Math.min(sourceIdx, destIdx);
    const end = Math.max(sourceIdx, destIdx);
    
    return {
      full: routeShape,
      journey: routeShape.slice(start, end + 1)
    };
  }, [routeShape, sourcePosition, destinationPosition]);

  const bounds = useMemo(() => {
    if (viewMode === 'full' && routeShape && routeShape.length > 0) {
      return L.latLngBounds(routeShape);
    }
    return activePoints.length > 0 ? L.latLngBounds(activePoints) : null;
  }, [sourcePosition, destinationPosition, viewMode, routeShape]);

  return (
    <div className="w-full h-full relative z-0">
      <MapContainer
        center={activePoints.length > 0 ? activePoints[0] : defaultCenter}
        zoom={12}
        style={{ width: '100%', height: '100%', background: '#0F0F0F' }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        
        {routeSegments.full && (
          <Polyline positions={routeSegments.full} color="#C0C0C0" weight={4} opacity={0.7} />
        )}
        
        {routeSegments.journey && (
          <Polyline positions={routeSegments.journey} color="#FF4500" weight={6} opacity={1} />
        )}

        {/* Intermediate Stop Markers */}
        {tripStops && tripStops.map((stop) => {
          if (!stop.stop_lat || !stop.stop_lon) return null;
          
          const safeSource = (sourceName || '').toLowerCase().trim();
          const safeDest = (destinationName || '').toLowerCase().trim();
          const safeName = (stop.stop_name || '').toLowerCase().trim();
          const safeId = (stop.stop_id || '').toLowerCase().trim();
          
          const isSource = safeName === safeSource || safeId === safeSource;
          const isDest = safeName === safeDest || safeId === safeDest;
          
          // Don't render circle markers for source and dest, we use actual Markers for them
          if (isSource || isDest) return null;

          // Determine if stop is within user segment
          // We can use routeSegments.journey and min distance to determine, but since we have stop_sequence,
          // it's easier to find the sequence of source and dest.
          let sourceSeq = -1;
          let destSeq = -1;
          for (const s of tripStops) {
            const sn = (s.stop_name || '').toLowerCase().trim();
            const si = (s.stop_id || '').toLowerCase().trim();
            if (sn === safeSource || si === safeSource) sourceSeq = s.stop_sequence;
            if (sn === safeDest || si === safeDest) destSeq = s.stop_sequence;
          }

          let isWithinSegment = false;
          if (sourceSeq !== -1 && destSeq !== -1) {
            const minSeq = Math.min(sourceSeq, destSeq);
            const maxSeq = Math.max(sourceSeq, destSeq);
            isWithinSegment = stop.stop_sequence > minSeq && stop.stop_sequence < maxSeq;
          }

          const color = isWithinSegment ? '#FF4500' : '#888888';
          const radius = isWithinSegment ? 4 : 3;
          
          return (
            <CircleMarker
              key={stop.stop_id}
              center={[stop.stop_lat, stop.stop_lon]}
              radius={radius}
              pathOptions={{
                fillColor: color,
                fillOpacity: 1,
                color: '#1A1A1A',
                weight: 1
              }}
            >
              <Popup className="transit-popup">
                <div className="font-sans text-sm font-semibold text-gray-900">
                  {stop.stop_name}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {sourcePosition && (
          <Marker position={sourcePosition} icon={createCustomIcon('#10B981', 16)}>
            <Popup className="transit-popup">
              <div className="font-sans">
                <div className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">
                  Source
                </div>
                <div className="font-semibold text-gray-900">
                  {sourceName}
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {destinationPosition && (
          <Marker position={destinationPosition} icon={createCustomIcon('#EF4444', 16)}>
            <Popup className="transit-popup">
              <div className="font-sans">
                <div className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">
                  Destination
                </div>
                <div className="font-semibold text-gray-900">
                  {destinationName}
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {bounds && <BoundsUpdater bounds={bounds} />}
      </MapContainer>

      {/* Floating Legend */}
      <div className="absolute top-4 right-4 z-[400] bg-[#111111]/90 backdrop-blur-md border border-white/10 p-3 rounded-xl shadow-2xl text-xs font-medium text-white/80 flex flex-col gap-2 pointer-events-none">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#10B981] shadow-[0_0_5px_#10B981]" />
          <span>Start</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#EF4444] shadow-[0_0_5px_#EF4444]" />
          <span>Destination</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#FF4500]" />
          <span>Your Segment</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#C0C0C0]" />
          <span>Complete Route</span>
        </div>
      </div>
    </div>
  );
}
