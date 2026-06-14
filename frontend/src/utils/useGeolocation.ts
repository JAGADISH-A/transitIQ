import { useState, useCallback } from 'react';

interface GeolocationState {
  loading: boolean;
  error: string | null;
  lat: number | null;
  lon: number | null;
}

export function useGeolocation() {
  const [state, setState] = useState<GeolocationState>({
    loading: false,
    error: null,
    lat: null,
    lon: null,
  });

  const requestLocation = useCallback(() => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    if (!navigator.geolocation) {
      setState({
        loading: false,
        error: "Location services unavailable.",
        lat: null,
        lon: null,
      });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setState({
          loading: false,
          error: null,
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        });
      },
      (error) => {
        let errorMessage = "Location services unavailable.";
        if (error.code === error.PERMISSION_DENIED) {
          errorMessage = "Location access denied. Search manually.";
        }
        setState({
          loading: false,
          error: errorMessage,
          lat: null,
          lon: null,
        });
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      }
    );
  }, []);

  return { ...state, requestLocation };
}
