import { useEffect, useState } from 'react';
import { X, Loader2 } from 'lucide-react';
import { GlobalAlertModal } from './GlobalAlertModal';
import { TripStop } from '../App';

interface TripStopsResponse {
  feed: string;
  trip_id: string;
  stops: TripStop[];
}

interface FullRouteExplorerProps {
  isOpen: boolean;
  onClose: () => void;
  feed: string;
  tripId: string;
  sourceStopName: string; // To highlight
  destinationStopName: string; // To highlight
  routeName: string;
  preloadedStops?: TripStop[];
}

export default function FullRouteExplorer({
  isOpen,
  onClose,
  feed,
  tripId,
  sourceStopName,
  destinationStopName,
  routeName,
  preloadedStops,
}: FullRouteExplorerProps) {
  const [stops, setStops] = useState<TripStop[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !tripId || !feed) return;

    if (preloadedStops && preloadedStops.length > 0) {
      setStops(preloadedStops);
      return;
    }

    const fetchStops = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(`http://localhost:8000/trips/${feed}/${tripId}/stops`);
        if (!response.ok) {
          throw new Error('Failed to fetch stops');
        }
        const data: TripStopsResponse = await response.json();
        setStops(data.stops);
      } catch (err) {
        console.error(err);
        setError('Failed to load route details.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchStops();
  }, [isOpen, tripId, feed, preloadedStops]);

  // Determine state of each stop
  let hasPassedSource = false;
  let hasPassedDest = false;

  return (
    <>
      {/* Backdrop overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/40 z-40 transition-opacity backdrop-blur-sm"
          onClick={onClose}
        />
      )}
      
      {/* Slide-out Drawer */}
      <div 
        className={`fixed top-0 right-0 h-full w-[400px] max-w-full bg-[#111111] border-l border-white/10 shadow-2xl z-50 transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <div>
            <h2 className="text-xl font-bold text-white">Full Route</h2>
            <p className="text-sm text-white/50">{routeName}</p>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/10 text-white/50 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
          {isLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <Loader2 className="animate-spin text-[#FF4500]" size={32} />
              <p className="text-white/50">Loading route timeline...</p>
            </div>
          )}

          {/* Replaced inline error with GlobalAlertModal */}

          {!isLoading && !error && stops.length > 0 && (
            <div className="relative pl-6">
              {stops.map((stop, index) => {
                const safeSource = (sourceStopName || '').toLowerCase().trim();
                const safeDest = (destinationStopName || '').toLowerCase().trim();
                const safeName = (stop.stop_name || '').toLowerCase().trim();
                const safeId = (stop.stop_id || '').toLowerCase().trim();
                
                const isSource = safeName === safeSource || safeId === safeSource;
                const isDest = safeName === safeDest || safeId === safeDest;
                
                if (isSource) hasPassedSource = true;
                
                const isBetween = hasPassedSource && !hasPassedDest;
                const isMuted = !hasPassedSource || hasPassedDest;
                
                if (isDest) hasPassedDest = true;

                // Line segment connecting to next stop
                const isLast = index === stops.length - 1;
                const lineActive = isBetween && !isDest;

                return (
                  <div key={stop.stop_id} className={`relative pb-8 ${isMuted ? 'opacity-40' : 'opacity-100'}`}>
                    {/* Vertical connecting line */}
                    {!isLast && (
                      <div 
                        className={`absolute left-[-17px] top-6 bottom-0 w-[2px] ${
                          lineActive ? 'bg-[#FF4500]' : 'bg-white/10'
                        }`}
                      >
                        {lineActive && isSource && (
                          <div className="absolute left-2 top-4 text-[10px] font-bold text-[#FF4500] uppercase tracking-widest whitespace-nowrap bg-[#111111] py-1 z-10">
                            Your Journey
                          </div>
                        )}
                      </div>
                    )}

                    {/* Timeline Node */}
                    <div className="absolute left-[-22px] top-1">
                      {isSource ? (
                        <div className="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)] z-10 relative border-2 border-[#111111]" />
                      ) : isDest ? (
                        <div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)] z-10 relative border-2 border-[#111111]" />
                      ) : isBetween ? (
                        <div className="w-3 h-3 rounded-full bg-[#FF4500] z-10 relative border-2 border-[#111111]" />
                      ) : (
                        <div className="w-3 h-3 rounded-full bg-white/20 z-10 relative border-2 border-[#111111]" />
                      )}
                    </div>

                    <div className="flex flex-col items-start">
                      <span className={`font-medium text-sm ${isSource || isDest ? 'text-white' : 'text-white/80'}`}>
                        {stop.stop_name}
                      </span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <div className="text-xs text-white/50 tabular-nums">
                          {stop.arrival_display?.display_time || stop.departure_display?.display_time || '-'}
                        </div>
                        {((stop.arrival_display?.day_offset || 0) > 0 || (stop.departure_display?.day_offset || 0) > 0) && (
                          <span className="text-[9px] font-bold uppercase tracking-wider text-[#FF4500] bg-[#FF4500]/10 px-1 rounded">
                            +{(stop.arrival_display?.day_offset || stop.departure_display?.day_offset)} Day
                          </span>
                        )}
                      </div>
                      {isSource && <span className="text-xs text-green-400 mt-1 font-medium">Board Here</span>}
                      {isDest && <span className="text-xs text-red-400 mt-1 font-medium">Get Off Here</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <GlobalAlertModal
        isOpen={!!error && !isLoading}
        onClose={() => setError(null)}
        message={error || ""}
        title="Route Load Error"
      />
    </>
  );
}
