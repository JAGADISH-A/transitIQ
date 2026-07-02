import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { NormalizedRoute, TripStop } from '../types/transit';

interface JourneyTimelineProps {
  route: NormalizedRoute;
  tripStops?: TripStop[];
  transferStops?: TripStop[][] | null;
  onStationHover?: (lat: number, lon: number) => void;
  onStationLeave?: () => void;
}

export const JourneyTimeline: React.FC<JourneyTimelineProps> = ({ route, tripStops, transferStops, onStationHover, onStationLeave }) => {
  const allStops = useMemo(() => {
    if (!route.isTransfer) return tripStops || [];
    
    let combined: TripStop[] = [];
    if (transferStops && Array.isArray(transferStops)) {
      transferStops.forEach(legStops => {
        if (legStops) {
          combined = combined.concat(legStops);
        }
      });
    }
    return combined;
  }, [route, tripStops, transferStops]);

  if (!allStops || allStops.length === 0) return null;

  const handleHover = (stop: TripStop) => {
    if (stop.stop_lat && stop.stop_lon && onStationHover) {
      onStationHover(stop.stop_lat, stop.stop_lon);
    }
  };

  const handleLeave = () => {
    if (onStationLeave) {
      onStationLeave();
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.05 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0 }
  };

  return (
    <motion.div 
      className="flex flex-col py-6 px-4"
      variants={containerVariants}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true }}
    >
      {allStops.map((stop, index) => {
        const isFirst = index === 0;
        const isLast = index === allStops.length - 1;
        const time = stop.arrival_time ? stop.arrival_time.substring(0, 5) : (stop.departure_time ? stop.departure_time.substring(0, 5) : '--:--');

        return (
          <motion.div 
            key={`${stop.stop_id}-${index}`} 
            variants={itemVariants}
            className="flex flex-col relative group"
            onMouseEnter={() => handleHover(stop)}
            onMouseLeave={handleLeave}
          >
            {/* Top Connector (Line above the dot) */}
            {!isFirst && (
              <div className="absolute left-[33px] top-[-16px] bottom-[28px] w-[2px] bg-white/10 group-hover:bg-[#FF4500]/50 transition-colors" />
            )}
            
            <div className="flex items-center gap-6 h-14 relative z-10">
              {/* Time */}
              <div className="w-12 text-right">
                <span className={`text-[13px] font-medium transition-colors ${isFirst || isLast ? 'text-zinc-200' : 'text-zinc-500 group-hover:text-zinc-300'}`}>
                  {time}
                </span>
              </div>
              
              {/* Node */}
              <div className={`w-3 h-3 rounded-full border-2 transition-all duration-300 shadow-[0_0_10px_rgba(0,0,0,0.5)] shrink-0
                ${isFirst || isLast 
                  ? 'w-4 h-4 bg-white border-[#FF4500] shadow-[0_0_10px_rgba(255,69,0,0.6)]' 
                  : 'bg-[#1a1a1a] border-zinc-600 group-hover:border-[#FF4500] group-hover:bg-[#FF4500]'}
              `} />
              
              {/* Station Name */}
              <div className={`text-[15px] transition-all duration-300 flex-1
                ${isFirst || isLast ? 'font-bold text-white' : 'font-medium text-zinc-400 group-hover:text-zinc-200 group-hover:translate-x-1'}
              `}>
                {stop.stop_name}
              </div>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
};
