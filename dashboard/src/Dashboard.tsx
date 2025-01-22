import { useEffect, useState } from "react";

import { HttpData } from "./http_types";

export default function Dashboard() {
  // The most recent data returned from the receiver.
  //
  // undefined means we haven't received a response from the receiver yet, null
  // means we've received a response but it contained no data (the receiver is
  // probably running from a file and hasn't finished acquisition yet).
  const [data, setData] = useState<HttpData | null | undefined>();

  // Fetch data from the server every 1 s.
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

  if (data === undefined) {
    return <p>Waiting to receive data from the receiver.</p>;
  } else if (data === null) {
    return <p>The receiver is running but it hasn't collected any data yet.</p>;
  } else {
    return <pre>{JSON.stringify(data)}</pre>;
  }
}
