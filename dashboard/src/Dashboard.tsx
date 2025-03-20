import {
  AdvancedMarker,
  Map,
  Pin,
  RenderingType,
  useMap,
  useMapsLibrary,
} from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";

import "./Dashboard.css";
import { HttpData } from "./http_types";
import TrackedSatelliteInformation from "./TrackedSatelliteInformation";

export default function Dashboard() {
  const actualLocation = getActualLocation();

  // Periodically fetch data from the server.
  //
  // undefined means we haven't received a response from the receiver yet, null
  // means we've received a response but it contained no data (the receiver is
  // probably running from a file and hasn't finished acquisition yet).
  const [data, setData] = useState<HttpData | null | undefined>();
  useEffect(() => {
    const intervalId = setInterval(async () => {
      try {
        const response = await fetch("http://localhost:8080/");
        setData(await response.json());
      } catch {
        setData(undefined);
      }
    }, 2000);
    return () => clearInterval(intervalId);
  }, []);

  // Update the map's viewport to contain the location estimate.
  const core = useMapsLibrary("core");
  const map = useMap();
  useEffect(() => {
    if (core !== null && data != null && map !== null) {
      const bounds = new core.LatLngBounds();
      if (actualLocation !== null) {
        bounds.extend(actualLocation);
      }
      if (data.latest_solution !== null) {
        const {
          position: { latitude: lat, longitude: lng },
        } = data.latest_solution;
        bounds.extend({ lat, lng });

        // Extend the bounds a little so we can see the area around the location
        const buffer = 0.001;
        bounds.extend({ lat: lat - buffer, lng: lng - buffer });
        bounds.extend({ lat: lat + buffer, lng: lng + buffer });
      }
      map.fitBounds(bounds, 0);
    }
  }, [actualLocation, core, data, map]);

  if (data === undefined) {
    return <p className="message">Waiting for the server to start.</p>;
  }

  if (data === null) {
    return <p className="message">Waiting for the server to collect data.</p>;
  }

  return (
    <>
      {/* Map */}
      <div className="map-container">
        <Map
          clickableIcons={false}
          defaultCenter={{ lat: 0, lng: 0 }}
          defaultZoom={0}
          disableDefaultUI
          gestureHandling="none"
          mapId="DEMO_MAP_ID"
          renderingType={RenderingType.VECTOR}
        >
          {actualLocation && (
            <AdvancedMarker key="actual" position={actualLocation}>
              <Pin
                background="#4285F4"
                borderColor="#174EA6"
                glyphColor="#174EA6"
              />
            </AdvancedMarker>
          )}
          {data.latest_solution && (
            <AdvancedMarker
              key="estimated"
              position={{
                lat: data.latest_solution.position.latitude,
                lng: data.latest_solution.position.longitude,
              }}
            />
          )}
        </Map>
      </div>

      {/* Tracked satellites */}
      {data.tracked_satellites.length === 0 ? (
        <p>No satellites have been acquired yet.</p>
      ) : (
        <div className="tracked-satellites-container">
          {data.tracked_satellites
            .toSorted(({ satellite_id: a }, { satellite_id: b }) => a - b)
            .map((trackedSatellite) => (
              <TrackedSatelliteInformation
                key={trackedSatellite.satellite_id}
                trackedSatellite={trackedSatellite}
              />
            ))}
        </div>
      )}
    </>
  );
}

function getActualLocation(): google.maps.LatLngLiteral | null {
  const s = import.meta.env.VITE_ACTUAL_LOCATION;
  if (s === undefined) {
    return null;
  }

  const ss = s.split(",");
  if (ss.length !== 2) {
    throw Error(`Invalid actual location: ${s}`);
  }

  const ns = ss.map(parseFloat);
  if (ns.some(isNaN)) {
    throw Error(`Invalid actual location: ${s}`);
  }

  return { lat: ns[0], lng: ns[1] };
}
