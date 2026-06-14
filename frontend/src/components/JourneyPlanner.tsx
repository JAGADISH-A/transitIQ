import { useState, useEffect, useRef } from 'react';
import { MapPin, Navigation, ArrowDownUp, Clock, Search, Loader2 } from 'lucide-react';
import WheelTimePicker from './WheelTimePicker';
import type { StopResult, SearchResponse } from '../types/transit';
import { useGeolocation } from '../utils/useGeolocation';

interface JourneyPlannerProps {
  onSearch: (source: StopResult, destination: StopResult, departureTime?: string) => void;
  isLoading?: boolean;
  initialSource?: string;
  initialDestination?: string;
  initialTime?: string;
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

export default function JourneyPlanner({ 
  onSearch, 
  isLoading = false, 
  initialSource = '', 
  initialDestination = '',
  initialTime
}: JourneyPlannerProps) {
  // Source State
  const [sourceQuery, setSourceQuery] = useState(initialSource);
  const [selectedSource, setSelectedSource] = useState<StopResult | null>(null);
  const [sourceSuggestions, setSourceSuggestions] = useState<StopResult[]>([]);
  const [isSourceFocused, setIsSourceFocused] = useState(false);
  const debouncedSourceQuery = useDebounce(sourceQuery, 300);

  // Destination State
  const [destQuery, setDestQuery] = useState(initialDestination);
  const [selectedDest, setSelectedDest] = useState<StopResult | null>(null);
  const [destSuggestions, setDestSuggestions] = useState<StopResult[]>([]);
  const [isDestFocused, setIsDestFocused] = useState(false);
  const debouncedDestQuery = useDebounce(destQuery, 300);
  
  // Time State
  const parsedTime = initialTime ? initialTime.slice(0, 5) : '';
  const [timeMode, setTimeMode] = useState<'now' | 'custom'>(initialTime ? 'custom' : 'now');
  const [customTime, setCustomTime] = useState<string>(parsedTime);

  const { requestLocation, loading: locationLoading, error: locationError, lat, lon } = useGeolocation();
  const [nearestStopDetecting, setNearestStopDetecting] = useState(false);

  const [isSourceLoading, setIsSourceLoading] = useState(false);
  const [isDestLoading, setIsDestLoading] = useState(false);
  const [isSearchSubmitting, setIsSearchSubmitting] = useState(false);
  const [loadingText, setLoadingText] = useState('');

  // Fetch nearest stop when location is detected
  useEffect(() => {
    if (lat !== null && lon !== null) {
      setNearestStopDetecting(true);
      fetch(`http://localhost:8000/stops/nearby?lat=${lat}&lon=${lon}`)
        .then(res => res.json())
        .then(data => {
          if (data.results && data.results.length > 0) {
            const nearest = data.results[0];
            setSelectedSource(nearest);
            setSourceQuery(nearest.stop_name);
          }
        })
        .catch(err => console.error('Error fetching nearby stop:', err))
        .finally(() => {
          setNearestStopDetecting(false);
          setIsSourceFocused(false);
        });
    }
  }, [lat, lon]);

  // Fetch Source Suggestions
  useEffect(() => {
    if (debouncedSourceQuery.length >= 2 && (!selectedSource || selectedSource.stop_name !== debouncedSourceQuery)) {
      setIsSourceLoading(true);
      fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(debouncedSourceQuery)}`)
        .then(res => res.json())
        .then((data: SearchResponse) => {
          setSourceSuggestions(data.results || []);
        })
        .catch(err => console.error('Error fetching source stops:', err))
        .finally(() => setIsSourceLoading(false));
    } else {
      setSourceSuggestions([]);
    }
  }, [debouncedSourceQuery, selectedSource]);

  // Fetch Destination Suggestions
  useEffect(() => {
    if (debouncedDestQuery.length >= 2 && (!selectedDest || selectedDest.stop_name !== debouncedDestQuery)) {
      setIsDestLoading(true);
      fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(debouncedDestQuery)}`)
        .then(res => res.json())
        .then((data: SearchResponse) => {
          setDestSuggestions(data.results || []);
        })
        .catch(err => console.error('Error fetching destination stops:', err))
        .finally(() => setIsDestLoading(false));
    } else {
      setDestSuggestions([]);
    }
  }, [debouncedDestQuery, selectedDest]);

  const handleSearch = async () => {
    console.log('[SEARCH_BUTTON_CLICKED]');
    setIsSearchSubmitting(true);
    setLoadingText('Searching Stops...');

    let finalSource = selectedSource;
    let finalDest = selectedDest;

    try {
      // Force source resolution before search
      if (!finalSource && sourceQuery.trim() !== '') {
        setLoadingText('Searching Stops...');
        const res = await fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(sourceQuery)}`);
        const data = await res.json();
        if (data.results && data.results.length > 0) {
          finalSource = data.results[0];
          setSelectedSource(finalSource);
          setSourceQuery(finalSource!.stop_name);
          console.log('[SOURCE_RESOLVED]');
        }
      }

      // Force destination resolution before search
      if (!finalDest && destQuery.trim() !== '') {
        setLoadingText('Resolving Destination...');
        const res = await fetch(`http://localhost:8000/stops/search?q=${encodeURIComponent(destQuery)}`);
        const data = await res.json();
        if (data.results && data.results.length > 0) {
          finalDest = data.results[0];
          setSelectedDest(finalDest);
          setDestQuery(finalDest!.stop_name);
          console.log('[DESTINATION_RESOLVED]');
        }
      }

      if (!finalSource || !finalDest) {
        console.log('[SEARCH_ABORTED]', {
          reason: 'source or destination could not be resolved',
          source: sourceQuery,
          destination: destQuery,
          sourceSuggestionsLength: sourceSuggestions.length,
          destSuggestionsLength: destSuggestions.length
        });
        return;
      }

      let timeToSend: string | undefined = undefined;
      if (timeMode === 'custom' && customTime) {
        timeToSend = customTime.length === 5 ? customTime + ":00" : customTime;
      }
      
      setLoadingText('Finding Routes...');
      console.log('[JOURNEY_REQUEST_START]');
      await onSearch(finalSource, finalDest, timeToSend);
      console.log('[JOURNEY_REQUEST_COMPLETE]');
    } catch (err) {
      console.error('Error during search resolution:', err);
    } finally {
      setIsSearchSubmitting(false);
      setLoadingText('');
    }
  };

  const handleSwap = () => {
    const tempQuery = sourceQuery;
    const tempSelected = selectedSource;
    
    setSourceQuery(destQuery);
    setSelectedSource(selectedDest);
    
    setDestQuery(tempQuery);
    setSelectedDest(tempSelected);
  };

  const sourceRef = useRef<HTMLDivElement>(null);
  const destRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sourceRef.current && !sourceRef.current.contains(event.target as Node)) {
        setIsSourceFocused(false);
      }
      if (destRef.current && !destRef.current.contains(event.target as Node)) {
        setIsDestFocused(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="w-full h-full bg-[#1A1A1A] border border-white/10 rounded-2xl p-6 flex flex-col gap-6 shadow-xl">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-medium text-white/90">Plan your journey</h2>
        <p className="text-sm text-white/50">Find the fastest route using AI prediction.</p>
      </div>

      <div className="flex flex-col gap-4 relative mt-2">
        <div className="absolute left-5 top-[28px] bottom-[28px] w-[1px] bg-white/10 z-0 hidden sm:block"></div>

        {/* Source Autocomplete */}
        <div className="flex items-center gap-3 relative z-30" ref={sourceRef}>
          <div className="w-10 h-10 rounded-full bg-[#0F0F0F] border border-white/10 flex items-center justify-center shrink-0">
            <MapPin size={18} className="text-white/70" />
          </div>
          <div className="w-full relative">
            <input 
              type="text" 
              placeholder="Where are you starting?" 
              value={sourceQuery}
              onChange={(e) => {
                setSourceQuery(e.target.value);
                setSelectedSource(null);
              }}
              onFocus={() => setIsSourceFocused(true)}
              className="w-full bg-[#0F0F0F] border border-white/10 rounded-2xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-[#FF4500]/50 focus:ring-1 focus:ring-[#FF4500]/50 transition-all placeholder:text-white/30"
              disabled={isLoading}
            />
            {isSourceFocused && (
              <div className="absolute top-[calc(100%+8px)] left-0 w-full bg-[#111111] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50">
                {/* Use My Location Option */}
                <button
                  className="w-full text-left px-4 py-3 text-sm text-[#FF4500] hover:bg-white/5 font-medium transition-colors border-b border-white/5 flex items-center gap-2"
                  onClick={(e) => {
                    e.preventDefault();
                    requestLocation();
                  }}
                  disabled={locationLoading || nearestStopDetecting}
                >
                  📍 {locationLoading || nearestStopDetecting ? "Detecting location..." : "Use My Current Location"}
                </button>
                
                {locationError && (
                  <div className="px-4 py-2 text-xs text-red-400 bg-red-400/10">
                    {locationError}
                  </div>
                )}

                {sourceSuggestions.length > 0 && sourceSuggestions.map((stop) => (
                  <button
                    key={stop.stop_id}
                    className="w-full text-left px-4 py-3 text-sm text-white/80 hover:bg-white/5 hover:text-white transition-colors border-b border-white/5 last:border-0"
                    onClick={() => {
                      setSelectedSource(stop);
                      setSourceQuery(stop.stop_name);
                      setIsSourceFocused(false);
                    }}
                  >
                    {stop.stop_name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Nearby Context Chip */}
        {selectedSource && lat && lon && selectedSource.lat && selectedSource.lon && (
           <div className="ml-12 -mt-1 z-10 flex items-center gap-1.5 text-xs font-medium text-white/60 bg-white/5 w-fit px-2 py-1 rounded-md border border-white/5">
             <MapPin size={12} className="text-[#FF4500]" />
             <span>Near {selectedSource.stop_name}</span>
           </div>
        )}

        <button 
          className="absolute left-[20px] top-1/2 -translate-y-1/2 -translate-x-1/2 w-7 h-7 rounded-full bg-[#2A2A2A] border border-white/10 flex items-center justify-center z-40 hover:bg-[#333333] transition-colors cursor-pointer text-white/70 hover:text-white hidden sm:flex"
          onClick={handleSwap}
          disabled={isLoading}
        >
          <ArrowDownUp size={14} />
        </button>

        {/* Destination Autocomplete */}
        <div className="flex items-center gap-3 relative z-20" ref={destRef}>
          <div className="w-10 h-10 rounded-full bg-[#0F0F0F] border border-[#FF4500]/30 flex items-center justify-center shrink-0">
            <Navigation size={18} className="text-zinc-400" />
          </div>
          <div className="w-full relative">
            <input 
              type="text" 
              placeholder="Where do you want to go?" 
              value={destQuery}
              onChange={(e) => {
                setDestQuery(e.target.value);
                setSelectedDest(null);
              }}
              onFocus={() => setIsDestFocused(true)}
              className="w-full bg-[#0F0F0F] border border-white/10 rounded-2xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-[#FF4500]/50 focus:ring-1 focus:ring-[#FF4500]/50 transition-all placeholder:text-white/30"
              disabled={isLoading}
            />
            {isDestFocused && destSuggestions.length > 0 && (
              <div className="absolute top-[calc(100%+8px)] left-0 w-full bg-[#111111] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50">
                {destSuggestions.map((stop) => (
                  <button
                    key={stop.stop_id}
                    className="w-full text-left px-4 py-3 text-sm text-white/80 hover:bg-white/5 hover:text-white transition-colors border-b border-white/5 last:border-0"
                    onClick={() => {
                      setSelectedDest(stop);
                      setDestQuery(stop.stop_name);
                      setIsDestFocused(false);
                    }}
                  >
                    {stop.stop_name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-3 mt-2">
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setTimeMode('now')}
            className={`flex-1 border rounded-2xl px-4 py-3 text-sm flex items-center justify-center gap-2 transition-colors ${timeMode === 'now' ? 'bg-zinc-800 border-zinc-600 text-zinc-200' : 'bg-zinc-950 border-zinc-800 text-zinc-500 hover:bg-zinc-900'}`}
          >
            <Clock size={16} />
            <span>Leave now</span>
          </button>
          <button 
            onClick={() => setTimeMode('custom')}
            className={`flex-1 border rounded-2xl px-4 py-3 text-sm flex items-center justify-center gap-2 transition-colors ${timeMode === 'custom' ? 'bg-zinc-800 border-zinc-600 text-zinc-200' : 'bg-zinc-950 border-zinc-800 text-zinc-500 hover:bg-zinc-900'}`}
          >
            <Clock size={16} />
            <span>Custom time</span>
          </button>
        </div>
        
        {timeMode === 'custom' && (
          <div className="flex items-center gap-3 relative animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="w-full pt-2">
              <WheelTimePicker 
                value={customTime} 
                onChange={(newTime) => setCustomTime(newTime)} 
              />
            </div>
          </div>
        )}
      </div>

      <button 
        onClick={handleSearch}
        disabled={isLoading || isSearchSubmitting || isSourceLoading || isDestLoading || (!selectedSource && sourceQuery.trim() === '') || (!selectedDest && destQuery.trim() === '')}
        className="w-full mt-auto bg-[#FF4500] hover:bg-[#ff571a] disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-2xl py-3.5 flex items-center justify-center gap-2 transition-colors shadow-[0_0_20px_rgba(255,69,0,0.3)]"
      >
        {isLoading || isSearchSubmitting ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            <span>{loadingText || 'Finding Routes...'}</span>
          </>
        ) : (
          <>
            <Search size={18} />
            <span>Find Routes</span>
          </>
        )}
      </button>
    </div>
  );
}
