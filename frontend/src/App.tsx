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

interface JourneyResponse {
  success: boolean;
  routes: JourneyRoute[];
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
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [journeyRoutes, setJourneyRoutes] = useState<JourneyRoute[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<JourneyRoute | null>(null);
  const [routeShape, setRouteShape] = useState<[number, number][] | null>(null);
  const [tripStops, setTripStops] = useState<TripStop[]>([]);
  const [viewMode, setViewMode] = useState<'journey' | 'full'>('journey');
  const [appView, setAppView] = useState<'planner' | 'explorer'>('planner');
  const [searchTime, setSearchTime] = useState<string | undefined>(undefined);

  const handleRouteSelect = async (route: JourneyRoute | null) => {
    setSelectedRoute(route);
    setRouteShape(null); // Clear previous route shape immediately
    setTripStops([]); // Clear previous trip stops

    if (!route) return; // If null is passed, we just unselect

    // Fetch trip stops
    try {
      const stopsRes = await fetch(`http://localhost:8000/trips/${route.feed}/${route.trip_id}/stops`);
      if (stopsRes.ok) {
        const data = await stopsRes.json();
        setTripStops(data.stops || []);
      }
    } catch (err) {
      console.error('Error fetching trip stops:', err);
    }

    if (!route.shape_id) {
      console.warn('No shape_id available for this route.');
      return;
    }

    try {
      const res = await fetch(`http://localhost:8000/routes/shape?feed=${encodeURIComponent(route.feed)}&shape_id=${encodeURIComponent(route.shape_id)}`);
      if (!res.ok) throw new Error('Failed to fetch route shape');
      const data = await res.json();

      if (data.points && data.points.length > 0) {
        const shapeCoords: [number, number][] = data.points.map((p: any) => [p.lat, p.lon]);
        setRouteShape(shapeCoords);
      }
    } catch (err) {
      console.error('Error fetching route shape:', err);
    }
  };

  const handleNewSearch = () => {
    setJourneyRoutes([]);
    setSelectedRoute(null);
    setRouteShape(null);
    setError(null);
  };

  const handleSearch = async (source: string, destination: string, departureTime?: string) => {
    setIsLoading(true);
    setError(null);
    setJourneyRoutes([]);
    setSelectedRoute(null);
    setRouteShape(null);
    
    try {
      // Step 1: Search for source and destination stops
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

      if (s?.lat == null || s?.lon == null) {
        throw new Error(`Coordinates missing for source: ${s?.stop_name || source}`);
      }
      if (d?.lat == null || d?.lon == null) {
        throw new Error(`Coordinates missing for destination: ${d?.stop_name || destination}`);
      }

      setSourcePosition([s.lat, s.lon]);
      setSourceName(s.stop_name);
      setDestinationPosition([d.lat, d.lon]);
      setDestinationName(d.stop_name);

      // Step 2: Fetch journey routes using the resolved stop IDs
      let searchTimeString = departureTime;
      if (!searchTimeString) {
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        const ss = String(now.getSeconds()).padStart(2, '0');
        searchTimeString = `${hh}:${mm}:${ss}`;
      }
      setSearchTime(searchTimeString);

      console.log(`Searching journeys after ${searchTimeString}`);

      const journeyRes = await fetch(
        `http://localhost:8000/journey?source_stop_id=${encodeURIComponent(s.stop_id)}&destination_stop_id=${encodeURIComponent(d.stop_id)}&departure_after=${encodeURIComponent(searchTimeString)}`
      );

      if (journeyRes.ok) {
        const journeyData: JourneyResponse = await journeyRes.json();
        if (journeyData.success) {
          setJourneyRoutes(journeyData.routes);
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
      {/* 1. Header (Top) */}
      <Header />

      <main className="flex-1 flex flex-col p-4 md:p-6 gap-6 max-w-[1600px] w-full mx-auto relative">
        {appView === 'explorer' ? (
          <div className="absolute inset-0 z-50 bg-[#0F0F0F]">
            <JourneyExplorer
              routes={journeyRoutes}
              sourceName={sourceName || ''}
              destinationName={destinationName || ''}
              departureAfter={searchTime}
              onBack={() => setAppView('planner')}
              onRouteSelect={(route) => {
                setAppView('planner');
                handleRouteSelect(route);
              }}
            />
          </div>
        ) : null}

        {/* 2. Main Area (30% Planner / 70% Map) */}
        <section className={`flex flex-col lg:flex-row gap-6 min-h-[600px] lg:h-[80vh] ${appView === 'explorer' ? 'hidden' : ''}`}>
          {/* Left Panel - 30% Width */}
          <div className="w-full lg:w-[30%] flex flex-col gap-4 overflow-y-auto max-h-[80vh] pr-2 custom-scrollbar">
            {journeyRoutes.length > 0 || isLoading ? (
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
                  isLoading={isLoading} 
                  selectedRoute={selectedRoute}
                  onRouteSelect={handleRouteSelect}
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

          {/* Right Panel - 70% Width */}
          <div className="w-full lg:w-[70%] flex flex-col relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
            <TransitMap 
              sourcePosition={sourcePosition} 
              destinationPosition={destinationPosition} 
              sourceName={sourceName}
              destinationName={destinationName}
              routeShape={routeShape}
              viewMode={viewMode}
              tripStops={tripStops}
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
