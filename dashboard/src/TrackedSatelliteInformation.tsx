import { useCallback, useMemo } from "react";
import {
  Dot,
  DotProps,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  XAxis,
  XAxisProps,
  YAxis,
  YAxisProps,
} from "recharts";

import { TrackedSatellite } from "./http_types";
import "./TrackedSatelliteInformation.css";

export default function TrackedSatelliteInformation({
  trackedSatellite: {
    bit_boundary_found,
    bit_phase,
    carrier_frequency_shifts,
    correlations,
    duration,
    prn_code_phase_shifts,
    required_subframes_received,
    satellite_id,
    subframe_count,
  },
}: {
  trackedSatellite: TrackedSatellite;
}) {
  return (
    <div className="tracked-satellite-container">
      <h1>#{satellite_id}</h1>
      <ol>
        <li>{toEmoji(bit_boundary_found)} Bit boundary</li>
        <li>{toEmoji(bit_phase !== null)} Bit phase</li>
        <li>{toEmoji(required_subframes_received)} Required subframes</li>
      </ol>
      <dl>
        <dt>Duration:</dt>
        <dd>{toHoursMinutesSeconds(duration)}</dd>
        <dt>Subframes:</dt>
        <dd>{subframe_count}</dd>
      </dl>
      <div className="line-charts-container">
        <LineChart_
          data={carrier_frequency_shifts}
          title="Carrier frequency shift"
        />
        <LineChart_ data={prn_code_phase_shifts} title="PRN code phase shift" />
      </div>
      <CorrelationChart data={correlations} />
    </div>
  );
}

/** Converts a boolean value to an appropriate emoji. */
function toEmoji(value: boolean): string {
  return value ? "✅" : "❌";
}

/**
 * Converts a duration in seconds to a string.
 *
 *     toHoursMinutesSeconds(6020) === "1h 40m 20s"
 */
function toHoursMinutesSeconds(duration: number): string {
  const hours = Math.floor(duration / 3600);
  const minutes = Math.floor((duration % 3600) / 60);
  const seconds = Math.floor(duration % 60);
  return [
    hours ? `${hours}h` : "",
    minutes ? `${minutes}m` : "",
    seconds ? `${seconds}s` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function LineChart_({ data, title }: { data: number[]; title: string }) {
  const identity = useCallback((x: unknown) => x, []);
  const xTickFormatter = useCallback(
    (n: number) => (n === 0 ? "-1s" : "0s"),
    [],
  );
  const yTickFormatter = useCallback((n: number) => `${Math.floor(n)}`, []);

  return (
    <div className="line-chart-container">
      <p className="chart-title">{title}</p>
      <ResponsiveContainer height={100} width="100%">
        <LineChart data={data}>
          <Line animationDuration={0} dataKey={identity} dot={false} />
          <XAxis height={15} tickFormatter={xTickFormatter} ticks={[0, 999]} />
          <YAxis
            domain={["dataMin", "dataMax"]}
            tickFormatter={yTickFormatter}
            type="number"
            width={40}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function CorrelationChart({ data }: { data: number[][] }) {
  // For some reason domain={["dataMin", "dataMax"]} doesn't seem to work for
  // scatter plots. Calculate each axes' domain manually.
  const xDomain = useMemo<NonNullable<XAxisProps["domain"]>>(() => {
    const xs = data.map(([x]) => x);
    return [Math.floor(Math.min(...xs)), Math.ceil(Math.max(...xs))];
  }, [data]);
  const yDomain = useMemo<NonNullable<YAxisProps["domain"]>>(() => {
    const ys = data.map(([y]) => y);
    return [Math.floor(Math.min(...ys)), Math.ceil(Math.max(...ys))];
  }, [data]);

  return (
    <div className="correlation-chart-container">
      <p className="chart-title">Correlations</p>
      <ResponsiveContainer height={200} width="100%">
        <ScatterChart>
          <Scatter
            animationDuration={0}
            data={data}
            shape={<CorrelationDot />}
          />
          <XAxis dataKey={0} domain={xDomain} height={15} type="number" />
          <YAxis dataKey={1} domain={yDomain} type="number" width={20} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function CorrelationDot({ cx, cy }: DotProps) {
  return <Dot cx={cx} cy={cy} fill="#3182bd80" r={2} />;
}
