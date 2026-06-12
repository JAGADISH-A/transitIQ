import React from 'react';
import type { TripStop } from '../types/transit';

interface FullRouteTimelineProps {
  stops: TripStop[];
  sourceStopName: string;
  destinationStopName: string;
  color?: 'green' | 'cyan';
}

export const FullRouteTimeline: React.FC<FullRouteTimelineProps> = ({ 
  stops, 
  sourceStopName, 
  destinationStopName,
  color = 'green'
}) => {
  let hasPassedSource = false;
  let hasPassedDest = false;

  if (!stops || stops.length === 0) {
    return <div className="text-zinc-500 text-sm italic">No timeline data available.</div>;
  }

  return (
    <div className="relative pl-6 mt-4">
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

        const colorClasses = color === 'green' 
          ? { bg: 'bg-green-500', shadow: 'shadow-[0_0_8px_rgba(34,197,94,0.5)]', glow: 'group-hover:shadow-[0_0_12px_rgba(34,197,94,0.8)]' }
          : { bg: 'bg-cyan-500', shadow: 'shadow-[0_0_8px_rgba(6,182,212,0.5)]', glow: 'group-hover:shadow-[0_0_12px_rgba(6,182,212,0.8)]' };

        return (
          <div key={stop.stop_id + index} className={`relative pb-8 group ${isMuted ? 'opacity-40' : 'opacity-100'}`}>
            {/* Vertical connecting line */}
            {!isLast && (
              <div 
                className={`absolute left-[-16px] top-6 bottom-0 w-[2px] ${
                  lineActive ? `${colorClasses.bg} ${colorClasses.shadow}` : 'bg-zinc-800'
                }`}
              >
                {lineActive && isSource && (
                  <div className="absolute left-3 top-4 text-xs font-medium text-zinc-500 whitespace-nowrap bg-zinc-950 py-1 z-10">
                    Stay On Board
                  </div>
                )}
              </div>
            )}

            {/* Timeline Node */}
            <div className="absolute left-[-22px] top-1">
              {isSource ? (
                <div className={`w-3.5 h-3.5 rounded-full ${colorClasses.bg} z-10 relative border-2 border-zinc-950 transition-all duration-300 group-hover:scale-110 ${colorClasses.glow}`} style={{ animation: 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite' }} />
              ) : isDest ? (
                <div className="w-3.5 h-3.5 rounded-full bg-red-500 z-10 relative border-2 border-zinc-950 transition-all duration-300 group-hover:scale-110 group-hover:shadow-[0_0_12px_rgba(239,68,68,0.8)]" style={{ animation: 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite' }} />
              ) : isBetween ? (
                <div className={`w-3.5 h-3.5 rounded-full ${colorClasses.bg} z-10 relative border-2 border-zinc-950 transition-all duration-300 group-hover:scale-110 ${colorClasses.glow}`} />
              ) : (
                <div className="w-3.5 h-3.5 rounded-full bg-zinc-800 z-10 relative border-2 border-zinc-950" />
              )}
            </div>

            <div className="flex flex-col items-start">
              <span className={`text-sm ${isSource || isDest ? 'font-medium text-white' : 'font-normal text-zinc-400'}`}>
                {stop.stop_name}
              </span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <div className="text-[13px] font-normal text-zinc-500 tabular-nums">
                  {stop.arrival_display?.display_time || stop.departure_display?.display_time || '-'}
                </div>
                {((stop.arrival_display?.day_offset || 0) > 0 || (stop.departure_display?.day_offset || 0) > 0) && (
                  <span className="text-[10px] text-zinc-400 bg-zinc-800/50 px-1.5 py-0.5 rounded">
                    +{(stop.arrival_display?.day_offset || stop.departure_display?.day_offset)}d
                  </span>
                )}
              </div>
              {isSource && <span className="text-[13px] text-zinc-300 mt-1 font-medium">Board Here</span>}
              {isDest && <span className="text-[13px] text-zinc-300 mt-1 font-medium">Get Off Here</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
};
