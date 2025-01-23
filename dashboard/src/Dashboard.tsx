import {
  AdvancedMarker,
  Map,
  RenderingType,
  useMap,
  useMapsLibrary,
} from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";

import "./Dashboard.css";
import { HttpData } from "./http_types";
import TrackedSatelliteInformation from "./TrackedSatelliteInformation";

export default function Dashboard() {
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
      } catch (e) {
        console.error(e);
        setData(undefined);
      }
    }, 2000);
    return () => clearInterval(intervalId);
  }, []);

  // Update the map's viewport to contain the location estimates.
  const core = useMapsLibrary("core");
  const map = useMap();
  useEffect(() => {
    if (core !== null && data != null && map !== null) {
      const bounds = new core.LatLngBounds();
      for (const {
        position: { latitude: lat, longitude: lng },
      } of data.solutions) {
        bounds.extend({ lat, lng });
      }
      map.fitBounds(bounds, 150);
    }
  }, [core, data, map]);

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
          {data.solutions.map(
            ({ position: { latitude: lat, longitude: lng } }, i) => (
              <AdvancedMarker key={i} position={{ lat, lng }} />
            ),
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
