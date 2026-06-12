import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Sparkles, X, Send, Loader2, Train, AlertTriangle, Clock, MapPin, ArrowRight } from 'lucide-react';

import type { JourneyNarrative, JourneyContext, JourneyRoute, NormalizedRoute, TransferJourney } from '../types/transit';
import type { RouteRecommendation } from '../ai/types';
import { recommendBestRoute } from '../ai/journeyIntelligence';

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
  onSearch?: (source: string, destination: string, departureTime?: string) => Promise<SearchResult>;
  activeRoute?: any;
  onRouteSelect?: (route: NormalizedRoute | null) => void;
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
const AssistantCard = React.memo(({ msg, onRouteSelect }: { msg: Message, onRouteSelect?: (route: NormalizedRoute | null) => void }) => {
  if (msg.type === 'searching') {
    return (
      <div className="flex items-start gap-3 w-full max-w-[90%]">
        <div className="w-6 h-6 rounded bg-[#FF4500] flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles size={12} className="text-white" />
        </div>
        <div className="bg-[#161616] border border-[#252525] rounded-lg px-4 py-3 border-l-2 border-l-[#FF4500]">
          <div className="flex items-center gap-2 text-[13px] text-[#FF4500] font-medium mb-1.5">
            <Train size={14} />
            <span>Searching transit network</span>
          </div>
          {msg.source && msg.destination && (
            <div className="flex items-center gap-2 text-[13px] text-[#888] mt-2">
              <span className="bg-[#1e1e1e] border border-[#2a2a2a] rounded px-2 py-0.5 text-[#bbb]">📍 {msg.source}</span>
              <span className="text-[#555]">→</span>
              <span className="bg-[#1e1e1e] border border-[#2a2a2a] rounded px-2 py-0.5 text-[#bbb]">🚉 {msg.destination}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 mt-2">
            <Loader2 size={12} className="text-[#FF4500] animate-spin" />
            <span className="text-[12px] text-[#666]">Looking for available routes...</span>
          </div>
        </div>
      </div>
    );
  }

  if (msg.type === 'result') {
    return (
      <div className="flex items-start gap-3 w-full max-w-[95%]">
        <div className="w-6 h-6 rounded bg-[#FF4500] flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles size={12} className="text-white" />
        </div>
        
        {msg.recommendation && msg.recommendedRoute ? (
          <div className="w-full flex flex-col gap-3">
            {/* Expansive Recommendation Card */}
            <div className="bg-[#111] border border-[#252525] shadow-lg rounded-xl p-5 w-full flex flex-col md:flex-row gap-5 items-start justify-between">
              
              <div className="flex flex-col gap-3 flex-1 w-full">
                <div className="flex items-center gap-2">
                  <h4 className="text-[16px] font-bold text-white flex items-center gap-1.5">
                    🔥 {msg.recommendation.title}
                  </h4>
                  <div className={`ml-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide shrink-0
                    ${msg.recommendation.confidence === 'high' ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 
                      msg.recommendation.confidence === 'medium' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 
                      'bg-red-500/10 text-red-400 border border-red-500/20'}`}
                  >
                    {msg.recommendation.confidence} Match
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-[13px] text-[#ccc]">
                  <div className="flex items-center gap-1.5">
                    <Train size={14} className="text-zinc-500" />
                    <span className="font-medium text-white">{msg.recommendedRoute.isTransfer ? 'Multiple Services' : (msg.recommendedRoute.originalData as JourneyRoute).route_name || 'Direct Service'}</span>
                  </div>
                  <div className="hidden sm:block w-1 h-1 rounded-full bg-zinc-700" />
                  <div className="flex items-center gap-1.5">
                    <Clock size={14} className="text-zinc-500" />
                    <span>{formatDuration(msg.recommendedRoute.durationMinutes)}</span>
                  </div>
                  <div className="hidden sm:block w-1 h-1 rounded-full bg-zinc-700" />
                  <div className="flex items-center gap-1.5">
                    <ArrowRight size={14} className="text-zinc-500" />
                    <span>{msg.recommendedRoute.transferCount === 0 ? 'Direct' : `${msg.recommendedRoute.transferCount} Transfer`}</span>
                  </div>
                </div>

                <div className="mt-2 bg-[#1a1a1a] border border-[#252525] rounded-lg p-3">
                  <p className="text-[13px] text-[#d0d0d0] font-medium mb-2">Why this route?</p>
                  <ul className="flex flex-col gap-1.5 text-[13px] text-[#aaa]">
                    {msg.recommendation.reasons.map((r, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-green-500 mt-0.5 font-bold">✓</span>
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {onRouteSelect && (
                <div className="shrink-0 flex items-center justify-end w-full md:w-auto md:h-full">
                  <button 
                    onClick={() => onRouteSelect(msg.recommendedRoute!)}
                    className="w-full md:w-auto px-5 py-2.5 bg-[#FF4500] hover:bg-[#e63e00] text-white font-medium text-[13px] rounded-lg transition-colors shadow-[0_4px_14px_rgba(255,69,0,0.3)] hover:shadow-[0_6px_20px_rgba(255,69,0,0.4)]"
                  >
                    Explore Full Journey
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

  // Default text message
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
const ContextPanel = ({ route, recommendation }: { route: NormalizedRoute | null, recommendation?: RouteRecommendation }) => {
  if (!route) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center border-l border-[#1e1e1e] bg-zinc-950">
        <div className="w-16 h-16 rounded-full bg-[#111] border border-[#222] flex items-center justify-center mb-4">
          <Sparkles size={24} className="text-[#333]" />
        </div>
        <h3 className="text-[16px] font-medium text-white/40 mb-2">Journey Intelligence</h3>
        <p className="text-[13px] text-white/20">Ask for a route to view deep insights, comparisons, and predictive travel intelligence here.</p>
      </div>
    );
  }

  const { isTransfer, originalData } = route;
  
  // Calculate Quality / Risk
  const qualityScore = route.qualityScore || 0;
  const qualityPct = Math.max(0, 100 - (qualityScore * 10)); // rough estimate
  let riskLevel = 'Low';
  if (isTransfer) {
    if (route.transferWait! > 60) riskLevel = 'High';
    else if (route.transferWait! > 30) riskLevel = 'Medium';
  }

  const trainLabel = isTransfer ? 'Multiple Services' : (originalData as JourneyRoute).route_name || 'Direct Service';

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto border-l border-[#1e1e1e] bg-zinc-950 custom-scrollbar">
      <div className="p-5 border-b border-[#1e1e1e] sticky top-0 bg-zinc-950/90 backdrop-blur z-10">
        <h3 className="text-[14px] font-bold text-white tracking-wide uppercase flex items-center gap-2">
          <Sparkles size={14} className="text-[#FF4500]" /> Journey Intelligence
        </h3>
      </div>

      <div className="p-5 flex flex-col gap-6">
        
        {/* Basic Metadata */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-[13px] text-[#ccc]">
            <Train size={16} className="text-[#888]" />
            <span className="font-semibold text-white">{trainLabel}</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#111] border border-[#222] rounded-lg p-3">
              <p className="text-[11px] text-[#666] uppercase tracking-wider mb-1">Duration</p>
              <p className="text-[14px] font-semibold text-white">{formatDuration(route.durationMinutes)}</p>
            </div>
            <div className="bg-[#111] border border-[#222] rounded-lg p-3">
              <p className="text-[11px] text-[#666] uppercase tracking-wider mb-1">Transfers</p>
              <p className="text-[14px] font-semibold text-white">{route.transferCount === 0 ? 'Direct' : route.transferCount}</p>
            </div>
          </div>
        </div>

        {/* Timeline */}
        <div className="flex flex-col gap-3">
          <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider">Journey Overview</h4>
          <div className="bg-[#111] border border-[#222] rounded-lg p-4 relative">
            <div className="flex flex-col">
              <div className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="w-2.5 h-2.5 rounded-full border-2 border-white bg-black z-10" />
                  <div className="w-px h-12 bg-[#333]" />
                </div>
                <div className="flex flex-col pb-4">
                  <span className="text-[13px] font-medium text-white">{route.departureDisplay.display_time}</span>
                  <span className="text-[12px] text-[#888]">{(originalData as any).source_stop || 'Source'}</span>
                </div>
              </div>

              {isTransfer && (
                <div className="flex gap-4 -mt-2">
                  <div className="flex flex-col items-center">
                    <div className="w-2 h-2 rounded-full border border-amber-500 bg-amber-500/20 z-10" />
                    <div className="w-px h-12 bg-amber-500/30 border-l-2 border-dashed border-amber-500/50" />
                  </div>
                  <div className="flex flex-col pb-4 -mt-1">
                    <span className="text-[12px] font-medium text-amber-500">Wait {formatDuration(route.transferWait || 0)}</span>
                    <span className="text-[12px] text-[#666]">Change at {route.transferStopName}</span>
                  </div>
                </div>
              )}

              <div className="flex gap-4 -mt-2">
                <div className="flex flex-col items-center">
                  <div className="w-2.5 h-2.5 rounded-full border-2 border-white bg-[#FF4500] z-10" />
                </div>
                <div className="flex flex-col -mt-1">
                  <span className="text-[13px] font-medium text-white">{route.arrivalDisplay.display_time}</span>
                  <span className="text-[12px] text-[#888]">{(originalData as any).destination_stop || 'Destination'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Insight Card */}
        {recommendation ? (
          <div className="bg-[#111] border border-[#222] rounded-lg p-4">
            <h4 className="text-[13px] font-semibold text-white mb-2 flex items-center gap-1.5">
              🧠 TransitIQ Insight
            </h4>
            <p className="text-[13px] text-[#aaa] mb-3">This route is recommended because:</p>
            <ul className="flex flex-col gap-2 text-[12px] text-[#ccc]">
              {recommendation.reasons.map((r, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-green-500">✓</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          route.transferWait && route.transferWait > 60 && (
            <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4">
              <h4 className="text-[13px] font-semibold text-red-400 mb-2 flex items-center gap-1.5">
                <AlertTriangle size={14} /> Travel Advisory
              </h4>
              <p className="text-[12px] text-red-300/80">
                {route.transferWait} minute transfer wait at {route.transferStopName}. Consider alternative departures.
              </p>
            </div>
          )
        )}

        {/* Quick Stats */}
        <div className="flex flex-col gap-3">
          <h4 className="text-[13px] font-semibold text-[#888] uppercase tracking-wider">Quick Stats</h4>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#111] border border-[#222] rounded-lg px-3 py-2.5">
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-[11px] text-[#666] uppercase">Quality</span>
                <span className="text-[12px] font-bold text-white">{qualityPct}%</span>
              </div>
              <div className="w-full bg-[#222] rounded-full h-1.5">
                <div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${qualityPct}%` }}></div>
              </div>
            </div>
            <div className="bg-[#111] border border-[#222] rounded-lg px-3 py-2.5">
              <span className="text-[11px] text-[#666] uppercase block mb-1">Transfer Risk</span>
              <span className={`text-[12px] font-bold ${riskLevel === 'Low' ? 'text-green-400' : riskLevel === 'Medium' ? 'text-amber-400' : 'text-red-400'}`}>
                {riskLevel}
              </span>
            </div>
            <div className="bg-[#111] border border-[#222] rounded-lg px-3 py-2.5">
              <span className="text-[11px] text-[#666] uppercase block mb-1">Complexity</span>
              <span className={`text-[12px] font-bold ${route.transferCount === 0 ? 'text-green-400' : 'text-amber-400'}`}>
                {route.transferCount === 0 ? 'Low' : 'High'}
              </span>
            </div>
            <div className="bg-[#111] border border-[#222] rounded-lg px-3 py-2.5">
              <span className="text-[11px] text-[#666] uppercase block mb-1">Confidence</span>
              <span className="text-[12px] font-bold text-white">
                {recommendation?.confidence ? recommendation.confidence.toUpperCase() : 'N/A'}
              </span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

/* ─── Main component ─── */
export default function FloatingAIAssistant({ onSearch, activeRoute, onRouteSelect }: FloatingAIAssistantProps) {
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
              recommendedRoute
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
  const currentRecRoute = lastRecMsg?.recommendedRoute || null;
  const currentRec = lastRecMsg?.recommendation;

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
                        : <AssistantCard key={m.id} msg={m} onRouteSelect={handleRouteSelectWithClose} />
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
              <ContextPanel route={currentRecRoute} recommendation={currentRec} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
