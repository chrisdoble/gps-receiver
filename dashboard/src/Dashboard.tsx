import {
  AdvancedMarker,
  Map,
  RenderingType,
  useMap,
  useMapsLibrary,
} from "@vis.gl/react-google-maps";
import { useEffect, useState } from "react";

import { HttpData } from "./http_types";

export default function Dashboard() {
  // Fetch data from the server every 1 s.
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
    }, 1000);
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
      map.fitBounds(bounds, 200);
    }
  }, [core, data, map]);

  if (data === undefined) {
    return <p>Waiting to receive data from the server.</p>;
  }

  if (data === null) {
    return <p>The server is running but it hasn't collected any data yet.</p>;
  }

  return (
    <div style={{ height: "500px" }}>
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
  );
}
