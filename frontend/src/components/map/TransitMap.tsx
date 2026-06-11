import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface TransitMapProps {
  sourcePosition?: [number, number];
  destinationPosition?: [number, number];
  sourceName?: string;
  destinationName?: string;
  routeShape?: [number, number][] | null;
}

const BoundsUpdater = ({ bounds }: { bounds: L.LatLngBoundsExpression | null }) => {
  const map = useMap();
  useEffect(() => {
    if (bounds) {
      map.flyToBounds(bounds, { padding: [30, 30], duration: 1.5 });
    }
  }, [map, bounds]);
  return null;
};

const createCustomIcon = (color: string) => {
  return L.divIcon({
    className: 'custom-marker',
    html: `
      <div style="
        background-color: ${color};
        width: 16px;
        height: 16px;
        border-radius: 50%;
        border: 2px solid #1A1A1A;
        box-shadow: 0 0 10px ${color};
      "></div>
    `,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });
};

export default function TransitMap({ 
  sourcePosition, 
  destinationPosition,
  sourceName = "Source",
  destinationName = "Destination",
  routeShape
}: TransitMapProps) {
  // If neither is provided, center somewhere default (e.g., Chennai)
  const defaultCenter: [number, number] = [13.0827, 80.2707];
  
  const activePoints: [number, number][] = [];
  if (sourcePosition) activePoints.push(sourcePosition);
  if (destinationPosition) activePoints.push(destinationPosition);

  // Focus bounds on the route shape if selected, otherwise just the source/dest markers
  const bounds = useMemo(() => {
    if (routeShape && routeShape.length > 0) {
      return L.latLngBounds(routeShape);
    }
    return activePoints.length > 0 ? L.latLngBounds(activePoints) : null;
  }, [routeShape, sourcePosition, destinationPosition]);

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
        
        {routeShape && routeShape.length > 0 && (
          <Polyline positions={routeShape} color="#FF4500" weight={4} opacity={0.8} />
        )}

        {sourcePosition && (
          <Marker position={sourcePosition} icon={createCustomIcon('#10B981')}>
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
          <Marker position={destinationPosition} icon={createCustomIcon('#EF4444')}>
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
    </div>
  );
}
