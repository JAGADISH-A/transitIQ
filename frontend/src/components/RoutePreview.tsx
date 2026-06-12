import React from 'react';
import type { NormalizedRoute } from '../types/transit';

interface RoutePreviewProps {
  route: NormalizedRoute;
  onClick: () => void;
  isSelected?: boolean;
  isHero?: boolean;
  isCompared?: boolean;
  onCompareToggle?: (e: React.MouseEvent) => void;
}

export const RoutePreview: React.FC<RoutePreviewProps> = ({ route, onClick, isSelected, isHero = false, isCompared = false, onCompareToggle }) => {
  if (!route) return null;

  const {
    sourceName,
    destName,
    departureDisplay,
    arrivalDisplay,
    durationMinutes,
    transferCount,
    originalData
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

  return (
    <div className={`relative w-full rounded-[20px] transition-all duration-200 overflow-hidden ${
      isHero 
        ? 'p-5 bg-zinc-900 border border-zinc-700/50 shadow-md' 
        : 'bg-white/[0.02] border backdrop-blur-md hover:-translate-y-1 hover:shadow-lg ' + 
          (isCompared 
            ? 'border-[#FF4500]/50 shadow-[0_8px_30px_rgba(255,69,0,0.15)]' 
            : 'border-white/10 hover:border-white/20')
    } ${isSelected && !isHero ? 'bg-zinc-900 border-zinc-700' : ''}`}>
      
      {/* Compare Checkbox for Explorer Mode */}
      {onCompareToggle && (
        <button 
          onClick={onCompareToggle}
          className={`absolute top-4 right-4 w-6 h-6 rounded-full border flex items-center justify-center transition-colors z-10 ${
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
        className="w-full text-left p-4 cursor-pointer"
      >
      {isHero && (
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#FF4500]/80 to-[#FF4500]/20" />
      )}
      {/* Time Row */}
      <div className={`flex items-center gap-3 mb-1 ${isHero ? 'mb-2' : ''}`}>
        <span className="text-lg font-medium text-white">
          {departureDisplay?.display_time || '-'}
        </span>
        <span className="text-zinc-500">→</span>
        <span className="text-lg font-medium text-white">
          {arrivalDisplay?.display_time || '-'}
        </span>
        
        {/* Next Day Indication */}
        {(arrivalDisplay?.day_offset || 0) > 0 && (
          <span className="text-[10px] text-zinc-500 bg-zinc-800/50 px-2 py-0.5 rounded-full">
            +{arrivalDisplay?.day_offset}d
          </span>
        )}
      </div>

      {/* Route Name & Metadata */}
      <div className="flex flex-col gap-1.5 mb-3 mt-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-zinc-300 truncate">{sourceName}</span>
          <span className="text-zinc-600 text-[10px] pl-1">↓</span>
          <span className="text-sm font-medium text-zinc-300 truncate">{destName}</span>
        </div>
        
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-normal text-zinc-500 mt-1">
          <span>{formattedDuration}</span>
          <span>•</span>
          <span>{transferCount > 0 ? `${transferCount} Transfer${transferCount > 1 ? 's' : ''}` : 'Direct'}</span>
        </div>
      </div>

      {/* Recommendation / Quality Reason */}
      {showRecommendation && (
        <div className="text-sm font-normal text-zinc-400 mt-1">
          {isHero ? `✨ ${recommendation}` : recommendation}
        </div>
      )}
      {/* Missing Data Fields per User Requirement */}
      {onCompareToggle && (
        <div className="flex flex-wrap gap-x-4 gap-y-2 mt-4 pt-3 border-t border-white/5">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase text-zinc-500 font-bold">Fare</span>
            <span className="text-sm font-medium text-zinc-300">—</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] uppercase text-zinc-500 font-bold">Reliability</span>
            <span className="text-sm font-medium text-zinc-300">Not Available</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] uppercase text-zinc-500 font-bold">Walk</span>
            <span className="text-sm font-medium text-zinc-300">—</span>
          </div>
        </div>
      )}
    </button>
    </div>
  );
};
