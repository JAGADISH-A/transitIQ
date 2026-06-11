import { useState, useMemo } from 'react';
import { ArrowLeft, ArrowRight, Train, Zap, Trophy, BarChart2, Check, X } from 'lucide-react';
import TransferRouteCard from './TransferRouteCard';
import { RouteFlags } from './RouteFlags';

import { JourneyRoute, TransferJourney } from '../App';

interface JourneyExplorerProps {
  routes: JourneyRoute[];
  transferRoutes?: TransferJourney[];
  sourceName: string;
  destinationName: string;
  departureAfter?: string;
  onBack: () => void;
  onRouteSelect: (route: JourneyRoute) => void;
  onTransferRouteSelect?: (route: TransferJourney) => void;
}

export default function JourneyExplorer({
  routes,
  transferRoutes = [],
  sourceName,
  destinationName,
  departureAfter,
  onBack,
  onRouteSelect,
  onTransferRouteSelect
}: JourneyExplorerProps) {
  const [sortBy, setSortBy] = useState<'earliest_departure' | 'earliest_arrival' | 'shortest_duration' | 'quality'>('quality');
  const [compareRouteIds, setCompareRouteIds] = useState<Set<string>>(new Set());
  const [showComparison, setShowComparison] = useState(false);

  const [showTransfers, setShowTransfers] = useState(true);

  const compareRoutes = useMemo(() => {
    const direct = routes.filter(r => compareRouteIds.has(r.trip_id));
    const transfers = transferRoutes.filter(r => {
      const id = `transfer-${r.transfer_stop}-${r.first_leg.trip_id}-${r.second_leg.trip_id}`;
      return compareRouteIds.has(id);
    });
    return [...direct, ...transfers] as any[];
  }, [routes, transferRoutes, compareRouteIds]);

  const compFastest = useMemo(() => {
    let min = Infinity;
    compareRoutes.forEach(r => {
      const dur = r.journey_type === "TRANSFER" ? r.total_duration : r.duration_minutes;
      if (dur !== undefined && dur < min) {
        min = dur;
      }
    });
    return min !== Infinity ? min : null;
  }, [compareRoutes]);

  const compEarliestDep = useMemo(() => {
    if (compareRoutes.length === 0) return null;
    const deps = compareRoutes.map(r => r.journey_type === "TRANSFER" ? r.first_leg.departure_time : r.departure_time).filter(Boolean);
    if (deps.length === 0) return null;
    return deps.sort((a, b) => a!.localeCompare(b!))[0];
  }, [compareRoutes]);

  const compEarliestArr = useMemo(() => {
    if (compareRoutes.length === 0) return null;
    const arrs = compareRoutes.map(r => r.journey_type === "TRANSFER" ? r.second_leg.arrival_time : r.arrival_time).filter(Boolean);
    if (arrs.length === 0) return null;
    return arrs.sort((a, b) => a!.localeCompare(b!))[0];
  }, [compareRoutes]);

  // Deduplicate routes based on route_id/trip_id if needed, but since we want ALL departures, 
  // we should just show all unique trips.
  const displayRoutes = useMemo(() => {
    let sorted = [...routes];
    
    sorted.sort((a, b) => {
      if (sortBy === 'earliest_departure') {
        const timeA = a.departure_time || '99:99:99';
        const timeB = b.departure_time || '99:99:99';
        return timeA.localeCompare(timeB);
      } else if (sortBy === 'earliest_arrival') {
        const timeA = a.arrival_time || '99:99:99';
        const timeB = b.arrival_time || '99:99:99';
        return timeA.localeCompare(timeB);
      } else if (sortBy === 'shortest_duration') {
        const durA = a.duration_minutes ?? Infinity;
        const durB = b.duration_minutes ?? Infinity;
        return durA - durB;
      }
      return 0;
    });

    return sorted;
  }, [routes, sortBy]);

  // Summary Metrics
  const nextDeparture = useMemo(() => {
    const directDeps = routes.map(r => r.departure_time).filter(Boolean);
    const transferDeps = transferRoutes.map(r => r.first_leg.departure_time).filter(Boolean);
    const allDeps = [...directDeps, ...transferDeps] as string[];
    return allDeps.sort((a, b) => a.localeCompare(b))[0] || null;
  }, [routes, transferRoutes]);

  const fastestDuration = useMemo(() => {
    let min = Infinity;
    routes.forEach(r => {
      if (r.duration_minutes !== undefined && r.duration_minutes < min) {
        min = r.duration_minutes;
      }
    });
    transferRoutes.forEach(r => {
      if (r.total_duration !== undefined && r.total_duration < min) {
        min = r.total_duration;
      }
    });
    return min !== Infinity ? min : null;
  }, [routes, transferRoutes]);

  const earliestArrival = useMemo(() => {
    const directArrs = routes.map(r => r.arrival_time).filter(Boolean);
    const transferArrs = transferRoutes.map(r => r.second_leg.arrival_time).filter(Boolean);
    const allArrs = [...directArrs, ...transferArrs] as string[];
    return allArrs.sort((a, b) => a.localeCompare(b))[0] || null;
  }, [routes, transferRoutes]);

  return (
    <div className="flex flex-col h-full bg-[#0F0F0F] text-white relative">
      {/* Header */}
      <div className="flex items-center justify-between p-4 md:px-6 border-b border-white/5 bg-[#141414] sticky top-0 z-20 shadow-sm">
        <div className="flex items-center gap-4">
          <button 
            onClick={onBack}
            className="p-2 hover:bg-white/10 rounded-full transition-colors text-white/60 hover:text-white"
          >
            <ArrowLeft size={20} />
          </button>
          <div className="flex flex-col">
            <div className="flex items-center gap-2 text-lg font-bold tracking-tight">
              <span>{sourceName}</span>
              <ArrowRight size={14} className="text-white/40" />
              <span>{destinationName}</span>
            </div>
            <div className="text-sm font-medium text-white/50 flex items-center gap-1.5">
              <span>{routes.length + transferRoutes.length} Options</span>
              {departureAfter && (
                <>
                  <span className="w-1 h-1 rounded-full bg-white/20" />
                  <span>After {departureAfter}</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-4 md:p-6 overflow-y-auto custom-scrollbar">
        <div className="max-w-4xl mx-auto flex flex-col gap-6">
          
          {/* Route Comparison Summary */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="flex flex-col p-3 bg-[#1A1A1A] border border-white/5 rounded-xl">
              <span className="text-[10px] font-semibold text-blue-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                <Train size={12} /> Next Departure
              </span>
              <span className="text-lg font-bold text-white">{nextDeparture || '-'}</span>
            </div>

            <div className="flex flex-col p-3 bg-[#1A1A1A] border border-[#FF4500]/20 rounded-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                <Zap size={32} className="text-[#FF4500]" />
              </div>
              <span className="text-[10px] font-semibold text-[#FF4500] uppercase tracking-wider mb-1 flex items-center gap-1 relative z-10">
                <Zap size={12} /> Fastest
              </span>
              <span className="text-lg font-bold text-[#FF4500] relative z-10">{fastestDuration ? `${fastestDuration} min` : '-'}</span>
            </div>

            <div className="flex flex-col p-3 bg-[#1A1A1A] border border-white/5 rounded-xl">
              <span className="text-[10px] font-semibold text-yellow-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                <Trophy size={12} /> Earliest Arrival
              </span>
              <span className="text-lg font-bold text-white">{earliestArrival || '-'}</span>
            </div>

            <div className="flex flex-col p-3 bg-[#1A1A1A] border border-white/5 rounded-xl">
              <span className="text-[10px] font-semibold text-green-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                <BarChart2 size={12} /> Options
              </span>
              <span className="text-lg font-bold text-white">{routes.length + transferRoutes.length}</span>
            </div>
          </div>

          {/* Sorting Controls */}
          <div className="flex items-center gap-2 bg-[#1A1A1A] p-1 rounded-xl w-fit border border-white/5 flex-wrap">
            <span className="text-xs font-semibold text-white/50 uppercase tracking-wider px-3">Sort By</span>
            <button 
              onClick={() => setSortBy('quality')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${sortBy === 'quality' ? 'bg-[#2A2A2A] text-white shadow-sm' : 'text-white/50 hover:text-white/80'}`}
            >
              Quality Score
            </button>
            <button 
              onClick={() => setSortBy('earliest_departure')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${sortBy === 'earliest_departure' ? 'bg-[#2A2A2A] text-white shadow-sm' : 'text-white/50 hover:text-white/80'}`}
            >
              Departure
            </button>
            <button 
              onClick={() => setSortBy('earliest_arrival')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${sortBy === 'earliest_arrival' ? 'bg-[#2A2A2A] text-white shadow-sm' : 'text-white/50 hover:text-white/80'}`}
            >
              Arrival
            </button>
            <button 
              onClick={() => setSortBy('shortest_duration')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${sortBy === 'shortest_duration' ? 'bg-[#2A2A2A] text-white shadow-sm' : 'text-white/50 hover:text-white/80'}`}
            >
              Duration
            </button>
          </div>

          {/* Route List */}
          <div className="flex flex-col gap-3 pb-24">
            {displayRoutes.map((route) => {
              const isNextDeparture = nextDeparture && route.departure_time === nextDeparture;
              const isFastest = fastestDuration !== null && route.duration_minutes === fastestDuration;
              const isEarliestArrival = earliestArrival && route.arrival_time === earliestArrival;
              const isComparing = compareRouteIds.has(route.trip_id);

              return (
                <div 
                  key={route.trip_id}
                  onClick={() => onRouteSelect(route)}
                  className="flex flex-col p-4 bg-[#141414] border border-white/10 rounded-2xl hover:bg-[#1A1A1A] hover:border-white/20 transition-all cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex flex-wrap items-center gap-2">
                       {/* Badges */}
                       {route.quality && (
                         <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                           route.quality.classification === 'Rejected' ? 'bg-red-500/10 text-red-400' :
                           route.quality.classification === 'Excellent' ? 'bg-[#10B981]/10 text-[#10B981]' :
                           route.quality.classification === 'Good' ? 'bg-[#3B82F6]/10 text-[#3B82F6]' :
                           route.quality.classification === 'Acceptable' ? 'bg-yellow-500/10 text-yellow-400' :
                           'bg-[#FF4500]/10 text-[#FF4500]'
                         }`}>
                           {route.quality.classification === 'Excellent' ? '⭐ Excellent' : route.quality.classification} ({Math.round(route.quality.score)})
                         </span>
                       )}
                       {isNextDeparture && <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded">🚆 Next Departure</span>}
                       {isFastest && <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF4500] bg-[#FF4500]/10 px-2 py-0.5 rounded">⚡ Fastest</span>}
                       {isEarliestArrival && <span className="text-[10px] font-bold uppercase tracking-wider text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">🏆 Earliest Arrival</span>}
                    </div>

                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        const newSet = new Set(compareRouteIds);
                        if (isComparing) {
                          newSet.delete(route.trip_id);
                          if (newSet.size === 0) setShowComparison(false);
                        } else {
                          if (newSet.size >= 3) return;
                          newSet.add(route.trip_id);
                        }
                        setCompareRouteIds(newSet);
                      }}
                      className={`text-xs font-medium px-2.5 py-1 rounded-full transition-colors border flex items-center gap-1 ${
                        isComparing 
                          ? 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/20' 
                          : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10 hover:text-white'
                      }`}
                    >
                      {isComparing ? <><Check size={12} /> Added</> : 'Compare'}
                    </button>
                  </div>

                  {/* Departure -> Arrival */}
                  <div className="flex items-center gap-3 mb-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xl font-bold text-white tracking-tight">{route.departure_display?.display_time}</span>
                      {route.departure_display && route.departure_display.day_offset > 0 && (
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF4500] bg-[#FF4500]/10 px-1 py-0.5 rounded">
                          +{route.departure_display.day_offset}
                        </span>
                      )}
                    </div>
                    <ArrowRight className="text-white/20" size={16} />
                    <div className="flex items-center gap-1.5">
                      <span className="text-xl font-bold text-white/80 tracking-tight">{route.arrival_display?.display_time}</span>
                      {route.arrival_display && route.arrival_display.day_offset > 0 && (
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF4500] bg-[#FF4500]/10 px-1 py-0.5 rounded">
                          +{route.arrival_display.day_offset}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Route Name */}
                    <div className="flex items-center gap-3">
                      <span className="font-medium text-white/90 truncate">{route.route_name}</span>
                      {route.quality?.recommendation_reason && (
                        <div className="text-[11px] text-emerald-400 mt-0.5">
                          • {route.quality.recommendation_reason}
                        </div>
                      )}
                      <RouteFlags flags={route.quality?.route_flags} />
                    </div>

                  {/* Duration • Stops */}
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <span className="text-[#FF4500]">{route.duration_minutes !== undefined ? `${route.duration_minutes} min` : '-'}</span>
                    <span className="w-1 h-1 rounded-full bg-white/20" />
                    <span className="text-white/50">{route.stops_between} stops</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Transfer Routes Section */}
          {transferRoutes && transferRoutes.length > 0 && (
            <div className="mb-24 flex flex-col gap-4">
              <button 
                onClick={() => setShowTransfers(!showTransfers)}
                className="w-full flex items-center justify-between p-4 bg-[#1A1A1A] border border-white/10 rounded-xl hover:bg-[#222] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-[#FF5A00] text-xl">🔄</span>
                  <span className="font-semibold text-white">Transfer Options ({transferRoutes.length})</span>
                </div>
                <ArrowRight className={`w-5 h-5 text-white/40 transition-transform duration-300 ${showTransfers ? 'rotate-90' : ''}`} />
              </button>
              
              {showTransfers && (
                <div className="flex flex-col gap-3">
                  {transferRoutes.map((tRoute, idx) => {
                    const id = `transfer-${tRoute.transfer_stop}-${tRoute.first_leg.trip_id}-${tRoute.second_leg.trip_id}`;
                    const isComparing = compareRouteIds.has(id);
                    
                    return (
                      <TransferRouteCard 
                        key={idx}
                        route={tRoute}
                        isCompareSelected={isComparing}
                        onCompareToggle={(routeId) => {
                          const newSet = new Set(compareRouteIds);
                          if (isComparing) {
                            newSet.delete(routeId);
                            if (newSet.size === 0) setShowComparison(false);
                          } else {
                            if (newSet.size >= 3) return;
                            newSet.add(routeId);
                          }
                          setCompareRouteIds(newSet);
                        }}
                        onClick={() => {
                          if (onTransferRouteSelect) {
                            onTransferRouteSelect(tRoute);
                          }
                        }}
                      />
                    );
                  })}
                </div>
              )}
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
                      const isTransfer = route.journey_type === "TRANSFER";
                      const id = isTransfer ? `transfer-${route.transfer_stop}-${route.first_leg.trip_id}-${route.second_leg.trip_id}` : route.trip_id;
                      
                      const cFastest = compFastest !== null && (isTransfer ? route.total_duration === compFastest : route.duration_minutes === compFastest);
                      const cEarliestArr = compEarliestArr !== null && (isTransfer ? route.second_leg.arrival_time === compEarliestArr : route.arrival_time === compEarliestArr);
                      const cEarliestDep = compEarliestDep !== null && (isTransfer ? route.first_leg.departure_time === compEarliestDep : route.departure_time === compEarliestDep);
                      
                      return (
                        <tr key={id} className="text-white group">
                          <td className="py-2 pr-4 font-medium text-white/90 text-xs">
                            {isTransfer ? `🔄 via ${route.transfer_stop}` : route.route_name}
                          </td>
                          <td className="py-2 pr-4">
                            <div className="flex items-center gap-1">
                              <span className="font-bold">
                                {isTransfer ? route.first_leg.departure_display?.display_time : route.departure_display?.display_time}
                              </span>
                              {cEarliestDep && <span className="text-[9px] text-blue-400 font-bold uppercase">Best</span>}
                            </div>
                          </td>
                          <td className="py-2 pr-4">
                            <div className="flex items-center gap-1">
                              <span className="font-bold text-white/80">
                                {isTransfer ? route.second_leg.arrival_display?.display_time : route.arrival_display?.display_time}
                              </span>
                              {cEarliestArr && <span className="text-[9px] text-yellow-400 font-bold uppercase">Best</span>}
                            </div>
                          </td>
                          <td className="py-2 pr-4">
                            <div className="flex items-center gap-1 text-[#FF4500] font-bold">
                              {isTransfer ? route.total_duration : route.duration_minutes} min
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

          <div className="bg-[#1A1A1A] border border-white/10 p-2 rounded-full shadow-2xl flex items-center justify-between w-full">
            <span className="text-sm font-medium text-white ml-4">
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
                className={`text-sm font-semibold px-4 py-2 rounded-full transition-all flex items-center gap-2 ${
                  compareRouteIds.size >= 2 
                    ? 'bg-white text-black hover:bg-gray-200' 
                    : 'bg-white/10 text-white/40 cursor-not-allowed'
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
