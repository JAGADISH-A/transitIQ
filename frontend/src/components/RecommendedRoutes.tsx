import { Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { NormalizedRoute } from '../types/transit';
import { RoutePreview } from './RoutePreview';
import { RouteDetail } from './RouteDetail';

interface RecommendedRoutesProps {
  routes?: NormalizedRoute[];
  isLoading?: boolean;
  selectedRoute?: NormalizedRoute | null;
  onRouteSelect?: (route: NormalizedRoute | null) => void;
  viewMode?: 'journey' | 'full';
  onViewModeChange?: (mode: 'journey' | 'full') => void;
  onViewAll?: () => void;
}

export default function RecommendedRoutes({ 
  routes: normalizedRoutes = [], 
  isLoading = false, 
  selectedRoute = null, 
  onRouteSelect,
  onViewAll
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

  const totalRoutes = sortedRoutes.length;
  const displayRoutes = sortedRoutes.slice(0, 5);
  const hiddenCount = totalRoutes - 5;

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
            {sortedRoutes.length > 0 && (
              <div className="flex flex-col gap-3">
                <h3 className="text-sm font-medium text-zinc-400">Recommended For You</h3>
                <RoutePreview 
                  route={sortedRoutes[0]}
                  isHero={true}
                  onClick={() => onRouteSelect?.(sortedRoutes[0])}
                />
              </div>
            )}
            
            {/* Other Options Section */}
            {sortedRoutes.length > 1 && (
              <div className="flex flex-col gap-3">
                <h3 className="text-sm font-medium text-zinc-400">Other Options</h3>
                <div className="flex flex-col gap-2">
                  {displayRoutes.slice(1).map(route => {
                    return (
                      <RoutePreview 
                        key={route.id}
                        route={route}
                        onClick={() => onRouteSelect?.(route)}
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
                onBack={() => onRouteSelect?.(null)}
              />
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
