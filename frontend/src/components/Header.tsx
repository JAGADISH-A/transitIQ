
import { Route } from 'lucide-react';

export default function Header() {
  return (
    <header className="w-full flex items-center justify-between px-6 py-5 border-b border-white/10 bg-[#0F0F0F] z-10">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#1A1A1A] border border-white/10 flex items-center justify-center text-[#FF4500]">
          <Route size={22} strokeWidth={2.5} />
        </div>
        <div className="flex flex-col">
          <h1 className="text-xl font-semibold tracking-tight text-white/90">
            Transit<span className="text-[#FF4500]">IQ</span>
          </h1>
          <p className="text-xs text-white/50 font-medium tracking-wide">
            AI-POWERED PUBLIC TRANSIT ASSISTANT
          </p>
        </div>
      </div>
      
      {/* Placeholder for future auth/menu */}
      <div className="flex items-center gap-4">
        <div className="w-8 h-8 rounded-full bg-[#1A1A1A] border border-white/10"></div>
      </div>
    </header>
  );
}
