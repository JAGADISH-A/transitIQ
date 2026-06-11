import { useRef, useEffect, useState } from 'react';

interface WheelColumnProps {
  items: string[];
  selectedValue: string;
  onChange: (val: string) => void;
  width?: string;
}

function WheelColumn({ items, selectedValue, onChange, width = "w-16" }: WheelColumnProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const itemHeight = 40; // 40px height for each item

  useEffect(() => {
    // Scroll to the selected item initially
    if (scrollRef.current) {
      const index = items.indexOf(selectedValue);
      if (index !== -1) {
        scrollRef.current.scrollTop = index * itemHeight;
      }
    }
  }, []); // Only run once on mount

  const handleScroll = () => {
    if (!scrollRef.current) return;
    
    // Determine which item is currently in the center
    const scrollTop = scrollRef.current.scrollTop;
    const index = Math.round(scrollTop / itemHeight);
    
    if (index >= 0 && index < items.length) {
      const currentItem = items[index];
      if (currentItem !== selectedValue) {
        onChange(currentItem);
      }
    }
  };

  return (
    <div className={`relative h-[120px] ${width} overflow-hidden font-medium`}>
      <div 
        ref={scrollRef}
        className="h-full overflow-y-auto snap-y snap-mandatory scrollbar-none scroll-smooth"
        onScroll={handleScroll}
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        <div style={{ height: `${itemHeight}px` }} /> {/* Top padding */}
        {items.map((item) => {
          const isSelected = item === selectedValue;
          return (
            <div 
              key={item} 
              className={`h-[40px] snap-center flex items-center justify-center transition-colors duration-200 cursor-pointer ${
                isSelected ? 'text-[#FF4500] scale-110 font-bold' : 'text-white/40 scale-100 hover:text-white/60'
              }`}
              onClick={() => {
                if (scrollRef.current) {
                  const index = items.indexOf(item);
                  scrollRef.current.scrollTo({ top: index * itemHeight, behavior: 'smooth' });
                }
              }}
            >
              {item}
            </div>
          );
        })}
        <div style={{ height: `${itemHeight}px` }} /> {/* Bottom padding */}
      </div>
    </div>
  );
}

export default function WheelTimePicker({ 
  value, 
  onChange 
}: { 
  value: string; 
  onChange: (time: string) => void;
}) {
  // Parsing initial value "HH:MM"
  let initialHr = 12;
  let initialMin = 0;
  let initialAmPm = 'AM';

  if (value) {
    const parts = value.split(':');
    if (parts.length >= 2) {
      const hr24 = parseInt(parts[0], 10);
      initialMin = parseInt(parts[1], 10);
      initialAmPm = hr24 >= 12 ? 'PM' : 'AM';
      initialHr = hr24 % 12;
      if (initialHr === 0) initialHr = 12;
    }
  } else {
    // Default to current time if no value
    const now = new Date();
    const hr24 = now.getHours();
    initialMin = now.getMinutes();
    initialAmPm = hr24 >= 12 ? 'PM' : 'AM';
    initialHr = hr24 % 12;
    if (initialHr === 0) initialHr = 12;
  }

  const [hour, setHour] = useState<string>(String(initialHr).padStart(2, '0'));
  const [minute, setMinute] = useState<string>(String(initialMin).padStart(2, '0'));
  const [ampm, setAmpm] = useState<string>(initialAmPm);

  const hours = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'));
  const minutes = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'));
  const ampms = ['AM', 'PM'];

  // Update parent when any part changes
  useEffect(() => {
    let hr24 = parseInt(hour, 10);
    if (ampm === 'PM' && hr24 < 12) {
      hr24 += 12;
    } else if (ampm === 'AM' && hr24 === 12) {
      hr24 = 0;
    }
    const hh = String(hr24).padStart(2, '0');
    const newTime = `${hh}:${minute}`;
    if (newTime !== value) {
      onChange(newTime);
    }
  }, [hour, minute, ampm]);

  return (
    <div className="relative w-full bg-[#0F0F0F]/80 backdrop-blur-md border border-[#FF4500]/30 rounded-2xl p-4 flex justify-center items-center gap-2 shadow-[0_8px_32px_rgba(0,0,0,0.4)] overflow-hidden">
      
      {/* Floating Highlight Band */}
      <div className="absolute top-1/2 left-4 right-4 -translate-y-1/2 h-[40px] bg-[#FF4500]/10 border border-[#FF4500]/40 rounded-xl pointer-events-none z-0 shadow-[0_0_15px_rgba(255,69,0,0.1)]"></div>
      
      {/* Fade Overlays */}
      <div className="absolute top-0 left-0 right-0 h-10 bg-gradient-to-b from-[#0F0F0F] to-transparent pointer-events-none z-10 rounded-t-2xl"></div>
      <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-[#0F0F0F] to-transparent pointer-events-none z-10 rounded-b-2xl"></div>

      {/* Columns */}
      <div className="flex items-center gap-4 z-20">
        <WheelColumn items={hours} selectedValue={hour} onChange={setHour} width="w-12" />
        <span className="text-white/40 font-bold text-xl -translate-y-[2px] animate-pulse">:</span>
        <WheelColumn items={minutes} selectedValue={minute} onChange={setMinute} width="w-12" />
        <div className="w-4"></div> {/* Spacer */}
        <WheelColumn items={ampms} selectedValue={ampm} onChange={setAmpm} width="w-14" />
      </div>
    </div>
  );
}
