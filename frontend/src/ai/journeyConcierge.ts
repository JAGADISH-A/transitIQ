import type { NormalizedRoute } from '../types/transit';
import type { WorkspaceIntelligence, TimelineMilestone } from './types';

export function generateWorkspaceIntelligence(route: NormalizedRoute): WorkspaceIntelligence {
  const isTransfer = route.isTransfer;
  const transferWait = route.transferWait;
  const originalData = route.originalData as any;

  // 1. Generate Guidance
  let guidance = "";
  if (!isTransfer) {
    guidance = "This is a straightforward journey. Board once and remain on the same service until your destination.";
  } else if (transferWait !== undefined) {
    const stopName = route.transferStopName || "your transfer station";
    if (transferWait < 15) {
      guidance = `After arriving at ${stopName}, head directly to your next platform. You only have about ${Math.round(transferWait)} minutes before the connecting train departs.`;
    } else if (transferWait > 45) {
      guidance = `You have a long wait at ${stopName}. Consider stepping into the waiting hall, having a meal, or checking live departure boards before your next train.`;
    } else {
      guidance = `You'll have some free time at ${stopName}. This is a good opportunity to grab tea, recharge devices, or locate your next platform before boarding.`;
    }
  }

  // 2. Generate Timeline
  const timeline: TimelineMilestone[] = [];
  if (!isTransfer) {
    timeline.push({
      step: `Board ${originalData.route_name || "train"} at ${originalData.source_stop}`,
      time: route.departureTime || undefined,
      icon: "board"
    });
    timeline.push({
      step: `Travel to ${originalData.destination_stop}`,
      icon: "travel"
    });
    timeline.push({
      step: `Arrive at destination`,
      time: route.arrivalTime || undefined,
      icon: "destination"
    });
  } else {
    const firstLeg = originalData.first_leg;
    const secondLeg = originalData.second_leg;
    
    timeline.push({
      step: `Board ${firstLeg?.route_name || "first train"} at ${firstLeg?.source_stop}`,
      time: firstLeg?.departure_time,
      icon: "board"
    });
    timeline.push({
      step: `Travel to ${route.transferStopName}`,
      icon: "travel"
    });
    timeline.push({
      step: `Arrive at ${route.transferStopName}`,
      time: firstLeg?.arrival_time,
      icon: "arrive"
    });
    timeline.push({
      step: `Wait approximately ${Math.round(transferWait || 0)} minutes`,
      icon: "wait"
    });
    timeline.push({
      step: `Board ${secondLeg?.route_name || "connecting train"}`,
      time: secondLeg?.departure_time,
      icon: "change"
    });
    timeline.push({
      step: `Continue to ${secondLeg?.destination_stop}`,
      icon: "travel"
    });
    timeline.push({
      step: `Arrive at destination`,
      time: secondLeg?.arrival_time,
      icon: "destination"
    });
  }

  // 3. Generate Tips
  const tips: string[] = [];
  if (isTransfer && transferWait !== undefined) {
    if (transferWait < 15) {
      tips.push("⚠ Keep luggage ready before arrival to make the transfer smoother.");
    } else if (transferWait > 45) {
      tips.push("☕ Enough time to grab refreshments before boarding the next service.");
    }
  }
  
  if (route.durationMinutes > 240) {
    tips.push("🧳 Carry water and charge devices before departure.");
  }
  
  // Late night check (departing after 10 PM or arriving before 5 AM)
  const isLate = route.departureTime?.startsWith("22:") || route.departureTime?.startsWith("23:") || 
                 route.arrivalTime?.startsWith("00:") || route.arrivalTime?.startsWith("01:") || 
                 route.arrivalTime?.startsWith("02:") || route.arrivalTime?.startsWith("03:") || route.arrivalTime?.startsWith("04:");
  if (isLate) {
    tips.push("🌙 Consider keeping valuables secure and setting an arrival alarm.");
  }

  if (tips.length === 0) {
    tips.push("🎫 Keep your tickets handy for verification.");
  }

  return { guidance, timeline, tips };
}
