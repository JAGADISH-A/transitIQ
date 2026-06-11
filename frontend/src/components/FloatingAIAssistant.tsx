
import { Sparkles } from 'lucide-react';

export default function FloatingAIAssistant() {
  return (
    <div className="fixed bottom-6 right-6 z-50">
      <button className="group flex items-center gap-3 bg-[#1A1A1A] border border-white/10 hover:border-[#FF4500]/50 rounded-full pl-3 pr-5 py-3 shadow-[0_8px_30px_rgb(0,0,0,0.4)] transition-all duration-300 hover:scale-105 hover:bg-[#202020]">
        <div className="w-8 h-8 rounded-full bg-[#FF4500] flex items-center justify-center text-white shadow-[0_0_15px_rgba(255,69,0,0.5)]">
          <Sparkles size={16} fill="currentColor" className="opacity-90" />
        </div>
        <span className="text-sm font-medium text-white/90 group-hover:text-white transition-colors">
          Ask TransitIQ
        </span>
      </button>
    </div>
  );
}
