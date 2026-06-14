import { Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { NormalizedRoute } from '../types/transit';
import { RouteCard } from './RouteCard';
import { RouteDetail } from './RouteDetail';
import { recommendBestRoute } from '../ai/journeyIntelligence';

interface RecommendedRoutesProps {
  routes?: NormalizedRoute[];
  isLoading?: boolean;
  selectedRoute?: NormalizedRoute | null;
  onRouteSelect?: (route: NormalizedRoute | null) => void;
  onOpenRoadmap?: (route: NormalizedRoute) => void;
  viewMode?: 'journey' | 'full';
  onViewModeChange?: (mode: 'journey' | 'full') => void;
  onViewAll?: () => void;
  onOpenAI?: () => void;
}

export default function RecommendedRoutes({ 
  routes: normalizedRoutes = [], 
  isLoading = false, 
  selectedRoute = null, 
  onRouteSelect,
  onOpenRoadmap,
  
  onViewAll,
  onOpenAI
}: RecommendedRoutesProps) {

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 mt-2">
        <h3 className="text-[15px] font-medium text-white/90">Recommended Routes</h3>
        <div className="flex items-center justify-center p-12 border border-white/10 rounded-2xl bg-zinc-950">
          <Loader2 className="animate-spin text-zinc-500" size={32} />
        </div>
      </div>
    );
  }

  if (normalizedRoutes.length === 0) {
    return (
      <div className="flex flex-col gap-4 mt-2">
        <h3 className="text-[15px] font-medium text-white/90">Recommended Routes</h3>
        <div className="flex items-center justify-center p-12 border border-white/10 rounded-2xl bg-zinc-950">
          <p className="text-zinc-500 text-[13px]">Search for a journey to see recommended routes.</p>
        </div>
      </div>
    );
  }

  // Filter valid routes before sorting and deduplicate by route_id
  const uniqueNormalizedRoutes = [];
  const seenOriginalIds = new Set<string>();

  for (const route of normalizedRoutes) {
    const orig = route.originalData as any;
    if (orig.quality?.classification === "Rejected") continue;
    
    const id = route.isTransfer 
      ? `transfer-${orig.transfer_stop}-${orig.first_leg?.trip_id}-${orig.second_leg?.trip_id}` 
      : orig.route_id || orig.trip_id;

    if (!seenOriginalIds.has(id)) {
      seenOriginalIds.add(id);
      uniqueNormalizedRoutes.push(route);
    }
  }
  
  // Sort by quality score (lower is better, directly mapped in normalizeRoutes)
  const sortedRoutes = uniqueNormalizedRoutes.sort((a, b) => a.qualityScore - b.qualityScore);

  const recommendation = uniqueNormalizedRoutes.length > 0 ? recommendBestRoute(uniqueNormalizedRoutes) : null;
  const recommendedRoute = recommendation ? uniqueNormalizedRoutes.find(r => r.id === recommendation.recommendedRouteId) || sortedRoutes[0] : sortedRoutes[0];
  const otherRoutes = sortedRoutes.filter(r => r.id !== recommendedRoute?.id);

  const totalRoutes = sortedRoutes.length;
  const displayRoutes = otherRoutes.slice(0, 4);
  const hiddenCount = totalRoutes - (displayRoutes.length + (recommendedRoute ? 1 : 0));

  const isDetailView = selectedRoute !== null;

  return (
    <div className="relative w-full h-full overflow-x-hidden">
      <AnimatePresence mode="wait">
        {!isDetailView ? (
          <motion.div 
            key="list"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.15 }}
            className="flex flex-col gap-6 w-full"
          >
            {/* Hero Section */}
            {recommendedRoute && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-zinc-400">Recommended For You</h3>
                  {recommendation && (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-purple-500/10 text-purple-400 rounded-md text-[10px] font-bold uppercase tracking-wider border border-purple-500/20">
                      <span className="text-xs">🧠</span> Recommended by TransitIQ
                    </div>
                  )}
                </div>
                <RouteCard 
                  route={recommendedRoute}
                  isHero={true}
                  onClick={() => onRouteSelect?.(recommendedRoute)}
                  onDetails={() => onRouteSelect?.(recommendedRoute)}
                  onRoadmap={() => onOpenRoadmap?.(recommendedRoute)}
                />
              </div>
            )}
            
            {/* Other Options Section */}
            {otherRoutes.length > 0 && (
              <div className="flex flex-col gap-3">
                <h3 className="text-sm font-medium text-zinc-400">Other Options</h3>
                <div className="flex flex-col gap-2">
                  {displayRoutes.map(route => {
                    return (
                      <RouteCard 
                        key={route.id}
                        route={route}
                        onClick={() => onRouteSelect?.(route)}
                        onDetails={() => onRouteSelect?.(route)}
                        onRoadmap={() => onOpenRoadmap?.(route)}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {hiddenCount > 0 && (
              <button 
                onClick={onViewAll}
                className="w-full py-3 mt-2 rounded-xl border border-zinc-800 text-sm font-medium text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 hover:border-zinc-700 transition-colors"
              >
                Explore All {totalRoutes} Routes
              </button>
            )}
          </motion.div>
        ) : (
          <motion.div 
            key="detail"
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            transition={{ duration: 0.15 }}
            className="w-full"
          >
            {selectedRoute ? (
              <RouteDetail 
                route={selectedRoute}
                allRoutes={uniqueNormalizedRoutes}
                onBack={() => onRouteSelect?.(null)}
                onOpenRoadmap={() => onOpenRoadmap?.(selectedRoute)}
                onOpenAI={onOpenAI}
              />
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
