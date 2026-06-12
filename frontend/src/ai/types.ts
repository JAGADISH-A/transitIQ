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
  workspaceIntelligence?: WorkspaceIntelligence;
  comparison?: RouteComparison;
}

export interface JourneyInsight {
  category: "connection" | "long_distance" | "layover" | "comfort" | "timing" | "general";
  title: string;
  message: string;
  priority: "low" | "medium" | "high";
}

export interface RouteTradeoff {
  title: string;
  description: string;
  type: "advantage" | "tradeoff" | "alternative";
}

export interface RouteComparison {
  winnerRouteId: string;
  advantages: RouteTradeoff[];
  tradeoffs: RouteTradeoff[];
  alternatives: {
    routeId: string;
    label: string;
    pros: string[];
    cons: string[];
  }[];
}

export interface TimelineMilestone {
  step: string;
  time?: string;
  icon: "board" | "travel" | "arrive" | "wait" | "change" | "destination";
}

export interface WorkspaceIntelligence {
  guidance: string;
  timeline: TimelineMilestone[];
  tips: string[];
}
