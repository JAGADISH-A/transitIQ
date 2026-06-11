import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import Header from './components/Header';
import JourneyPlanner from './components/JourneyPlanner';
import TransitMap from './components/map/TransitMap';
import RecommendedRoutes from './components/RecommendedRoutes';
import FloatingAIAssistant from './components/FloatingAIAssistant';
import JourneyExplorer from './components/JourneyExplorer';

interface StopResult {
  stop_id: string;
  stop_name: string;
  lat: number;
  lon: number;
}

interface SearchResponse {
  query: string;
  results: StopResult[];
  count: number;
}

interface JourneyRoute {
  feed: string;
  trip_id: string;
  route_id: string;
  route_name: string;
  source_stop: string;
  destination_stop: string;
  stops_between: number;
  departure_time?: string;
  shape_id?: string;
}

interface TransferJourney {
  journey_type: "TRANSFER";
  transfer_stop: string;
  first_leg: JourneyRoute;
  second_leg: JourneyRoute;
  total_duration: number;
  transfer_wait: number;
}

interface JourneyResponse {
  success: boolean;
  routes: JourneyRoute[];
  transfer_routes: TransferJourney[];
}

export interface TripStop {
  stop_id: string;
  stop_name: string;
  stop_sequence: number;
  arrival_time?: string;
  departure_time?: string;
  stop_lat?: number;
  stop_lon?: number;
}

function App() {
  const [sourcePosition, setSourcePosition] = useState<[number, number] | undefined>(undefined);
  const [destinationPosition, setDestinationPosition] = useState<[number, number] | undefined>(undefined);
  const [sourceName, setSourceName] = useState<string | undefined>(undefined);
  const [destinationName, setDestinationName] = useState<string | undefined>(undefined);
  const [transferPosition, setTransferPosition] = useState<[number, number] | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [journeyRoutes, setJourneyRoutes] = useState<JourneyRoute[]>([]);
  const [transferRoutes, setTransferRoutes] = useState<TransferJourney[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<JourneyRoute | null>(null);
  const [selectedTransferRoute, setSelectedTransferRoute] = useState<TransferJourney | null>(null);
  const [routeShape, setRouteShape] = useState<[number, number][] | null>(null);
  const [transferShapes, setTransferShapes] = useState<{leg1: [number, number][], leg2: [number, number][]} | null>(null);
  const [tripStops, setTripStops] = useState<TripStop[]>([]);
  const [transferStops, setTransferStops] = useState<{leg1: TripStop[], leg2: TripStop[]} | null>(null);
  const [viewMode, setViewMode] = useState<'journey' | 'full'>('journey');
  const [appView, setAppView] = useState<'planner' | 'explorer'>('planner');
  const [searchTime, setSearchTime] = useState<string | undefined>(undefined);

  const fetchTripStops = async (feed: string, trip_id: string) => {
    try {
      const stopsRes = await fetch(`http://localhost:8000/trips/${feed}/${trip_id}/stops`);
      if (stopsRes.ok) {
        const data = await stopsRes.json();
        setTripStops(data.stops || []);
      }
    } catch (err) {
      console.error('Error fetching trip stops:', err);
    }
  };

  const fetchRouteShape = async (feed: string, shape_id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/routes/shape?feed=${encodeURIComponent(feed)}&shape_id=${encodeURIComponent(shape_id)}`);
      if (!res.ok) throw new Error('Failed to fetch route shape');
      const data = await res.json();
      if (data.points && data.points.length > 0) {
        return data.points.map((p: any) => [p.lat, p.lon]) as [number, number][];
      }
      return null;
    } catch (err) {
      console.error('Error fetching route shape:', err);
      return null;
    }
  };

  const handleRouteSelect = async (route: JourneyRoute | null) => {
    setSelectedRoute(route);
    setSelectedTransferRoute(null);
    setRouteShape(null);
    setTransferShapes(null);
    setTripStops([]);
    setTransferStops(null);
    setTransferPosition(undefined);

    if (!route) return;

    fetchTripStops(route.feed, route.trip_id);
    if (route.shape_id) {
      const shape = await fetchRouteShape(route.feed, route.shape_id);
      if (shape) setRouteShape(shape);
    }
  };

  const handleTransferRouteSelect = async (route: TransferJourney | null) => {
    setSelectedTransferRoute(route);
    setSelectedRoute(null);
    setRouteShape(null);
    setTransferShapes(null);
    setTripStops([]);
    setTransferStops(null);
    setTransferPosition(undefined);

    if (!route) return;

    try {
      const res = await fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(route.transfer_stop)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.results && data.results.length > 0) {
          setTransferPosition([data.results[0].lat, data.results[0].lon]);
        }
      }
    } catch (err) {
      console.error('Error fetching transfer stop:', err);
    }

    let leg1Shape = null;
    let leg2Shape = null;

    if (route.first_leg.shape_id) {
      leg1Shape = await fetchRouteShape(route.first_leg.feed, route.first_leg.shape_id);
    }
    if (route.second_leg.shape_id) {
      leg2Shape = await fetchRouteShape(route.second_leg.feed, route.second_leg.shape_id);
    }

    if (leg1Shape || leg2Shape) {
      setTransferShapes({
        leg1: leg1Shape || [],
        leg2: leg2Shape || []
      });
    }

    let leg1Stops: TripStop[] = [];
    let leg2Stops: TripStop[] = [];

    try {
      const res1 = await fetch(`http://localhost:8000/trips/${route.first_leg.feed}/${route.first_leg.trip_id}/stops`);
      if (res1.ok) {
        const d = await res1.json();
        leg1Stops = d.stops || [];
      }
      const res2 = await fetch(`http://localhost:8000/trips/${route.second_leg.feed}/${route.second_leg.trip_id}/stops`);
      if (res2.ok) {
        const d = await res2.json();
        leg2Stops = d.stops || [];
      }
    } catch (err) {
      console.error('Error fetching transfer trip stops:', err);
    }
    setTransferStops({ leg1: leg1Stops, leg2: leg2Stops });
  };

  const handleNewSearch = () => {
    setJourneyRoutes([]);
    setTransferRoutes([]);
    setSelectedRoute(null);
    setSelectedTransferRoute(null);
    setRouteShape(null);
    setTransferShapes(null);
    setTripStops([]);
    setTransferStops(null);
    setError(null);
  };

  const handleSearch = async (source: string, destination: string, departureTime?: string) => {
    setIsLoading(true);
    setError(null);
    setJourneyRoutes([]);
    setTransferRoutes([]);
    setSelectedRoute(null);
    setSelectedTransferRoute(null);
    setRouteShape(null);
    setTransferShapes(null);
    setTripStops([]);
    setTransferStops(null);
    
    try {
      const [sourceRes, destRes] = await Promise.all([
        fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(source)}`),
        fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(destination)}`)
      ]);

      if (!sourceRes.ok) throw new Error('Failed to fetch source stops');
      if (!destRes.ok) throw new Error('Failed to fetch destination stops');

      const sourceData: SearchResponse = await sourceRes.json();
      const destData: SearchResponse = await destRes.json();

      if (!sourceData.results || sourceData.results.length === 0) {
        throw new Error(`Source not found: ${source}`);
      }
      if (!destData.results || destData.results.length === 0) {
        throw new Error(`Destination not found: ${destination}`);
      }

      const s = sourceData.results[0];
      const d = destData.results[0];

      setSourcePosition([s.lat, s.lon]);
      setSourceName(s.stop_name);
      setDestinationPosition([d.lat, d.lon]);
      setDestinationName(d.stop_name);

      let searchTimeString = departureTime;
      if (!searchTimeString) {
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        const ss = String(now.getSeconds()).padStart(2, '0');
        searchTimeString = `${hh}:${mm}:${ss}`;
      }
      setSearchTime(searchTimeString);

      const journeyRes = await fetch(
        `http://localhost:8000/journey?source_stop_id=${encodeURIComponent(s.stop_id)}&destination_stop_id=${encodeURIComponent(d.stop_id)}&departure_after=${encodeURIComponent(searchTimeString)}`
      );

      if (journeyRes.ok) {
        const data: JourneyResponse = await journeyRes.json();
        if (data.success && (data.routes.length > 0 || data.transfer_routes.length > 0)) {
          setJourneyRoutes(data.routes);
          setTransferRoutes(data.transfer_routes || []);
        } else {
          setError('No routes found between these stops.');
        }
      }

    } catch (err: any) {
      console.error(err);
      setError(err.message || 'An unexpected error occurred during search.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#0F0F0F] text-white/90 font-sans selection:bg-[#FF4500]/30 selection:text-white">
      <Header />

      <main className="flex-1 flex flex-col p-4 md:p-6 gap-6 max-w-[1600px] w-full mx-auto relative">
        {appView === 'explorer' ? (
          <div className="absolute inset-0 z-50 bg-[#0F0F0F]">
            <JourneyExplorer
              routes={journeyRoutes}
              transferRoutes={transferRoutes}
              sourceName={sourceName || ''}
              destinationName={destinationName || ''}
              departureAfter={searchTime}
              onBack={() => setAppView('planner')}
              onRouteSelect={(route) => {
                setAppView('planner');
                handleRouteSelect(route);
              }}
              onTransferRouteSelect={(route) => {
                setAppView('planner');
                handleTransferRouteSelect(route);
              }}
            />
          </div>
        ) : null}

        <section className={`flex flex-col lg:flex-row gap-6 min-h-[600px] lg:h-[80vh] ${appView === 'explorer' ? 'hidden' : ''}`}>
          <div className="w-full lg:w-[30%] flex flex-col gap-4 overflow-y-auto max-h-[80vh] pr-2 custom-scrollbar">
            {journeyRoutes.length > 0 || transferRoutes.length > 0 || isLoading ? (
              <div className="flex flex-col gap-4">
                <button 
                  onClick={handleNewSearch}
                  className="flex items-center gap-2 text-sm font-medium text-white/60 hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl w-fit"
                >
                  <ArrowLeft size={16} />
                  Back
                </button>
                <RecommendedRoutes 
                  routes={journeyRoutes} 
                  transferRoutes={transferRoutes}
                  isLoading={isLoading} 
                  selectedRoute={selectedRoute}
                  selectedTransferRoute={selectedTransferRoute}
                  onRouteSelect={handleRouteSelect}
                  onTransferRouteSelect={handleTransferRouteSelect}
                  viewMode={viewMode}
                  onViewModeChange={setViewMode}
                  onViewAll={() => setAppView('explorer')}
                  tripStops={tripStops}
                />
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <JourneyPlanner 
                  onSearch={handleSearch} 
                  isLoading={isLoading} 
                  initialSource={sourceName || ''}
                  initialDestination={destinationName || ''}
                  initialTime={searchTime}
                />
                {error && (
                  <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 text-red-500 text-sm">
                    {error}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="w-full lg:w-[70%] flex flex-col relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
            <TransitMap 
              sourcePosition={sourcePosition} 
              destinationPosition={destinationPosition} 
              sourceName={sourceName}
              destinationName={destinationName}
              selectedRoute={selectedRoute}
              selectedTransferRoute={selectedTransferRoute}
              transferPosition={transferPosition}
              routeShape={routeShape}
              transferShapes={transferShapes}
              viewMode={viewMode}
              tripStops={tripStops}
              transferStops={transferStops}
            />
          </div>
        </section>
      </main>

      {/* 4. Floating AI Assistant (Bottom Right) */}
      <FloatingAIAssistant />
    </div>
  );
}

export default App;
