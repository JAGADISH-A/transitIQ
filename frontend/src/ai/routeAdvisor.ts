import type { NormalizedRoute } from '../types/transit';
import type { RouteRecommendation } from './types';
import { generateTravelAdvice } from './travelAdvisor';
import { analyzeTransferRisk } from './transferRiskAnalyzer';
import { generateWorkspaceIntelligence } from './journeyConcierge';
import { analyzeRouteTradeoffs } from './routeTradeoffAnalyzer';

export function recommendBestRoute(routes: NormalizedRoute[]): RouteRecommendation | null {
  if (!routes || routes.length === 0) return null;

  // 1. Calculate baselines
  const minDuration = Math.min(...routes.map(r => r.durationMinutes));

  // 2. Score routes
  const scoredRoutes = routes.map(route => {
    let score = 1000;
    const reasons: string[] = [];
    const penalties: string[] = [];
    
    // Duration
    const durationDiff = route.durationMinutes - minDuration;
    if (durationDiff > 0) {
      score -= durationDiff * 2;
    } else {
      reasons.push("Fastest available journey");
    }

    // Direct Service
    if (route.transferCount === 0) {
      score += 200;
      reasons.push("No transfers required");
      reasons.push("Lower travel complexity");
    } else {
      score -= route.transferCount * 150;
    }

    // Wait Time
    if (route.transferWait) {
      if (route.transferWait > 60) {
        score -= 500;
        penalties.push(`Wait time of ${route.transferWait} minutes at ${route.transferStopName || 'transfer stop'}`);
      } else if (route.transferWait > 30) {
        score -= 200;
        penalties.push(`Moderate wait of ${route.transferWait} minutes`);
      }
    }

    return { route, score, reasons, penalties };
  });

  // Sort descending by score
  scoredRoutes.sort((a, b) => b.score - a.score);

  const best = scoredRoutes[0];
  const worst = scoredRoutes[scoredRoutes.length - 1];

  const title = "TransitIQ Recommendation";
  let summary = "";
  const finalReasons = [...best.reasons];
  let confidence: "high" | "medium" | "low" = "medium";

  // Compare best with second best if exists
  if (scoredRoutes.length > 1) {
    const margin = best.score - scoredRoutes[1].score;
    if (margin > 200) confidence = "high";
    else if (margin < 50) confidence = "medium";

    // If there's a terrible route, maybe point it out if best is clear
    if (worst.penalties.length > 0 && worst.route.transferWait! > 60) {
      const transferStop = worst.route.transferStopName || "transfer station";
      // Let's adopt the "Avoid..." logic if the best route is just okay but the worst is terrible
      if (best.route.transferCount === 0 && margin > 300) {
        summary = "I recommend the direct service.";
        finalReasons.push(`Avoids the ${worst.route.transferWait} minute transfer wait at ${transferStop} on alternative routes`);
      }
    }
  } else {
    // Only one route
    confidence = best.score > 800 ? "high" : (best.score > 400 ? "medium" : "low");
  }

  // Fallback summaries if empty
  if (!summary) {
    if (best.route.transferCount === 0) {
      summary = "I recommend the direct service.";
    } else {
      const stop = best.route.transferStopName || "a transfer station";
      summary = `I recommend this route via ${stop}.`;
    }
  }

  // Ensure unique reasons and limit to top 4
  const uniqueReasons = Array.from(new Set(finalReasons)).slice(0, 4);

  // If the best route has terrible wait time, that means ALL routes are terrible
  if (best.route.transferWait && best.route.transferWait > 60) {
    confidence = "low";
    summary = `Expect delays. The best available route still requires a ${best.route.transferWait} minute wait.`;
    uniqueReasons.length = 0; // clear reasons to put warnings
    uniqueReasons.push(`${best.route.transferWait} minute transfer wait at ${best.route.transferStopName}`);
    uniqueReasons.push("Significantly increases journey time");
    uniqueReasons.push("Higher risk of travel disruption");
  } else if (best.route.transferCount === 0 && !uniqueReasons.includes("Fastest available journey")) {
    uniqueReasons.unshift("Direct connection");
  }

  const advice = generateTravelAdvice(best.route, routes);
  const transferRisk = analyzeTransferRisk(best.route);
  const workspaceIntelligence = generateWorkspaceIntelligence(best.route);
  const comparison = analyzeRouteTradeoffs(routes, best.route);

  return {
    recommendedRouteId: best.route.id,
    title: advice.headline,
    summary: advice.message,
    reasons: uniqueReasons.length > 0 ? uniqueReasons : ["Provides the most balanced travel experience"],
    confidence,
    advice,
    transferRisk,
    workspaceIntelligence,
    comparison
  };
}
