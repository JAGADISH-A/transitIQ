import { useState, useMemo } from 'react';
import { ArrowLeft } from 'lucide-react';
import Header from './components/Header';
import JourneyPlanner from './components/JourneyPlanner';
import TransitMap from './components/map/TransitMap';
import RecommendedRoutes from './components/RecommendedRoutes';
import type { JourneyRoute, TransferJourney, NormalizedRoute } from './types/transit';
import FloatingAIAssistant from './components/FloatingAIAssistant';
import JourneyExplorer from './components/JourneyExplorer';
import { GlobalAlertModal } from './components/GlobalAlertModal';
import { normalizeRoutes } from './utils/routeNormalizer';

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

export interface DisplayTime {
  display_time: string;
  day_offset: number;
}

export interface ActiveJourney {
  source: string;
  destination: string;
  departure_time: string;
  transfer_station?: string;
  transfer_count: number;
}

export interface PreviousRouteComparison {
  duration_minutes: number;
  transfer_count: number;
  quality_classification: string;
}

export interface JourneyContext {
  source?: string;
  destination?: string;
  departure_time?: string;
  route_preference?: string;
  last_updated?: string;
  active_journey?: ActiveJourney;
  previous_comparison?: PreviousRouteComparison;
}

export interface JourneyNarrative {
  headline: string;
  summary: string;
  recommendation: string;
  warnings: string[];
  alternatives_available: number;
}

export interface JourneyQuality {
  score: number;
  classification: "Excellent" | "Good" | "Acceptable" | "Poor" | "Low Quality" | "Rejected";
  recommendation_reason?: string;
  route_flags: string[];
}

interface JourneyResponse {
  success: boolean;
  narrative?: JourneyNarrative;
  routes: JourneyRoute[];
  transfer_routes: TransferJourney[];
}

export interface TripStop {
  stop_id: string;
  stop_name: string;
  stop_sequence: number;
  arrival_time?: string;
  departure_time?: string;
  arrival_display?: DisplayTime;
  departure_display?: DisplayTime;
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
  const [selectedRoute, setSelectedRoute] = useState<NormalizedRoute | null>(null);
  const [routeShape, setRouteShape] = useState<[number, number][] | null>(null);
  const [transferShapes, setTransferShapes] = useState<{leg1: [number, number][], leg2: [number, number][]} | null>(null);
  const [tripStops, setTripStops] = useState<TripStop[]>([]);
  const [transferStops, setTransferStops] = useState<{leg1: TripStop[], leg2: TripStop[]} | null>(null);
  const [appView, setAppView] = useState<'planner' | 'explorer'>('planner');
  const [searchTime, setSearchTime] = useState<string | undefined>(undefined);

  const normalizedRoutes = useMemo(() => normalizeRoutes(journeyRoutes, transferRoutes), [journeyRoutes, transferRoutes]);

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

  const handleRouteSelect = async (route: NormalizedRoute | null) => {
    setSelectedRoute(route);
    setRouteShape(null);
    setTransferShapes(null);
    setTripStops([]);
    setTransferStops(null);
    setTransferPosition(undefined);

    if (!route) return;

    if (route.isTransfer) {
      const tRoute = route.originalData as TransferJourney;
      try {
        const res = await fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(tRoute.transfer_stop)}`);
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

      if (tRoute.first_leg.shape_id) {
        leg1Shape = await fetchRouteShape(tRoute.first_leg.feed, tRoute.first_leg.shape_id);
      }
      if (tRoute.second_leg.shape_id) {
        leg2Shape = await fetchRouteShape(tRoute.second_leg.feed, tRoute.second_leg.shape_id);
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
        const res1 = await fetch(`http://localhost:8000/trips/${tRoute.first_leg.feed}/${tRoute.first_leg.trip_id}/stops`);
        if (res1.ok) {
          const d = await res1.json();
          leg1Stops = d.stops || [];
        }
        const res2 = await fetch(`http://localhost:8000/trips/${tRoute.second_leg.feed}/${tRoute.second_leg.trip_id}/stops`);
        if (res2.ok) {
          const d = await res2.json();
          leg2Stops = d.stops || [];
        }
      } catch (err) {
        console.error('Error fetching transfer trip stops:', err);
      }
      setTransferStops({ leg1: leg1Stops, leg2: leg2Stops });
    } else {
      const dRoute = route.originalData as JourneyRoute;
      fetchTripStops(dRoute.feed, dRoute.trip_id);
      if (dRoute.shape_id) {
        const shape = await fetchRouteShape(dRoute.feed, dRoute.shape_id);
        if (shape) setRouteShape(shape);
      }
    }
  };

  
  const handleNewSearch = () => {
    setJourneyRoutes([]);
    setTransferRoutes([]);
    setSelectedRoute(null);
    setRouteShape(null);
    setTransferShapes(null);
    setTripStops([]);
    setTransferStops(null);
    setError(null);
  };

  const handleSearch = async (source: string, destination: string, departureTime?: string): Promise<{directCount: number; transferCount: number; source: string; destination: string; error?: string; narrative?: JourneyNarrative; topDirectRoute?: JourneyRoute; topTransferRoute?: TransferJourney}> => {
    setIsLoading(true);
    setError(null);
    setJourneyRoutes([]);
    setTransferRoutes([]);
    setSelectedRoute(null);
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
          return { 
             directCount: data.routes.length, 
             transferCount: (data.transfer_routes || []).length, 
             source: s.stop_name, 
             destination: d.stop_name, 
             narrative: data.narrative,
             topDirectRoute: data.routes[0],
             topTransferRoute: data.transfer_routes ? data.transfer_routes[0] : undefined
          };
        } else {
          setError('No routes found between these stops.');
          return { directCount: 0, transferCount: 0, source: s.stop_name, destination: d.stop_name, narrative: data.narrative };
        }
      }
      
      return { directCount: 0, transferCount: 0, source, destination, error: 'Journey search failed' };

    } catch (err: any) {
      console.error(err);
      const errMsg = err.message || 'An unexpected error occurred during search.';
      setError(errMsg);
      return { directCount: 0, transferCount: 0, source, destination, error: errMsg };
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
              routes={normalizedRoutes}
              sourceName={sourceName || ''}
              destinationName={destinationName || ''}
              onBack={() => setAppView('planner')}
              onRouteSelect={(route) => {
                setAppView('planner');
                handleRouteSelect(route);
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
                  routes={normalizedRoutes} 
                  isLoading={isLoading} 
                  selectedRoute={selectedRoute}
                  onRouteSelect={handleRouteSelect}
                  viewMode={appView === 'explorer' ? 'full' : 'journey'}
                  onViewModeChange={(mode: any) => setAppView(mode === 'full' ? 'explorer' : 'planner')}
                  onViewAll={() => setAppView('explorer')}
                />
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <JourneyPlanner 
                  onSearch={(src, dst, time) => handleSearch(src.stop_name, dst.stop_name, time)} 
                  isLoading={isLoading} 
                  initialSource={sourceName || ''}
                  initialDestination={destinationName || ''}
                  initialTime={searchTime}
                />
                <FloatingAIAssistant 
                  onSearch={handleSearch} 
                  activeRoute={selectedRoute ? selectedRoute.originalData : null} 
                />
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
              
              transferPosition={transferPosition}
              routeShape={routeShape}
              transferShapes={transferShapes}
              viewMode={appView === 'explorer' ? 'full' : 'journey'}
              tripStops={tripStops}
              transferStops={transferStops}
            />
          </div>
        </section>
      </main>

      {/* 4. Floating AI Assistant (Bottom Right) */}
      <FloatingAIAssistant 
        onSearch={handleSearch} 
        activeRoute={selectedRoute ? selectedRoute.originalData : null} 
      />

      {/* Global Alert Modal */}
      <GlobalAlertModal
        isOpen={!!error}
        onClose={() => setError(null)}
        message={error || ""}
        title="Search Error"
      />
    </div>
  );
}

export default App;
