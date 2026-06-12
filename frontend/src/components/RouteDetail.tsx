import React from 'react';
import { TrainFront, Footprints, User, Target, Play, CheckCircle2, X, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';
import type { NormalizedRoute, JourneyRoute, TransferJourney } from '../types/transit';

interface RouteDetailProps {
  route: NormalizedRoute;
  onBack: () => void;
}

export const RouteDetail: React.FC<RouteDetailProps> = ({ 
  route, 
  onBack
}) => {
  if (!route) return null;
  const isTransfer = route.isTransfer;

  console.log("ROUTE DETAIL INPUT", route);

  const duration = route.durationMinutes;
  

  
  const quality = (route.originalData as any).quality;

  const sourceName = route.sourceName;
  const destName = route.destName;

  const departureDisplay = route.departureDisplay;
  const arrivalDisplay = route.arrivalDisplay;

  const formatDuration = (mins: number) => {
    if (mins < 60) return `${mins}m`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  };

  const formattedDuration = formatDuration(duration);
  const recommendation = quality?.recommendation_reason !== 'Standard Route' ? quality?.recommendation_reason : null;

  const JourneyRow = ({ time, stationName, MainIcon, iconColor, actionTitle, ActionIcon, actionSubtitle, statusText, StatusIcon, statusColor, glowColor, isLast, railColor }: any) => (
    <div className="relative flex items-start gap-4 min-h-[56px]">
      {/* Timeline Rail */}
      {!isLast && (
        <div className={`absolute left-4 top-8 bottom-[-16px] w-[2px] ${railColor || 'bg-zinc-800/50'}`} />
      )}
      
      {/* Icon Node */}
      <div className={`relative z-10 flex items-center justify-center w-8 h-8 rounded-full bg-zinc-950 border border-zinc-800/80 shrink-0 ${iconColor}`}>
        <MainIcon size={16} strokeWidth={1.5} />
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 pt-1 pb-5">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[15px] font-semibold text-zinc-100 tracking-wide uppercase leading-none">{stationName}</span>
          <span className="text-xs font-medium text-zinc-500">{time || '-'}</span>
        </div>
        
        {(actionTitle || actionSubtitle) && (
          <div className="flex items-center gap-2 text-[13px] text-zinc-200 font-medium mb-2">
            {ActionIcon && <ActionIcon size={14} strokeWidth={1.5} className="text-zinc-500" />}
            <span>{actionTitle}</span>
            {actionSubtitle && <span className="text-zinc-500 font-normal ml-0.5 text-[12px]">{actionSubtitle}</span>}
          </div>
        )}

        {statusText && (
          <div className={`flex items-center gap-1.5 h-6 px-2.5 rounded-full bg-white/[0.03] border border-white/5 backdrop-blur-md w-fit text-[11px] font-medium text-zinc-300 tracking-wide ${glowColor || ''}`}>
            {StatusIcon && <StatusIcon size={12} strokeWidth={1.5} className={statusColor || 'text-zinc-400'} />}
            <span>{statusText}</span>
          </div>
        )}
      </div>
    </div>
  );

  const renderTimeline = () => {
    if (!isTransfer) {
      const r = route.originalData as JourneyRoute;
      return (
        <div className="flex flex-col pt-2">
          <JourneyRow 
            time={r.departure_display?.display_time}
            stationName={r.source_stop}
            MainIcon={TrainFront}
            iconColor="text-green-500"
            actionTitle="Board Train"
            ActionIcon={TrainFront}
            actionSubtitle={r.feed ? r.feed.toUpperCase() : 'LOCAL'}
            statusText={`On Board · ${r.duration_minutes} min`}
            StatusIcon={Play}
            statusColor="text-green-500/80"
            glowColor="shadow-[0_0_6px_rgba(34,197,94,0.08)]"
            railColor="bg-green-500/20"
          />
          <JourneyRow 
            time={r.arrival_display?.display_time}
            stationName={r.destination_stop}
            MainIcon={Target}
            iconColor="text-red-500"
            actionTitle="Destination Reached"
            ActionIcon={CheckCircle2}
            statusText="Arrived"
            StatusIcon={CheckCircle2}
            statusColor="text-red-500/80"
            glowColor="shadow-[0_0_6px_rgba(239,68,68,0.08)]"
            isLast={true}
          />
        </div>
      );
    }

    const r = route.originalData as TransferJourney;
    return (
      <div className="flex flex-col pt-2">
        {/* First Leg Origin */}
        <JourneyRow 
          time={r.first_leg.departure_display?.display_time}
          stationName={r.first_leg.source_stop}
          MainIcon={TrainFront}
          iconColor="text-green-500"
          actionTitle="Board Train"
          ActionIcon={TrainFront}
          actionSubtitle={r.first_leg.feed ? r.first_leg.feed.toUpperCase() : 'LOCAL'}
          statusText={`On Board · ${r.first_leg.duration_minutes} min`}
          StatusIcon={Play}
          statusColor="text-green-500/80"
          glowColor="shadow-[0_0_6px_rgba(34,197,94,0.08)]"
          railColor="bg-green-500/20"
        />
        
        {/* Transfer Stop */}
        <JourneyRow 
          time={r.first_leg.arrival_display?.display_time}
          stationName={r.transfer_stop}
          MainIcon={Footprints}
          iconColor="text-amber-500"
          actionTitle="Transfer Here"
          ActionIcon={Footprints}
          statusText={`Waiting · ${r.transfer_wait} min`}
          StatusIcon={User}
          statusColor="text-amber-500/80"
          glowColor="shadow-[0_0_6px_rgba(245,158,11,0.08)]"
          railColor="bg-amber-500/20"
        />

        {/* Second Leg Origin */}
        <JourneyRow 
          time={r.second_leg.departure_display?.display_time}
          stationName={r.transfer_stop}
          MainIcon={TrainFront}
          iconColor="text-cyan-500"
          actionTitle="Board Train"
          ActionIcon={TrainFront}
          actionSubtitle={r.second_leg.feed ? r.second_leg.feed.toUpperCase() : 'LOCAL'}
          statusText={`On Board · ${r.second_leg.duration_minutes} min`}
          StatusIcon={Play}
          statusColor="text-cyan-500/80"
          glowColor="shadow-[0_0_6px_rgba(6,182,212,0.08)]"
          railColor="bg-cyan-500/20"
        />

        {/* Final Destination */}
        <JourneyRow 
          time={r.second_leg.arrival_display?.display_time}
          stationName={r.second_leg.destination_stop}
          MainIcon={Target}
          iconColor="text-red-500"
          actionTitle="Destination Reached"
          ActionIcon={CheckCircle2}
          statusText="Arrived"
          StatusIcon={CheckCircle2}
          statusColor="text-red-500/80"
          glowColor="shadow-[0_0_6px_rgba(239,68,68,0.08)]"
          isLast={true}
        />
      </div>
    );
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: -10 }} 
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.2 }}
      className="flex flex-col w-full bg-[#111111] rounded-[20px] border border-white/5 shadow-2xl relative p-6 overflow-hidden"
    >
      {/* Top Navigation Row */}
      <div className="flex items-center justify-between mb-6">
        <button 
          onClick={onBack}
          className="flex items-center gap-2 text-[13px] font-medium text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={16} />
          Search Results
        </button>
        <button 
          onClick={onBack}
          className="w-8 h-8 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-all"
        >
          <X size={16} />
        </button>
      </div>

      {/* Page Header */}
      <div className="flex flex-col gap-4 pb-6 mb-6 border-b border-white/[0.08]">
        <div className="flex items-center gap-2 text-[24px] font-semibold text-zinc-100 tracking-tight pr-12">
          <span className="capitalize">{sourceName.toLowerCase()}</span>
          <span className="text-zinc-600 font-normal">→</span>
          <span className="capitalize">{destName.toLowerCase()}</span>
        </div>

        <div className="flex items-center gap-3 text-[16px] text-zinc-300 font-medium">
          <span>{departureDisplay?.display_time}</span>
          <span className="text-zinc-600">→</span>
          <span>{arrivalDisplay?.display_time}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[14px] text-zinc-400 font-medium">
          <span>{formattedDuration}</span>
          <span className="text-zinc-700">•</span>
          <span>{isTransfer ? '1 Transfer' : 'Direct'}</span>
          {recommendation && (
            <>
              <span className="text-zinc-700">•</span>
              <span className="text-zinc-300">✨ {recommendation}</span>
            </>
          )}
        </div>
      </div>

      {/* Main Journey Flow */}
      <div className="mb-4 pl-2 mt-2">
        {renderTimeline()}
      </div>
    </motion.div>
  );
};
