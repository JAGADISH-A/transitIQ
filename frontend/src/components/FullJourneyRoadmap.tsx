import { useState, useMemo } from 'react';
import { Clock, Brain, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { NormalizedRoute, TripStop, TransferJourney, JourneyRoute } from '../types/transit';
import { analyzeTransferRisk } from '../ai/journeyIntelligence';

interface FullJourneyRoadmapProps {
  route: NormalizedRoute;
  tripStops: TripStop[];
  transferStops: TripStop[][] | null;
  onStationClick: (lat: number, lon: number) => void;
}

const StopNode = ({ 
  stop, 
  isActive, 
  isFirstActive, 
  isLastActive, 
  onClick 
}: { 
  stop: TripStop; 
  isActive: boolean; 
  isFirstActive: boolean; 
  isLastActive: boolean;
  onClick: () => void;
}) => {
  const isEndpoint = isFirstActive || isLastActive;
  
  return (
    <motion.div 
      className="relative flex items-center gap-4 cursor-pointer group py-1.5"
      onClick={onClick}
      whileHover={{ scale: 1.01 }}
    >
      {/* Timeline Node */}
      <div className="relative z-10 w-6 h-6 flex items-center justify-center shrink-0">
        <motion.div 
          className={`w-3 h-3 rounded-full transition-colors duration-300 ${
            isEndpoint ? 'bg-[#FF4500] ring-4 ring-[#FF4500]/20' : 
            isActive ? 'bg-white border-2 border-[#FF4500]' : 'bg-[#333] border-2 border-[#555]'
          }`}
          whileHover={{ scale: 1.2 }}
        />
      </div>
      
      {/* Content */}
      <div className="flex-1 flex items-center justify-between">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h4 className={`text-[15px] transition-colors duration-300 ${
              isEndpoint ? 'font-bold text-white' : 
              isActive ? 'font-medium text-white/90 group-hover:text-white' : 'font-normal text-white/40 group-hover:text-white/60'
            }`}>
              {stop.stop_name}
            </h4>
            {isFirstActive && <span className="text-[10px] uppercase font-bold tracking-wider text-[#FF4500] bg-[#FF4500]/10 px-2 py-0.5 rounded-full">Source</span>}
            {isLastActive && <span className="text-[10px] uppercase font-bold tracking-wider text-[#FF4500] bg-[#FF4500]/10 px-2 py-0.5 rounded-full">Destination</span>}
          </div>
        </div>
        
        <div className="text-right">
          {stop.arrival_time && (
            <div className={`text-[13px] font-medium transition-colors duration-300 ${isActive ? 'text-white/70' : 'text-white/30'}`}>
              {stop.arrival_time.substring(0, 5)}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

const CollapsibleSegment = ({ 
  stops, 
  isActive, 
  label, 
  onStationClick 
}: { 
  stops: TripStop[]; 
  isActive: boolean; 
  label: string; 
  onStationClick: (lat: number, lon: number) => void;
}) => {
  const [expanded, setExpanded] = useState(false);

  if (stops.length === 0) return null;

  return (
    <div className="relative">
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 py-2 pl-[38px] text-[13px] text-white/40 hover:text-white/70 transition-colors"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        <span>{expanded ? 'Hide' : `⋯ ${stops.length} stations ${label}`}</span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            {stops.map(stop => (
              <StopNode 
                key={stop.stop_id} 
                stop={stop} 
                isActive={isActive} 
                isFirstActive={false} 
                isLastActive={false} 
                onClick={() => {
                  if (stop.stop_lat && stop.stop_lon) {
                    onStationClick(stop.stop_lat, stop.stop_lon);
                  }
                }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const RoadmapLeg = ({ 
  stops, 
  startName, 
  endName, 
  onStationClick,
}: {  
  stops: TripStop[]; 
  startName: string; 
  endName: string; 
  onStationClick: (lat: number, lon: number) => void;
}) => {
  if (!stops || stops.length === 0) return null;

  const startIndex = Math.max(0, stops.findIndex(s => s.stop_name === startName));
  let endIndex = stops.findIndex(s => s.stop_name === endName);
  if (endIndex === -1) endIndex = stops.length - 1;

  const beforeStops = stops.slice(0, startIndex);
  const activeStops = stops.slice(startIndex, endIndex + 1);
  const afterStops = stops.slice(endIndex + 1);

  return (
    <div className="relative">
      {/* Continuous Track Line */}
      <div className="absolute left-[11px] top-4 bottom-4 w-[2px] bg-gradient-to-b from-[#333] via-[#FF4500] to-[#333] opacity-50" />
      
      <div className="relative z-10 flex flex-col gap-1 py-4">
        {/* Before Journey */}
        <CollapsibleSegment 
          stops={beforeStops} 
          isActive={false} 
          label="before" 
          onStationClick={onStationClick} 
        />

        {/* Active Journey */}
        {activeStops.map((stop, i) => (
          <StopNode 
            key={stop.stop_id} 
            stop={stop} 
            isActive={true} 
            isFirstActive={i === 0} 
            isLastActive={i === activeStops.length - 1} 
            onClick={() => {
              if (stop.stop_lat && stop.stop_lon) {
                onStationClick(stop.stop_lat, stop.stop_lon);
              }
            }}
          />
        ))}

        {/* After Journey */}
        <CollapsibleSegment 
          stops={afterStops} 
          isActive={false} 
          label="after" 
          onStationClick={onStationClick} 
        />
      </div>
    </div>
  );
};

export default function FullJourneyRoadmap({
  route,
  tripStops,
  transferStops,
  onStationClick
}: FullJourneyRoadmapProps) {
  
  const legs = useMemo(() => {
    if (!route?.isTransfer || !route?.originalData) return [];
    const original = route.originalData as TransferJourney;
    return [
      original.first_leg,
      original.second_leg,
      original.third_leg
    ].filter(Boolean) as JourneyRoute[];
  }, [route]);

  const transferStopNames = useMemo(() => {
    if (!route?.isTransfer || !route?.originalData) return [];
    const original = route.originalData as TransferJourney;
    return [
      original.transfer_stop,
      original.transfer_stop_2
    ].filter(Boolean) as string[];
  }, [route]);

  const transferWaitTimes = useMemo(() => {
    if (!route?.isTransfer || !route?.originalData) return [];
    const original = route.originalData as TransferJourney;
    return [
      original.transfer_wait,
      original.transfer_wait_2
    ].filter(Boolean) as number[];
  }, [route]);

  const transferRisk = analyzeTransferRisk(route);

  return (
    <div className="flex flex-col gap-2 p-2">
      {/* Roadmap Content */}
      <div className="bg-[#0F0F0F] rounded-xl overflow-hidden p-4">
        {!route.isTransfer ? (
          <RoadmapLeg 
            stops={tripStops} 
            startName={route.sourceName} 
            endName={route.destName} 
            onStationClick={onStationClick} 
          />
        ) : (
          <div className="flex flex-col">
            {legs.map((_, index) => {
              const startName = index === 0 ? route.sourceName : transferStopNames[index - 1];
              const endName = index === legs.length - 1 ? route.destName : transferStopNames[index];
              const stops = transferStops?.[index] || [];
              
              return (
                <div key={`leg-${index}`}>
                  <RoadmapLeg 
                    stops={stops} 
                    startName={startName} 
                    endName={endName} 
                    onStationClick={onStationClick}
                  />
                  
                  {/* Transfer Node */}
                  {index < legs.length - 1 && (
                    <div className="my-4 ml-[11px] pl-[27px] relative border-l-2 border-dashed border-[#FF4500]/50 py-4 flex flex-col gap-2">
                      <div className="absolute -left-[17px] top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-[#FF4500]/10 flex items-center justify-center border border-[#FF4500]/30 shadow-[0_0_15px_rgba(255,69,0,0.2)]">
                        <Clock size={14} className="text-[#FF4500]" />
                      </div>
                      <div className="text-[11px] text-[#FF4500] uppercase tracking-wider font-bold">Change Train</div>
                      <div className="text-[15px] font-bold text-white">
                        {transferStopNames[index] || `Transfer Station ${index + 1}`}
                      </div>
                      <div className="text-[13px] text-white/50">
                        Wait {Math.round(transferWaitTimes[index] || 0)} minutes before boarding.
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* TransitIQ Thinking */}
      <div className="bg-[#1A1A1A] rounded-xl p-5 flex flex-col gap-5 border border-white/5">
        <div className="flex items-center gap-2">
          <Brain size={18} className="text-[#FF4500]" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wide">TransitIQ Insights</h3>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h4 className="text-[11px] uppercase tracking-wider text-white/40 font-bold">Why this route?</h4>
            <div className="text-[13px] text-white/80 leading-relaxed">
              {route.durationMinutes < 60 ? "Fastest available option." : "Provides the most balanced travel experience."}
              {route.transferCount === 0 && " Direct connection without transfers."}
            </div>
          </div>

          {route.isTransfer && (
            <>
              <div className="flex flex-col gap-1">
                <h4 className="text-[11px] uppercase tracking-wider text-white/40 font-bold">Transfer Assessment</h4>
                <div className="text-[13px] text-white/80 leading-relaxed">
                  {transferRisk.message}
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <h4 className="text-[11px] uppercase tracking-wider text-white/40 font-bold">Connection Risk</h4>
                <div className={`text-[13px] font-medium ${transferRisk.level === 'low' ? 'text-green-400' : transferRisk.level === 'medium' ? 'text-amber-400' : 'text-red-400'}`}>
                  {transferRisk.level.toUpperCase()} - {transferRisk.score}/100
                </div>
              </div>
            </>
          )}

          <div className="flex flex-col gap-1">
            <h4 className="text-[11px] uppercase tracking-wider text-white/40 font-bold">Travel Tips</h4>
            <ul className="list-disc list-inside text-[13px] text-white/80 leading-relaxed space-y-1">
              {Array.isArray(transferRisk.recommendations) && transferRisk.recommendations.length > 0 
                ? transferRisk.recommendations.map((rec, idx) => <li key={idx}>{rec}</li>)
                : <li>Arrive 5 minutes early to the platform.</li>
              }
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
