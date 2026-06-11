
import { Map } from 'lucide-react';

export default function InteractiveMap() {
  return (
    <div className="w-full h-full min-h-[400px] bg-[#141414] relative flex flex-col items-center justify-center overflow-hidden">
      {/* Subtle grid pattern background */}
      <div className="absolute inset-0 z-0 opacity-20" style={{
        backgroundImage: 'radial-gradient(#333 1px, transparent 1px)',
        backgroundSize: '24px 24px'
      }}></div>
      
      {/* Map visual elements */}
      <div className="absolute top-8 left-8 w-64 h-64 bg-[#FF4500]/5 rounded-full blur-3xl z-0"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#4e1d08]/10 rounded-full blur-3xl z-0"></div>
      
      {/* Placeholder content */}
      <div className="z-10 flex flex-col items-center gap-4 bg-[#1A1A1A]/80 backdrop-blur-sm border border-white/10 p-6 rounded-2xl shadow-2xl">
        <div className="w-16 h-16 rounded-full bg-[#0F0F0F] border border-white/10 flex items-center justify-center text-white/50">
          <Map size={28} strokeWidth={1.5} />
        </div>
        <div className="text-center">
          <h2 className="text-xl font-medium text-white/90">Interactive Transit Map</h2>
          <p className="text-sm text-white/50 mt-1 max-w-xs">Enter your destination to see real-time routes, vehicle locations, and stops.</p>
        </div>
      </div>
      
      {/* Map Controls placeholder */}
      <div className="absolute right-4 bottom-4 flex flex-col gap-2 z-10">
        <div className="w-10 h-10 bg-[#1A1A1A] border border-white/10 rounded-xl shadow-lg"></div>
        <div className="w-10 h-10 bg-[#1A1A1A] border border-white/10 rounded-xl shadow-lg"></div>
      </div>
    </div>
  );
}
