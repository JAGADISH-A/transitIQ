import { useState, useMemo } from 'react';
import { ArrowLeft, ArrowRight, Zap, BarChart2, X, Clock, TrainFront, Footprints } from 'lucide-react';
import { RoutePreview } from './RoutePreview';
import type { NormalizedRoute, TransferJourney, JourneyRoute } from '../types/transit';

interface JourneyExplorerProps {
  routes: NormalizedRoute[];
  sourceName: string;
  destinationName: string;
  onBack: () => void;
  onRouteSelect: (route: NormalizedRoute) => void;
}

const MODE_MAP: Record<string, string> = {
  railways: "Rail",
  chennai_metro: "Metro",
  metro: "Metro",
  mtc: "Bus",
  bus: "Bus"
};

export default function JourneyExplorer({
  routes: rawRoutes,
  sourceName,
  destinationName,
  onBack,
  onRouteSelect
}: JourneyExplorerProps) {
  const [sortBy, setSortBy] = useState<'earliest_departure' | 'earliest_arrival' | 'shortest_duration' | 'quality'>('shortest_duration');
  
  // Filter States
  const [filterTransfer, setFilterTransfer] = useState<'all' | 'direct' | '1' | '2+'>('all');
  const [filterMode, setFilterMode] = useState<Set<string>>(new Set(['all']));

  const [compareRouteIds, setCompareRouteIds] = useState<Set<string>>(new Set());
  const [showComparison, setShowComparison] = useState(false);

  // 1. Deduplicate Routes
  const dedupedRoutes = useMemo(() => {
    const seen = new Set<string>();
    const unique: NormalizedRoute[] = [];
    
    for (const r of rawRoutes) {
      let routePathIds = '';
      if (r.isTransfer) {
        const t = r.originalData as TransferJourney;
        const extT = t as any;
        if (extT.third_leg) {
          routePathIds = `${t.first_leg.route_id}_${t.second_leg.route_id}_${extT.third_leg.route_id}`;
        } else {
          routePathIds = `${t.first_leg.route_id}_${t.second_leg.route_id}`;
        }
      } else {
        const t = r.originalData as JourneyRoute;
        routePathIds = `${t.route_id}`;
      }
      
      const key = `${r.sourceName}_${r.destName}_${r.departureTime}_${r.arrivalTime}_${r.transferCount}_${routePathIds}`;
      
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(r);
      }
    }
    return unique;
  }, [rawRoutes]);

  // 2. Compute Hero Statistics (from dedupedRoutes)
  const stats = useMemo(() => {
    if (dedupedRoutes.length === 0) return null;
    const durations = dedupedRoutes.map(r => r.durationMinutes);
    const fastest = Math.min(...durations);
    const deps = dedupedRoutes.map(r => r.departureTime).filter(Boolean) as string[];
    const earliest = deps.length > 0 ? deps.sort((a, b) => a.localeCompare(b))[0] : '-';
    const direct = dedupedRoutes.filter(r => r.transferCount === 0).length;
    const transfer = dedupedRoutes.length - direct;
    
    return { fastest, earliest, direct, transfer };
  }, [dedupedRoutes]);

  // 3. Filter Routes
  const filteredRoutes = useMemo(() => {
    return dedupedRoutes.filter(r => {
      // Transfer Filter
      if (filterTransfer === 'direct' && r.transferCount !== 0) return false;
      if (filterTransfer === '1' && r.transferCount !== 1) return false;
      if (filterTransfer === '2+' && r.transferCount < 2) return false;

      // Mode Filter
      if (!filterMode.has('all')) {
        const modes: string[] = [];
        if (r.isTransfer) {
          const t = r.originalData as TransferJourney;
          const extT = t as any;
          modes.push(MODE_MAP[t.first_leg.feed] || 'Rail');
          modes.push(MODE_MAP[t.second_leg.feed] || 'Rail');
          if (extT.third_leg) {
            modes.push(MODE_MAP[extT.third_leg.feed] || 'Rail');
          }
        } else {
          const t = r.originalData as JourneyRoute;
          modes.push(MODE_MAP[t.feed] || 'Rail');
        }
        
        // If route uses any mode NOT in our selected filters, we could drop it.
        // Usually, OR logic is preferred: does route have ANY of selected modes?
        const hasSelectedMode = modes.some(m => filterMode.has(m));
        if (!hasSelectedMode) return false;
      }

      return true;
    });
  }, [dedupedRoutes, filterTransfer, filterMode]);

  // 4. Sort Routes
  const displayRoutes = useMemo(() => {
    const sorted = [...filteredRoutes];
    
    sorted.sort((a, b) => {
      if (sortBy === 'shortest_duration') {
        if (a.durationMinutes === b.durationMinutes) {
          const timeA = a.departureTime || '99:99:99';
          const timeB = b.departureTime || '99:99:99';
          return timeA.localeCompare(timeB);
        }
        return a.durationMinutes - b.durationMinutes;
      } else if (sortBy === 'earliest_departure') {
        const timeA = a.departureTime || '99:99:99';
        const timeB = b.departureTime || '99:99:99';
        if (timeA === timeB) return a.durationMinutes - b.durationMinutes;
        return timeA.localeCompare(timeB);
      } else if (sortBy === 'earliest_arrival') {
        const timeA = a.arrivalTime || '99:99:99';
        const timeB = b.arrivalTime || '99:99:99';
        if (timeA === timeB) return a.durationMinutes - b.durationMinutes;
        return timeA.localeCompare(timeB);
      } else if (sortBy === 'quality') {
        return a.qualityScore - b.qualityScore;
      }
      return 0;
    });

    return sorted;
  }, [filteredRoutes, sortBy]);

  // Comparison State
  const compareRoutes = useMemo(() => {
    return dedupedRoutes.filter(r => compareRouteIds.has(r.id));
  }, [dedupedRoutes, compareRouteIds]);

  const compFastest = useMemo(() => {
    if (compareRoutes.length === 0) return null;
    return Math.min(...compareRoutes.map(r => r.durationMinutes));
  }, [compareRoutes]);

  const compEarliestDep = useMemo(() => {
    if (compareRoutes.length === 0) return null;
    const deps = compareRoutes.map(r => r.departureTime).filter(Boolean) as string[];
    if (deps.length === 0) return null;
    return deps.sort((a, b) => a.localeCompare(b))[0];
  }, [compareRoutes]);

  const compEarliestArr = useMemo(() => {
    if (compareRoutes.length === 0) return null;
    const arrs = compareRoutes.map(r => r.arrivalTime).filter(Boolean) as string[];
    if (arrs.length === 0) return null;
    return arrs.sort((a, b) => a.localeCompare(b))[0];
  }, [compareRoutes]);

  const handleRouteSelect = (route: NormalizedRoute) => {
    onRouteSelect(route);
  };

  const handleCompareToggle = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const newSet = new Set(compareRouteIds);
    if (newSet.has(id)) newSet.delete(id);
    else { if (newSet.size < 3) newSet.add(id); }
    setCompareRouteIds(newSet);
  };

  const toggleModeFilter = (mode: string) => {
    const newSet = new Set(filterMode);
    if (mode === 'all') {
      newSet.clear();
      newSet.add('all');
    } else {
      newSet.delete('all');
      if (newSet.has(mode)) newSet.delete(mode);
      else newSet.add(mode);
      if (newSet.size === 0) newSet.add('all');
    }
    setFilterMode(newSet);
  };

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] text-white relative custom-scrollbar overflow-y-auto">
      {/* Top Header Row (Back Button & Summary) */}
      <div className="flex items-start justify-between p-4 md:px-8 bg-black/40 backdrop-blur-md border-b border-white/5 sticky top-0 z-30">
        <div className="flex items-start gap-6 w-full">
          <button 
            onClick={onBack}
            className="flex items-center gap-2 text-[13px] font-medium text-zinc-300 hover:text-white transition-colors h-9 px-[14px] rounded-full bg-white/[0.05] border border-white/[0.08] backdrop-blur-md shrink-0 mt-1"
          >
            <ArrowLeft size={14} />
            Back
          </button>
          
          <div className="flex flex-col flex-1">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              {dedupedRoutes.length} Routes Found
              <span className="text-sm font-medium px-2 py-1 bg-white/10 rounded-full text-zinc-300">
                {displayRoutes.length} matching filters
              </span>
            </h1>
            <div className="text-[14px] font-medium text-[#FF4500] mt-1 flex items-center gap-2">
              {sourceName} <ArrowRight size={14} /> {destinationName}
            </div>
            
            {/* Stats Row */}
            {stats && (
              <div className="flex flex-wrap items-center gap-3 mt-4">
                <div className="flex items-center gap-2 bg-white/[0.03] border border-white/5 rounded-lg px-3 py-1.5 text-xs">
                  <Zap size={14} className="text-yellow-400" />
                  <span className="text-zinc-400">Fastest:</span>
                  <span className="font-bold text-white">{stats.fastest}m</span>
                </div>
                <div className="flex items-center gap-2 bg-white/[0.03] border border-white/5 rounded-lg px-3 py-1.5 text-xs">
                  <Clock size={14} className="text-blue-400" />
                  <span className="text-zinc-400">Earliest:</span>
                  <span className="font-bold text-white">{stats.earliest}</span>
                </div>
                <div className="flex items-center gap-2 bg-white/[0.03] border border-white/5 rounded-lg px-3 py-1.5 text-xs">
                  <TrainFront size={14} className="text-green-400" />
                  <span className="text-zinc-400">Direct:</span>
                  <span className="font-bold text-white">{stats.direct}</span>
                </div>
                <div className="flex items-center gap-2 bg-white/[0.03] border border-white/5 rounded-lg px-3 py-1.5 text-xs">
                  <Footprints size={14} className="text-amber-400" />
                  <span className="text-zinc-400">Transfers:</span>
                  <span className="font-bold text-white">{stats.transfer}</span>
                </div>
              </div>
            )}
          </div>
          
          <button 
            onClick={onBack}
            className="w-9 h-9 rounded-full bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/[0.1] transition-all backdrop-blur-md shrink-0 mt-1"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Control Bar (Sticky) */}
      <div className="flex flex-col gap-3 p-4 md:px-8 bg-zinc-950/80 backdrop-blur-xl border-b border-white/5 sticky top-[100px] z-20">
        
        {/* Sort Controls */}
        <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar pb-1">
          <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest px-2 shrink-0">Sort By</span>
          <button onClick={() => setSortBy('shortest_duration')} className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${sortBy === 'shortest_duration' ? 'bg-[#FF4500] text-white' : 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10'}`}>Duration</button>
          <button onClick={() => setSortBy('earliest_departure')} className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${sortBy === 'earliest_departure' ? 'bg-[#FF4500] text-white' : 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10'}`}>Departure</button>
          <button onClick={() => setSortBy('earliest_arrival')} className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${sortBy === 'earliest_arrival' ? 'bg-[#FF4500] text-white' : 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10'}`}>Arrival</button>
          <button onClick={() => setSortBy('quality')} className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${sortBy === 'quality' ? 'bg-[#FF4500] text-white' : 'bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10'}`}>Quality</button>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar pb-1">
          <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest px-2 shrink-0">Filter</span>
          
          <div className="flex items-center bg-white/5 rounded-full p-0.5 shrink-0 mr-2">
            <button onClick={() => setFilterTransfer('all')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterTransfer === 'all' ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>All Transfers</button>
            <button onClick={() => setFilterTransfer('direct')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterTransfer === 'direct' ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>Direct</button>
            <button onClick={() => setFilterTransfer('1')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterTransfer === '1' ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>1 Transfer</button>
            <button onClick={() => setFilterTransfer('2+')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterTransfer === '2+' ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>2+ Transfers</button>
          </div>

          <div className="flex items-center bg-white/5 rounded-full p-0.5 shrink-0">
            <button onClick={() => toggleModeFilter('all')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterMode.has('all') ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>All Modes</button>
            <button onClick={() => toggleModeFilter('Rail')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterMode.has('Rail') ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>Rail</button>
            <button onClick={() => toggleModeFilter('Metro')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterMode.has('Metro') ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>Metro</button>
            <button onClick={() => toggleModeFilter('Bus')} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${filterMode.has('Bus') ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-white'}`}>Bus</button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-4 md:px-8 pb-32">
        <div className="flex flex-col gap-3 max-w-[1200px] mx-auto w-full">
          {displayRoutes.length === 0 ? (
            <div className="text-center py-20 text-zinc-500 font-medium">
              No routes match your current filters.
            </div>
          ) : (
            displayRoutes.map((route) => {

              return (
                <RoutePreview
                  key={route.id}
                  route={route}
                  onClick={() => handleRouteSelect(route)}
                  isCompared={compareRouteIds.has(route.id)}
                  onCompareToggle={(e) => handleCompareToggle(e, route.id)}
                />
              );
            })
          )}
        </div>
      </div>

      {/* Floating Action Bar (Comparison Tray) */}
      {compareRouteIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex flex-col items-center w-[90vw] max-w-3xl pointer-events-none">
          {showComparison && (
            <div className="w-full bg-[#1A1A1A] border border-white/10 p-4 rounded-2xl shadow-2xl mb-4 animate-in fade-in slide-in-from-bottom-4 pointer-events-auto">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <BarChart2 size={16} className="text-[#FF4500]" />
                  Comparing {compareRouteIds.size} Routes
                </h3>
                <button 
                  onClick={() => setShowComparison(false)} 
                  className="p-1 text-white/50 hover:text-white rounded-full bg-white/5 hover:bg-white/10"
                >
                  <X size={16} />
                </button>
              </div>
              
              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-left text-sm whitespace-nowrap">
                  <thead>
                    <tr className="text-white/40 uppercase tracking-wider text-[10px] border-b border-white/10">
                      <th className="pb-2 font-medium">Route</th>
                      <th className="pb-2 font-medium">Depart</th>
                      <th className="pb-2 font-medium">Arrive</th>
                      <th className="pb-2 font-medium">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {compareRoutes.map(route => {
                      const cFastest = compFastest !== null && route.durationMinutes === compFastest;
                      const cEarliestArr = compEarliestArr !== null && route.arrivalTime === compEarliestArr;
                      const cEarliestDep = compEarliestDep !== null && route.departureTime === compEarliestDep;
                      
                      return (
                        <tr key={route.id} className="text-white group">
                          <td className="py-3 pr-4 font-medium text-white/90 text-xs">
                            {route.isTransfer ? `🔄 via ${route.transferStopName}` : (route.originalData as any).route_name}
                          </td>
                          <td className="py-3 pr-4">
                            <div className="flex items-center gap-1">
                              <span className="font-bold">
                                {route.departureDisplay?.display_time}
                              </span>
                              {cEarliestDep && <span className="text-[9px] text-blue-400 font-bold uppercase">Best</span>}
                            </div>
                          </td>
                          <td className="py-3 pr-4">
                            <div className="flex items-center gap-1">
                              <span className="font-bold text-white/80">
                                {route.arrivalDisplay?.display_time}
                              </span>
                              {cEarliestArr && <span className="text-[9px] text-yellow-400 font-bold uppercase">Best</span>}
                            </div>
                          </td>
                          <td className="py-3 pr-4">
                            <div className="flex items-center gap-1 text-[#FF4500] font-bold">
                              {route.durationMinutes} min
                              {cFastest && <Zap size={12} />}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="bg-[#1a1a1a]/95 border border-[#FF4500]/50 backdrop-blur-xl p-2 rounded-full shadow-[0_10px_40px_rgba(255,69,0,0.3)] flex items-center justify-between w-full pointer-events-auto">
            <span className="text-sm font-semibold text-white ml-4 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-[#FF4500] animate-pulse" />
              {compareRouteIds.size} Selected
            </span>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => {
                  setCompareRouteIds(new Set());
                  setShowComparison(false);
                }}
                className="text-xs font-medium text-white/50 hover:text-white px-3 py-2 rounded-full transition-colors"
              >
                Clear
              </button>
              <button 
                onClick={() => setShowComparison(!showComparison)}
                disabled={compareRouteIds.size < 2}
                className={`text-sm font-semibold px-5 py-2 rounded-full transition-all flex items-center gap-2 ${
                  compareRouteIds.size >= 2 
                    ? 'bg-[#FF4500] text-white hover:bg-[#FF4500]/90 shadow-md' 
                    : 'bg-white/5 text-white/40 cursor-not-allowed border border-white/10'
                }`}
              >
                <BarChart2 size={16} />
                {showComparison ? 'Hide' : 'Compare'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
