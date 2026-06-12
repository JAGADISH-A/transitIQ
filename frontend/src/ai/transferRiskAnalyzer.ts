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
    message = "This is the simplest way to travel. Stay on the same train for the entire journey with no station changes required.";
  } else if (wait !== undefined) {
    if (wait < 5) {
      score = 20;
      level = "high";
      title = `⚠ Very tight connection at ${station}`;
      message = "A delay on your first train could make this connection difficult. Move quickly to your next platform.";
    } else if (wait < 10) {
      score = 45;
      level = "high";
      title = `⏱ ${wait} minutes to change trains at ${station}`;
      message = "This leaves little room for delays. We recommend proceeding directly to your next platform upon arrival.";
    } else if (wait < 20) {
      score = 70;
      level = "medium";
      title = `⏱ About ${wait} minutes to connect at ${station}`;
      message = "This should be enough time, but pay attention to platform announcements as soon as you arrive.";
    } else if (wait <= 60) {
      score = 90;
      level = "low";
      title = `🟢 Comfortable ${wait} minute connection at ${station}`;
      message = "You should have plenty of time to move between services without rushing.";
    } else {
      score = 60;
      level = "medium";
      title = `☕ ${wait} minute wait at ${station}`;
      message = "This connection is very safe, but it adds significant waiting time to your journey.";
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
