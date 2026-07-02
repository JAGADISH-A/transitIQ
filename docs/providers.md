# Transport Provider API

## Architecture

```
BaseTransportProvider (ABC, app/providers/base.py)
├── RailwayProvider   (app/providers/railway_provider.py)  — wraps TransitService
├── BusProvider       (app/providers/bus_provider.py)      — built-in + GTFS ready
├── MetroProvider     (app/providers/metro_provider.py)    — built-in + GTFS ready
└── FerryProvider     (app/providers/ferry_provider.py)    — built-in + GTFS ready

ProviderRegistry (app/providers/registry.py) — singleton, routes queries
MultiModalPlanner (app/providers/multi_modal_planner.py) — cross-provider routing
```

## Interface

Every provider must implement `BaseTransportProvider` (app/providers/base.py):

| Method/Property | Returns | Required |
|---|---|---|
| `provider_id` | `str` | Yes |
| `provider_name` | `str` | Yes |
| `mode` | `TransportMode` enum | Yes |
| `is_available()` | `bool` | Yes |
| `get_info()` | `ProviderInfo` | Yes |
| `search_stops(query)` | `List[TransportStop]` | Yes |
| `get_stop_by_id(stop_id)` | `TransportStop \| None` | Yes |
| `find_journeys(src, dst, dep_after)` | `List[TransportJourney]` | Optional (default `[]`) |
| `get_nearby_stops(lat, lon, radius_km)` | `List[TransportStop]` | Optional (default `[]`) |
| `get_stops_for_journey_planning()` | `List[TransportStop]` | Optional (default `[]`) |

## TransportMode enum

```python
class TransportMode(str, Enum):
    RAIL = "RAIL"
    BUS = "BUS"
    METRO = "METRO"
    FERRY = "FERRY"
    WALK = "WALK"
    TRAM = "TRAM"
    OTHER = "OTHER"
```

## Adding a New Provider

### 1. Create the provider class

Create `app/providers/your_provider.py`:

```python
import logging
from typing import List
from app.models.transit import (
    TransportJourney, TransportMode, TransportSegment,
    TransportStop, ProviderInfo,
)
from app.providers.base import BaseTransportProvider

logger = logging.getLogger(__name__)

class YourProvider(BaseTransportProvider):
    provider_id = "your_id"
    provider_name = "Your Display Name"
    mode = TransportMode.BUS  # or METRO, FERRY, etc.

    def __init__(self):
        self._stops: List[TransportStop] = []
        self._load_data()

    def _load_data(self):
        """Load stops from built-in data or GTFS."""
        self._stops = [...]

    def is_available(self) -> bool:
        return len(self._stops) > 0

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            mode=self.mode,
            available=self.is_available(),
            stop_count=len(self._stops),
            data_source="built-in",  # or "gtfs"
            description="...",
        )

    def search_stops(self, query: str) -> List[TransportStop]:
        q = query.lower().strip()
        return [s for s in self._stops
                if q in s.stop_name.lower() or q in s.stop_id.lower()][:10]

    def get_stop_by_id(self, stop_id: str) -> TransportStop | None:
        for s in self._stops:
            if s.stop_id == stop_id:
                return s
        return None

    def find_journeys(self, source_stop_id: str, destination_stop_id: str,
                      departure_after: str | None = None) -> List[TransportJourney]:
        # Implement routing logic or use haversine fallback
        ...

    def get_nearby_stops(self, lat: float, lon: float,
                         radius_km: float = 2.0) -> List[TransportStop]:
        from app.utils.geo_utils import haversine
        nearby = [s for s in self._stops
                  if haversine(lat, lon, s.lat, s.lon) <= radius_km]
        nearby.sort(key=lambda s: haversine(lat, lon, s.lat, s.lon))
        return nearby[:10]

    def get_stops_for_journey_planning(self) -> List[TransportStop]:
        return self._stops.copy()

your_provider = YourProvider()
```

### 2. Register the provider

In `app/main.py`, import and register during startup:

```python
from app.providers.your_provider import your_provider

# Inside lifespan():
provider_registry.register(your_provider)
```

### 3. (Optional) Add agent tools

If your provider needs custom agent-facing tools, add methods in `app/services/agent_tools.py` and define tools in `app/services/foundry_agent.py`.

## GTFS Integration

When a GTFS feed with matching name is loaded (e.g., "bus", "metro", "ferry"),
providers can switch from built-in data to GTFS. Pattern used by RailwayProvider:

```python
def _load_gtfs_if_available(self) -> None:
    from app.services.transit_service import transit_service
    loader = transit_service.get_feed("your_feed_name")
    self._gtfs_loaded = loader is not None
    if self._gtfs_loaded:
        # Populate stops from loader.stops DataFrame
        ...
```

The `ProviderInfo.data_source` field should reflect the active source:
- `"built-in"` — using hardcoded data
- `"gtfs"` — using loaded GTFS feed

## Data Model Reference

### TransportStop
| Field | Type | Description |
|---|---|---|
| stop_id | str | Unique ID within provider |
| stop_name | str | Human-readable name |
| lat | float | Latitude |
| lon | float | Longitude |
| mode | TransportMode | Transport mode enum |
| provider | str | Provider ID |
| stop_code | str \| None | Public-facing code/plate number |
| zone | str \| None | Fare zone |
| wheelchair_accessible | bool \| None | Accessibility flag |

### TransportJourney
| Field | Type | Description |
|---|---|---|
| segments | list[TransportSegment] | Legs of the journey |
| total_duration_minutes | int \| None | Total travel time |
| total_transfers | int | Number of transfers |
| modes_used | list[TransportMode] | Modes involved |
| providers_used | list[str] | Providers involved |
| quality | JourneyQuality \| None | Quality ranking |
| narrative_summary | str \| None | Human description |

### TransportPreference
| Field | Type | Default |
|---|---|---|
| preferred_modes | list[TransportMode] | [] |
| avoided_modes | list[TransportMode] | [] |
| max_transfers | int \| None | None |
| max_walk_minutes | int \| None | None |
| accessibility_required | bool | False |
| optimized_for | str | "balanced" |

## Testing

Create tests in `tests/` following existing patterns:

```python
def test_your_provider_search():
    assert len(your_provider.search_stops("query")) > 0

def test_your_provider_find_journeys():
    journeys = your_provider.find_journeys("src_id", "dst_id")
    assert len(journeys) >= 1
```

Run with:
```bash
pytest tests/ -v
```
