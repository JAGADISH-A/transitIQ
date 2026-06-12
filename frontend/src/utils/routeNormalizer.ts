import type { JourneyRoute, TransferJourney, NormalizedRoute } from '../types/transit';

const createDisplayFallback = (time: string | null) => {
  if (!time) return null;
  const parts = time.split(':');
  if (parts.length >= 2) {
    let h = parseInt(parts[0], 10);
    const m = parts[1];
    let day_offset = 0;
    if (h >= 24) {
      day_offset = Math.floor(h / 24);
      h = h % 24;
    }
    const ampm = h >= 12 ? 'PM' : 'AM';
    const displayH = h % 12 === 0 ? 12 : h % 12;
    return {
      display_time: `${displayH}:${m} ${ampm}`,
      day_offset
    };
  }
  return { display_time: time, day_offset: 0 };
};

export function normalizeRoutes(routes: JourneyRoute[], transferRoutes: TransferJourney[]): NormalizedRoute[] {
  const direct: NormalizedRoute[] = (routes || [])
    .filter(r => r && r.trip_id)
    .map(r => ({
      id: crypto.randomUUID(),
      isTransfer: false,
      sourceName: r.source_stop || "Unknown Source",
      destName: r.destination_stop || "Unknown Destination",
      departureTime: r.departure_time || null,
      arrivalTime: r.arrival_time || null,
      departureDisplay: r.departure_display || createDisplayFallback(r.departure_time),
      arrivalDisplay: r.arrival_display || createDisplayFallback(r.arrival_time),
      durationMinutes: r.duration_minutes || 0,
      transferCount: 0,
      qualityScore: (r.duration_minutes || 0),
      originalData: r
    }));

  const transfers: NormalizedRoute[] = (transferRoutes || [])
    .filter(r => r && r.first_leg && r.second_leg)
    .map(r => ({
      id: crypto.randomUUID(),
      isTransfer: true,
      sourceName: r.first_leg.source_stop || "Unknown Source",
      destName: r.second_leg.destination_stop || "Unknown Destination",
      departureTime: r.first_leg.departure_time || null,
      arrivalTime: r.second_leg.arrival_time || null,
      departureDisplay: r.first_leg.departure_display || createDisplayFallback(r.first_leg.departure_time),
      arrivalDisplay: r.second_leg.arrival_display || createDisplayFallback(r.second_leg.arrival_time),
      durationMinutes: r.total_duration || 0,
      transferCount: 1,
      transferWait: r.transfer_wait,
      transferStopName: r.transfer_stop,
      qualityScore: 1000 + ((r.transfer_wait || 0) * 2) + (r.total_duration || 0),
      originalData: r
    }));

  const allRoutes = [...direct, ...transfers];
  console.log("=== NORMALIZATION AUDIT ===");
  if (routes && routes.length > 0) {
    console.log("RAW DIRECT ROUTE[0]", routes[0]);
    console.log("NORMALIZED DIRECT ROUTE[0]", direct[0]);
  }
  if (transferRoutes && transferRoutes.length > 0) {
    console.log("RAW TRANSFER ROUTE[0]", transferRoutes[0]);
    console.log("NORMALIZED TRANSFER ROUTE[0]", transfers[0]);
  }
  return allRoutes;
}
