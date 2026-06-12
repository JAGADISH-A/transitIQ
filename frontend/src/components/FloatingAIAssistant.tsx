import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Sparkles, X, Send, Loader2, Train, AlertTriangle } from 'lucide-react';

import type { JourneyNarrative, JourneyContext, JourneyRoute } from '../types/transit';

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
}

interface FloatingAIAssistantProps {
  onSearch?: (source: string, destination: string, departureTime?: string) => Promise<SearchResult>;
  activeRoute?: any; // Simplified for now since we just need to pass the selected route down
}

const chipSuggestions = [
  { icon: "🚆", label: "Chennai Central from Avadi" },
  { icon: "🏢", label: "Guindy from Avadi" },
  { icon: "📍", label: "Chennai Beach" },
  { icon: "⚡", label: "Fastest route to Guindy" },
];

/* ─── Assistant message card ─── */
const AssistantCard = React.memo(({ msg }: { msg: Message }) => {
  if (msg.type === 'searching') {
    return (
      <div className="flex items-start gap-3 max-w-[85%]">
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
      <div className="flex items-start gap-3 max-w-[85%]">
        <div className="w-6 h-6 rounded bg-[#FF4500] flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles size={12} className="text-white" />
        </div>
        <div className="bg-[#161616] border border-[#252525] rounded-lg px-4 py-3 border-l-2 border-l-[#FF4500]">
          {msg.narrative ? (
            <div className="flex flex-col gap-2">
              <h4 className="text-[15px] font-semibold text-white">{msg.narrative.headline}</h4>
              <p className="text-[14px] text-[#d0d0d0] leading-relaxed">{msg.narrative.summary}</p>
              <p className="text-[14px] text-[#d0d0d0] leading-relaxed">{msg.narrative.recommendation}</p>
              
              {msg.narrative.warnings && msg.narrative.warnings.length > 0 && (
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
                {msg.narrative.alternatives_available > 0 && <span className="text-[#666]">{msg.narrative.alternatives_available} alternative options</span>}
              </div>
            </div>
          ) : (
            <p className="text-[14px] text-[#999] leading-relaxed">{msg.text}</p>
          )}
        </div>
      </div>
    );
  }

  if (msg.type === 'not-found' || msg.type === 'error') {
    return (
      <div className="flex items-start gap-3 max-w-[85%]">
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
    <div className="flex items-start gap-3 max-w-[85%]">
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
    <div className="bg-[#1e1e1e] border border-[#2a2a2a] hover:border-[#FF4500]/30 text-[#e0e0e0] text-[14px] px-3.5 py-2 rounded-lg max-w-[60%] transition-colors">
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
    <div className="flex items-center bg-[#161616] border border-[#252525] focus-within:border-[#3a3a3a] rounded-lg overflow-hidden transition-colors">
      <input
        type="text"
        autoFocus
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && submit()}
        disabled={disabled}
        placeholder="Ask TransitIQ..."
        className={`flex-1 bg-transparent text-[#e0e0e0] ${large ? 'text-[15px] px-4 py-3.5' : 'text-[14px] px-3.5 py-2.5'} focus:outline-none placeholder:text-[#555] disabled:opacity-40`}
      />
      <button
        onClick={submit}
        disabled={!val.trim() || disabled}
        className="mr-1.5 w-7 h-7 rounded bg-[#FF4500] hover:bg-[#e63e00] disabled:bg-[#333] disabled:opacity-30 flex items-center justify-center text-white transition-colors"
      >
        {disabled ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
      </button>
    </div>
  );
};

/* ─── Main component ─── */
export default function FloatingAIAssistant({ onSearch, activeRoute }: FloatingAIAssistantProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionContext, setSessionContext] = useState<JourneyContext | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Update active_journey when activeRoute changes
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

        // Top routes for comparison memory
        const comp = sessionContext?.previous_comparison || undefined;
        // Update context
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
            // Check if it's a stop resolution error from the planner
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
            addMsg({
              role: 'assistant',
              type: 'result',
              text: '',
              directCount: r.directCount,
              transferCount: r.transferCount,
              narrative: r.narrative
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
  }, [isLoading, onSearch, addMsg]);

  return (
    <>
      {/* FAB */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-5 right-5 z-[100] flex items-center gap-2 bg-[#161616] hover:bg-[#1e1e1e] border border-[#2a2a2a] hover:border-[#FF4500]/40 rounded-full pl-2.5 pr-3.5 py-2 text-[13px] font-medium text-[#aaa] hover:text-white transition-all"
      >
        <div className="w-5 h-5 rounded-full bg-[#FF4500] flex items-center justify-center">
          <Sparkles size={11} className="text-white" fill="currentColor" />
        </div>
        TransitIQ
      </button>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-[200] flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-[8px]"
          onClick={e => { if (e.target === e.currentTarget) setIsOpen(false); }}
        >
          <div
            className="flex flex-col bg-[#111] border border-[#1e1e1e] rounded-t-xl sm:rounded-xl overflow-hidden"
            style={{ width: 'min(92vw, 760px)', height: 'min(82vh, 640px)' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1e1e1e] shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded bg-[#FF4500] flex items-center justify-center">
                  <Sparkles size={11} className="text-white" fill="currentColor" />
                </div>
                <span className="text-[13px] font-semibold text-[#ccc] tracking-wide">TransitIQ Copilot</span>
              </div>
              <button onClick={() => setIsOpen(false)} className="p-1 rounded hover:bg-[#1e1e1e] text-[#666] hover:text-[#ccc] transition-colors">
                <X size={16} />
              </button>
            </div>

            {messages.length === 0 ? (
              /* ─── Empty state ─── */
              <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-lg mx-auto w-full">
                <div className="w-10 h-10 rounded-lg bg-[#FF4500]/10 border border-[#FF4500]/20 flex items-center justify-center mb-4">
                  <Sparkles size={20} className="text-[#FF4500]" />
                </div>
                <h2 className="text-[18px] font-semibold text-[#ddd] mb-1">TransitIQ Copilot</h2>
                <p className="text-[13px] text-[#666] mb-8">Ask naturally — describe where you want to go.</p>

                <div className="w-full mb-6">
                  <ChatInput onSubmit={handleSubmit} disabled={isLoading} large />
                </div>

                <div className="w-full grid grid-cols-2 gap-2">
                  {chipSuggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => handleSubmit(s.label)}
                      className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-[#161616] border border-[#222] hover:border-[#FF4500]/30 text-left transition-colors group"
                    >
                      <span className="text-[14px] opacity-60 group-hover:opacity-100 transition-opacity">{s.icon}</span>
                      <span className="text-[13px] text-[#888] group-hover:text-[#ccc] transition-colors">{s.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* ─── Chat ─── */
              <>
                <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
                  {messages.map(m =>
                    m.role === 'user'
                      ? <UserBubble key={m.id} text={m.text} />
                      : <AssistantCard key={m.id} msg={m} />
                  )}
                  {isLoading && (
                    <div className="flex items-center gap-1.5 ml-9 h-5">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#FF4500] animate-pulse" />
                      <div className="w-1.5 h-1.5 rounded-full bg-[#FF4500] animate-pulse" style={{ animationDelay: '200ms' }} />
                      <div className="w-1.5 h-1.5 rounded-full bg-[#FF4500] animate-pulse" style={{ animationDelay: '400ms' }} />
                    </div>
                  )}
                  <div ref={endRef} />
                </div>
                <div className="p-3 border-t border-[#1e1e1e] shrink-0">
                  <ChatInput onSubmit={handleSubmit} disabled={isLoading} />
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
