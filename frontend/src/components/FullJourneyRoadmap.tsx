import React, { useState } from 'react';
import { MapPin, Train, ArrowRight, Clock, ChevronDown, ChevronRight, CheckCircle2 } from 'lucide-react';
import type { NormalizedRoute, TripStop, TransferJourney, JourneyRoute } from '../types/transit';

interface FullJourneyRoadmapProps {
  route: NormalizedRoute;
  tripStops: TripStop[];
  transferStops: { leg1: TripStop[], leg2: TripStop[] } | null;
  onStationClick: (lat: number, lon: number) => void;
}

export default function FullJourneyRoadmap({
  route,
  tripStops,
  transferStops,
  onStationClick
}: FullJourneyRoadmapProps) {
  const [expandedStops, setExpandedStops] = useState<Set<string>>(new Set());

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

  const renderStop = (stop: TripStop, index: number, total: number, segmentType: 'past' | 'active' | 'future', trainName: string, trainNo: string) => {
    const isFirst = index === 0;
    const isLast = index === total - 1;
    const isExpanded = expandedStops.has(stop.stop_id);
    
    // Determine dot color
    let dotColor = 'bg-[#444] border-[#222]'; // default past
    let lineColor = 'bg-[#333]';
    
    if (segmentType === 'active') {
      dotColor = isFirst || isLast ? 'bg-[#FF4500] border-[#FF4500]/30 shadow-[0_0_10px_rgba(255,69,0,0.5)]' : 'bg-white border-[#FF4500]';
      lineColor = 'bg-[#FF4500]';
    } else if (segmentType === 'future') {
      dotColor = isFirst || isLast ? 'bg-[#ff9470] border-[#ff9470]/30' : 'bg-[#aaa] border-[#888]';
      lineColor = 'bg-[#ff9470]';
    }

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
    if (!tripStops.length) return <div className="text-[#888] p-4 text-[13px]">Loading stops...</div>;

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

        {tripStops.map((stop, i) => renderStop(stop, i, tripStops.length, 'active', r.route_name, r.trip_id))}

        {/* DESTINATION Marker */}
        <div className="mt-2 bg-[#1a1a1a] rounded-lg p-3 border border-[#333] flex items-center gap-3">
          <CheckCircle2 size={18} className="text-[#FF4500]" />
          <div>
            <div className="text-[11px] text-[#888] uppercase tracking-wider">Destination</div>
            <div className="text-[14px] font-bold text-white">{route.destName}</div>
          </div>
        </div>
      </div>
    );
  };

  const renderTransferJourney = () => {
    const r = route.originalData as TransferJourney;
    if (!transferStops) return <div className="text-[#888] p-4 text-[13px]">Loading stops...</div>;

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

        {/* Leg 1 */}
        {transferStops.leg1.map((stop, i) => renderStop(stop, i, transferStops.leg1.length, 'active', r.first_leg.route_name, r.first_leg.trip_id))}

        {/* TRANSFER Marker */}
        <div className="my-6 bg-[#2a1a10] rounded-lg p-4 border border-[#FF4500]/30 flex flex-col gap-2 relative">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#FF4500]/20 flex items-center justify-center">
              <Clock size={16} className="text-[#FF4500]" />
            </div>
            <div>
              <div className="text-[11px] text-[#FF4500] uppercase tracking-wider font-bold mb-0.5">Change Train</div>
              <div className="text-[15px] font-bold text-white">{route.transferStopName}</div>
            </div>
          </div>
          <div className="ml-11 text-[13px] text-[#ffccaa]">
            Wait {Math.round(route.transferWait || 0)} minutes before boarding the next train.
          </div>
        </div>

        {/* Leg 2 */}
        {transferStops.leg2.map((stop, i) => renderStop(stop, i, transferStops.leg2.length, 'future', r.second_leg.route_name, r.second_leg.trip_id))}

        {/* DESTINATION Marker */}
        <div className="mt-2 bg-[#1a1a1a] rounded-lg p-3 border border-[#333] flex items-center gap-3">
          <CheckCircle2 size={18} className="text-[#FF4500]" />
          <div>
            <div className="text-[11px] text-[#888] uppercase tracking-wider">Destination</div>
            <div className="text-[14px] font-bold text-white">{route.destName}</div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] text-white custom-scrollbar overflow-y-auto p-5">
      <div className="mb-4">
        <h2 className="text-[20px] font-black text-white uppercase tracking-tight">Full Journey Roadmap</h2>
        <p className="text-[13px] text-[#888] mt-1">Interactive timeline of your trip</p>
      </div>
      
      <div className="flex-1">
        {route.isTransfer ? renderTransferJourney() : renderDirectJourney()}
      </div>
    </div>
  );
}
