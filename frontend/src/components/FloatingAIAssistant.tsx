import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Sparkles, X, Send, Loader2, Train, AlertTriangle, Clock, MapPin, ArrowRight, RefreshCw, BarChart2, GitBranch, Footprints, Zap } from 'lucide-react';

import type { JourneyNarrative, JourneyContext, JourneyRoute, NormalizedRoute, TransferJourney } from '../types/transit';
import type { RouteRecommendation, JourneyInsight } from '../ai/types';
import { recommendBestRoute } from '../ai/routeAdvisor';
import { analyzeTransferRisk } from '../ai/transferRiskAnalyzer';
import { generateWorkspaceIntelligence } from '../ai/journeyConcierge';

type MessageType = 'text' | 'searching' | 'result' | 'error' | 'not-found';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  type: MessageType;
  text: string;
  source?: string;
  destination?: string;
  directCount?: number;
  transferCount?: number;
  narrative?: JourneyNarrative;
  suggestions?: string[];
  recommendation?: RouteRecommendation;
  recommendedRoute?: NormalizedRoute;
  allRoutes?: NormalizedRoute[];
};

interface SearchResult {
  directCount: number;
  transferCount: number;
  source: string;
  destination: string;
  error?: string;
  narrative?: JourneyNarrative;
  topDirectRoute?: JourneyRoute;
  topTransferRoute?: any;
  normalizedRoutes?: NormalizedRoute[];
}

interface FloatingAIAssistantProps {
  onSearch: (source: string, destination: string, time?: string) => Promise<any>;
  activeRoute: NormalizedRoute | null;
  onRouteSelect?: (route: NormalizedRoute | null) => void;
  tripStops?: any[];
  transferStops?: {leg1: any[], leg2: any[]} | null;
  onStationFocus?: (coords: [number, number] | null) => void;
}

const chipSuggestions = [
  { icon: "🚆", label: "Chennai Central from Avadi" },
  { icon: "🏢", label: "Guindy from Avadi" },
  { icon: "📍", label: "Chennai Beach" },
  { icon: "⚡", label: "Fastest route to Guindy" },
];

const formatDuration = (mins: number) => {
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
};


/* ─── Assistant message card ─── */
const AssistantCard = React.memo(({ 
  msg, 
  activeRouteId,
  allRoutes,
  onRouteSelect 
}: { 
  msg: Message, 
  activeRouteId?: string,
  allRoutes?: NormalizedRoute[],
  onRouteSelect?: (route: NormalizedRoute | null) => void 
}) => {
  const activeRoute = allRoutes?.find(r => r.id === activeRouteId) || msg.recommendedRoute;
  const intel = activeRoute ? generateWorkspaceIntelligence(activeRoute) : null;

  if (msg.role === 'assistant') {
    return (
      <div className="flex w-full mb-4">
        <div className="flex items-start gap-3 w-full">
          <div className="w-8 h-8 rounded-full bg-[#111] border border-[#222] flex items-center justify-center shrink-0 shadow-lg mt-0.5">
            {msg.type === 'searching' ? (
              <Loader2 size={14} className="text-[#888] animate-spin" />
            ) : (
              <Sparkles size={14} className="text-[#FF4500]" />
            )}
          </div>
          
          {msg.type === 'searching' ? (
            <div className="bg-[#111] border border-[#222] rounded-lg px-4 py-3 flex items-center gap-3">
              <span className="text-[#888] text-[14px]">Searching optimal routes...</span>
            </div>
          ) : msg.type === 'result' && msg.recommendedRoute ? (
            <div className="flex flex-col gap-2 w-full">
              <div className="flex flex-col md:flex-row gap-4 bg-[#111] border border-[#252525] rounded-xl p-5 shadow-2xl w-full">
                <div className="flex-1 flex flex-col gap-5">
                  
                  {/* Guidance Section */}
                  <div className="flex flex-col gap-2">
                    <h4 className="text-[14px] font-bold text-white flex items-center gap-2">
                      <Sparkles size={14} className="text-[#FF4500]" /> 🧠 TransitIQ Guidance
                    </h4>
                    <p className="text-[14px] text-[#ccc] leading-relaxed">
                      {intel?.guidance}
                    </p>
                  </div>

                  {/* Timeline Section */}
                  {intel?.timeline && intel.timeline.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <h4 className="text-[14px] font-bold text-white flex items-center gap-2">
                        <Footprints size={14} className="text-[#FF4500]" /> 🚶 What Happens Next
                      </h4>
                      <div className="mt-2 flex flex-col gap-0 border-l-2 border-[#333] ml-2 pl-4 py-1 relative">
                        {intel.timeline.map((step, i) => (
                          <div key={i} className="flex items-center gap-3 mb-4 last:mb-0 relative">
                            <div className="absolute -left-[21px] w-2 h-2 rounded-full bg-[#FF4500]" />
                            {step.time && <span className="text-[13px] font-medium text-[#888] w-16">{step.time}</span>}
                            <span className={`text-[13px] ${step.time ? 'text-white' : 'text-[#aaa]'}`}>{step.step}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tips Section */}
                  {intel?.tips && intel.tips.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <h4 className="text-[14px] font-bold text-white flex items-center gap-2">
                        <Zap size={14} className="text-[#FF4500]" /> 💡 Travel Tips
                      </h4>
                      <div className="flex flex-col gap-2 mt-1">
                        {intel.tips.map((tip, i) => (
                          <div key={i} className="flex items-start gap-2 bg-[#1a1a1a] border border-[#252525] rounded-lg p-3">
                            <span className="text-[13px] text-[#ccc] leading-relaxed">{tip}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {onRouteSelect && (
                  <div className="shrink-0 flex items-center justify-end w-full md:w-auto md:h-full">
                    <button 
                      onClick={() => onRouteSelect(activeRoute!)}
                      className="w-full md:w-auto px-5 py-2.5 bg-[#FF4500] hover:bg-[#e63e00] text-white font-medium text-[13px] rounded-lg transition-colors shadow-[0_4px_14px_rgba(255,69,0,0.3)] hover:shadow-[0_6px_20px_rgba(255,69,0,0.4)] focus:outline-none"
                    >
                      More Information
                    </button>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-3 px-1 text-[12px] text-[#888]">
                <span>Found {msg.directCount} direct, {msg.transferCount} transfer routes</span>
              </div>
            </div>
          ) : (
            <div className="bg-[#161616] border border-[#252525] rounded-lg px-4 py-3 border-l-2 border-l-[#FF4500]">
            <div className="flex flex-col gap-2">
              <h4 className="text-[15px] font-semibold text-white">{msg.narrative?.headline || 'Results Found'}</h4>
              <p className="text-[14px] text-[#d0d0d0] leading-relaxed">{msg.narrative?.summary || msg.text}</p>
              {msg.narrative?.recommendation && (
                <p className="text-[14px] text-[#d0d0d0] leading-relaxed">{msg.narrative.recommendation}</p>
              )}
              
              {msg.narrative?.warnings && msg.narrative.warnings.length > 0 && (
                <div className="flex flex-col gap-1 mt-1">
                  {msg.narrative.warnings.map((w, i) => (
                    <div key={i} className="flex items-center gap-1.5 text-[13px] text-amber-400">
                      <AlertTriangle size={12} />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="flex items-center gap-3 mt-2 pt-2 border-t border-[#252525] text-[12px] text-[#888]">
                {msg.directCount! > 0 && <span className="bg-[#1e1e1e] border border-[#2a2a2a] rounded px-2 py-0.5">{msg.directCount} direct</span>}
                {msg.transferCount! > 0 && <span className="bg-[#1e1e1e] border border-[#2a2a2a] rounded px-2 py-0.5">{msg.transferCount} transfer</span>}
              </div>
            </div>
          </div>
        )}
        </div>
      </div>
    );
  }

  if (msg.type === 'not-found' || msg.type === 'error') {
    return (
      <div className="flex items-start gap-3 w-full max-w-[90%]">
        <div className="w-6 h-6 rounded bg-[#FF4500] flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles size={12} className="text-white" />
        </div>
        <div className="bg-[#161616] border border-[#252525] rounded-lg px-4 py-3 border-l-2 border-l-amber-500/60">
          <div className="flex items-center gap-2 text-[13px] text-amber-400 font-medium mb-1.5">
            <AlertTriangle size={14} />
            <span>{msg.type === 'not-found' ? 'Route Search Issue' : 'Connection Error'}</span>
          </div>
          <p className="text-[13px] text-[#999] leading-relaxed">{msg.text}</p>
          {msg.suggestions && msg.suggestions.length > 0 && (
            <div className="mt-2.5 pt-2 border-t border-[#222]">
              <p className="text-[12px] text-[#666] mb-1.5">Try:</p>
              <div className="flex flex-col gap-1">
                {msg.suggestions.map((s, i) => (
                  <span key={i} className="text-[12px] text-[#888]">• {s}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 w-full max-w-[90%]">
      <div className="w-6 h-6 rounded bg-[#FF4500] flex items-center justify-center shrink-0 mt-0.5">
        <Sparkles size={12} className="text-white" />
      </div>
      <div className="bg-[#161616] border border-[#252525] rounded-lg px-4 py-3 border-l-2 border-l-[#FF4500]">
        <p className="text-[14px] text-[#d0d0d0] leading-relaxed">{msg.text}</p>
      </div>
    </div>
  );
});

/* ─── User message bubble ─── */
const UserBubble = React.memo(({ text }: { text: string }) => (
  <div className="flex w-full justify-end">
    <div className="bg-[#1e1e1e] border border-[#2a2a2a] hover:border-[#FF4500]/30 text-[#e0e0e0] text-[14px] px-4 py-2.5 rounded-xl max-w-[70%] transition-colors">
      {text}
    </div>
  </div>
));

/* ─── Isolated input ─── */
const ChatInput = ({ onSubmit, disabled, large }: { onSubmit: (t: string) => void; disabled: boolean; large?: boolean }) => {
  const [val, setVal] = useState('');
  const submit = useCallback(() => {
    if (!val.trim() || disabled) return;
    onSubmit(val);
    setVal('');
  }, [val, disabled, onSubmit]);

  return (
    <div className="flex items-center bg-[#111] border border-[#2a2a2a] focus-within:border-[#444] shadow-inner rounded-xl overflow-hidden transition-colors">
      <input
        type="text"
        autoFocus
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && submit()}
        disabled={disabled}
        placeholder="Ask TransitIQ to plan a journey..."
        className={`flex-1 bg-transparent text-[#e0e0e0] ${large ? 'text-[15px] px-4 py-4' : 'text-[14px] px-4 py-3'} focus:outline-none placeholder:text-[#555] disabled:opacity-40`}
      />
      <button
        onClick={submit}
        disabled={!val.trim() || disabled}
        className="mr-2 w-8 h-8 rounded-lg bg-[#FF4500] hover:bg-[#e63e00] disabled:bg-[#333] disabled:opacity-30 flex items-center justify-center text-white transition-colors"
      >
        {disabled ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
      </button>
    </div>
  );
};

/* ─── Context Panel Component ─── */
const ContextPanel = ({ 
  route, 
  recommendation,
  allRoutes,
  onSelectAlternative
}: { 
  route: NormalizedRoute | null; 
  recommendation?: RouteRecommendation;
  allRoutes?: NormalizedRoute[];
  onSelectAlternative?: (r: NormalizedRoute) => void;
}) => {
  if (!route) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center border-l border-[#1e1e1e] bg-zinc-950">
        <div className="w-16 h-16 rounded-full bg-[#111] border border-[#222] flex items-center justify-center mb-4">
          <Sparkles size={24} className="text-[#333]" />
        </div>
        <h3 className="text-[16px] font-medium text-white/40 mb-2">Journey Dashboard</h3>
        <p className="text-[13px] text-white/20">Ask for a route to view deep insights, comparisons, and predictive travel intelligence here.</p>
      </div>
    );
  }

  const { isTransfer, originalData } = route;
  const risk = recommendation?.transferRisk || (route ? analyzeTransferRisk(route) : null);
  const isRecommended = recommendation && route.id === recommendation.recommendedRouteId;
  const activeAlt = !isRecommended ? recommendation?.comparison?.alternatives.find(a => a.routeId === route.id) : null;

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto border-l border-[#1e1e1e] bg-zinc-950 custom-scrollbar">
      <div className="p-5 border-b border-[#1e1e1e] sticky top-0 bg-zinc-950/90 backdrop-blur z-10 flex items-center gap-2">
        <Sparkles size={14} className="text-[#FF4500]" /> 
        <h3 className="text-[14px] font-bold text-white tracking-wide uppercase">Journey Dashboard</h3>
      </div>

      <div className="p-5 flex flex-col gap-6">
        
        {/* Selected Journey */}
        <div className="flex flex-col gap-3">
          <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider flex items-center gap-2">
            <Train size={14} /> Selected Journey
          </h4>
          <div className="bg-[#111] border border-[#222] rounded-lg p-4 flex flex-col gap-4">
            {!isTransfer ? (
              <div className="flex flex-col gap-2">
                <p className="text-[12px] text-[#FF4500] font-semibold uppercase tracking-wider">Train 1: {(originalData as any).route_name}</p>
                <div className="flex justify-between items-center text-[13px]">
                  <div className="flex flex-col">
                    <span className="text-[#888]">From:</span>
                    <span className="text-white font-medium">{(originalData as any).source_stop}</span>
                    <span className="text-white">{route.departureDisplay?.display_time}</span>
                  </div>
                  <div className="w-px h-8 bg-[#333]" />
                  <div className="flex flex-col text-right">
                    <span className="text-[#888]">To:</span>
                    <span className="text-white font-medium">{(originalData as any).destination_stop}</span>
                    <span className="text-white">{route.arrivalDisplay?.display_time}</span>
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-[#222] text-[12px] text-[#888]">
                  Travel Time: {formatDuration(route.durationMinutes)}
                </div>
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-2">
                  <p className="text-[12px] text-[#FF4500] font-semibold uppercase tracking-wider">Train 1: {(originalData as any).first_leg?.route_name}</p>
                  <div className="flex justify-between items-center text-[13px]">
                    <div className="flex flex-col">
                      <span className="text-[#888]">From:</span>
                      <span className="text-white font-medium">{(originalData as any).first_leg?.source_stop}</span>
                      <span className="text-white">{(originalData as any).first_leg?.departure_time}</span>
                    </div>
                    <div className="w-px h-8 bg-[#333]" />
                    <div className="flex flex-col text-right">
                      <span className="text-[#888]">To:</span>
                      <span className="text-white font-medium">{(originalData as any).first_leg?.destination_stop}</span>
                      <span className="text-white">{(originalData as any).first_leg?.arrival_time}</span>
                    </div>
                  </div>
                </div>
                <div className="h-px w-full bg-[#333]" />
                <div className="flex flex-col gap-2">
                  <p className="text-[12px] text-[#FF4500] font-semibold uppercase tracking-wider">Train 2: {(originalData as any).second_leg?.route_name}</p>
                  <div className="flex justify-between items-center text-[13px]">
                    <div className="flex flex-col">
                      <span className="text-[#888]">From:</span>
                      <span className="text-white font-medium">{(originalData as any).second_leg?.source_stop}</span>
                      <span className="text-white">{(originalData as any).second_leg?.departure_time}</span>
                    </div>
                    <div className="w-px h-8 bg-[#333]" />
                    <div className="flex flex-col text-right">
                      <span className="text-[#888]">To:</span>
                      <span className="text-white font-medium">{(originalData as any).second_leg?.destination_stop}</span>
                      <span className="text-white">{(originalData as any).second_leg?.arrival_time}</span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Train Change Details */}
        {isTransfer && (
          <div className="flex flex-col gap-3">
            <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider flex items-center gap-2">
              <RefreshCw size={14} /> Train Change Details
            </h4>
            <div className="bg-[#111] border border-[#222] rounded-lg p-4">
              <p className="text-[13px] text-[#ccc] mb-2">You need to change trains at:</p>
              <p className="text-[14px] font-bold text-white flex items-center gap-1.5 mb-4">
                <MapPin size={14} className="text-[#FF4500]" /> {route.transferStopName}
              </p>
              <p className="text-[13px] text-[#ccc] mb-1">Available time:</p>
              <p className="text-[14px] font-bold text-white mb-4 flex items-center gap-1.5">
                <Clock size={14} className="text-amber-500" /> {formatDuration(route.transferWait || 0)}
              </p>
              <div className="pt-3 border-t border-[#222]">
                <p className="text-[12px] font-semibold text-[#888] uppercase tracking-wider mb-1.5">Advice</p>
                <p className="text-[13px] text-[#ccc] leading-relaxed">{risk?.message}</p>
              </div>
            </div>
          </div>
        )}

        {/* Quick Journey Facts */}
        <div className="flex flex-col gap-3">
          <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider flex items-center gap-2">
            <BarChart2 size={14} /> Quick Journey Facts
          </h4>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-[#111] border border-[#222] rounded-lg p-3">
              <p className="text-[11px] text-[#666] uppercase tracking-wider mb-1">Total Duration</p>
              <p className="text-[14px] font-semibold text-white">{formatDuration(route.durationMinutes)}</p>
            </div>
            <div className="bg-[#111] border border-[#222] rounded-lg p-3">
              <p className="text-[11px] text-[#666] uppercase tracking-wider mb-1">Number of Trains</p>
              <p className="text-[14px] font-semibold text-white">{route.transferCount + 1}</p>
            </div>
            <div className="bg-[#111] border border-[#222] rounded-lg p-3">
              <p className="text-[11px] text-[#666] uppercase tracking-wider mb-1">Train Changes</p>
              <p className="text-[14px] font-semibold text-white">{route.transferCount}</p>
            </div>
            <div className="bg-[#111] border border-[#222] rounded-lg p-3">
              <p className="text-[11px] text-[#666] uppercase tracking-wider mb-1">Waiting Time</p>
              <p className="text-[14px] font-semibold text-white">{route.transferWait ? formatDuration(route.transferWait) : '0 min'}</p>
            </div>
          </div>
        </div>

        {/* Comparison Engine */}
        {isRecommended ? (
          <div className="flex flex-col gap-3">
            <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider flex items-center gap-2">
              <Sparkles size={14} /> 🧠 Why TransitIQ Chose This Route
            </h4>
            <div className="flex flex-col gap-3">
              {recommendation?.comparison?.advantages?.length ? (
                <div className="bg-[#111] border border-[#222] rounded-lg p-4">
                  <p className="text-[12px] font-semibold text-[#888] uppercase tracking-wider mb-3">Advantages</p>
                  <ul className="flex flex-col gap-3">
                    {recommendation.comparison.advantages.map((adv, i) => (
                      <li key={i} className="flex flex-col gap-0.5">
                        <span className="text-[13px] font-bold text-white">{adv.title}</span>
                        <span className="text-[13px] text-[#ccc] leading-relaxed">
                          <span className="text-[#888] mr-1.5">•</span>{adv.description}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {recommendation?.comparison?.tradeoffs?.length ? (
                <div className="bg-[#111] border border-[#222] rounded-lg p-4">
                  <p className="text-[12px] font-semibold text-[#888] uppercase tracking-wider mb-3">Things To Know</p>
                  <ul className="flex flex-col gap-3">
                    {recommendation.comparison.tradeoffs.map((trd, i) => (
                      <li key={i} className="flex flex-col gap-0.5">
                        <span className="text-[13px] font-bold text-white">{trd.title}</span>
                        <span className="text-[13px] text-[#ccc] leading-relaxed">
                          <span className="text-[#888] mr-1.5">•</span>{trd.description}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </div>
        ) : activeAlt ? (
          <div className="flex flex-col gap-3">
            <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider flex items-center gap-2">
              <Sparkles size={14} /> 🔍 How This Route Compares
            </h4>
            <div className="bg-[#111] border border-[#222] rounded-lg p-4">
              <p className="text-[14px] font-bold text-white mb-3">{activeAlt.label} Alternative</p>
              <ul className="flex flex-col gap-2">
                {activeAlt.pros.map((pro, i) => (
                  <li key={`pro-${i}`} className="text-[13px] text-[#ccc] flex items-start gap-2 leading-relaxed">
                    <span className="text-emerald-500 font-bold mt-0.5">+</span> {pro}
                  </li>
                ))}
                {activeAlt.cons.map((con, i) => (
                  <li key={`con-${i}`} className="text-[13px] text-[#ccc] flex items-start gap-2 leading-relaxed">
                    <span className="text-rose-500 font-bold mt-0.5">-</span> {con}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}

        {/* Alternative Choices */}
        {recommendation?.comparison?.alternatives && recommendation.comparison.alternatives.filter(a => a.routeId !== route.id).length > 0 && (
          <div className="flex flex-col gap-3">
            <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider flex items-center gap-2">
              <GitBranch size={14} /> Alternative Choices
            </h4>
            <div className="flex flex-col gap-3">
              {recommendation.comparison.alternatives.filter(a => a.routeId !== route.id).map((alt, i) => {
                const altRoute = allRoutes?.find(r => r.id === alt.routeId);
                return (
                  <div key={i} className="bg-[#111] border border-[#222] rounded-lg p-3 flex flex-col gap-3 group transition-colors hover:border-[#444]">
                    <div className="flex items-center justify-between">
                      <span className="text-[14px] font-bold text-white">{alt.label}</span>
                      <button 
                        onClick={() => altRoute && onSelectAlternative?.(altRoute)}
                        className="px-3 py-1.5 rounded-lg bg-[#222] hover:bg-[#FF4500] border border-[#333] hover:border-[#FF4500] text-[12px] font-medium text-white transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
                      >
                        View Route
                      </button>
                    </div>
                    <ul className="flex flex-col gap-1.5">
                      {alt.pros.map((pro, j) => (
                        <li key={`pro-${j}`} className="text-[13px] text-[#ccc] flex items-start gap-2 leading-relaxed">
                          <span className="text-emerald-500 font-bold mt-0.5">+</span> {pro}
                        </li>
                      ))}
                      {alt.cons.map((con, j) => (
                        <li key={`con-${j}`} className="text-[13px] text-[#ccc] flex items-start gap-2 leading-relaxed">
                          <span className="text-rose-500 font-bold mt-0.5">-</span> {con}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

/* ─── Main component ─── */
export default function FloatingAIAssistant({ 
  onSearch, 
  activeRoute, 
  onRouteSelect,
  tripStops,
  transferStops,
  onStationFocus 
}: FloatingAIAssistantProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionContext, setSessionContext] = useState<JourneyContext | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeRoute) {
      setSessionContext(prev => ({
        ...prev,
        active_journey: {
          source: activeRoute.source_stop || (activeRoute.first_leg && activeRoute.first_leg.source_stop) || '',
          destination: activeRoute.destination_stop || (activeRoute.second_leg && activeRoute.second_leg.destination_stop) || '',
          departure_time: activeRoute.departure_time || (activeRoute.first_leg && activeRoute.first_leg.departure_time) || '',
          transfer_station: activeRoute.transfer_stop || undefined,
          transfer_count: activeRoute.journey_type === 'TRANSFER' ? 1 : 0
        }
      }));
    }
  }, [activeRoute]);

  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === 'Escape' && isOpen) setIsOpen(false); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [isOpen]);

  useEffect(() => {
    document.body.style.overflow = isOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const addMsg = useCallback((msg: Omit<Message, 'id'>) => {
    setMessages(prev => [...prev, { ...msg, id: Date.now().toString() + Math.random().toString(36).slice(2, 6) }]);
  }, []);

  const handleSubmit = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    addMsg({ role: 'user', type: 'text', text });
    setIsLoading(true);

    try {
      const res = await fetch('http://localhost:8000/ai/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, context: sessionContext })
      });
      if (!res.ok) throw new Error('Failed to reach AI planner');

      const intent = await res.json();
      
      if (intent.intent_type === 'CONTEXT_EXPIRED' || intent.error_message) {
         setSessionContext(null);
         addMsg({ role: 'assistant', type: 'error', text: intent.error_message || "I'm not sure which journey you're referring to. Could you tell me the route again?" });
         return;
      }
      
      if (intent.intent_type === 'EXPLAIN_ROUTE') {
         if (sessionContext?.active_journey) {
            const aj = sessionContext.active_journey;
            let text = "This is a direct service with no transfers.";
            if (aj.transfer_count > 0) {
               text = `This route has ${aj.transfer_count} transfer(s). You will change trains at ${aj.transfer_station}.`;
            }
            addMsg({ role: 'assistant', type: 'text', text });
         } else {
            addMsg({ role: 'assistant', type: 'text', text: "You haven't selected a specific route yet for me to explain." });
         }
         return;
      }

      const src = intent.source?.trim();
      const dst = intent.destination?.trim();

      if (src || dst) {
        const from = src || 'your location';
        const to = dst || 'your destination';

        const comp = sessionContext?.previous_comparison || undefined;
        setSessionContext(prev => ({
           ...prev,
           source: src,
           destination: dst,
           departure_time: intent.departure_time,
           last_updated: new Date().toISOString(),
           previous_comparison: comp
        }));

        addMsg({
          role: 'assistant',
          type: 'searching',
          text: `Looking for routes from ${from} to ${to}.`,
          source: from,
          destination: to,
        });

        if (src && dst && onSearch) {
          const r = await onSearch(src, dst, intent.departure_time || undefined);
          const total = r.directCount + r.transferCount;

          if (r.error) {
            if (r.error.startsWith("Source not found:") || r.error.startsWith("Destination not found:")) {
              const notFoundStop = r.error.split(": ")[1];
              addMsg({
                role: 'assistant',
                type: 'not-found',
                text: `I couldn't match "${notFoundStop}" to known transit stops in the network.`,
                suggestions: [`${notFoundStop} Railway Station`, 'Or select a stop from the planner panel'],
              });
            } else {
              addMsg({ role: 'assistant', type: 'error', text: r.error });
            }
          } else if (total === 0) {
            addMsg({
              role: 'assistant',
              type: 'result',
              text: `No routes are currently available between ${r.source} and ${r.destination}.`,
              directCount: 0,
              transferCount: 0,
            });
          } else {
            let recommendation;
            let recommendedRoute;
            if (r.normalizedRoutes && r.normalizedRoutes.length > 0) {
              const bestRec = recommendBestRoute(r.normalizedRoutes);
              if (bestRec) {
                recommendation = bestRec;
                recommendedRoute = r.normalizedRoutes.find(n => n.id === bestRec.recommendedRouteId);
              }
            }

            addMsg({
              role: 'assistant',
              type: 'result',
              text: '',
              directCount: r.directCount,
              transferCount: r.transferCount,
              narrative: r.narrative,
              recommendation,
              recommendedRoute,
              allRoutes: r.normalizedRoutes,
            });
          }
        }
      } else {
        addMsg({
          role: 'assistant',
          type: 'text',
          text: 'I couldn\'t understand that. Try something like "Avadi to Guindy" or "Reach Chennai Central from Avadi".',
        });
      }
    } catch {
      addMsg({ role: 'assistant', type: 'error', text: 'Unable to connect. Please check your connection and try again.' });
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, onSearch, addMsg, sessionContext]);

  const lastRecMsg = [...messages].reverse().find(m => m.recommendation);
  const latestMsgId = lastRecMsg?.id;

  const [panelMsgId, setPanelMsgId] = useState<string | null>(null);
  const [panelRouteId, setPanelRouteId] = useState<string | null>(null);

  useEffect(() => {
    if (latestMsgId && latestMsgId !== panelMsgId) {
      setPanelMsgId(latestMsgId);
      setPanelRouteId(lastRecMsg?.recommendedRoute?.id || null);
    }
  }, [latestMsgId, panelMsgId, lastRecMsg]);

  const panelMsg = messages.find(m => m.id === panelMsgId);
  const currentRecRoute = panelMsg?.allRoutes?.find(r => r.id === panelRouteId) || panelMsg?.recommendedRoute || null;
  const currentRec = panelMsg?.recommendation;
  const allRoutes = panelMsg?.allRoutes || [];

  const handleRouteSelectWithClose = (route: NormalizedRoute | null) => {
    if (onRouteSelect) {
      onRouteSelect(route);
      setIsOpen(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-5 right-5 z-[100] flex items-center gap-2 bg-[#161616] hover:bg-[#1e1e1e] border border-[#2a2a2a] hover:border-[#FF4500]/40 rounded-full pl-2.5 pr-3.5 py-2 text-[13px] font-medium text-[#aaa] hover:text-white shadow-2xl transition-all"
      >
        <div className="w-5 h-5 rounded-full bg-[#FF4500] flex items-center justify-center">
          <Sparkles size={11} className="text-white" fill="currentColor" />
        </div>
        TransitIQ
      </button>

      {isOpen && (
        <div
          className="fixed inset-0 z-[200] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-[6px]"
          onClick={e => { if (e.target === e.currentTarget) setIsOpen(false); }}
        >
          <div
            className="flex flex-col md:flex-row bg-[#0a0a0a] border border-[#1e1e1e] sm:rounded-xl overflow-hidden shadow-[0_8px_30px_rgba(0,0,0,0.5)] w-full h-[95vh] sm:h-[85vh] sm:w-[95vw] md:w-[85vw] max-w-[1400px]"
          >
            {/* Left Panel: Conversation */}
            <div className="w-full md:w-[68%] flex flex-col relative bg-[#111] h-full">
              <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e1e1e] shrink-0 bg-[#0a0a0a]">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded bg-[#FF4500] flex items-center justify-center">
                    <Sparkles size={13} className="text-white" fill="currentColor" />
                  </div>
                  <span className="text-[14px] font-bold text-white tracking-wide">TransitIQ Workspace</span>
                </div>
                <button onClick={() => setIsOpen(false)} className="p-1.5 rounded-lg hover:bg-[#1e1e1e] text-[#888] hover:text-white transition-colors">
                  <X size={18} />
                </button>
              </div>

              {messages.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center p-8 max-w-2xl mx-auto w-full">
                  <div className="w-12 h-12 rounded-xl bg-[#FF4500]/10 border border-[#FF4500]/20 flex items-center justify-center mb-6">
                    <Sparkles size={24} className="text-[#FF4500]" />
                  </div>
                  <h2 className="text-[20px] font-bold text-white mb-2">Transit Intelligence Command Center</h2>
                  <p className="text-[14px] text-[#888] mb-10 text-center max-w-md">Ask questions, explore journeys, compare routes, and receive travel guidance.</p>

                  <div className="w-full mb-8">
                    <ChatInput onSubmit={handleSubmit} disabled={isLoading} large />
                  </div>

                  <div className="w-full grid grid-cols-2 gap-3">
                    {chipSuggestions.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => handleSubmit(s.label)}
                        className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[#161616] border border-[#222] hover:border-[#FF4500]/30 hover:bg-[#1a1a1a] text-left transition-colors group"
                      >
                        <span className="text-[16px] opacity-60 group-hover:opacity-100 transition-opacity">{s.icon}</span>
                        <span className="text-[13px] font-medium text-[#888] group-hover:text-[#ccc] transition-colors">{s.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col overflow-hidden relative">
                  <div className="flex-1 overflow-y-auto px-5 py-6 flex flex-col gap-5 custom-scrollbar">
                    {messages.map(m =>
                      m.role === 'user'
                        ? <UserBubble key={m.id} text={m.text} />
                        : <AssistantCard 
                            key={m.id} 
                            msg={m} 
                            activeRouteId={m.id === panelMsgId ? panelRouteId || undefined : undefined} 
                            allRoutes={m.id === panelMsgId ? m.allRoutes : undefined}
                            onRouteSelect={handleRouteSelectWithClose} 
                          />
                    )}
                    {isLoading && (
                      <div className="flex items-center gap-1.5 ml-11 h-5">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#FF4500] animate-pulse" />
                        <div className="w-1.5 h-1.5 rounded-full bg-[#FF4500] animate-pulse" style={{ animationDelay: '200ms' }} />
                        <div className="w-1.5 h-1.5 rounded-full bg-[#FF4500] animate-pulse" style={{ animationDelay: '400ms' }} />
                      </div>
                    )}
                    <div ref={endRef} />
                  </div>
                  <div className="p-4 bg-[#0a0a0a] border-t border-[#1e1e1e] shrink-0">
                    <ChatInput onSubmit={handleSubmit} disabled={isLoading} />
                  </div>
                </div>
              )}
            </div>

            {/* Right Panel: Context / Journey Intelligence */}
            <div className="hidden md:flex w-[32%] h-full relative">
              <ContextPanel 
                route={currentRecRoute} 
                recommendation={currentRec}
                allRoutes={allRoutes}
                onSelectAlternative={(r) => setPanelRouteId(r.id)}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
