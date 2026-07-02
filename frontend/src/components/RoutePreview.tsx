import React from 'react';
import type { NormalizedRoute, JourneyRoute, TransferJourney } from '../types/transit';
import { TrainFront, Bus, TramFront, ArrowRight } from 'lucide-react';

interface RoutePreviewProps {
  route: NormalizedRoute;
  onClick: () => void;
  isSelected?: boolean;
  isHero?: boolean;
  isCompared?: boolean;
  onCompareToggle?: (e: React.MouseEvent) => void;
}

const MODE_MAP: Record<string, string> = {
  railways: "Rail",
  chennai_metro: "Metro",
  metro: "Metro",
  mtc: "Bus",
  bus: "Bus"
};

const getModeIcon = (mode: string) => {
  switch (mode) {
    case 'Rail': return <TrainFront size={16} />;
    case 'Metro': return <TramFront size={16} />;
    case 'Bus': return <Bus size={16} />;
    default: return <TrainFront size={16} />;
  }
};

const toTitleCase = (str: string) => {
  return str.replace(
    /\w\S*/g,
    (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase()
  );
};

export const RoutePreview: React.FC<RoutePreviewProps> = ({ 
  route, 
  onClick, 
  isSelected, 
  isCompared = false, 
  onCompareToggle 
}) => {
  if (!route) return null;

  const {
    sourceName,
    destName,
    departureDisplay,
    arrivalDisplay,
    durationMinutes,
    transferCount,
    originalData,
    isTransfer
  } = route;

  const formatDuration = (mins: number) => {
    if (mins < 60) return `${mins}m`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  };

  const formattedDuration = formatDuration(durationMinutes);
  const quality = (originalData as any).quality;
  const recommendation = quality?.recommendation_reason;
  const showRecommendation = recommendation && recommendation !== "Standard Route";

  // Determine Modes used
  const modes: string[] = [];
  let trainLabel = '';
  
  if (isTransfer) {
    const t = originalData as TransferJourney;
    const extT = t as any;
    const mode1 = MODE_MAP[t.first_leg.feed] || 'Rail';
    const mode2 = MODE_MAP[t.second_leg.feed] || 'Rail';
    if (!modes.includes(mode1)) modes.push(mode1);
    if (!modes.includes(mode2)) modes.push(mode2);
    if (extT.third_leg) {
      const mode3 = MODE_MAP[extT.third_leg.feed] || 'Rail';
      if (!modes.includes(mode3)) modes.push(mode3);
      trainLabel = 'Multiple (3 Services)';
    } else {
      trainLabel = 'Multiple';
    }
  } else {
    const t = originalData as JourneyRoute;
    const mode = MODE_MAP[t.feed] || 'Rail';
    modes.push(mode);
    const name = t.route_name;
    const id = t.route_id;
    if (name && id && name !== id) trainLabel = `${toTitleCase(name)} (${id})`;
    else if (name && name === id) trainLabel = `Train No. ${id}`;
    else if (name) trainLabel = toTitleCase(name);
    else if (id) trainLabel = `Train No. ${id}`;
  }

  if (route.transferCount === 2) {
      source: route.sourceName,
      destination: route.destName,
      transferCount: route.transferCount,
      hasThirdLeg: !!(route.originalData as any).third_leg
    });
  }

  return (
    <div className={`relative w-full rounded-2xl transition-all duration-200 group ${
      isCompared 
        ? 'bg-zinc-900 border border-[#FF4500]/50 shadow-[0_4px_20px_rgba(255,69,0,0.15)] z-10' 
        : 'bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] hover:border-white/10 hover:-translate-y-[2px] hover:shadow-lg'
    } ${isSelected ? 'ring-2 ring-[#FF4500]/50' : ''}`}>
      
      {/* Compare Checkbox */}
      {onCompareToggle && (
        <button 
          onClick={onCompareToggle}
          className={`absolute top-1/2 -translate-y-1/2 left-4 w-6 h-6 rounded-full border flex items-center justify-center transition-colors z-20 ${
            isCompared 
              ? 'bg-[#FF4500] border-[#FF4500] text-white' 
              : 'border-white/20 hover:border-white/40 text-transparent hover:text-white/20'
          }`}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </button>
      )}

      <button
        onClick={onClick}
        className="w-full text-left p-4 pl-14 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer"
      >
        
        {/* Left Section: Time & Modes */}
        <div className="flex items-center gap-6 md:w-1/3">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-white tracking-tight">
                {departureDisplay?.display_time || '-'}
              </span>
              <span className="text-zinc-500">→</span>
              <span className="text-xl font-bold text-white tracking-tight">
                {arrivalDisplay?.display_time || '-'}
              </span>
              {(arrivalDisplay?.day_offset || 0) > 0 && (
                <span className="text-[10px] font-bold text-[#FF4500] bg-[#FF4500]/10 px-1.5 py-0.5 rounded">
                  +{arrivalDisplay?.day_offset}d
                </span>
              )}
            </div>
            
            <div className="flex items-center gap-2 mt-1.5 text-xs text-zinc-400">
              <div className="flex items-center gap-1 text-[#FF4500]">
                {modes.map((m, i) => (
                  <span key={i} title={m}>{getModeIcon(m)}</span>
                ))}
              </div>
              <span className="truncate max-w-[150px]">{trainLabel || modes.join(' + ')}</span>
            </div>
          </div>
        </div>

        {/* Center Section: Path & Duration */}
        <div className="flex flex-col md:items-center gap-1 md:w-1/3">
          <div className="flex items-center gap-2 text-sm font-medium text-zinc-300 w-full md:justify-center">
            <span className="truncate text-right">{sourceName}</span>
            <ArrowRight size={14} className="text-zinc-500 shrink-0" />
            <span className="truncate text-left">{destName}</span>
          </div>
          
          <div className="flex items-center gap-2 text-xs font-semibold mt-1">
            <span className="text-[#FF4500] bg-[#FF4500]/10 px-2 py-0.5 rounded-full">
              {formattedDuration}
            </span>
            <span className={`px-2 py-0.5 rounded-full ${transferCount === 0 ? 'text-green-400 bg-green-400/10' : 'text-amber-400 bg-amber-400/10'}`}>
              {transferCount === 0 ? 'Direct' : `${transferCount} Transfer${transferCount > 1 ? 's' : ''}`}
            </span>
          </div>
        </div>

        {/* Right Section: Badges */}
        <div className="flex items-center md:justify-end gap-4 md:w-1/3">
          {showRecommendation ? (
            <div className="hidden md:flex flex-col items-end">
              <span className="text-[10px] uppercase tracking-wider text-[#FF4500] font-bold">Quality</span>
              <span className="text-sm font-medium text-zinc-300 truncate max-w-[120px]">{recommendation}</span>
            </div>
          ) : (
            <div className="hidden md:flex flex-col items-end">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold">Reliability</span>
              <span className="text-sm font-medium text-zinc-400">Standard</span>
            </div>
          )}
          
          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold">Fare</span>
            <span className="text-sm font-medium text-zinc-400">—</span>
          </div>
        </div>

      </button>
    </div>
  );
};
