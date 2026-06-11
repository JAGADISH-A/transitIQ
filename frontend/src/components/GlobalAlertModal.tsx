"use client";

import { motion, AnimatePresence } from "framer-motion";
import { WarningGraphic } from "./WarningGraphic";
import { AlertTriangle, X } from "lucide-react";
import { useEffect } from "react";

interface GlobalAlertModalProps {
  isOpen: boolean;
  onClose: () => void;
  message: string;
  title?: string;
}

export function GlobalAlertModal({
  isOpen,
  onClose,
  message,
  title = "System Alert"
}: GlobalAlertModalProps) {

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop Blur */}
          <motion.div
            initial={{ opacity: 0, backdropFilter: "blur(0px)" }}
            animate={{ opacity: 1, backdropFilter: "blur(8px)" }}
            exit={{ opacity: 0, backdropFilter: "blur(0px)" }}
            transition={{ duration: 0.4, ease: "easeInOut" }}
            className="fixed inset-0 z-[100] bg-black/40"
            onClick={onClose}
          />

          {/* Modal Container */}
          <div className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none">
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              transition={{ 
                type: "spring", 
                stiffness: 400, 
                damping: 30,
                duration: 0.5 
              }}
              className="relative w-full max-w-md pointer-events-auto"
            >
              {/* Outer Glow / Layered Depth */}
              <div className="absolute inset-0 rounded-3xl bg-[#FDC221]/10 blur-2xl transform scale-105" />
              
              {/* Main Modal Body (Dark Glassmorphism) */}
              <div className="relative flex flex-col items-center p-8 bg-[#0F0F0F]/80 backdrop-blur-xl border border-white/10 rounded-3xl shadow-[0_0_50px_-12px_rgba(253,194,33,0.3)] overflow-hidden">
                
                {/* Subtle Orange Accent Lighting inside */}
                <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-transparent via-[#FDC221] to-transparent opacity-50" />
                <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-48 h-48 bg-[#FDC221]/20 rounded-full blur-[50px] pointer-events-none" />

                {/* Close Button */}
                <button
                  onClick={onClose}
                  className="absolute top-4 right-4 p-2 text-white/50 hover:text-white bg-white/5 hover:bg-white/10 rounded-full transition-colors"
                >
                  <X size={20} />
                </button>

                {/* Hero Visual: WarningGraphic */}
                <div className="mb-8 mt-4 relative z-10">
                  <WarningGraphic width={180} height={58} className="drop-shadow-[0_0_15px_rgba(253,194,33,0.5)]" />
                </div>

                {/* Content */}
                <div className="flex flex-col items-center text-center gap-3 relative z-10">
                  <h2 className="text-xl font-semibold text-white tracking-wide uppercase flex items-center gap-2">
                    <AlertTriangle className="text-[#FDC221]" size={20} />
                    {title}
                  </h2>
                  <p className="text-white/70 text-sm leading-relaxed">
                    {message}
                  </p>
                </div>

                {/* Action Button */}
                <button
                  onClick={onClose}
                  className="mt-8 w-full py-3 px-6 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-white font-medium transition-all hover:shadow-[0_0_20px_-5px_rgba(253,194,33,0.3)] hover:border-[#FDC221]/30 active:scale-[0.98]"
                >
                  Acknowledge
                </button>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
