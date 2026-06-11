
import { ArrowDown, Train, Bus, Zap, X, Loader2 } from 'lucide-react';

interface JourneyRoute {
  feed: string;
  trip_id: string;
  route_id: string;
  route_name: string;
  source_stop: string;
  destination_stop: string;
  stops_between: number;
}

interface RecommendedRoutesProps {
  routes?: JourneyRoute[];
  isLoading?: boolean;
  selectedRoute?: JourneyRoute | null;
  onRouteSelect?: (route: JourneyRoute) => void;
}

export default function RecommendedRoutes({ routes = [], isLoading = false, selectedRoute = null, onRouteSelect }: RecommendedRoutesProps) {
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

  if (routes.length === 0) {
    return (
      <div className="flex flex-col gap-4 mt-2">
        <h3 className="text-lg font-medium text-white/90">Recommended Routes</h3>
        <div className="flex items-center justify-center p-12 border border-white/10 rounded-2xl bg-[#1A1A1A]">
          <p className="text-white/50">Search for a journey to see recommended routes.</p>
        </div>
      </div>
    );
  }

  // Deduplicate and limit to top 3 for UI
  // Group by route_id and pick the first one to avoid showing 10 of the same train
  const uniqueRoutes: JourneyRoute[] = [];
  const seenRouteIds = new Set<string>();
  
  for (const route of routes) {
    if (!seenRouteIds.has(route.route_id)) {
      seenRouteIds.add(route.route_id);
      uniqueRoutes.push(route);
    }
  }

  const displayRoutes = uniqueRoutes.slice(0, 3);

  return (
    <div className="flex flex-col gap-4 mt-2">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-white/90">
          {selectedRoute ? 'Route Details' : 'Recommended Routes'}
        </h3>
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
              
              {/* Route Name */}
              <div className={`flex items-start justify-between gap-2 ${isSelected ? 'mb-5' : 'mb-4'}`}>
                <div className="flex items-center gap-2">
                  <h4 className={`text-lg leading-tight ${isSelected ? 'text-white font-extrabold' : 'text-white/90 font-bold'}`} title={route.route_name}>
                    {route.route_name}
                  </h4>
                  
                  {(() => {
                    let badgeText = "";
                    let badgeClass = "";
                    if (index === 0) {
                      badgeText = "Fastest";
                      badgeClass = "bg-[#FF4500]/10 text-[#FF4500]";
                    } else if (index === 1) {
                      badgeText = "Recommended";
                      badgeClass = "bg-[#3B82F6]/10 text-[#3B82F6]";
                    } else {
                      badgeText = "Alternative";
                      badgeClass = "bg-white/10 text-white/70";
                    }
                    return (
                      <div className={`text-xs px-2 py-1 rounded-md font-semibold shrink-0 ${badgeClass}`}>
                        {badgeText}
                      </div>
                    );
                  })()}
                </div>
                {isSelected && (
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      onRouteSelect?.(null as any);
                    }}
                    className="p-1.5 hover:bg-white/10 rounded-full transition-colors text-white/60 hover:text-white"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
              
              {/* Expanded Details: Stations with Arrow */}
              {isSelected && (
                <div className="flex flex-col gap-1.5 mb-6 pl-1 border-l-2 border-white/10 ml-1 animate-in fade-in slide-in-from-top-2 duration-300">
                  <span className="text-sm font-semibold text-white/80 truncate pl-3 relative before:absolute before:w-2 before:h-2 before:rounded-full before:bg-[#10B981] before:-left-[5px] before:top-1.5" title={route.source_stop}>
                    {route.source_stop}
                  </span>
                  <div className="pl-3 py-1">
                    <ArrowDown size={14} className="text-white/30" />
                  </div>
                  <span className="text-sm font-semibold text-white/80 truncate pl-3 relative before:absolute before:w-2 before:h-2 before:rounded-full before:bg-[#EF4444] before:-left-[5px] before:top-1.5" title={route.destination_stop}>
                    {route.destination_stop}
                  </span>
                </div>
              )}
              
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
                  <Zap size={14} className={index === 0 ? 'text-[#FF4500]' : 'text-[#10B981]'} />
                  <span className="text-xs font-medium text-white/60">Direct Route</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
