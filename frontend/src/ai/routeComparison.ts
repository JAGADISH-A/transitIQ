import type { NormalizedRoute } from '../types/transit';
import type { RouteRecommendation } from './types';

export interface RouteComparison {
  title: string;
  explanation: string;
  badges: string[];
}

export function generateRouteComparison(
  activeRoute: NormalizedRoute,
  recommendedRoute?: NormalizedRoute,
  recommendation?: RouteRecommendation
): RouteComparison {
  // If viewing the recommended route
  if (!recommendedRoute || activeRoute.id === recommendedRoute.id) {
    return {
      title: "🤔 Why TransitIQ Recommended This Route",
      explanation: recommendation?.advice?.message || "This route provides the best balance of speed and convenience for your journey.",
      badges: []
    };
  }

  // If viewing an alternative route
  const badges: string[] = [];
  const points: string[] = [];
  
  const durDiff = activeRoute.durationMinutes - recommendedRoute.durationMinutes;

  if (activeRoute.transferCount === 0 && recommendedRoute.transferCount > 0) {
    badges.push("No Transfers");
    points.push("This is a direct journey, avoiding the transfer required by the recommended route.");
  } else if (activeRoute.transferCount < recommendedRoute.transferCount) {
    badges.push("Fewer Transfers");
    points.push("This route requires fewer train changes.");
  } else if (activeRoute.transferCount > recommendedRoute.transferCount) {
    badges.push("More Transfers");
    points.push("This route requires an additional train change.");
  }

  if (durDiff > 10) {
    badges.push("Longer Journey");
    if (activeRoute.transferCount === 0) {
      points.push(`However, it adds approximately ${durDiff} minutes to your overall travel time.`);
    } else {
      points.push(`It takes approximately ${durDiff} minutes longer than the recommended route.`);
    }
  } else if (durDiff < -10) {
    badges.push("Faster Journey");
    points.push(`It is approximately ${Math.abs(durDiff)} minutes faster than the recommended route.`);
  }

  if (activeRoute.transferWait && recommendedRoute.transferWait) {
    const waitDiff = activeRoute.transferWait - recommendedRoute.transferWait;
    if (waitDiff > 5) {
      if (activeRoute.transferWait >= 15) {
        badges.push("More Comfortable");
        points.push("This route provides a more comfortable transfer window.");
      }
    } else if (waitDiff < -5) {
      if (activeRoute.transferWait < 10) {
        badges.push("Tighter Transfer");
        points.push("Be aware that the transfer window is significantly tighter.");
      }
    }
  }

  // Parse departure times to compare if one leaves earlier
  if (activeRoute.departureTime && recommendedRoute.departureTime) {
    // Basic string comparison works for HH:MM:SS
    if (activeRoute.departureTime < recommendedRoute.departureTime) {
      badges.push("Earlier Departure");
    } else if (activeRoute.departureTime > recommendedRoute.departureTime) {
      badges.push("Later Departure");
    }
  }

  let explanation = points.join(" ");
  if (!explanation) {
    explanation = "TransitIQ ranked this route lower based on a combination of travel time, wait times, and overall journey complexity.";
  } else {
    explanation += " TransitIQ prioritized the recommended route to better balance travel time and convenience.";
  }

  return {
    title: "🔍 How This Route Compares",
    explanation,
    badges
  };
}
