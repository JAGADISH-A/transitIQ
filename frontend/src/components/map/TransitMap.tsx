import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { TripStop } from '../../App';

interface TransitMapProps {
  sourcePosition?: [number, number];
  destinationPosition?: [number, number];
  transferPosition?: [number, number];
  sourceName?: string;
  destinationName?: string;
  selectedRoute?: any;
  selectedTransferRoute?: any;
  routeShape?: [number, number][] | null;
  transferShapes?: {leg1: [number, number][], leg2: [number, number][]} | null;
  transferStops?: {leg1: TripStop[], leg2: TripStop[]} | null;
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

const createCustomIcon = (color: string, radius: number = 14) => {
  return L.divIcon({
    className: 'custom-marker',
    html: `
      <div style="
        background-color: ${color};
        width: ${radius}px;
        height: ${radius}px;
        border-radius: 50%;
        border: 2px solid #FFFFFF;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      "></div>
    `,
    iconSize: [radius, radius],
    iconAnchor: [radius / 2, radius / 2]
  });
};

export default function TransitMap({ 
  sourcePosition, 
  destinationPosition,
  transferPosition,
  sourceName = "Source",
  destinationName = "Destination",
  selectedTransferRoute,
  routeShape,
  transferShapes,
  viewMode = 'journey',
  tripStops = [],
  transferStops = null
}: TransitMapProps) {
  // If neither is provided, center somewhere default (e.g., Chennai)
  const defaultCenter: [number, number] = [13.0827, 80.2707];
  
  const activePoints: [number, number][] = [];
  if (sourcePosition) activePoints.push(sourcePosition);
  if (destinationPosition) activePoints.push(destinationPosition);
  if (transferPosition) activePoints.push(transferPosition);

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

  const transferSegments = useMemo(() => {
    if (!transferShapes) return { leg1: null, leg2: null };

    const sliceShape = (shape: [number, number][], posA: [number, number], posB: [number, number]) => {
      if (!shape || shape.length === 0) return { full: null, journey: null };
      if (!posA || !posB) return { full: shape, journey: shape };
      
      let minA = Infinity, idxA = 0;
      let minB = Infinity, idxB = 0;
      
      shape.forEach((pt, idx) => {
        const dA = Math.pow(pt[0] - posA[0], 2) + Math.pow(pt[1] - posA[1], 2);
        const dB = Math.pow(pt[0] - posB[0], 2) + Math.pow(pt[1] - posB[1], 2);
        if (dA < minA) { minA = dA; idxA = idx; }
        if (dB < minB) { minB = dB; idxB = idx; }
      });
      
      const start = Math.min(idxA, idxB);
      const end = Math.max(idxA, idxB);
      
      return {
        full: shape,
        journey: shape.slice(start, end + 1)
      };
    };

    const leg1 = transferShapes.leg1 && sourcePosition && transferPosition 
      ? sliceShape(transferShapes.leg1, sourcePosition, transferPosition) 
      : { full: transferShapes.leg1, journey: transferShapes.leg1 };
      
    const leg2 = transferShapes.leg2 && transferPosition && destinationPosition
      ? sliceShape(transferShapes.leg2, transferPosition, destinationPosition)
      : { full: transferShapes.leg2, journey: transferShapes.leg2 };

    return { leg1, leg2 };
  }, [transferShapes, sourcePosition, transferPosition, destinationPosition]);

  const renderStops = (stops: TripStop[] | undefined, startName: string, endName: string, segmentColor: string = '#F97316') => {
    if (!stops || stops.length === 0) return null;
    const safeStart = (startName || '').toLowerCase().trim();
    const safeEnd = (endName || '').toLowerCase().trim();
    
    let startSeq = -1;
    let endSeq = -1;
    for (const s of stops) {
      const sn = (s.stop_name || '').toLowerCase().trim();
      const si = (s.stop_id || '').toLowerCase().trim();
      if (sn === safeStart || si === safeStart) startSeq = s.stop_sequence;
      if (sn === safeEnd || si === safeEnd) endSeq = s.stop_sequence;
    }

    return stops.map((stop, idx) => {
      if (!stop.stop_lat || !stop.stop_lon) return null;
      
      const safeName = (stop.stop_name || '').toLowerCase().trim();
      const safeId = (stop.stop_id || '').toLowerCase().trim();
      
      const isStart = safeName === safeStart || safeId === safeStart;
      const isEnd = safeName === safeEnd || safeId === safeEnd;
      
      if (isStart || isEnd) return null;

      let isWithinSegment = false;
      if (startSeq !== -1 && endSeq !== -1) {
        const minSeq = Math.min(startSeq, endSeq);
        const maxSeq = Math.max(startSeq, endSeq);
        isWithinSegment = stop.stop_sequence > minSeq && stop.stop_sequence < maxSeq;
      }

      if (viewMode !== 'full' && !isWithinSegment) return null;

      const color = isWithinSegment ? segmentColor : '#888888';
      const radius = isWithinSegment ? 4 : 3;

      return (
        <CircleMarker
          key={`${stop.stop_id}-${idx}`}
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
    });
  };

  const bounds = useMemo(() => {
    let allPoints: [number, number][] = [...activePoints];
    if (viewMode === 'full' && routeShape && routeShape.length > 0) {
      allPoints = allPoints.concat(routeShape);
    }
    if (transferShapes) {
      if (transferShapes.leg1.length > 0) allPoints = allPoints.concat(transferShapes.leg1);
      if (transferShapes.leg2.length > 0) allPoints = allPoints.concat(transferShapes.leg2);
    }
    return allPoints.length > 0 ? L.latLngBounds(allPoints) : null;
  }, [sourcePosition, destinationPosition, transferPosition, viewMode, routeShape, transferShapes]);

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
        
        {routeSegments.full && viewMode === 'full' && (
          <Polyline positions={routeSegments.full} color="#9CA3AF" weight={3} opacity={0.4} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}
        
        {routeSegments.journey && (
          <Polyline positions={routeSegments.journey} color="#F97316" weight={4} opacity={0.9} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}

        {transferSegments.leg1?.full && viewMode === 'full' && (
          <Polyline positions={transferSegments.leg1.full} color="#9CA3AF" weight={3} opacity={0.4} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}
        {transferSegments.leg1?.journey && (
          <Polyline positions={transferSegments.leg1.journey} color="#F97316" weight={4} opacity={0.9} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}

        {transferSegments.leg2?.full && viewMode === 'full' && (
          <Polyline positions={transferSegments.leg2.full} color="#9CA3AF" weight={3} opacity={0.4} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}
        {transferSegments.leg2?.journey && (
          <Polyline positions={transferSegments.leg2.journey} color="#10B981" weight={4} opacity={0.9} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}

        {/* Intermediate Stop Markers */}
        {tripStops && tripStops.length > 0 && renderStops(tripStops, sourceName || '', destinationName || '')}
        
        {transferStops?.leg1 && transferStops.leg1.length > 0 && renderStops(transferStops.leg1, sourceName || '', selectedTransferRoute?.transfer_stop || '', '#F97316')}
        
        {transferStops?.leg2 && transferStops.leg2.length > 0 && renderStops(transferStops.leg2, selectedTransferRoute?.transfer_stop || '', destinationName || '', '#10B981')}

        {sourcePosition && (
          <Marker position={sourcePosition} icon={createCustomIcon('#097752ff', 16)}>
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

        {transferPosition && selectedTransferRoute && (
          <Marker position={transferPosition} icon={createCustomIcon('#F59E0B', 14)}>
            <Popup className="transit-popup">
              <div className="font-sans">
                <div className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">
                  Transfer Station
                </div>
                <div className="font-semibold text-gray-900">
                  {selectedTransferRoute.transfer_stop}
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
          <div className="w-3 h-3 rounded-full bg-[#10B981]" />
          <span>Start</span>
        </div>
        {transferPosition && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#F59E0B]" />
            <span>Transfer</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#EF4444]" />
          <span>Destination</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#F97316]" />
          <span>{transferPosition ? "First Segment" : "Your Segment"}</span>
        </div>
        {transferPosition && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#10B981]" />
            <span>Second Segment</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#9CA3AF] opacity-60" />
          <span>Complete Route</span>
        </div>
      </div>
    </div>
  );
}
