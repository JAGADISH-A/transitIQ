import { useEffect, useMemo, Fragment } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { TripStop, NormalizedRoute, TransferJourney } from '../../types/transit';

interface TransitMapProps {
  sourcePosition?: [number, number];
  destinationPosition?: [number, number];
  transferPositions?: [number, number][];
  sourceName?: string;
  destinationName?: string;
  selectedRoute?: NormalizedRoute | null;
  selectedTransferRoute?: TransferJourney | null;
  routeShape?: [number, number][] | null;
  transferShapes?: [number, number][][] | null;
  transferStops?: TripStop[][] | null;
  viewMode?: 'journey' | 'full';
  tripStops?: TripStop[];
  focusedLocation?: [number, number] | null;
}

const BoundsUpdater = ({ bounds, selectedRouteId }: { bounds: L.LatLngBounds | null; selectedRouteId?: string | null }) => {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.isValid()) {
      console.log("[MAP_NAV_DEBUG] fitBounds called with padding [50, 50] for selectedRouteId:", selectedRouteId);
      map.fitBounds(bounds, {
        padding: [50, 50]
      });
    }
  }, [map, bounds, selectedRouteId]);
  return null;
};

const LocationFocuser = ({ location }: { location: [number, number] | null }) => {
  const map = useMap();
  useEffect(() => {
    if (location) {
      map.flyTo(location, 14, { duration: 1.2 });
    }
  }, [map, location]);
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
  transferPositions = [],
  sourceName = "Source",
  destinationName = "Destination",
  selectedRoute,
  selectedTransferRoute: propSelectedTransferRoute,
  routeShape,
  transferShapes,
  viewMode = 'journey',
  tripStops = [],
  transferStops = null,
  focusedLocation = null
}: TransitMapProps) {
  // If neither is provided, center somewhere default (e.g., Chennai)
  const defaultCenter: [number, number] = [13.0827, 80.2707];
  
  console.log("[MAP_DEBUG]", {
    routeShape,
    transferShapes,
    tripStops,
    transferStops
  });

  const extRoute = selectedRoute?.originalData as TransferJourney | undefined;
  const selectedTransferRoute = propSelectedTransferRoute || (selectedRoute?.isTransfer ? selectedRoute.originalData as TransferJourney : null);

  if (extRoute) {
    console.log("[LEG3_SHAPE_CHECK]", {
      hasThirdLeg: !!extRoute.third_leg,
      thirdLegShapeId: extRoute.third_leg?.shape_id,
      thirdLegTripId: extRoute.third_leg?.trip_id
    });
  }
  
  const activePoints: [number, number][] = [];
  if (sourcePosition) activePoints.push(sourcePosition);
  if (destinationPosition) activePoints.push(destinationPosition);
  if (transferPositions) {
    transferPositions.forEach(pos => activePoints.push(pos));
  }

  const fallbackRouteShape = useMemo(() => {
    if (routeShape && routeShape.length > 0) return routeShape;
    if (tripStops && tripStops.length > 0) {
      return tripStops.filter(s => s.stop_lat && s.stop_lon).map(s => [s.stop_lat, s.stop_lon] as [number, number]);
    }
    return null;
  }, [routeShape, tripStops]);

  const routeSegments = useMemo(() => {
    const shapeToUse = fallbackRouteShape;
    if (!shapeToUse || shapeToUse.length === 0) return { full: null, journey: null };
    if (!sourcePosition || !destinationPosition) return { full: shapeToUse, journey: shapeToUse };

    let minSourceDist = Infinity;
    let sourceIdx = 0;
    let minDestDist = Infinity;
    let destIdx = 0;
    
    shapeToUse.forEach((pt, idx) => {
      const dSource = Math.pow(pt[0] - sourcePosition[0], 2) + Math.pow(pt[1] - sourcePosition[1], 2);
      const dDest = Math.pow(pt[0] - destinationPosition[0], 2) + Math.pow(pt[1] - destinationPosition[1], 2);
      if (dSource < minSourceDist) { minSourceDist = dSource; sourceIdx = idx; }
      if (dDest < minDestDist) { minDestDist = dDest; destIdx = idx; }
    });
    
    const start = Math.min(sourceIdx, destIdx);
    const end = Math.max(sourceIdx, destIdx);
    
    return {
      full: shapeToUse,
      journey: shapeToUse.slice(start, end + 1)
    };
  }, [fallbackRouteShape, sourcePosition, destinationPosition]);

  const legs = useMemo(() => {
    if (!selectedRoute?.isTransfer || !extRoute) return [];
    return [
      extRoute.first_leg,
      extRoute.second_leg,
      extRoute.third_leg
    ].filter(Boolean);
  }, [selectedRoute, extRoute]);

  const transferSegments = useMemo(() => {
    if (legs.length === 0) return [];

    const getStopsCoordinates = (stops: TripStop[] | undefined | null) => {
      if (!stops) return null;
      const coords = stops
        .filter(s => s.stop_lat !== undefined && s.stop_lon !== undefined && s.stop_lat !== null && s.stop_lon !== null)
        .map(s => [s.stop_lat!, s.stop_lon!] as [number, number]);
      return coords.length > 0 ? coords : null;
    };

    return legs.map((_, index) => {
      const shape = transferShapes?.[index];
      const stops = transferStops?.[index];
      const legShape = (shape && shape.length > 0)
        ? shape
        : getStopsCoordinates(stops);

      return legShape ? { full: legShape, journey: legShape } : null;
    });
  }, [legs, transferShapes, transferStops]);

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
    let allPoints: [number, number][] = [];
    if (sourcePosition) allPoints.push(sourcePosition);
    if (destinationPosition) allPoints.push(destinationPosition);
    if (transferPositions) {
      allPoints = allPoints.concat(transferPositions);
    }

    // Always include the journey's actual curved path in the bounding box
    if (routeSegments.journey && routeSegments.journey.length > 0) {
      allPoints = allPoints.concat(routeSegments.journey);
    }
    transferSegments.forEach(seg => {
      if (seg?.journey && seg.journey.length > 0) {
        allPoints = allPoints.concat(seg.journey);
      }
    });

    // Include the full un-trimmed shapes only if viewMode requires it
    if (viewMode === 'full') {
      if (routeSegments.full && routeSegments.full.length > 0) {
        allPoints = allPoints.concat(routeSegments.full);
      }
      transferSegments.forEach(seg => {
        if (seg?.full && seg.full.length > 0) {
          allPoints = allPoints.concat(seg.full);
        }
      });
    }
    
    return allPoints.length > 0 ? L.latLngBounds(allPoints) : null;
  }, [sourcePosition, destinationPosition, transferPositions, viewMode, routeSegments, transferSegments]);

  const transferStopNames = selectedTransferRoute
    ? [selectedTransferRoute.transfer_stop, selectedTransferRoute.transfer_stop_2].filter(Boolean) as string[]
    : [];

  // Temporary logs for debugging Map route & viewport state
  const debugJourneyCoords = routeSegments.journey || [];
  const debugTransferCoords = transferSegments.flatMap(seg => seg?.journey || []);
  const totalRouteCoordsCount = debugJourneyCoords.length + debugTransferCoords.length;

  console.log("[MAP_DEBUG_STATE]", {
    selectedRouteId: selectedRoute?.id || null,
    routeCoordinateCount: totalRouteCoordsCount,
    startCoordinate: sourcePosition || null,
    destinationCoordinate: destinationPosition || null,
    computedBounds: bounds ? [
      [bounds.getSouthWest().lat, bounds.getSouthWest().lng],
      [bounds.getNorthEast().lat, bounds.getNorthEast().lng]
    ] : null,
    markerCount: (sourcePosition ? 1 : 0) + (destinationPosition ? 1 : 0) + transferPositions.length + tripStops.length
  });

  // Verify coordinates are valid numbers and in [lat, lng] format
  const allCoordinatesToVerify = [...debugJourneyCoords, ...debugTransferCoords];
  allCoordinatesToVerify.forEach((pt, i) => {
    if (!pt || pt.length < 2 || typeof pt[0] !== 'number' || typeof pt[1] !== 'number' || isNaN(pt[0]) || isNaN(pt[1])) {
      console.warn(`[MAP_WARNING] Invalid coordinate at index ${i}:`, pt);
    }
  });

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
        
        {routeSegments.full && viewMode === 'full' && routeSegments.full.length >= 2 && (
          <Polyline positions={routeSegments.full} color="#9CA3AF" weight={3} opacity={0.4} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}
        
        {routeSegments.journey && routeSegments.journey.length >= 2 && (
          <Polyline positions={routeSegments.journey} color="#F97316" weight={4} opacity={0.9} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
        )}

        {/* Render transfer route polylines */}
        {transferSegments.map((seg, idx) => {
          if (!seg) return null;
          const colors = ['#F97316', '#fb923c', '#fdba74', '#fed7aa'];
          const color = colors[idx % colors.length];
          const opacity = 0.9 - (idx * 0.1);

          return (
            <Fragment key={`dynamic-leg-polyline-${idx}`}>
              {seg.full && viewMode === 'full' && seg.full.length >= 2 && (
                <Polyline positions={seg.full} color="#9CA3AF" weight={3} opacity={0.4} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
              )}
              {seg.journey && seg.journey.length >= 2 && (
                <Polyline positions={seg.journey} color={color} weight={4} opacity={opacity} lineCap="round" lineJoin="round" className="animate-in fade-in duration-700" />
              )}
            </Fragment>
          );
        })}

        {/* Intermediate Stop Markers */}
        {tripStops && tripStops.length > 0 && renderStops(tripStops, selectedRoute?.sourceName || sourceName || '', selectedRoute?.destName || destinationName || '')}
        
        {legs.map((_, idx) => {
          const stops = transferStops?.[idx];
          if (!stops || stops.length === 0) return null;
          const colors = ['#F97316', '#fb923c', '#fdba74', '#fed7aa'];
          const color = colors[idx % colors.length];

          const startStop = idx === 0 
            ? (selectedRoute?.sourceName || sourceName || '')
            : (transferStopNames[idx - 1] || '');

          const endStop = idx === legs.length - 1
            ? (selectedRoute?.destName || destinationName || '')
            : (transferStopNames[idx] || '');

          return (
            <Fragment key={`dynamic-leg-stops-${idx}`}>
              {renderStops(stops, startStop, endStop, color)}
            </Fragment>
          );
        })}

        {sourcePosition && (
          <Marker position={sourcePosition} icon={createCustomIcon('#097752ff', 16)}>
            <Popup className="transit-popup">
              <div className="font-sans">
                <div className="text-xs font-medium text-zinc-500 mb-1">
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
                <div className="text-xs font-medium text-zinc-500 mb-1">
                  Destination
                </div>
                <div className="font-semibold text-gray-900">
                  {destinationName}
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Render dynamic transfer station markers */}
        {transferPositions && transferPositions.map((pos, idx) => {
          const stopName = transferStopNames[idx] || `Transfer Station ${idx + 1}`;
          return (
            <Marker key={`dynamic-transfer-${idx}`} position={pos} icon={createCustomIcon('#F59E0B', 18)}>
              <Popup className="transit-popup">
                <div className="font-sans">
                  <div className="text-xs font-medium text-zinc-500 mb-1">
                    Transfer Station {idx + 1}
                  </div>
                  <div className="font-semibold text-gray-900">
                    {stopName}
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {bounds && !focusedLocation && <BoundsUpdater bounds={bounds} selectedRouteId={selectedRoute?.id} />}
        {focusedLocation && <LocationFocuser location={focusedLocation} />}
      </MapContainer>

      {/* Floating Legend */}
      <div className="absolute top-4 right-4 z-[400] bg-[#111111]/90 backdrop-blur-md border border-white/10 p-3 rounded-xl shadow-2xl text-xs font-medium text-white/80 flex flex-col gap-2 pointer-events-none">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#10B981]" />
          <span>Start</span>
        </div>
        {transferPositions && transferPositions.length > 0 && (
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
          <span>{transferPositions && transferPositions.length > 0 ? "Active Segment" : "Your Segment"}</span>
        </div>
        {transferPositions && transferPositions.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#fb923c]" />
            <span>Future Segment</span>
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
