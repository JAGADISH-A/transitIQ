import type { NormalizedRoute } from '../types/transit';
import type { JourneyInsight } from './types';
import { generateRouteExplanation } from './routeExplainer';

export function analyzeJourney(route: NormalizedRoute): JourneyInsight {
  return {
    explanation: generateRouteExplanation(route)
  };
}

export { recommendBestRoute } from './routeAdvisor';
export { analyzeTransferRisk } from './transferRiskAnalyzer';
