import React from 'react';
import { Zap, RefreshCcw, AlertTriangle, Moon, Train } from 'lucide-react';

interface RouteFlagsProps {
  flags?: string[];
}

export function RouteFlags({ flags }: RouteFlagsProps) {
  if (!flags || flags.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {flags.map((flag, idx) => {
        switch (flag) {
          case 'FASTEST_ROUTE':
            return (
              <span key={idx} className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <Zap size={10} /> Fastest Route
              </span>
            );
          case 'OPTIMAL_TRANSFER':
            return (
              <span key={idx} className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                <RefreshCcw size={10} /> Optimal Transfer
              </span>
            );
          case 'RISKY_TRANSFER':
            return (
              <span key={idx} className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <AlertTriangle size={10} /> Risky Transfer
              </span>
            );
          case 'LONG_TRANSFER_WAIT':
            return (
              <span key={idx} className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">
                <AlertTriangle size={10} /> Long Transfer Wait
              </span>
            );
          case 'VERY_LONG_TRANSFER_WAIT':
            return (
              <span key={idx} className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                <AlertTriangle size={10} /> Extended Wait
              </span>
            );
          case 'DIRECT_SERVICE':
            return (
              <span key={idx} className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Train size={10} /> Direct Service
              </span>
            );
          case 'OVERNIGHT_JOURNEY':
            return (
              <span key={idx} className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <Moon size={10} /> Overnight Journey
              </span>
            );
          default:
            return null;
        }
      })}
    </div>
  );
}
