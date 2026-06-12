import { useState, useMemo } from 'react';
import { ArrowLeft, Zap, BarChart2, X } from 'lucide-react';
import { RoutePreview } from './RoutePreview';

import type { NormalizedRoute } from '../types/transit';

interface JourneyExplorerProps {
  routes: NormalizedRoute[];
  sourceName: string;
  destinationName: string;
  onBack: () => void;
  onRouteSelect: (route: NormalizedRoute) => void;
}

export default function JourneyExplorer({
  routes: normalizedRoutes,
  sourceName,
  destinationName,
  onBack,
  onRouteSelect
}: JourneyExplorerProps) {
  const [sortBy, setSortBy] = useState<'earliest_departure' | 'earliest_arrival' | 'shortest_duration' | 'quality'>('quality');
  const [compareRouteIds, setCompareRouteIds] = useState<Set<string>>(new Set());
  const [showComparison, setShowComparison] = useState(false);


  const compareRoutes = useMemo(() => {
    return normalizedRoutes.filter(r => compareRouteIds.has(r.id));
  }, [normalizedRoutes, compareRouteIds]);

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

  const displayRoutes = useMemo(() => {
    let sorted = [...normalizedRoutes];
    
    sorted.sort((a, b) => {
      if (sortBy === 'earliest_departure') {
        const timeA = a.departureTime || '99:99:99';
        const timeB = b.departureTime || '99:99:99';
        if (timeA === timeB) return a.transferCount - b.transferCount;
        return timeA.localeCompare(timeB);
      } else if (sortBy === 'earliest_arrival') {
        const timeA = a.arrivalTime || '99:99:99';
        const timeB = b.arrivalTime || '99:99:99';
        if (timeA === timeB) return a.transferCount - b.transferCount;
        return timeA.localeCompare(timeB);
      } else if (sortBy === 'shortest_duration') {
        if (a.durationMinutes === b.durationMinutes) return a.transferCount - b.transferCount;
        return a.durationMinutes - b.durationMinutes;
      }
      return 0;
    });

    return sorted;
  }, [normalizedRoutes, sortBy]);

  const categorizedRoutes = useMemo(() => {
    // Sort by quality score (lower is better)
    const byQuality = [...normalizedRoutes].sort((a, b) => a.qualityScore - b.qualityScore);

    const recommended = byQuality[0];
    const seenIds = new Set<string>();

    if (recommended) {
      seenIds.add(recommended.id);
    }

    const byDuration = [...normalizedRoutes].sort((a, b) => {
      if (a.durationMinutes === b.durationMinutes) return a.transferCount - b.transferCount;
      return a.durationMinutes - b.durationMinutes;
    });

    const fastest = [];
    for (const r of byDuration) {
       if (!seenIds.has(r.id)) {
         fastest.push(r);
         seenIds.add(r.id);
         if (fastest.length >= 3) break;
       }
    }

    const byDeparture = [...normalizedRoutes].sort((a, b) => {
       const depA = a.departureTime || '99:99:99';
       const depB = b.departureTime || '99:99:99';
       if (depA === depB) return a.transferCount - b.transferCount;
       return depA.localeCompare(depB);
    });

    const earliest = [];
    for (const r of byDeparture) {
       if (!seenIds.has(r.id)) {
         earliest.push(r);
         seenIds.add(r.id);
         if (earliest.length >= 3) break;
       }
    }

    const fewestTransfers = [];
    const directSorted = [...normalizedRoutes]
      .filter(r => r.transferCount === 0)
      .sort((a, b) => a.durationMinutes - b.durationMinutes);
      
    for (const r of directSorted) {
       if (!seenIds.has(r.id)) {
         fewestTransfers.push(r);
         seenIds.add(r.id);
         if (fewestTransfers.length >= 3) break;
       }
    }

    const remaining = [];
    for (const r of normalizedRoutes) {
       if (!seenIds.has(r.id)) {
         remaining.push(r);
       }
    }

    return { recommended, fastest, earliest, fewestTransfers, remaining };
  }, [normalizedRoutes]);

  const [showRemaining, setShowRemaining] = useState(false);
  const isDefaultSort = sortBy === 'quality';

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

  return (
    <div className="flex flex-col h-full bg-transparent text-white relative">
      {/* Header */}
      <div className="flex items-center justify-between p-4 md:px-8 border-b border-white/5 bg-transparent sticky top-0 z-20 backdrop-blur-md">
        <div className="flex items-center gap-6 w-full">
          <button 
            onClick={onBack}
            className="flex items-center gap-2 text-[13px] font-medium text-zinc-300 hover:text-white transition-colors h-9 px-[14px] rounded-full bg-white/[0.05] border border-white/[0.08] backdrop-blur-md shrink-0"
          >
            <ArrowLeft size={14} />
            Back to Search Results
          </button>
          
          <div className="flex flex-col flex-1">
            <div className="text-xl font-semibold tracking-tight text-white">
              Explore All Routes
            </div>
            <div className="text-[13px] font-medium text-zinc-400">
              {normalizedRoutes.length} route options found between {sourceName} and {destinationName}
            </div>
          </div>
          
          <button 
            onClick={onBack}
            className="w-9 h-9 rounded-full bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/[0.1] transition-all backdrop-blur-md shrink-0"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-4 md:px-8 pb-32 overflow-y-auto custom-scrollbar pointer-events-auto">
        <div className="flex flex-col gap-6 max-w-[1600px] mx-auto w-full">
          {/* Header row: Toolbar / Sorting */}
          <div className="flex items-center justify-between bg-white/[0.02] border border-white/10 backdrop-blur-md rounded-[20px] p-2 sticky top-0 z-10">
            <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar">
              <span className="text-[11px] font-bold text-zinc-500 uppercase tracking-widest px-4 shrink-0">Sort By</span>
              <button onClick={() => setSortBy('shortest_duration')} className={`shrink-0 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${sortBy === 'shortest_duration' ? 'bg-[#FF4500]/20 text-[#FF4500] border border-[#FF4500]/30 shadow-[0_0_15px_rgba(255,69,0,0.1)]' : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'}`}>Duration</button>
              <button onClick={() => setSortBy('earliest_departure')} className={`shrink-0 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${sortBy === 'earliest_departure' ? 'bg-[#FF4500]/20 text-[#FF4500] border border-[#FF4500]/30 shadow-[0_0_15px_rgba(255,69,0,0.1)]' : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'}`}>Departure</button>
              <button onClick={() => setSortBy('earliest_arrival')} className={`shrink-0 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${sortBy === 'earliest_arrival' ? 'bg-[#FF4500]/20 text-[#FF4500] border border-[#FF4500]/30 shadow-[0_0_15px_rgba(255,69,0,0.1)]' : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'}`}>Arrival</button>
              <button onClick={() => setSortBy('quality')} className={`shrink-0 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${sortBy === 'quality' ? 'bg-[#FF4500]/20 text-[#FF4500] border border-[#FF4500]/30 shadow-[0_0_15px_rgba(255,69,0,0.1)]' : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'}`}>Quality</button>
            </div>
            
            {/* Compare Floating Button when selected - MOVED TO BOTTOM */}
            <div className="pr-2 shrink-0"></div>
          </div>

          {isDefaultSort ? (
            <div className="flex flex-col gap-10">
              {categorizedRoutes.recommended && (
                <section>
                  <h3 className="text-lg font-bold text-white mb-4 tracking-tight">Recommended Route</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    <RoutePreview
                      route={categorizedRoutes.recommended}
                      isHero={true}
                      onClick={() => handleRouteSelect(categorizedRoutes.recommended)}
                      isCompared={compareRouteIds.has(categorizedRoutes.recommended.id)}
                      onCompareToggle={(e) => handleCompareToggle(e, categorizedRoutes.recommended.id)}
                    />
                  </div>
                </section>
              )}

              {categorizedRoutes.fastest.length > 0 && (
                <section>
                  <h3 className="text-lg font-bold text-white mb-4 tracking-tight flex items-center gap-2">
                    Fastest Routes
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {categorizedRoutes.fastest.map((route) => (
                      <RoutePreview
                        key={route.id}
                        route={route}
                        onClick={() => handleRouteSelect(route)}
                        isCompared={compareRouteIds.has(route.id)}
                        onCompareToggle={(e) => handleCompareToggle(e, route.id)}
                      />
                    ))}
                  </div>
                </section>
              )}

              {categorizedRoutes.earliest.length > 0 && (
                <section>
                  <h3 className="text-lg font-bold text-white mb-4 tracking-tight flex items-center gap-2">
                    Earliest Departure
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {categorizedRoutes.earliest.map((route) => (
                      <RoutePreview
                        key={route.id}
                        route={route}
                        onClick={() => handleRouteSelect(route)}
                        isCompared={compareRouteIds.has(route.id)}
                        onCompareToggle={(e) => handleCompareToggle(e, route.id)}
                      />
                    ))}
                  </div>
                </section>
              )}

              {categorizedRoutes.fewestTransfers.length > 0 && (
                <section>
                  <h3 className="text-lg font-bold text-white mb-4 tracking-tight flex items-center gap-2">
                    Fewest Transfers
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {categorizedRoutes.fewestTransfers.map((route) => (
                      <RoutePreview
                        key={route.id}
                        route={route}
                        onClick={() => handleRouteSelect(route)}
                        isCompared={compareRouteIds.has(route.id)}
                        onCompareToggle={(e) => handleCompareToggle(e, route.id)}
                      />
                    ))}
                  </div>
                </section>
              )}

              {categorizedRoutes.remaining.length > 0 && (
                <section className="pb-10">
                  <button 
                    onClick={() => setShowRemaining(!showRemaining)}
                    className="w-full py-4 rounded-[20px] border border-white/10 bg-white/[0.02] hover:bg-white/[0.05] transition-all text-sm font-semibold text-white/70 hover:text-white"
                  >
                    {showRemaining ? 'Hide Remaining Options' : `Show ${categorizedRoutes.remaining.length} More Options`}
                  </button>

                  {showRemaining && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mt-6 animate-in fade-in slide-in-from-top-4">
                      {categorizedRoutes.remaining.map((route) => (
                        <RoutePreview
                          key={route.id}
                          route={route}
                          onClick={() => handleRouteSelect(route)}
                          isCompared={compareRouteIds.has(route.id)}
                          onCompareToggle={(e) => handleCompareToggle(e, route.id)}
                        />
                      ))}
                    </div>
                  )}
                </section>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {displayRoutes.map((route) => (
                <RoutePreview
                  key={route.id}
                  route={route}
                  onClick={() => handleRouteSelect(route)}
                  isCompared={compareRouteIds.has(route.id)}
                  onCompareToggle={(e) => handleCompareToggle(e, route.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Floating Action Bar */}
      {compareRouteIds.size > 0 && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 flex flex-col items-center w-[90vw] max-w-2xl">
          {showComparison && (
            <div className="w-full bg-[#1A1A1A] border border-white/10 p-4 rounded-2xl shadow-2xl mb-4 animate-in fade-in slide-in-from-bottom-4">
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
                          <td className="py-2 pr-4 font-medium text-white/90 text-xs">
                            {route.isTransfer ? `🔄 via ${route.transferStopName}` : (route.originalData as any).route_name}
                          </td>
                          <td className="py-2 pr-4">
                            <div className="flex items-center gap-1">
                              <span className="font-bold">
                                {route.departureDisplay?.display_time}
                              </span>
                              {cEarliestDep && <span className="text-[9px] text-blue-400 font-bold uppercase">Best</span>}
                            </div>
                          </td>
                          <td className="py-2 pr-4">
                            <div className="flex items-center gap-1">
                              <span className="font-bold text-white/80">
                                {route.arrivalDisplay?.display_time}
                              </span>
                              {cEarliestArr && <span className="text-[9px] text-yellow-400 font-bold uppercase">Best</span>}
                            </div>
                          </td>
                          <td className="py-2 pr-4">
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

          <div className="bg-[#FF4500]/10 border border-[#FF4500]/30 backdrop-blur-md p-2 rounded-full shadow-[0_10px_40px_rgba(255,69,0,0.2)] flex items-center justify-between w-full">
            <span className="text-sm font-semibold text-[#FF4500] ml-4">
              {compareRouteIds.size} Route{compareRouteIds.size !== 1 ? 's' : ''} Selected
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
                {showComparison ? 'Hide Comparison' : 'Compare Selected Routes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
