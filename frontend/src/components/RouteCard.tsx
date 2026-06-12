import React from 'react';
import type { NormalizedRoute, JourneyRoute, TransferJourney } from '../types/transit';
import { TrainFront, Bus, TramFront, ArrowRight } from 'lucide-react';

interface RouteCardProps {
  route: NormalizedRoute;
  onClick: () => void;
  isHero?: boolean;
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
    case 'Rail': return <TrainFront size={14} />;
    case 'Metro': return <TramFront size={14} />;
    case 'Bus': return <Bus size={14} />;
    default: return <TrainFront size={14} />;
  }
};

const toTitleCase = (str: string) => {
  return str.replace(
    /\w\S*/g,
    (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase()
  );
};

export const RouteCard: React.FC<RouteCardProps> = ({ route, onClick, isHero = false }) => {
  if (!route) return null;

  const {
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

  // Determine Modes used
  const modes: string[] = [];
  let trainLabel = '';
  
  if (isTransfer) {
    const t = originalData as TransferJourney;
    const mode1 = MODE_MAP[t.first_leg.feed] || 'Rail';
    const mode2 = MODE_MAP[t.second_leg.feed] || 'Rail';
    if (!modes.includes(mode1)) modes.push(mode1);
    if (!modes.includes(mode2)) modes.push(mode2);
    trainLabel = 'Multiple Services';
  } else {
    const t = originalData as JourneyRoute;
    const mode = MODE_MAP[t.feed] || 'Rail';
    modes.push(mode);
    const name = t.route_name;
    const id = t.route_id;
    if (name && id && name !== id) trainLabel = `${toTitleCase(name)}`;
    else if (name && name === id) trainLabel = `Train No. ${id}`;
    else if (name) trainLabel = toTitleCase(name);
    else if (id) trainLabel = `Train No. ${id}`;
  }

  return (
    <button
      onClick={onClick}
      className={`relative w-full text-left rounded-[24px] p-5 transition-all duration-300 group flex flex-col gap-4 ${
        isHero 
          ? 'bg-zinc-900 border border-[#FF4500]/50 shadow-[0_4px_20px_rgba(255,69,0,0.15)] -translate-y-0.5' 
          : 'bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] hover:border-white/10 hover:-translate-y-1 hover:shadow-lg'
      }`}
    >
      {/* Row 1: Times (Primary Focus) */}
      <div className="flex items-center gap-3 w-full">
        <span className="text-2xl font-bold text-white tracking-tight">
          {departureDisplay?.display_time || '-'}
        </span>
        <ArrowRight size={20} className="text-zinc-600 shrink-0" />
        <span className="text-2xl font-bold text-white tracking-tight">
          {arrivalDisplay?.display_time || '-'}
        </span>
        
        {(arrivalDisplay?.day_offset || 0) > 0 && (
          <span className="ml-auto text-[11px] font-bold text-[#FF4500] bg-[#FF4500]/10 px-2 py-1 rounded-full">
            +{arrivalDisplay?.day_offset} Day{arrivalDisplay?.day_offset! > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Row 2: Train/Service Name */}
      <div className="w-full">
        <span className="text-base font-semibold text-zinc-300 truncate block">
          {trainLabel || modes.join(' + ')}
        </span>
      </div>

      {/* Row 3: Compact Information Pills */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 bg-white/[0.04] border border-white/5 px-2.5 py-1 rounded-md text-xs font-semibold text-zinc-300">
          {formattedDuration}
        </div>
        
        <div className={`flex items-center gap-1.5 border px-2.5 py-1 rounded-md text-xs font-semibold ${
          transferCount === 0 
            ? 'bg-green-400/5 border-green-400/10 text-green-400' 
            : 'bg-amber-400/5 border-amber-400/10 text-amber-400'
        }`}>
          {transferCount === 0 ? 'Direct' : `${transferCount} Transfer${transferCount > 1 ? 's' : ''}`}
        </div>

        <div className="flex items-center gap-1.5 bg-white/[0.04] border border-white/5 px-2.5 py-1 rounded-md text-xs font-semibold text-zinc-300">
          {modes.map((m, i) => (
            <span key={i} title={m} className="flex items-center gap-1">
              {getModeIcon(m)}
              {m}
              {i < modes.length - 1 && <span className="text-zinc-600 mx-0.5">+</span>}
            </span>
          ))}
        </div>
      </div>

      {/* Row 4: Small Metadata Text */}
      <div className="w-full mt-1">
        <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-widest">
          Runs Daily
        </span>
      </div>
    </button>
  );
};
