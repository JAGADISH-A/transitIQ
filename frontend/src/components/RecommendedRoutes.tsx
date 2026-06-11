import { useState, useRef, useEffect } from 'react';
import { Train, Bus, Zap, X, Loader2 } from 'lucide-react';
import FullRouteExplorer from './FullRouteExplorer';
import { GlobalAlertModal } from './GlobalAlertModal';
import { JourneyRoute } from '../App';
import { RouteFlags } from './RouteFlags';
interface RecommendedRoutesProps {
  routes?: JourneyRoute[];
  transferRoutes?: any[];
  isLoading?: boolean;
  selectedRoute?: JourneyRoute | null;
  selectedTransferRoute?: any | null;
  onRouteSelect?: (route: JourneyRoute) => void;
  onTransferRouteSelect?: (route: any) => void;
  viewMode?: 'journey' | 'full';
  onViewModeChange?: (mode: 'journey' | 'full') => void;
  onViewAll?: () => void;
  tripStops?: any[];
}

export default function RecommendedRoutes({ 
  routes = [], 
  transferRoutes = [],
  isLoading = false, 
  selectedRoute = null, 
  selectedTransferRoute = null,
  onRouteSelect,
  onTransferRouteSelect,
  viewMode = 'journey',
  onViewModeChange,
  onViewAll,
  tripStops = []
}: RecommendedRoutesProps) {
  const [showExplorer, setShowExplorer] = useState(false);
  const [hasDismissedWarning, setHasDismissedWarning] = useState(false);
  const selectedRouteRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHasDismissedWarning(false);
  }, [routes, transferRoutes]);

  useEffect(() => {
    if (selectedRoute) {
      setTimeout(() => {
        selectedRouteRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        });
      }, 50);
    }
  }, [selectedRoute?.trip_id]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 mt-2">
        <h3 className="text-lg font-medium text-white/90">Recommended Routes</h3>
        <div className="flex items-center justify-center p-12 border border-white/10 rounded-2xl bg-[#1A1A1A]">
          <Loader2 className="animate-spin text-[#FF4500]" size={32} />
        </div>
      </div>
    );
  }

  if (routes.length === 0 && transferRoutes.length === 0) {
    return (
      <div className="flex flex-col gap-4 mt-2">
        <h3 className="text-lg font-medium text-white/90">Recommended Routes</h3>
        <div className="flex items-center justify-center p-12 border border-white/10 rounded-2xl bg-[#1A1A1A]">
          <p className="text-white/50">Search for a journey to see recommended routes.</p>
        </div>
      </div>
    );
  }

  const uniqueRoutes: JourneyRoute[] = [];
  const seenRouteIds = new Set<string>();
  
  for (const route of routes) {
    if (!seenRouteIds.has(route.route_id)) {
      seenRouteIds.add(route.route_id);
      uniqueRoutes.push(route);
    }
  }

  // Filter out rejected routes from top 3
  const validUniqueRoutes = uniqueRoutes.filter(r => r.quality?.classification !== "Rejected");

  let displayRoutes = validUniqueRoutes.slice(0, 3);

  if (selectedRoute) {
    const isSelectedInTop3 = displayRoutes.some(r => r.trip_id === selectedRoute.trip_id);
    if (!isSelectedInTop3) {
      displayRoutes = [selectedRoute, ...displayRoutes];
    }
  }

  // Same for transfers
  const validTransfers = transferRoutes.filter(r => r.quality?.classification !== "Rejected");
  let displayTransfers = validTransfers.slice(0, 3);

  if (selectedTransferRoute) {
    const isSelectedInTop3 = displayTransfers.some(
      r => r.first_leg.trip_id === selectedTransferRoute.first_leg.trip_id &&
           r.second_leg.trip_id === selectedTransferRoute.second_leg.trip_id
    );
    if (!isSelectedInTop3) {
      displayTransfers = [selectedTransferRoute, ...displayTransfers];
    }
  }



  return (
    <div className="flex flex-col gap-4 mt-2">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-white/90">
            {selectedRoute || selectedTransferRoute ? 'Route Details' : 'Recommended Routes'}
          </h3>
        </div>
        
        {selectedRoute && (
          <div className="flex p-1 bg-white/5 rounded-lg border border-white/10 w-fit">
            <button
              onClick={() => onViewModeChange?.('journey')}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                viewMode === 'journey' 
                  ? 'bg-white/10 text-white shadow-sm' 
                  : 'text-white/50 hover:text-white/80'
              }`}
            >
              Journey View
            </button>
            <button
              onClick={() => onViewModeChange?.('full')}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                viewMode === 'full' 
                  ? 'bg-white/10 text-white shadow-sm' 
                  : 'text-white/50 hover:text-white/80'
              }`}
            >
              Full Route View
            </button>
          </div>
        )}
      </div>
      
      <div className="flex flex-col gap-4 pb-4">
        {displayRoutes.map((route, index) => {
          // Attempt to guess the type based on the feed or route name
          const isBus = route.feed.toLowerCase().includes('bus') || route.route_name.toLowerCase().includes('bus');
          const type = isBus ? 'Bus' : 'Train';
          const icon = isBus ? <Bus size={14} className="text-white/70" /> : <Train size={14} className="text-white/70" />;
          
          const isSelected = selectedRoute?.trip_id === route.trip_id;
          const isAnotherSelected = selectedRoute && !isSelected;

          const baseClasses = "relative flex flex-col p-5 rounded-2xl border group transition-all duration-300 animate-slide-in-left overflow-hidden";
          
          let stateClasses = "";
          if (isSelected) {
            stateClasses = "border-white/10 bg-[#222222] shadow-[0_0_20px_rgba(255,69,0,0.1)] cursor-default";
          } else if (isAnotherSelected) {
            stateClasses = "border-white/5 bg-[#1A1A1A] opacity-60 hover:opacity-100 hover:bg-[#222222] cursor-pointer";
          } else {
            stateClasses = "border-white/10 bg-[#1A1A1A] hover:bg-[#222222] cursor-pointer";
          }

          return (
            <div 
              key={route.trip_id} 
              ref={isSelected ? selectedRouteRef : null}
              onClick={() => {
                if (!isSelected) onRouteSelect?.(route);
              }}
              className={`${baseClasses} ${stateClasses}`}
              style={{ 
                zIndex: isSelected ? 50 : 10 - index,
                animationDelay: `${index * 100}ms` 
              }}
            >
              {isSelected && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#FF4500]" />}
              
              {/* Route Name and Badges */}
              <div className={`flex flex-col gap-3 ${isSelected ? 'mb-5' : 'mb-4'}`}>
                {/* Top Row: Badge & Close Button */}
                <div className="flex items-start justify-between">
                    return (
                      <div className="flex items-center gap-2">
                        {isSelected && (
                          <div className="text-xs px-2 py-1 rounded-md font-semibold shrink-0 bg-[#10B981]/20 text-[#10B981]">
                            ✅ Selected Route
                          </div>
                        )}
                        {route.quality && !isSelected && (
                          <div className={`text-xs px-2 py-1 rounded-md font-semibold shrink-0 ${
                            route.quality.classification === 'Excellent' ? 'bg-[#10B981]/20 text-[#10B981]' :
                            route.quality.classification === 'Good' ? 'bg-[#3B82F6]/20 text-[#3B82F6]' :
                            route.quality.classification === 'Acceptable' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-[#FF4500]/20 text-[#FF4500]'
                          }`}>
                            {route.quality.classification === 'Excellent' ? '⭐ Excellent' : route.quality.classification} ({Math.round(route.quality.score)})
                          </div>
                        )}
                      </div>
                    );
                  })()}
                  
                  {isSelected && (
                    <button 
                      onClick={(e) => {
                        e.stopPropagation();
                        onRouteSelect?.(null as any);
                      }}
                      className="p-1.5 hover:bg-white/10 rounded-full transition-colors text-white/60 hover:text-white -mt-1 -mr-1"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>

                {/* Content */}
                {!isSelected ? (
                  <>
                    <div className="flex flex-col gap-0.5">
                      {route.departure_display && (
                        <div className="flex items-center gap-2">
                          <div className="text-xl font-bold text-white tracking-wide">
                            {route.departure_display.display_time}
                          </div>
                          {route.departure_display.day_offset > 0 && (
                            <span className="text-[10px] font-bold bg-[#FF4500]/20 text-[#FF4500] px-1.5 py-0.5 rounded uppercase tracking-wider">
                              +{route.departure_display.day_offset} Day
                            </span>
                          )}
                        </div>
                      )}
                      <h4 className="text-base leading-tight text-white/80 font-medium" title={route.route_name}>
                        {route.route_name}
                      </h4>
                      {route.quality?.recommendation_reason && (
                        <div className="text-xs text-[#10B981] mt-0.5 font-medium">{route.quality.recommendation_reason}</div>
                      )}
                      <RouteFlags flags={route.quality?.route_flags} />
                      {(route.arrival_display || route.duration_minutes !== undefined) && (
                        <div className="flex flex-col gap-0.5 mt-1.5 text-sm font-medium text-white/60">
                          {route.arrival_display && (
                            <div className="flex items-center gap-1.5">
                              Arrives {route.arrival_display.display_time}
                              {route.arrival_display.day_offset > 0 && (
                                <span className="text-[10px] font-bold bg-[#FF4500]/20 text-[#FF4500] px-1.5 py-0.5 rounded uppercase tracking-wider">
                                  +{route.arrival_display.day_offset} Day
                               </span>
                              )}
                            </div>
                          )}
                          {route.duration_minutes !== undefined && <div>Duration {route.duration_minutes} min</div>}
                        </div>
                      )}
                    </div>
                    {/* Bottom Metadata */}
                    <div className="mt-auto pt-4 border-t border-white/5 flex flex-col gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium text-white/70 bg-white/10 px-2.5 py-1 rounded-md">
                          {route.stops_between} stops
                        </span>
                        <span className="text-xs font-medium text-white/70 bg-white/10 px-2.5 py-1 rounded-md capitalize">
                          {route.feed.toLowerCase()}
                        </span>
                        <div className="flex items-center gap-1.5 text-xs font-medium text-white/70 bg-white/10 px-2.5 py-1 rounded-md">
                          {icon}
                          <span>{type}</span>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1.5">
                        <Zap size={14} className="text-[#10B981]" />
                        <span className="text-xs font-medium text-white/60">Direct Route</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col gap-5 animate-in fade-in duration-300">
                    <h4 className="text-lg leading-tight text-white font-bold" title={route.route_name}>
                      {route.route_name}
                    </h4>
                    <div className="flex flex-col gap-3 bg-white/5 p-4 rounded-xl border border-white/10">
                      <div>
                        <div className="text-xs text-white/50 mb-0.5">Departs:</div>
                        <div className="flex items-center gap-1.5">
                          <div className="text-sm font-bold text-white">{route.departure_display?.display_time || '-'}</div>
                          {route.departure_display && route.departure_display.day_offset > 0 && (
                            <span className="text-[10px] font-bold bg-[#FF4500]/20 text-[#FF4500] px-1.5 py-0.5 rounded uppercase tracking-wider">
                              +{route.departure_display.day_offset} Day
                            </span>
                          )}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-white/50 mb-0.5">Arrives:</div>
                        <div className="flex items-center gap-1.5">
                          <div className="text-sm font-bold text-white">{route.arrival_display?.display_time || '-'}</div>
                          {route.arrival_display && route.arrival_display.day_offset > 0 && (
                            <span className="text-[10px] font-bold bg-[#FF4500]/20 text-[#FF4500] px-1.5 py-0.5 rounded uppercase tracking-wider">
                              +{route.arrival_display.day_offset} Day
                            </span>
                          )}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-white/50 mb-0.5">Duration:</div>
                        <div className="text-sm font-bold text-white">{route.duration_minutes !== undefined ? `${route.duration_minutes} min` : '-'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-white/50 mb-0.5">Stops:</div>
                        <div className="text-sm font-bold text-white">{route.stops_between}</div>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowExplorer(true);
                      }}
                      className="w-full mt-2 bg-white/10 hover:bg-white/20 text-white font-medium py-2 rounded-xl transition-colors border border-white/10 text-sm"
                    >
                      View Full Route
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* NO DIRECT ROUTES BANNER replaced by GlobalAlertModal */}
      <GlobalAlertModal
        isOpen={routes.length === 0 && transferRoutes.length > 0 && !hasDismissedWarning}
        onClose={() => setHasDismissedWarning(true)}
        title="Routing Update"
        message="No direct routes are currently available between these locations. We've found the best transfer options for your journey."
      />

      {/* TRANSFER ROUTES SECTION */}
      {routes.length === 0 && transferRoutes.length > 0 && (
        <div className="flex flex-col gap-4 pb-4">
          <h3 className="text-lg font-medium text-white/90 mt-2 flex items-center gap-2">
            🔄 Transfer Options ({transferRoutes.length})
          </h3>
          {displayTransfers.map((route, index) => {
            const isSelected = selectedTransferRoute && 
              selectedTransferRoute.first_leg.trip_id === route.first_leg.trip_id &&
              selectedTransferRoute.second_leg.trip_id === route.second_leg.trip_id;
            const isAnotherSelected = (selectedRoute || selectedTransferRoute) && !isSelected;

            const baseClasses = "relative flex flex-col p-5 rounded-2xl border group transition-all duration-300 animate-slide-in-left overflow-hidden";
            let stateClasses = "";
            if (isSelected) {
              stateClasses = "border-white/10 bg-[#222222] shadow-[0_0_20px_rgba(255,90,0,0.1)] cursor-default";
            } else if (isAnotherSelected) {
              stateClasses = "border-white/5 bg-[#1A1A1A] opacity-60 hover:opacity-100 hover:bg-[#222222] cursor-pointer";
            } else {
              stateClasses = "border-white/10 bg-[#1A1A1A] hover:bg-[#222222] cursor-pointer";
            }

            return (
              <div 
                key={`transfer-${index}`}
                onClick={() => {
                  if (!isSelected) {
                    onRouteSelect?.(null as any);
                    onTransferRouteSelect?.(route);
                  }
                }}
                className={`${baseClasses} ${stateClasses}`}
                style={{ zIndex: isSelected ? 50 : 10 - index, animationDelay: `${index * 100}ms` }}
              >
                {isSelected && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#FF5A00]" />}
                
                <div className={`flex flex-col gap-3 ${isSelected ? 'mb-5' : 'mb-4'}`}>
                  {/* Top Row: Badge & Close Button */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <div className={`text-xs px-2 py-1 rounded-md font-semibold shrink-0 ${isSelected ? 'bg-[#10B981]/20 text-[#10B981]' : 'bg-[#FF5A00]/10 text-[#FF5A00]'}`}>
                        {isSelected ? "✅ Selected Route" : "🔄 1 Transfer"}
                      </div>
                      {route.quality && !isSelected && (
                        <div className={`text-xs px-2 py-1 rounded-md font-semibold shrink-0 ${
                          route.quality.classification === 'Excellent' ? 'bg-[#10B981]/20 text-[#10B981]' :
                          route.quality.classification === 'Good' ? 'bg-[#3B82F6]/20 text-[#3B82F6]' :
                          route.quality.classification === 'Acceptable' ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-[#FF4500]/20 text-[#FF4500]'
                        }`}>
                          {route.quality.classification === 'Excellent' ? '⭐ Excellent' : route.quality.classification} ({Math.round(route.quality.score)})
                        </div>
                      )}
                    </div>
                    {isSelected && (
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          onTransferRouteSelect?.(null as any);
                        }}
                        className="p-1.5 hover:bg-white/10 rounded-full transition-colors text-white/60 hover:text-white -mt-1 -mr-1"
                      >
                        <X size={16} />
                      </button>
                    )}
                  </div>
                  
                  {/* Content */}
                  {!isSelected ? (
                    <>
                      <div className="flex flex-col gap-0.5">
                        <div className="text-lg font-bold text-white tracking-wide flex items-center gap-2">
                          <span className="truncate">{route.first_leg.source_stop}</span>
                        </div>
                        <div className="text-[#FF5A00] font-medium text-sm my-0.5 flex items-center gap-1.5">
                          <span>↓</span> Transfer at {route.transfer_stop}
                        </div>
                        <div className="text-lg font-bold text-white tracking-wide flex items-center gap-2">
                          <span className="truncate">{route.second_leg.destination_stop}</span>
                        </div>
                        {route.quality?.recommendation_reason && (
                          <div className="text-xs text-[#3B82F6] mt-0.5 font-medium">{route.quality.recommendation_reason}</div>
                        )}
                        <RouteFlags flags={route.quality?.route_flags} />
                      </div>
                      
                      <div className="mt-auto pt-4 border-t border-white/5 grid grid-cols-2 gap-y-2 gap-x-4">
                        <div className="flex flex-col">
                          <span className="text-[10px] text-white/40 uppercase tracking-wider font-semibold">Total Duration</span>
                          <span className="text-sm font-bold text-white">{route.total_duration} min</span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[10px] text-white/40 uppercase tracking-wider font-semibold">Transfer Wait</span>
                          <span className="text-sm font-bold text-white">{route.transfer_wait} min</span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[10px] text-white/40 uppercase tracking-wider font-semibold">Departure</span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-bold text-white">{route.first_leg.departure_display?.display_time}</span>
                            {route.first_leg.departure_display && route.first_leg.departure_display.day_offset > 0 && (
                              <span className="text-[8px] font-bold bg-[#FF5A00]/20 text-[#FF5A00] px-1 rounded uppercase tracking-wider">
                                +{route.first_leg.departure_display.day_offset}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[10px] text-white/40 uppercase tracking-wider font-semibold">Arrival</span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-bold text-white">{route.second_leg.arrival_display?.display_time}</span>
                            {route.second_leg.arrival_display && route.second_leg.arrival_display.day_offset > 0 && (
                              <span className="text-[8px] font-bold bg-[#FF5A00]/20 text-[#FF5A00] px-1 rounded uppercase tracking-wider">
                                +{route.second_leg.arrival_display.day_offset}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-col gap-5 animate-in fade-in duration-300">
                      <div className="flex flex-col gap-2">
                        <h4 className="text-base leading-tight text-white font-bold truncate">
                          {route.first_leg.source_stop}
                        </h4>
                        <div className="text-[#FF5A00] text-sm flex items-center gap-2 font-medium">
                          <span>↓</span> Transfer at {route.transfer_stop}
                        </div>
                        <h4 className="text-base leading-tight text-white font-bold truncate">
                          {route.second_leg.destination_stop}
                        </h4>
                      </div>
                      <div className="grid grid-cols-2 gap-3 bg-white/5 p-4 rounded-xl border border-white/10">
                        <div>
                          <div className="text-xs text-white/50 mb-0.5">Departs:</div>
                          <div className="flex items-center gap-1.5">
                            <div className="text-sm font-bold text-white">{route.first_leg.departure_display?.display_time}</div>
                            {route.first_leg.departure_display && route.first_leg.departure_display.day_offset > 0 && (
                              <span className="text-[8px] font-bold bg-[#FF5A00]/20 text-[#FF5A00] px-1 rounded uppercase tracking-wider">
                                +{route.first_leg.departure_display.day_offset} Day
                              </span>
                            )}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-white/50 mb-0.5">Arrives:</div>
                          <div className="flex items-center gap-1.5">
                            <div className="text-sm font-bold text-white">{route.second_leg.arrival_display?.display_time}</div>
                            {route.second_leg.arrival_display && route.second_leg.arrival_display.day_offset > 0 && (
                              <span className="text-[8px] font-bold bg-[#FF5A00]/20 text-[#FF5A00] px-1 rounded uppercase tracking-wider">
                                +{route.second_leg.arrival_display.day_offset} Day
                              </span>
                            )}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-white/50 mb-0.5">Total Duration:</div>
                          <div className="text-sm font-bold text-white">{route.total_duration} min</div>
                        </div>
                        <div>
                          <div className="text-xs text-white/50 mb-0.5">Transfer Wait:</div>
                          <div className="text-sm font-bold text-white">{route.transfer_wait} min</div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          // No-op for now, per user "Do NOT modify map rendering yet"
                        }}
                        className="w-full mt-2 bg-white/10 hover:bg-white/20 text-white font-medium py-2 rounded-xl transition-colors border border-white/10 text-sm opacity-50 cursor-not-allowed"
                        disabled
                      >
                        Full Route View (Direct Only)
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}


      {routes.length > 3 && (
        <button
          onClick={onViewAll}
          className="w-full mb-4 bg-white/5 hover:bg-white/10 text-white/90 font-medium py-3 rounded-xl transition-colors border border-white/10 flex items-center justify-center gap-2"
        >
          View All Routes ({routes.length})
        </button>
      )}
      
      {selectedRoute && (
        <FullRouteExplorer
          isOpen={showExplorer}
          onClose={() => setShowExplorer(false)}
          feed={selectedRoute.feed}
          tripId={selectedRoute.trip_id}
          sourceStopName={selectedRoute.source_stop}
          destinationStopName={selectedRoute.destination_stop}
          routeName={selectedRoute.route_name}
          preloadedStops={tripStops}
        />
      )}
    </div>
  );
}
