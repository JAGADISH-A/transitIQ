import type { NormalizedRoute } from '../types/transit';
import type { RouteComparison, RouteTradeoff } from './types';

export function analyzeRouteTradeoffs(
  routes: NormalizedRoute[],
  recommendedRoute: NormalizedRoute
): RouteComparison {
  const advantages: RouteTradeoff[] = [];
  const tradeoffs: RouteTradeoff[] = [];
  const alternatives: RouteComparison['alternatives'] = [];

  const minDuration = Math.min(...routes.map(r => r.durationMinutes));

  // 1. Advantages
  if (recommendedRoute.durationMinutes === minDuration) {
    advantages.push({
      title: "⚡ Fastest Arrival",
      description: "Arrives earlier than all other available routes.",
      type: "advantage"
    });
  }

  if (recommendedRoute.transferCount === 0) {
    advantages.push({
      title: "🚆 Direct Journey",
      description: "No train changes required.",
      type: "advantage"
    });
  }

  if (recommendedRoute.transferCount > 0 && recommendedRoute.transferWait !== undefined && recommendedRoute.transferWait <= 10) {
    // Wait, the user specifically noted that if wait < 10, it is both an Efficient Transfer AND a Tight Transfer?
    // Let's use 10-20 for efficient? User spec: "Minimal Waiting: If transferWait <= 10 -> ⏱ Efficient Transfer".
    advantages.push({
      title: "⏱ Efficient Transfer",
      description: "Very little waiting between trains.",
      type: "advantage"
    });
  }

  // 2. Tradeoffs
  if (recommendedRoute.transferCount > 0 && recommendedRoute.transferWait !== undefined) {
    if (recommendedRoute.transferWait < 10) {
      tradeoffs.push({
        title: "⚠ Tight Transfer",
        description: `Only ${Math.round(recommendedRoute.transferWait)} minutes available to change trains.`,
        type: "tradeoff"
      });
    } else if (recommendedRoute.transferWait > 60) {
      tradeoffs.push({
        title: "☕ Long Wait",
        description: "Extended waiting period during transfer.",
        type: "tradeoff"
      });
    }
  }

  if (recommendedRoute.transferCount >= 2) {
    tradeoffs.push({
      title: "🔄 Complex Journey",
      description: "Requires multiple train changes.",
      type: "tradeoff"
    });
  }

  // Fallback advantage if none exist
  if (advantages.length === 0) {
    advantages.push({
      title: "⚖ Balanced Journey",
      description: "Provides the best balance of speed and convenience for your journey.",
      type: "advantage"
    });
  }

  // 3. Alternative Route Discovery
  const otherRoutes = routes.filter(r => r.id !== recommendedRoute.id);
  
  // A. Comfortable Option (if recommended has a tight transfer)
  if (recommendedRoute.transferCount > 0 && recommendedRoute.transferWait && recommendedRoute.transferWait <= 15) {
    const comfortable = otherRoutes.find(r => r.transferWait && r.transferWait >= 15);
    if (comfortable && !alternatives.find(a => a.routeId === comfortable.id)) {
      const durDiff = comfortable.durationMinutes - recommendedRoute.durationMinutes;
      alternatives.push({
        routeId: comfortable.id,
        label: "🛋 More Comfortable",
        pros: [
          `${Math.round(comfortable.transferWait!)} minutes available to change trains.`,
          "Lower chance of missing the next service."
        ],
        cons: [
          durDiff > 0 ? `Arrives ${Math.round(durDiff)} minutes later.` : "Overall travel time may be longer."
        ]
      });
    }
  }

  // B. Direct Option
  if (recommendedRoute.transferCount > 0) {
    const direct = otherRoutes.find(r => r.transferCount === 0);
    if (direct && !alternatives.find(a => a.routeId === direct.id)) {
      const durDiff = direct.durationMinutes - recommendedRoute.durationMinutes;
      alternatives.push({
        routeId: direct.id,
        label: "🚆 Direct Service",
        pros: [
          "Direct train with no station changes required."
        ],
        cons: [
          durDiff > 0 ? `Adds ${Math.round(durDiff)} minutes to your total travel time.` : "Arrives later than the recommended route."
        ]
      });
    }
  }

  // C. Earlier Departure
  if (recommendedRoute.departureTime) {
    const earlier = otherRoutes.find(r => r.departureTime && r.departureTime < recommendedRoute.departureTime);
    if (earlier && !alternatives.find(a => a.routeId === earlier.id)) {
      const durDiff = earlier.durationMinutes - recommendedRoute.durationMinutes;
      const consList = [];
      if (durDiff > 0) consList.push(`Takes ${Math.round(durDiff)} minutes longer overall.`);
      if (earlier.transferCount > recommendedRoute.transferCount) consList.push("Requires an additional train change.");
      if (consList.length === 0) consList.push("May arrive later than the recommended option.");

      alternatives.push({
        routeId: earlier.id,
        label: "🌅 Earlier Departure",
        pros: [
          "Leaves earlier if you need to start your journey sooner."
        ],
        cons: consList
      });
    }
  }
  
  // D. Fastest Option (if recommended isn't the absolute fastest, e.g. because of penalties)
  if (recommendedRoute.durationMinutes > minDuration) {
    const fastest = otherRoutes.find(r => r.durationMinutes === minDuration);
    if (fastest && !alternatives.find(a => a.routeId === fastest.id)) {
      const saved = recommendedRoute.durationMinutes - fastest.durationMinutes;
      const consList = [];
      if (fastest.transferCount > recommendedRoute.transferCount) {
        consList.push(`Requires changing trains at ${fastest.transferStopName || 'an intermediate station'}.`);
      } else if (fastest.transferWait && fastest.transferWait < 10) {
        consList.push(`Requires a very tight ${Math.round(fastest.transferWait)}-minute transfer.`);
      } else {
        consList.push("Provides less overall convenience.");
      }

      alternatives.push({
        routeId: fastest.id,
        label: "⚡ Fastest Option",
        pros: [
          `Saves ${Math.round(saved)} minutes overall.`
        ],
        cons: consList
      });
    }
  }

  return {
    winnerRouteId: recommendedRoute.id,
    advantages,
    tradeoffs,
    alternatives: alternatives.slice(0, 3) // limit to 3 meaningful alternatives
  };
}
