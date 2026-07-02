import { useEffect, useMemo, Fragment, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline, CircleMarker, Pane } from 'react-leaflet';
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
      map.fitBounds(bounds, {
        padding: [100, 100]
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

// --- Smooth Curve Algorithm (Distance-Adaptive) ---
function getSmoothSpline(points: [number, number][]): [number, number][] {
  if (points.length < 3) return points;
  
  const p = [points[0], ...points, points[points.length - 1]];
  const result: [number, number][] = [];

  for (let i = 1; i < p.length - 2; i++) {
    const p0 = p[i - 1];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[i + 2];

    // Adaptive segments based on distance
    const dist = Math.hypot(p1[0] - p2[0], p1[1] - p2[1]);
    const segments = Math.max(3, Math.min(20, Math.floor(dist * 1000)));

    for (let t = 0; t < segments; t++) {
      const t1 = t / segments;
      const t2 = t1 * t1;
      const t3 = t2 * t1;

      const q0 = -t3 + 2.0 * t2 - t1;
      const q1 = 3.0 * t3 - 5.0 * t2 + 2.0;
      const q2 = -3.0 * t3 + 4.0 * t2 + t1;
      const q3 = t3 - t2;

      const lat = 0.5 * (p0[0] * q0 + p1[0] * q1 + p2[0] * q2 + p3[0] * q3);
      const lng = 0.5 * (p0[1] * q0 + p1[1] * q1 + p2[1] * q2 + p3[1] * q3);

      result.push([lat, lng]);
    }
  }
  result.push(points[points.length - 1]);
  return result;
}

// --- Animated Route Rendering Component ---
const AnimatedRoute = ({ positions, innerColor, outerColor, isCompleteRoute = false }: { positions: [number, number][], innerColor: string, outerColor: string, isCompleteRoute?: boolean }) => {
  const outerRef = useRef<any>(null);
  const innerRef = useRef<any>(null);
  const tiesRef = useRef<any>(null);
  const smoothPositions = useMemo(() => getSmoothSpline(positions), [positions]);

  useEffect(() => {
    // Keep track of elements to clean up later
    const animatedEls: SVGElement[] = [];
    
    // Robust animation fallback
    const animateDraw = (ref: React.RefObject<any>) => {
      try {
        if (ref.current && ref.current.getElement) {
          const el = ref.current.getElement();
          if (el && el instanceof SVGPathElement) {
            const length = el.getTotalLength();
            if (length > 0) {
              // Ensure path is rendered before animating
              el.style.setProperty('--path-length', `${length}`);
              el.classList.add('route-path-animated');
              animatedEls.push(el);
            }
          }
        }
      } catch (e) {
        console.error("Route animation failed", e);
      }
    };
    
    // Slight delay to ensure DOM is ready
    const timer = setTimeout(() => {
      animateDraw(outerRef);
      animateDraw(innerRef);
      // We do not animate tiesRef because it has its own dashArray that conflicts with the animation
    }, 100);
    
    // After animation finishes, remove the class so zooming works correctly without path-length gaps
    const cleanupTimer = setTimeout(() => {
      animatedEls.forEach(el => el.classList.remove('route-path-animated'));
    }, 3000);
    
    return () => {
      clearTimeout(timer);
      clearTimeout(cleanupTimer);
    };
  }, [smoothPositions, isCompleteRoute]);

  return (
    <>
      {/* 1. Outer Shadow/Glow */}
      <Polyline 
        ref={outerRef}
        positions={smoothPositions} 
        color={outerColor} 
        weight={isCompleteRoute ? 4 : 8} 
        opacity={isCompleteRoute ? 0.2 : 0.4} 
        lineCap="round" 
        lineJoin="round" 
      />
      {/* 2. Inner Track Base */}
      <Polyline 
        ref={innerRef}
        positions={smoothPositions} 
        color={innerColor} 
        weight={isCompleteRoute ? 2 : 4} 
        opacity={isCompleteRoute ? 0.4 : 1} 
        lineCap="round" 
        lineJoin="round" 
      />
      {/* 3. Railway Ties (Dashed layer, only for active journey) */}
      {!isCompleteRoute && (
        <Polyline 
          ref={tiesRef}
          positions={smoothPositions} 
          color="#111111" 
          weight={2} 
          opacity={0.7} 
          dashArray="2, 8"
          lineCap="butt" 
          lineJoin="round" 
        />
      )}
      {!isCompleteRoute && <AnimatedTrainMarker path={smoothPositions} />}
    </>
  );
};

// --- Animated Train Marker Component ---
const AnimatedTrainMarker = ({ path }: { path: [number, number][] }) => {
  const markerRef = useRef<any>(null);
  
  useEffect(() => {
    if (!markerRef.current || path.length < 2) return;
    
    let animationFrameId: number;
    let startTime: number | null = null;
    const duration = Math.max(path.length * 15, 3000); 
    const totalPoints = path.length;

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = ((timestamp - startTime) % duration) / duration;
      
      const index = Math.floor(progress * (totalPoints - 1));
      const nextIndex = Math.min(index + 1, totalPoints - 1);
      
      const point1 = path[index];
      const point2 = path[nextIndex];
      
      const segmentProgress = (progress * (totalPoints - 1)) % 1;
      
      const lat = point1[0] + (point2[0] - point1[0]) * segmentProgress;
      const lng = point1[1] + (point2[1] - point1[1]) * segmentProgress;
      
      markerRef.current.setLatLng([lat, lng]);
      
      animationFrameId = requestAnimationFrame(animate);
    };
    
    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, [path]);

  const trainIcon = useMemo(() => L.divIcon({
    className: 'moving-train-icon',
    html: `<div style="
      width: 8px; 
      height: 8px; 
      background: #F59E0B; 
      border-radius: 50%; 
      box-shadow: 0 0 8px #FF8A00, 0 0 12px #FF8A00;
    "></div>`,
    iconSize: [8, 8],
    iconAnchor: [4, 4]
  }), []);

  return <Marker ref={markerRef} position={path[0]} icon={trainIcon} zIndexOffset={100} />;
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
  const defaultCenter: [number, number] = [13.0827, 80.2707];
  
  const extRoute = selectedRoute?.originalData as TransferJourney | undefined;
  const selectedTransferRoute = propSelectedTransferRoute || (selectedRoute?.isTransfer ? selectedRoute.originalData as TransferJourney : null);

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

      if (!legShape) return null;

      const start = 0;
      const end = legShape.length - 1;

      return legShape ? { full: legShape, journey: legShape.slice(start, end + 1) } : null;
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
      const radius = isWithinSegment ? 3 : 2;

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

    if (routeSegments.journey && routeSegments.journey.length > 0) {
      allPoints = allPoints.concat(routeSegments.journey);
    }
    transferSegments.forEach(seg => {
      if (seg?.journey && seg.journey.length > 0) {
        allPoints = allPoints.concat(seg.journey);
      }
    });

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

  return (
    <div className="w-full h-full relative z-0">
      <MapContainer
        center={activePoints.length > 0 ? activePoints[0] : defaultCenter}
        zoom={12}
        style={{ width: '100%', height: '100%', background: '#0F0F0F' }}
        zoomControl={false}
      >
        {/* Base Map without Labels */}
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
        />
        
        {/* Render Base Non-Transfer Journey Lines */}
        {routeSegments.full && viewMode === 'full' && routeSegments.full.length >= 2 && (
          <AnimatedRoute 
            positions={routeSegments.full} 
            innerColor="#9CA3AF" 
            outerColor="#4B5563" 
            isCompleteRoute={true} 
          />
        )}
        
        {routeSegments.journey && routeSegments.journey.length >= 2 && (
          <AnimatedRoute 
            positions={routeSegments.journey} 
            innerColor="#F59E0B" 
            outerColor="#B45309" 
          />
        )}

        {/* Render Transfer Lines */}
        {transferSegments.map((seg, idx) => {
          if (!seg) return null;
          const innerColors = ['#F59E0B', '#F97316', '#F59E0B', '#F97316'];
          const outerColors = ['#B45309', '#C2410C', '#B45309', '#C2410C'];
          
          const innerColor = innerColors[idx % innerColors.length];
          const outerColor = outerColors[idx % outerColors.length];

          return (
            <Fragment key={`dynamic-leg-polyline-${idx}`}>
              {seg.full && viewMode === 'full' && seg.full.length >= 2 && (
                <AnimatedRoute 
                  positions={seg.full} 
                  innerColor="#9CA3AF" 
                  outerColor="#4B5563" 
                  isCompleteRoute={true} 
                />
              )}
              {seg.journey && seg.journey.length >= 2 && (
                <AnimatedRoute 
                  positions={seg.journey} 
                  innerColor={innerColor} 
                  outerColor={outerColor} 
                />
              )}
            </Fragment>
          );
        })}

        {/* Labels Overlay (rendered above vectors but below markers naturally via Leaflet panes) */}
        <Pane name="labels" style={{ zIndex: 450, pointerEvents: 'none' }}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png" />
        </Pane>

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

        {/* Origin / Destination Markers */}
        {sourcePosition && (
          <Marker position={sourcePosition} icon={createCustomIcon('#097752', 14)}>
            <Popup className="transit-popup">
              <div className="font-sans">
                <div className="text-xs font-medium text-zinc-500 mb-1">Source</div>
                <div className="font-semibold text-gray-900">{sourceName}</div>
              </div>
            </Popup>
          </Marker>
        )}

        {destinationPosition && (
          <Marker position={destinationPosition} icon={createCustomIcon('#DC2626', 14)}>
            <Popup className="transit-popup">
              <div className="font-sans">
                <div className="text-xs font-medium text-zinc-500 mb-1">Destination</div>
                <div className="font-semibold text-gray-900">{destinationName}</div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Transfer Station Markers */}
        {transferPositions && transferPositions.map((pos, idx) => {
          const stopName = transferStopNames[idx] || `Transfer Station ${idx + 1}`;
          return (
            <Marker key={`dynamic-transfer-${idx}`} position={pos} icon={createCustomIcon('#D97706', 16)}>
              <Popup className="transit-popup">
                <div className="font-sans">
                  <div className="text-xs font-medium text-zinc-500 mb-1">Transfer Station {idx + 1}</div>
                  <div className="font-semibold text-gray-900">{stopName}</div>
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
          <div className="w-3 h-3 rounded-full bg-[#EA580C]" />
          <span>{transferPositions && transferPositions.length > 0 ? "Active Segment" : "Your Segment"}</span>
        </div>
        {transferPositions && transferPositions.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#F97316]" />
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
