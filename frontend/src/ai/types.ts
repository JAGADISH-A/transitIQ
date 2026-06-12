export interface RouteExplanation {
  summary: string;
  steps: string[];
  confidence: "high" | "medium" | "low";
}

export interface RouteRecommendation {
  recommendedRouteId: string;
  title: string;
  summary: string;
  reasons: string[];
  confidence: "high" | "medium" | "low";
}

export interface JourneyInsight {
  explanation: RouteExplanation;
}
