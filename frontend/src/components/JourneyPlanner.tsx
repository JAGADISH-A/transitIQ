import { useState } from 'react';
import { MapPin, Navigation, ArrowDownUp, Clock, Search, Loader2 } from 'lucide-react';

interface JourneyPlannerProps {
  onSearch: (source: string, destination: string) => void;
  isLoading?: boolean;
  initialSource?: string;
  initialDestination?: string;
}

export default function JourneyPlanner({ onSearch, isLoading = false, initialSource = '', initialDestination = '' }: JourneyPlannerProps) {
  const [source, setSource] = useState(initialSource);
  const [destination, setDestination] = useState(initialDestination);

  const handleSearch = () => {
    if (source.trim() && destination.trim()) {
      onSearch(source, destination);
    }
  };

  return (
    <div className="w-full h-full bg-[#1A1A1A] border border-white/10 rounded-2xl p-6 flex flex-col gap-6 shadow-xl">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-medium text-white/90">Plan your journey</h2>
        <p className="text-sm text-white/50">Find the fastest route using AI prediction.</p>
      </div>

      <div className="flex flex-col gap-4 relative mt-2">
        {/* Connection line between inputs */}
        <div className="absolute left-5 top-[28px] bottom-[28px] w-[1px] bg-white/10 z-0 hidden sm:block"></div>

        <div className="flex items-center gap-3 relative z-10">
          <div className="w-10 h-10 rounded-full bg-[#0F0F0F] border border-white/10 flex items-center justify-center shrink-0">
            <MapPin size={18} className="text-white/70" />
          </div>
          <div className="w-full relative">
            <input 
              type="text" 
              placeholder="Where are you starting?" 
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full bg-[#0F0F0F] border border-white/10 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-[#FF4500]/50 focus:ring-1 focus:ring-[#FF4500]/50 transition-all placeholder:text-white/30"
              disabled={isLoading}
            />
          </div>
        </div>

        <button 
          className="absolute left-[20px] top-1/2 -translate-y-1/2 -translate-x-1/2 w-7 h-7 rounded-full bg-[#2A2A2A] border border-white/10 flex items-center justify-center z-20 hover:bg-[#333333] transition-colors cursor-pointer text-white/70 hover:text-white hidden sm:flex"
          onClick={() => {
            setSource(destination);
            setDestination(source);
          }}
          disabled={isLoading}
        >
          <ArrowDownUp size={14} />
        </button>

        <div className="flex items-center gap-3 relative z-10">
          <div className="w-10 h-10 rounded-full bg-[#0F0F0F] border border-[#FF4500]/30 flex items-center justify-center shrink-0">
            <Navigation size={18} className="text-[#FF4500]" />
          </div>
          <div className="w-full relative">
            <input 
              type="text" 
              placeholder="Where do you want to go?" 
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              className="w-full bg-[#0F0F0F] border border-white/10 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-[#FF4500]/50 focus:ring-1 focus:ring-[#FF4500]/50 transition-all placeholder:text-white/30"
              disabled={isLoading}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 mt-2">
        <button className="flex-1 bg-[#0F0F0F] border border-white/10 rounded-xl px-4 py-3 text-sm flex items-center justify-center gap-2 text-white/70 hover:bg-[#2A2A2A] transition-colors">
          <Clock size={16} />
          <span>Leave now</span>
        </button>
      </div>

      <button 
        onClick={handleSearch}
        disabled={isLoading || !source.trim() || !destination.trim()}
        className="w-full mt-auto bg-[#FF4500] hover:bg-[#ff571a] disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-xl py-3.5 flex items-center justify-center gap-2 transition-colors shadow-[0_0_20px_rgba(255,69,0,0.3)]"
      >
        {isLoading ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            <span>Searching...</span>
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
