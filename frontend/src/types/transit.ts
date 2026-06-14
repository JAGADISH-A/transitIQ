export interface StopResult {
  stop_id: string;
  stop_name: string;
  lat: number;
  lon: number;
}

export interface SearchResponse {
  query: string;
  results: StopResult[];
  count: number;
}

export interface DisplayTime {
  display_time: string;
  day_offset: number;
}

export interface ActiveJourney {
  source: string;
  destination: string;
  departure_time: string;
  transfer_station?: string;
  transfer_count: number;
}

export interface PreviousRouteComparison {
  duration_minutes: number;
  transfer_count: number;
  quality_classification: string;
}

export interface JourneyContext {
  source?: string;
  destination?: string;
  departure_time?: string;
  route_preference?: string;
  last_updated?: string;
  active_journey?: ActiveJourney;
  previous_comparison?: PreviousRouteComparison;
}

export interface JourneyNarrative {
  headline: string;
  summary: string;
  recommendation: string;
  warnings: string[];
  alternatives_available: number;
}

export interface JourneyQuality {
  score: number;
  classification: "Excellent" | "Good" | "Acceptable" | "Poor" | "Low Quality" | "Rejected";
  recommendation_reason?: string;
  route_flags: string[];
}

export interface JourneyRoute {
  feed: string;
  trip_id: string;
  route_id: string;
  route_name: string;
  source_stop: string;
  destination_stop: string;
  stops_between: number;
  departure_time?: string;
  arrival_time?: string;
  departure_display?: DisplayTime;
  arrival_display?: DisplayTime;
  duration_minutes?: number;
  shape_id?: string;
  quality?: JourneyQuality;
}

export interface TransferJourney {
  journey_type: "TRANSFER";
  transfer_stop: string;
  first_leg: JourneyRoute;
  second_leg: JourneyRoute;
  third_leg?: JourneyRoute;
  transfer_stop_2?: string;
  transfer_wait_2?: number;
  total_duration: number;
  transfer_wait: number;
  quality?: JourneyQuality;
}

export interface JourneyResponse {
  success: boolean;
  narrative?: JourneyNarrative;
  routes: JourneyRoute[];
  transfer_routes: TransferJourney[];
}

export interface TripStop {
  stop_id: string;
  stop_name: string;
  stop_sequence: number;
  arrival_time?: string;
  departure_time?: string;
  arrival_display?: DisplayTime;
  departure_display?: DisplayTime;
  stop_lat?: number;
  stop_lon?: number;
}

export interface NormalizedRoute {
  id: string;
  isTransfer: boolean;
  sourceName: string;
  destName: string;
  departureTime: string | null;
  arrivalTime: string | null;
  departureDisplay: DisplayTime | null;
  arrivalDisplay: DisplayTime | null;
  durationMinutes: number;
  transferCount: number;
  transferWait?: number;
  transferStopName?: string;
  qualityScore: number;
  originalData: JourneyRoute | TransferJourney;
}
