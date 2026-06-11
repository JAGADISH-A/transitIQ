import { ArrowRight, Train, Check } from 'lucide-react';

import { TransferJourney } from '../App';
import { RouteFlags } from './RouteFlags';

interface TransferRouteCardProps {
  route: TransferJourney;
  isCompareSelected: boolean;
  onCompareToggle: (routeId: string) => void;
  onClick: (route: TransferJourney) => void;
}

export default function TransferRouteCard({
  route,
  isCompareSelected,
  onCompareToggle,
  onClick
}: TransferRouteCardProps) {
  const routeId = `transfer-${route.transfer_stop}-${route.first_leg.trip_id}-${route.second_leg.trip_id}`;

  return (
    <div 
      onClick={() => onClick(route)}
      className={`
        relative overflow-hidden rounded-xl border border-white/10
        bg-black/40 backdrop-blur-md p-4
        hover:border-white/20 transition-all duration-300
        cursor-pointer flex flex-col gap-3 group shadow-[0_4px_24px_-4px_rgba(0,0,0,0.3)]
        hover:shadow-[0_4px_32px_-4px_rgba(255,90,0,0.15)]
      `}
    >
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg text-white flex items-center gap-2">
          <span className="text-[#FF5A00]">🔄</span> Transfer at {route.transfer_stop}
        </h3>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-white/80 font-medium">
            <span className="text-[#FF5A00]">🔄</span> 1 Transfer
          </div>
          
          {route.quality && (
            <div className={`text-xs px-2 py-1 rounded-full font-semibold border ${
              route.quality.classification === 'Rejected' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
              route.quality.classification === 'Excellent' ? 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/20' :
              route.quality.classification === 'Good' ? 'bg-[#3B82F6]/10 text-[#3B82F6] border-[#3B82F6]/20' :
              route.quality.classification === 'Acceptable' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
              'bg-[#FF4500]/10 text-[#FF4500] border-[#FF4500]/20'
            }`}>
              {route.quality.classification === 'Excellent' ? '⭐ Excellent' : route.quality.classification} ({Math.round(route.quality.score)})
            </div>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onCompareToggle(routeId);
            }}
            className={`
              flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium
              transition-all duration-200 border
              ${isCompareSelected 
                ? 'bg-[#FF5A00]/20 border-[#FF5A00] text-[#FF5A00]' 
                : 'bg-white/5 border-white/10 text-white/70 hover:bg-white/10 hover:text-white'}
            `}
          >
            {isCompareSelected ? (
              <>
                <Check className="w-3.5 h-3.5" /> Added
              </>
            ) : (
              'Compare'
            )}
          </button>
        </div>
      </div>

      <div className="px-1">
        <RouteFlags flags={route.quality?.route_flags} />
      </div>

      <div className="flex items-start gap-4 mt-2">
        {/* Compact Timeline */}
        <div className="flex flex-col items-center pt-1.5">
          <div className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
          <div className="w-px h-[3.5rem] bg-gradient-to-b from-emerald-500/50 via-white/20 to-orange-500/50 my-1"></div>
          <div className="w-3 h-3 rounded-full bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.5)]"></div>
          <div className="w-px h-[3.5rem] bg-gradient-to-b from-orange-500/50 via-white/20 to-rose-500/50 my-1"></div>
          <div className="w-3 h-3 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]"></div>
        </div>

        {/* Detailed Info */}
        <div className="flex-1 flex flex-col gap-[0.8rem] text-sm text-white/80">
          <div>
            <div className="flex items-center justify-between">
              <span className="font-medium text-white">{route.first_leg.source_stop}</span>
              <span className="font-mono text-white/90">{route.first_leg.departure_display?.display_time || route.first_leg.departure_time}</span>
            </div>
            <div className="text-xs text-white/50 flex items-center gap-2 mt-0.5">
              <Train className="w-3 h-3" /> {route.first_leg.route_name}
            </div>
          </div>

          <div className="py-1 relative">
            <div className="flex items-center justify-between text-[#FF5A00]/90">
              <span className="font-medium">Arrive {route.transfer_stop}</span>
              <span className="font-mono">{route.first_leg.arrival_display?.display_time || route.first_leg.arrival_time}</span>
            </div>
            <div className="text-xs font-medium tracking-wide mt-1 text-white/60 bg-white/5 px-2 py-1 rounded-md inline-block">
              Wait: {route.transfer_wait} min
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <span className="font-medium text-white">Second Departure</span>
              <span className="font-mono text-white/90">{route.second_leg.departure_display?.display_time || route.second_leg.departure_time}</span>
            </div>
            <div className="text-xs text-white/50 flex items-center gap-2 mt-0.5">
              <Train className="w-3 h-3" /> {route.second_leg.route_name}
            </div>
          </div>

          <div className="flex items-center justify-between pt-1 border-t border-white/10">
            <span className="font-medium text-white">Arrive {route.second_leg.destination_stop}</span>
            <span className="font-mono text-white/90">{route.second_leg.arrival_display?.display_time || route.second_leg.arrival_time}</span>
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center pt-3 mt-1 border-t border-white/5">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <span className="text-xs text-white/50 uppercase tracking-wider font-semibold">Total Duration</span>
            <span className="text-lg font-medium text-white">{route.total_duration} <span className="text-sm text-white/60">min</span></span>
          </div>
        </div>
        <ArrowRight className="w-5 h-5 text-white/20 group-hover:text-[#FF5A00] transition-colors duration-300 transform group-hover:translate-x-1" />
      </div>
    </div>
  );
}
