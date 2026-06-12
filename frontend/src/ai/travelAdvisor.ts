import type { NormalizedRoute, JourneyRoute } from '../types/transit';
import type { TravelAdvice } from './types';

export function generateTravelAdvice(route: NormalizedRoute, allRoutes: NormalizedRoute[]): TravelAdvice {
  // Extract Train identity if available
  let trainIdentity = 'This service';
  let sourceStop = 'your station';
  let destStop = 'your destination';

  if (!route.isTransfer && route.originalData) {
    const data = route.originalData as JourneyRoute;
    if (data.route_name) {
      trainIdentity = `${data.route_name}${data.route_id ? ` (${data.route_id})` : ''}`;
    }
    if (data.source_stop) sourceStop = data.source_stop;
    if (data.destination_stop) destStop = data.destination_stop;
  }

  // Calculate if significantly fastest
  const sortedByDuration = [...allRoutes].sort((a, b) => a.durationMinutes - b.durationMinutes);
  let isSignificantlyFastest = false;
  if (sortedByDuration.length >= 2 && sortedByDuration[0].id === route.id) {
    const durationDifference = sortedByDuration[1].durationMinutes - sortedByDuration[0].durationMinutes;
    if (durationDifference >= 15) {
      isSignificantlyFastest = true;
    }
  }

  // Warning Tone (Long Wait)
  if (route.transferWait && route.transferWait > 60) {
    return {
      headline: "⚠ Heads Up",
      message: `This route includes a ${route.transferWait} minute wait at ${route.transferStopName || 'the junction'}.\n\nThat's a pretty long layover for a train connection.\n\nIf your schedule is flexible, a later departure may give you a smoother journey.`,
      tone: "warning"
    };
  }

  // Caution Tone (Tight Connection)
  if (route.transferWait && route.transferWait < 10) {
    return {
      headline: "🚨 Travel Advisory",
      message: `You'll only have about ${route.transferWait} minutes to change trains.\n\nIt's doable, but there isn't much room for delays.`,
      tone: "caution"
    };
  }

  // Busy Journey (Multiple Transfers)
  if (route.transferCount >= 2) {
    return {
      headline: "🔄 Busy Journey",
      message: `This route gets you there, but you'll need to change trains ${route.transferCount} times along the way.\n\nIf comfort is your priority, consider the direct alternatives.`,
      tone: "busy"
    };
  }

  // Efficient Tone (Fastest Choice threshold)
  if (isSignificantlyFastest) {
    return {
      headline: "⚡ Fastest Choice",
      message: `${trainIdentity} is the absolute fastest way to reach your destination.\n\nYou'll save significant time compared to other available options, making it the best choice if you're in a hurry.`,
      tone: "efficient"
    };
  }

  // Adventure Tone (Very long transfer route)
  if (route.durationMinutes > 15 * 60 && route.transferCount > 0) {
    return {
      headline: "🌍 Journey Ahead",
      message: `You have a long journey ahead. It will take over 15 hours with ${route.transferCount} transfer(s).\n\nMake sure to prepare for a multi-leg trip.`,
      tone: "adventure"
    };
  }

  // Smooth Tone (Direct Service)
  if (route.transferCount === 0) {
    return {
      headline: "🔥 Smoothest Option",
      message: `${trainIdentity} is the easiest way to get there.\n\nBoard once at ${sourceStop} and stay onboard until ${destStop}.\n\nNo train changes.\nNo waiting around at junctions.\n\nJust settle in and enjoy the ride.`,
      tone: "smooth"
    };
  }

  // Default fallback
  return {
    headline: "🔥 Solid Option",
    message: `${trainIdentity} provides a reliable way to reach your destination with ${route.transferCount} transfer(s).`,
    tone: "smooth"
  };
}
