import { useState, useMemo } from 'react';
import { Clock, CheckCircle2, MapPin, Brain } from 'lucide-react';
import type { NormalizedRoute, TripStop, TransferJourney, JourneyRoute } from '../types/transit';
import { analyzeTransferRisk } from '../ai/journeyIntelligence';

interface FullJourneyRoadmapProps {
  route: NormalizedRoute;
  tripStops: TripStop[];
  transferStops: TripStop[][] | null;
  onStationClick: (lat: number, lon: number) => void;
}

export default function FullJourneyRoadmap({
  route,
  tripStops,
  transferStops,
  onStationClick
}: FullJourneyRoadmapProps) {
  const [expandedStops, setExpandedStops] = useState<Set<string>>(new Set());

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

  const toggleStop = (id: string, lat?: number, lon?: number) => {
    const newSet = new Set(expandedStops);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
      if (lat && lon) {
        onStationClick(lat, lon);
      }
    }
    setExpandedStops(newSet);
  };

  const renderStop = (stop: TripStop, index: number, total: number, trainName: string, trainNo: string) => {
    const isFirst = index === 0;
    const isLast = index === total - 1;
    const isExpanded = expandedStops.has(stop.stop_id);
    
    // Train travel segments are always orange
    const dotColor = isFirst || isLast 
      ? 'bg-[#FF4500] border-[#FF4500]/30 shadow-[0_0_10px_rgba(255,69,0,0.5)]' 
      : 'bg-white border-[#FF4500]';
    const lineColor = 'bg-[#FF4500]';

    return (
      <div key={stop.stop_id} className="relative flex items-start gap-4 cursor-pointer group" onClick={() => toggleStop(stop.stop_id, stop.stop_lat, stop.stop_lon)}>
        {/* Timeline Line */}
        {!isLast && (
          <div className={`absolute left-[11px] top-[24px] bottom-[-8px] w-[2px] ${lineColor} opacity-80`} />
        )}
        
        {/* Timeline Dot */}
        <div className={`relative z-10 w-6 h-6 rounded-full border-[3px] flex items-center justify-center shrink-0 mt-1 transition-all ${dotColor}`}>
          {(isFirst || isLast) && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
        </div>
        
        {/* Content */}
        <div className="flex-1 pb-6 pt-1">
          <div className="flex items-start justify-between">
            <h4 className={`text-[15px] font-bold ${isFirst || isLast ? 'text-white' : 'text-[#ddd]'} group-hover:text-[#FF4500] transition-colors`}>
              {stop.stop_name}
            </h4>
            <div className="text-right">
              {stop.arrival_time && <div className="text-[13px] font-medium text-[#aaa]">{stop.arrival_time.substring(0, 5)}</div>}
            </div>
          </div>
          
          {/* Expanded Details */}
          {isExpanded && (
            <div className="mt-3 bg-[#111] border border-[#252525] rounded-lg p-3">
              <div className="grid grid-cols-2 gap-3 mb-2">
                <div>
                  <div className="text-[11px] text-[#888] uppercase tracking-wider mb-0.5">Train</div>
                  <div className="text-[13px] text-white font-medium">{trainName}</div>
                  <div className="text-[11px] text-[#FF4500]">{trainNo}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#888] uppercase tracking-wider mb-0.5">Time</div>
                  <div className="text-[13px] text-white">Arr: {stop.arrival_time?.substring(0,5) || '-'}</div>
                  <div className="text-[13px] text-white">Dep: {stop.departure_time?.substring(0,5) || '-'}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderDirectJourney = () => {
    const r = route.originalData as JourneyRoute;
    if (!Array.isArray(tripStops) || !tripStops.length) return <div className="text-[#888] p-4 text-[13px]">Loading stops...</div>;

    return (
      <div className="py-4">
        {/* START Marker */}
        <div className="mb-6 bg-[#1a1a1a] rounded-lg p-3 border border-[#333] flex items-center gap-3">
          <MapPin size={18} className="text-[#FF4500]" />
          <div>
            <div className="text-[11px] text-[#888] uppercase tracking-wider">Start Journey</div>
            <div className="text-[14px] font-bold text-white">{route.sourceName}</div>
          </div>
        </div>

        {tripStops.map((stop, i) => renderStop(stop, i, tripStops.length, r.route_name, r.trip_id))}

        {/* DESTINATION Marker */}
        <div className="mt-2 bg-[#1a2e26] rounded-lg p-3 border border-emerald-500/30 flex items-center gap-3">
          <CheckCircle2 size={18} className="text-[#10B981]" />
          <div>
            <div className="text-[11px] text-emerald-400 uppercase tracking-wider">Destination</div>
            <div className="text-[14px] font-bold text-white">{route.destName}</div>
          </div>
        </div>
      </div>
    );
  };

  const renderTransferJourney = () => {
    if (!Array.isArray(transferStops)) return <div className="text-[#888] p-4 text-[13px]">Loading stops...</div>;

    return (
      <div className="py-4">
        {/* START Marker */}
        <div className="mb-6 bg-[#1a1a1a] rounded-lg p-3 border border-[#333] flex items-center gap-3">
          <MapPin size={18} className="text-[#FF4500]" />
          <div>
            <div className="text-[11px] text-[#888] uppercase tracking-wider">Start Journey</div>
            <div className="text-[14px] font-bold text-white">{route.sourceName}</div>
          </div>
        </div>

        {/* Iterate over legs dynamically */}
        {legs.map((leg, index) => {
          const stops = transferStops?.[index];
          const hasStops = Array.isArray(stops) && stops.length > 0;

          return (
            <div key={`leg-wrapper-${index}`}>
              {/* Leg Stop Sequence */}
              {hasStops && stops.map((stop, i) => renderStop(stop, i, stops.length, leg.route_name, leg.trip_id))}

              {/* TRANSFER Marker (only if it's not the last leg) */}
              {index < legs.length - 1 && (
                <div className="my-6 bg-[#0f1126] rounded-lg p-4 border border-indigo-500/30 flex flex-col gap-2 relative">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center">
                      <Clock size={16} className="text-indigo-400" />
                    </div>
                    <div>
                      <div className="text-[11px] text-indigo-400 uppercase tracking-wider font-bold mb-0.5">Change Train</div>
                      <div className="text-[15px] font-bold text-white">
                        {transferStopNames[index] || `Transfer Station ${index + 1}`}
                      </div>
                    </div>
                  </div>
                  <div className="ml-11 text-[13px] text-indigo-200">
                    Wait {Math.round(transferWaitTimes[index] || 0)} minutes before boarding the next train.
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* DESTINATION Marker */}
        <div className="mt-2 bg-[#1a2e26] rounded-lg p-3 border border-emerald-500/30 flex flex-center gap-3 flex-row items-center">
          <CheckCircle2 size={18} className="text-[#10B981]" />
          <div>
            <div className="text-[11px] text-emerald-400 uppercase tracking-wider">Destination</div>
            <div className="text-[14px] font-bold text-white">{route.destName}</div>
          </div>
        </div>
      </div>
    );
  };
  const transferRisk = analyzeTransferRisk(route);

  return (
    <div className="flex h-full w-full bg-[#0a0a0a] text-white overflow-hidden relative">
      <div className="flex-1 flex flex-col h-full custom-scrollbar overflow-y-auto">
        <div className="p-5 flex-1">
          <div className="mb-4">
            <h2 className="text-[20px] font-black text-white uppercase tracking-tight">Full Journey Roadmap</h2>
            <p className="text-[13px] text-[#888] mt-1">Interactive timeline of your trip</p>
          </div>
          
          <div className="flex-1">
            {route.isTransfer ? renderTransferJourney() : renderDirectJourney()}
          </div>
        </div>

        {/* TransitIQ Thinking Section (Stacked vertically below the timeline) */}
        <div className="border-t border-white/5 bg-[#0f0f0f] p-5 flex flex-col gap-6 shrink-0">
          <div className="flex items-center gap-2">
            <Brain size={20} className="text-[#FF4500]" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wide">TransitIQ Thinking</h3>
          </div>

          <div className="flex flex-col gap-4">
            {/* Why this route? */}
            <div className="flex flex-col gap-1.5">
              <h4 className="text-[11px] uppercase tracking-wider text-zinc-500 font-bold">Why this route?</h4>
              <div className="text-[13px] text-zinc-300 leading-relaxed">
                {route.durationMinutes < 60 ? "Fastest available option." : "Provides the most balanced travel experience."}
                {route.transferCount === 0 && " Direct connection without transfers."}
              </div>
            </div>

            {/* Transfer Assessment */}
            {route.isTransfer && (
              <div className="flex flex-col gap-1.5">
                <h4 className="text-[11px] uppercase tracking-wider text-zinc-500 font-bold">Transfer Assessment</h4>
                <div className="text-[13px] text-zinc-300 leading-relaxed">
                  {transferRisk.message}
                </div>
              </div>
            )}

            {/* Connection Risk */}
            {route.isTransfer && (
              <div className="flex flex-col gap-1.5">
                <h4 className="text-[11px] uppercase tracking-wider text-zinc-500 font-bold">Connection Risk</h4>
                <div className={`text-[13px] font-medium ${transferRisk.level === 'low' ? 'text-green-400' : transferRisk.level === 'medium' ? 'text-amber-400' : 'text-red-400'}`}>
                  {transferRisk.level.toUpperCase()} - {transferRisk.score}/100
                </div>
              </div>
            )}

            {/* Journey Confidence */}
            <div className="flex flex-col gap-1.5">
              <h4 className="text-[11px] uppercase tracking-wider text-zinc-500 font-bold">Journey Confidence</h4>
              <div className="text-[13px] text-green-400 font-medium">
                HIGH CONFIDENCE
              </div>
            </div>

            {/* Travel Tips */}
            <div className="flex flex-col gap-1.5">
              <h4 className="text-[11px] uppercase tracking-wider text-zinc-500 font-bold">Travel Tips</h4>
              <ul className="list-disc list-inside text-[13px] text-zinc-300 leading-relaxed">
                {Array.isArray(transferRisk.recommendations) && transferRisk.recommendations.length > 0 
                  ? transferRisk.recommendations.map((rec, idx) => <li key={idx}>{rec}</li>)
                  : <li>Arrive 5 minutes early to the platform.</li>
                }
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
