import { useState, useMemo } from 'react';
import { ArrowLeft, X } from 'lucide-react';
import Header from './components/Header';
import JourneyPlanner from './components/JourneyPlanner';
import TransitMap from './components/map/TransitMap';
import RecommendedRoutes from './components/RecommendedRoutes';
import type { NormalizedRoute, TransferJourney, JourneyRoute } from './types/transit';

import FloatingAIAssistant from './components/FloatingAIAssistant';
import JourneyExplorer from './components/JourneyExplorer';
import FullJourneyRoadmap from './components/FullJourneyRoadmap';
import { GlobalAlertModal } from './components/GlobalAlertModal';
import { normalizeRoutes } from './utils/routeNormalizer';
import API_BASE from '@/lib/api';





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
  const [transferPositions, setTransferPositions] = useState<[number, number][]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [journeyRoutes, setJourneyRoutes] = useState<JourneyRoute[]>([]);
  const [transferRoutes, setTransferRoutes] = useState<TransferJourney[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<NormalizedRoute | null>(null);
  const [routeShape, setRouteShape] = useState<[number, number][] | null>(null);
  const [transferShapes, setTransferShapes] = useState<[number, number][][] | null>(null);
  const [tripStops, setTripStops] = useState<TripStop[]>([]);
  const [transferStops, setTransferStops] = useState<TripStop[][] | null>(null);
  const [appView, setAppView] = useState<'planner' | 'explorer' | 'roadmap' | 'details'>('planner');
  const [searchTime, setSearchTime] = useState<string | undefined>(undefined);
  const [focusedLocation, setFocusedLocation] = useState<[number, number] | null>(null);
  const [isAIOpen, setIsAIOpen] = useState(false);

  const normalizedRoutes = useMemo(() => normalizeRoutes(journeyRoutes, transferRoutes), [journeyRoutes, transferRoutes]);

  const fetchTripStops = async (feed: string, trip_id: string) => {
    try {
      const stopsRes = await fetch(`${API_BASE}/trips/${feed}/${trip_id}/stops`);
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
      const res = await fetch(`${API_BASE}/routes/shape?feed=${encodeURIComponent(feed)}&shape_id=${encodeURIComponent(shape_id)}`);
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
    setTransferPositions([]);

    if (!route) return;

    if (route.isTransfer) {
      const tRoute = route.originalData as TransferJourney;
      const legs = [
        tRoute.first_leg,
        tRoute.second_leg,
        tRoute.third_leg
      ].filter(Boolean) as JourneyRoute[];

      const transferStopNames = [
        tRoute.transfer_stop,
        tRoute.transfer_stop_2
      ].filter(Boolean) as string[];

      const positions: [number, number][] = [];
      for (const stopName of transferStopNames) {
        try {
          const res = await fetch(`${API_BASE}/stops/search?q=${encodeURIComponent(stopName)}`);
          if (res.ok) {
            const data = await res.json();
            if (data.results && data.results.length > 0) {
              positions.push([data.results[0].lat, data.results[0].lon]);
            }
          }
        } catch (err) {
          console.error('Error fetching transfer stop:', err);
        }
      }
      setTransferPositions(positions);

      const shapes = await Promise.all(
        legs.map(async (leg) => {
          if (leg.shape_id) {
            return await fetchRouteShape(leg.feed, leg.shape_id);
          }
          return null;
        })
      );
      setTransferShapes(shapes.map(s => s || []));

      const stopsList = await Promise.all(
        legs.map(async (leg) => {
          try {
            const res = await fetch(`${API_BASE}/trips/${leg.feed}/${leg.trip_id}/stops`);
            if (res.ok) {
              const d = await res.json();
              return d.stops || [];
            }
          } catch (err) {
            console.error('Error fetching transfer trip stops:', err);
          }
          return [];
        })
      );
      setTransferStops(stopsList);
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
    setTransferPositions([]);
    setError(null);
  };

  const handleSearch = async (source: string | any, destination: string | any, departureTime?: string): Promise<{directCount: number; transferCount: number; source: string; destination: string; error?: string; narrative?: JourneyNarrative; topDirectRoute?: JourneyRoute; topTransferRoute?: TransferJourney; normalizedRoutes?: NormalizedRoute[]}> => {
    setIsLoading(true);
    setError(null);
    setJourneyRoutes([]);
    setTransferRoutes([]);
    setSelectedRoute(null);
    setRouteShape(null);
    setTransferShapes(null);
    setTripStops([]);
    setTransferStops(null);
    setTransferPositions([]);
    
    try {
      let s: any;
      let d: any;

      if (typeof source === 'string') {
        const sourceRes = await fetch(`${API_BASE}/stops/search?q=${encodeURIComponent(source)}`);
        if (!sourceRes.ok) throw new Error('Failed to fetch source stops');
        const sourceData = await sourceRes.json();
        if (!sourceData.results || sourceData.results.length === 0) {
          throw new Error(`Source not found: ${source}`);
        }
        s = sourceData.results[0];
      } else {
        s = source;
      }

      if (typeof destination === 'string') {
        const destRes = await fetch(`${API_BASE}/stops/search?q=${encodeURIComponent(destination)}`);
        if (!destRes.ok) throw new Error('Failed to fetch destination stops');
        const destData = await destRes.json();
        if (!destData.results || destData.results.length === 0) {
          throw new Error(`Destination not found: ${destination}`);
        }
        d = destData.results[0];
      } else {
        d = destination;
      }

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
        `${API_BASE}/journey?source_stop_id=${encodeURIComponent(s.stop_id)}&destination_stop_id=${encodeURIComponent(d.stop_id)}&departure_after=${encodeURIComponent(searchTimeString)}`
      );

      if (journeyRes.ok) {
        const data: JourneyResponse = await journeyRes.json();
        if (data.success && (data.routes.length > 0 || data.transfer_routes.length > 0)) {
          setJourneyRoutes(data.routes);
          setTransferRoutes(data.transfer_routes || []);
          const normalized = normalizeRoutes(data.routes, data.transfer_routes || []);
          if (normalized.length > 0) {
            handleRouteSelect(normalized[0]);
          }
          return { 
             directCount: data.routes.length, 
             transferCount: (data.transfer_routes || []).length, 
             source: s.stop_name, 
             destination: d.stop_name, 
             narrative: data.narrative,
             topDirectRoute: data.routes[0],
             topTransferRoute: data.transfer_routes ? data.transfer_routes[0] : undefined,
             normalizedRoutes: normalized
          };
        } else {
          setError('No routes found between these stops.');
          return { directCount: 0, transferCount: 0, source: s.stop_name, destination: d.stop_name, narrative: data.narrative };
        }
      }
      
      const sourceStr = typeof source === 'string' ? source : source.stop_name;
      const destStr = typeof destination === 'string' ? destination : destination.stop_name;
      return { directCount: 0, transferCount: 0, source: sourceStr, destination: destStr, error: 'Journey search failed' };

    } catch (err: any) {
      console.error(err);
      const errMsg = err.message || 'An unexpected error occurred during search.';
      setError(errMsg);
      const sourceStr = typeof source === 'string' ? source : source.stop_name;
      const destStr = typeof destination === 'string' ? destination : destination.stop_name;
      return { directCount: 0, transferCount: 0, source: sourceStr, destination: destStr, error: errMsg };
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
          
          {/* LEFT PANEL */}
          <div className={`w-full ${appView === 'roadmap' ? 'lg:w-[25%]' : 'lg:w-[30%]'} flex flex-col gap-4 overflow-y-auto max-h-[80vh] pr-2 custom-scrollbar transition-all duration-300`}>
            {appView === 'planner' && journeyRoutes.length === 0 && transferRoutes.length === 0 && !isLoading ? (
              <div className="flex flex-col gap-4">
                <JourneyPlanner 
                  onSearch={(src, dst, time) => handleSearch(src, dst, time)} 
                  isLoading={isLoading} 
                  initialSource={sourceName || ''}
                  initialDestination={destinationName || ''}
                  initialTime={searchTime}
                />
              </div>
            ) : (
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
                  onOpenRoadmap={(r: any) => { handleRouteSelect(r); setAppView('roadmap'); }}
                  viewMode={appView === 'explorer' ? 'full' : 'journey'}
                  onViewModeChange={(mode: any) => setAppView(mode === 'full' ? 'explorer' : 'planner')}
                  onViewAll={() => setAppView('explorer')}
                  onOpenAI={() => setIsAIOpen(true)}
                />
              </div>
            )}
          </div>

          {/* MAP */}
          <div className="w-full flex-1 flex flex-col relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl transition-all duration-300">
            <TransitMap 
              sourcePosition={sourcePosition}
              destinationPosition={destinationPosition}
              transferPositions={transferPositions}
              routeShape={routeShape}
              transferShapes={transferShapes}
              sourceName={sourceName}
              destinationName={destinationName}
              tripStops={tripStops}
              transferStops={transferStops}
              focusedLocation={focusedLocation}
              selectedRoute={selectedRoute}
            />
          </div>

          {/* RIGHT PANEL (ROADMAP) */}
          {appView === 'roadmap' && selectedRoute && (
            <div className="w-full lg:w-[25%] flex flex-col gap-4 overflow-y-auto max-h-[80vh] pl-2 custom-scrollbar transition-all duration-300">
              <div className="h-full bg-[#1A1A1A] rounded-2xl overflow-hidden border border-white/10 shadow-2xl flex flex-col">
                <div className="p-4 border-b border-white/10 flex justify-between items-center bg-[#0F0F0F]">
                  <h2 className="text-lg font-semibold text-white/90">Journey Roadmap</h2>
                  <button onClick={() => setAppView('details')} className="p-1 rounded-full text-white/40 hover:text-white hover:bg-white/10 transition-colors">
                    <X size={18} />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto custom-scrollbar bg-[#0F0F0F]">
                  <FullJourneyRoadmap 
                    route={selectedRoute} 
                    tripStops={tripStops} 
                    transferStops={transferStops} 
                    onStationClick={(lat, lon) => setFocusedLocation([lat, lon])}
                  />
                </div>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* Global AI Assistant Modal */}
      <FloatingAIAssistant 
        isOpen={isAIOpen}
        onOpen={() => setIsAIOpen(true)}
        onClose={() => setIsAIOpen(false)}
        onSearch={handleSearch} 
        activeRoute={selectedRoute} 
        onRouteSelect={(r) => { setAppView('details'); handleRouteSelect(r); }}
        tripStops={tripStops || undefined}
        transferStops={transferStops || undefined}
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
