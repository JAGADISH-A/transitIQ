import React from 'react';
import { TrainFront, Footprints, User, Target, Play, CheckCircle2, X, ArrowLeft, Brain, Map } from 'lucide-react';
import { motion } from 'framer-motion';
import type { NormalizedRoute, JourneyRoute, TransferJourney } from '../types/transit';
import { analyzeTransferRisk } from '../ai/journeyIntelligence';
import { analyzeRouteTradeoffs } from '../ai/routeTradeoffAnalyzer';

interface RouteDetailProps {
  route: NormalizedRoute;
  allRoutes?: NormalizedRoute[];
  onBack: () => void;
  onOpenRoadmap: () => void;
  onOpenAI?: () => void;
}

export const RouteDetail: React.FC<RouteDetailProps> = ({ 
  route, 
  allRoutes,
  onBack,
  onOpenRoadmap,
  onOpenAI
}) => {
  if (!route) return null;
  const isTransfer = route.isTransfer;


  if (route.transferCount === 2) {
      source: route.sourceName,
      destination: route.destName,
      transferCount: route.transferCount,
      hasThirdLeg: !!(route.originalData as any).third_leg
    });
  }

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

  const toTitleCase = (str: string) => {
    return str.replace(
      /\w\S*/g,
      (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase()
    );
  };

  const getTrainTitle = (journeyRoute: JourneyRoute) => {
    const name = journeyRoute.route_name;
    const id = journeyRoute.route_id;
    
    if (name && id && name !== id) return `🚆 ${toTitleCase(name)} (${id})`;
    if (name && name === id) return `🚆 Train No. ${id}`;
    if (name) return `🚆 ${toTitleCase(name)}`;
    if (id) return `🚆 Train No. ${id}`;
    
    return "Board Train";
  };

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
            actionTitle={getTrainTitle(r)}
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
    const extR = r as any;
    const hasThirdLeg = !!extR.third_leg;

    if (hasThirdLeg) {
      return (
        <div className="flex flex-col pt-2">
          {/* First Leg Origin */}
          <JourneyRow 
            time={r.first_leg.departure_display?.display_time}
            stationName={r.first_leg.source_stop}
            MainIcon={TrainFront}
            iconColor="text-green-500"
            actionTitle={getTrainTitle(r.first_leg)}
            ActionIcon={TrainFront}
            actionSubtitle={r.first_leg.feed ? r.first_leg.feed.toUpperCase() : 'LOCAL'}
            statusText={`On Board · ${r.first_leg.duration_minutes} min`}
            StatusIcon={Play}
            statusColor="text-green-500/80"
            glowColor="shadow-[0_0_6px_rgba(34,197,94,0.08)]"
            railColor="bg-green-500/20"
          />
          
          {/* Transfer Stop 1 */}
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
            actionTitle={getTrainTitle(r.second_leg)}
            ActionIcon={TrainFront}
            actionSubtitle={r.second_leg.feed ? r.second_leg.feed.toUpperCase() : 'LOCAL'}
            statusText={`On Board · ${r.second_leg.duration_minutes} min`}
            StatusIcon={Play}
            statusColor="text-cyan-500/80"
            glowColor="shadow-[0_0_6px_rgba(6,182,212,0.08)]"
            railColor="bg-cyan-500/20"
          />

          {/* Transfer Stop 2 */}
          <JourneyRow 
            time={r.second_leg.arrival_display?.display_time}
            stationName={extR.transfer_stop_2}
            MainIcon={Footprints}
            iconColor="text-amber-500"
            actionTitle="Transfer Here"
            ActionIcon={Footprints}
            statusText={`Waiting · ${extR.transfer_wait_2} min`}
            StatusIcon={User}
            statusColor="text-amber-500/80"
            glowColor="shadow-[0_0_6px_rgba(245,158,11,0.08)]"
            railColor="bg-amber-500/20"
          />

          {/* Third Leg Origin */}
          <JourneyRow 
            time={extR.third_leg.departure_display?.display_time}
            stationName={extR.transfer_stop_2}
            MainIcon={TrainFront}
            iconColor="text-indigo-500"
            actionTitle={getTrainTitle(extR.third_leg)}
            ActionIcon={TrainFront}
            actionSubtitle={extR.third_leg.feed ? extR.third_leg.feed.toUpperCase() : 'LOCAL'}
            statusText={`On Board · ${extR.third_leg.duration_minutes} min`}
            StatusIcon={Play}
            statusColor="text-indigo-500/80"
            glowColor="shadow-[0_0_6px_rgba(99,102,241,0.08)]"
            railColor="bg-indigo-500/20"
          />

          {/* Final Destination */}
          <JourneyRow 
            time={extR.third_leg.arrival_display?.display_time}
            stationName={extR.third_leg.destination_stop}
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

    return (
      <div className="flex flex-col pt-2">
        {/* First Leg Origin */}
        <JourneyRow 
          time={r.first_leg.departure_display?.display_time}
          stationName={r.first_leg.source_stop}
          MainIcon={TrainFront}
          iconColor="text-green-500"
          actionTitle={getTrainTitle(r.first_leg)}
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
          actionTitle={getTrainTitle(r.second_leg)}
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
          <span>{isTransfer ? (route.transferCount === 2 ? '2 Transfers' : '1 Transfer') : 'Direct'}</span>
          {recommendation && (
            <>
              <span className="text-zinc-700">•</span>
              <span className="text-zinc-300">✨ {recommendation}</span>
            </>
          )}
        </div>
      </div>

      {/* Prominent Journey Roadmap CTA */}
      {onOpenRoadmap && (
        <button 
          onClick={onOpenRoadmap}
          className="w-full flex items-center justify-center gap-2 mb-6 py-3.5 bg-[#FF4500] hover:bg-[#e63e00] text-white font-semibold rounded-xl shadow-[0_4px_20px_rgba(255,69,0,0.3)] hover:shadow-[0_6px_25px_rgba(255,69,0,0.4)] transition-all"
        >
          <Map size={18} />
          <span>Open Journey Roadmap</span>
        </button>
      )}

      {/* TransitIQ Insight */}
      {(() => {
        const transferRisk = analyzeTransferRisk(route);

        if (allRoutes && allRoutes.length > 1) {
          const comparison = analyzeRouteTradeoffs(allRoutes, route);
          return (
            <div className="flex flex-col gap-4 mb-6">
              {/* Advantages */}
              {comparison.advantages.length > 0 && (
                <div className="flex flex-col gap-2 p-4 bg-[#FF4500]/5 border border-[#FF4500]/20 rounded-xl">
                  <div className="flex items-center gap-2 text-[14px] font-semibold text-[#FF4500] mb-1">
                    <Brain size={16} />
                    Why Choose This Route
                  </div>
                  <ul className="flex flex-col gap-2 text-[13px] text-zinc-300">
                    {comparison.advantages.map((adv, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <CheckCircle2 size={14} className="text-[#FF4500] shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold text-zinc-200">{adv.title}: </span>
                          <span className="text-zinc-400">{adv.description}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Tradeoffs */}
              {comparison.tradeoffs.length > 0 && (
                <div className="flex flex-col gap-2 p-4 bg-amber-500/5 border border-amber-500/20 rounded-xl">
                  <div className="flex items-center gap-2 text-[14px] font-semibold text-amber-500 mb-1">
                    <Brain size={16} />
                    Things to Consider
                  </div>
                  <ul className="flex flex-col gap-2 text-[13px] text-zinc-300">
                    {comparison.tradeoffs.map((td, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <X size={14} className="text-amber-500 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold text-zinc-200">{td.title}: </span>
                          <span className="text-zinc-400">{td.description}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Alternatives */}
              {comparison.alternatives.length > 0 && (
                <div className="flex flex-col gap-2 p-4 bg-zinc-900 border border-white/5 rounded-xl">
                  <div className="flex items-center gap-2 text-[14px] font-semibold text-zinc-300 mb-2">
                    <Target size={16} />
                    Alternative Options
                  </div>
                  <div className="flex flex-col gap-3">
                    {comparison.alternatives.map((alt, i) => (
                      <div key={i} className="flex flex-col gap-1 text-[13px] border-l-2 border-[#FF4500]/40 pl-3">
                        <span className="font-semibold text-zinc-200">{alt.label}</span>
                        <ul className="text-zinc-400 space-y-1">
                          {alt.pros.map((pro, j) => <li key={`pro-${j}`}>• {pro}</li>)}
                          {alt.cons.map((con, j) => <li key={`con-${j}`}>• {con}</li>)}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        }
        
        const reasons = [];
        // Basic intelligence logic using existing data
        if (route.durationMinutes < 60) reasons.push("Fast and efficient journey duration");
        if (route.transferCount === 0) reasons.push("Direct service with no transfers needed");
        else reasons.push(`${transferRisk.title}: ${transferRisk.message}`);
        
        if (route.transferWait) {
           reasons.push(`${route.transferWait} minute connection buffer`);
        }

        return (
          <div className="flex flex-col gap-3 mb-6 p-4 bg-[#FF4500]/5 border border-[#FF4500]/20 rounded-xl">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2 text-[14px] font-semibold text-[#FF4500]">
                <Brain size={16} />
                TransitIQ Insight
              </div>
            </div>
            <p className="text-[13px] text-zinc-300 leading-relaxed font-medium">
              TransitIQ highlights this route because:
            </p>
            <ul className="flex flex-col gap-1.5 mt-1 text-[13px] text-zinc-300">
              {reasons.map((reason, i) => (
                <li key={i} className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="text-[#FF4500] shrink-0 mt-0.5" />
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      })()}

      {/* AI Contextual Action */}
      {onOpenAI && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#1a1a1a] border border-[#FF4500]/30 rounded-xl p-3 sm:px-4 mb-6 shadow-[0_4px_12px_rgba(0,0,0,0.5)]">
          <div className="flex items-center gap-2 text-[13px] font-medium text-zinc-200">
            <div className="w-6 h-6 rounded-full bg-[#FF4500]/20 flex items-center justify-center shrink-0">
              <Brain size={13} className="text-[#FF4500]" />
            </div>
            <span>Have questions about this route?</span>
          </div>
          <button
            onClick={onOpenAI}
            className="shrink-0 flex items-center justify-center gap-1.5 bg-[#FF4500] hover:bg-[#e63e00] text-white px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors"
          >
            Ask TransitIQ
          </button>
        </div>
      )}

      {/* Main Journey Flow */}
      <div className="mb-4 pl-2 mt-2">
        {renderTimeline()}
      </div>
    </motion.div>
  );
};
