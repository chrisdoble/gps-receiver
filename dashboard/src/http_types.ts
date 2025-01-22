/**
 * This file was automatically generated. Don't edit it by hand. Instead, change
 * gpsreceiver/gpsreceiver/http_types.py and run bin/generate_dashboard_types.sh.
 */

/**
 * Data sent to the HTTP server subprocess to be served to clients.
 */
export interface HttpData {
  solutions: GeodeticSolution[];
  tracked_satellites: TrackedSatellite[];
  untracked_satellites: UntrackedSatellite[];
}
/**
 * A computed solution with the position in geodetic coordinates.
 */
export interface GeodeticSolution {
  clock_bias: number;
  position: GeodeticCoordinates;
}
/**
 * A location expressed in geodetic coordinates.
 */
export interface GeodeticCoordinates {
  height: number;
  latitude: number;
  longitude: number;
}
/**
 * Data regarding a tracked satellite.
 */
export interface TrackedSatellite {
  acquired_at: string;
  bit_boundary_found: boolean;
  bit_phase: (-1 | 1) | null;
  carrier_frequency_shifts: number[];
  correlations: string[];
  prn_code_phase_shifts: number[];
  required_subframes_received: boolean;
  satellite_id: number;
  subframe_count: number;
}
/**
 * Data regarding an untracked satellite.
 */
export interface UntrackedSatellite {
  next_acquisition_at: string;
  satellite_id: number;
}

