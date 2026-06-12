export interface RouteExplanation {
  summary: string;
  steps: string[];
  confidence: "high" | "medium" | "low";
}

export interface TravelAdvice {
  headline: string;
  message: string;
  tone: "smooth" | "warning" | "efficient" | "adventure" | "caution" | "busy";
}

export interface TransferRiskAnalysis {
  level: "low" | "medium" | "high";
  title: string;
  message: string;
  score: number;
  recommendations: string[];
}

export interface RouteRecommendation {
  recommendedRouteId: string;
  title: string;
  summary: string;
  reasons: string[];
  confidence: "high" | "medium" | "low";
  advice?: TravelAdvice;
  transferRisk?: TransferRiskAnalysis;
}

export interface JourneyInsight {
  explanation: RouteExplanation;
}
