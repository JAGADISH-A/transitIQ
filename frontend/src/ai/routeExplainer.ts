import type { NormalizedRoute, JourneyRoute, TransferJourney } from '../types/transit';
import type { RouteExplanation } from './types';

function toTitleCase(str: string): string {
  if (!str) return '';
  return str.replace(
    /\w\S*/g,
    (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase()
  );
}

function getTrainName(leg: JourneyRoute): string {
  const name = leg.route_name;
  const id = leg.route_id || leg.trip_id;
  
  if (name && id && name !== id) return `${toTitleCase(name)} (${id})`;
  if (name && name === id) return `Train No. ${id}`;
  if (name) return `${toTitleCase(name)}`;
  if (id) return `Train No. ${id}`;
  
  return "Train";
}

function formatDuration(mins: number): string {
  if (mins < 60) return `${mins} minutes`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h} hours ${m} minutes` : `${h} hours`;
}

export function generateRouteExplanation(route: NormalizedRoute): RouteExplanation {
  const isTransfer = route.isTransfer;
  const durationStr = formatDuration(route.durationMinutes);
  
  let summary = '';
  const steps: string[] = [];
  
  let missingMetadataCount = 0;
  
  if (!isTransfer) {
    const leg = route.originalData as JourneyRoute;
    const trainName = getTrainName(leg);
    
    if (trainName === "Train") missingMetadataCount++;
    if (!leg.departure_display?.display_time) missingMetadataCount++;
    if (!leg.arrival_display?.display_time) missingMetadataCount++;

    summary = `This route uses ${trainName} and provides a direct connection from ${toTitleCase(route.sourceName)} to ${toTitleCase(route.destName)} in approximately ${durationStr}.`;
    
    steps.push(`Board ${trainName} at ${toTitleCase(route.sourceName)}.`);
    if (leg.departure_display?.display_time) {
      steps.push(`Depart at ${leg.departure_display.display_time}.`);
    }
    steps.push(`Remain onboard for approximately ${formatDuration(leg.duration_minutes || route.durationMinutes)}.`);
    
    if (leg.arrival_display?.display_time) {
      steps.push(`Arrive at ${toTitleCase(route.destName)} at ${leg.arrival_display.display_time}.`);
    } else {
      steps.push(`Arrive at ${toTitleCase(route.destName)}.`);
    }
    
  } else {
    const transfer = route.originalData as TransferJourney;
    const leg1 = transfer.first_leg;
    const leg2 = transfer.second_leg;
    
    const train1 = getTrainName(leg1);
    const train2 = getTrainName(leg2);
    
    if (train1 === "Train" || train2 === "Train") missingMetadataCount++;
    if (!leg1.departure_display?.display_time || !leg2.arrival_display?.display_time) missingMetadataCount++;

    const transferStop = toTitleCase(route.transferStopName || transfer.transfer_stop || "transfer station");
    const waitStr = formatDuration(route.transferWait || transfer.transfer_wait || 0);

    summary = `This journey requires one transfer at ${transferStop} and takes approximately ${durationStr}.`;
    
    steps.push(`Board ${train1} at ${toTitleCase(route.sourceName)}.`);
    steps.push(`Travel to ${transferStop}.`);
    steps.push(`Transfer trains at ${transferStop}.`);
    steps.push(`Wait approximately ${waitStr}.`);
    steps.push(`Board ${train2}.`);
    steps.push(`Continue to ${toTitleCase(route.destName)}.`);
    
    if (leg2.arrival_display?.display_time) {
      steps.push(`Arrive at ${leg2.arrival_display.display_time}.`);
    } else {
      steps.push(`Arrive at your destination.`);
    }
  }

  let confidence: "high" | "medium" | "low" = "high";
  if (missingMetadataCount >= 2) {
    confidence = "low";
  } else if (missingMetadataCount === 1) {
    confidence = "medium";
  }

  return {
    summary,
    steps,
    confidence
  };
}
