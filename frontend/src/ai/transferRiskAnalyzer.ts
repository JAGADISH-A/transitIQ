import type { NormalizedRoute } from '../types/transit';
import type { TransferRiskAnalysis } from './types';

export function analyzeTransferRisk(route: NormalizedRoute): TransferRiskAnalysis {
  let score = 100;
  let level: "low" | "medium" | "high" = "low";
  let title = "🟢 Direct Journey";
  let message = "No transfers required. You can remain onboard for the entire trip.";
  const recommendations: string[] = [];

  const wait = route.transferWait;
  const station = route.transferStopName || 'the junction';

  if (route.transferCount === 0) {
    score = 100;
    level = "low";
    title = "🟢 Direct Journey";
    message = "No transfers required.\n\nYou can remain onboard for the entire journey.";
  } else if (wait !== undefined) {
    if (wait < 5) {
      score = 20;
      level = "high";
      title = "🔴 High Risk Connection";
      message = `This transfer leaves very little room for delays.\n\nA late arrival could cause you to miss the next service at ${station}.`;
    } else if (wait < 10) {
      score = 45;
      level = "high";
      title = "🟠 Tight Connection";
      message = `You'll have only ${wait} minutes between trains.\n\nReach your next platform promptly after arrival at ${station}.`;
    } else if (wait < 20) {
      score = 70;
      level = "medium";
      title = "🟡 Moderate Transfer";
      message = `You'll have around ${wait} minutes to make your connection at ${station}.\n\nPay attention to platform information after arrival.`;
    } else if (wait <= 60) {
      score = 90;
      level = "low";
      title = "🟢 Comfortable Transfer";
      message = `${wait} minute transfer window at ${station}.\n\nThis should provide enough time to move between services without rushing.`;
    } else {
      score = 60;
      level = "medium";
      title = "⚠ Long Layover";
      message = `This journey includes a ${wait} minute wait at ${station}.\n\nWhile the connection is safe, it significantly increases total travel time.`;
    }
  }

  if (route.transferCount >= 2) {
    score = Math.max(0, score - 15);
    recommendations.push("🔄 Multiple Transfers: This journey requires several train changes. Expect a more active journey with additional coordination.");
  }

  return {
    level,
    title,
    message,
    score,
    recommendations
  };
}
