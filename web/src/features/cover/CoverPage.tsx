import type { CoverResponse, Fuel } from "../../types/api";
import { quantity } from "../../lib/format";

const fuels: Fuel[] = ["DIESEL", "PETROL", "OCTANE"];

export default function CoverPage({
  cover,
  loading,
  error,
}: {
  cover: CoverResponse | undefined;
  loading: boolean;
  error: boolean;
}) {
  if (loading) {
    return <section className="panel section-panel"><p>Calculating days of cover and scarcity metrics…</p></section>;
  }

  if (error || !cover) {
    return (
      <section className="panel section-panel">
        <p className="eyebrow">SCARCITY & RATIONING</p>
        <h2>Finite Supply Intelligence Unavailable</h2>
        <p className="muted">Could not retrieve supply cover data from the API.</p>
      </section>
    );
  }

  const {
    supply_ends_tick,
    current_tick,
    ticks_remaining_supply,
    rationing_active,
    rationing_mode,
    network_days_of_cover,
    fuel_cover,
    stations,
  } = cover;

  const pctToScarcity = Math.min(100, Math.round((current_tick / supply_ends_tick) * 100));

  return (
    <>
      <section className="overview-heading">
        <div>
          <p className="eyebrow">FINITE SUPPLY & RATIONING</p>
          <h2>Network Cover & Scarcity Window</h2>
          <p className="muted">
            Scheduled supply arrivals end at <strong>Tick {supply_ends_tick}</strong> (3 waves of 6 arrivals).
            After tick {supply_ends_tick}, total available fuel is finite (~6 days).
          </p>
        </div>
        <div className="metric-card">
          <span className="metric-label">NETWORK COVER</span>
          <strong>{network_days_of_cover.toFixed(1)}d</strong>
          <span>{ticks_remaining_supply} ticks until supply ends</span>
        </div>
      </section>

      {/* Finite Supply Scarcity Bar */}
      <section className="panel section-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">SUPPLY HORIZON TIMELINE</p>
            <h2>Scheduled Arrivals Window</h2>
          </div>
          <span
            className={`status-pill ${
              rationing_active ? "status-failed" : "status-healthy"
            }`}
          >
            {rationing_mode}
          </span>
        </div>
        <div className="scarcity-progress-container" style={{ margin: "1rem 0" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "0.85rem",
              marginBottom: "0.4rem",
              fontFamily: "monospace",
            }}
          >
            <span>Tick 0 (Origin)</span>
            <span>Current: Tick {current_tick} ({pctToScarcity}%)</span>
            <span>Supply Ends: Tick {supply_ends_tick}</span>
          </div>
          <div
            style={{
              height: "12px",
              background: "#1e2433",
              borderRadius: "6px",
              overflow: "hidden",
              border: "1px solid #2d3748",
            }}
          >
            <div
              style={{
                width: `${pctToScarcity}%`,
                height: "100%",
                background: rationing_active
                  ? "linear-gradient(90deg, #f59e0b, #ef4444)"
                  : "linear-gradient(90deg, #3b82f6, #10b981)",
                transition: "width 0.5s ease",
              }}
            />
          </div>
        </div>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          {rationing_active
            ? "⚠️ CRITICAL: Finite supply horizon reached. Dynamic policy has switched from naive top-ups to rationing mode (protecting minimum service level across all stations)."
            : "ℹ️ Scheduled supply waves are recurring on schedule. Stations replenish normally."}
        </p>
      </section>

      {/* Fuel Breakdown Grid */}
      <section className="panel section-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">SYSTEM FUEL COVER</p>
            <h2>Days of Cover by Fuel</h2>
          </div>
          <span className="section-note">Total station & depot inventory vs 24h burn rate</span>
        </div>
        <div className="fuel-cover-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
          {fuels.map((fuel) => {
            const data = fuel_cover[fuel];
            if (!data) return null;
            return (
              <div
                key={fuel}
                className="panel"
                style={{
                  background: "#141824",
                  padding: "1rem",
                  border: "1px solid #232b3e",
                  borderRadius: "6px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <strong style={{ fontSize: "1.1rem", color: "#f8fafc" }}>{fuel}</strong>
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontWeight: 700,
                      color: data.days_of_cover < 3 ? "#f43f5e" : data.days_of_cover < 6 ? "#f59e0b" : "#10b981",
                    }}
                  >
                    {data.days_of_cover.toFixed(1)} days
                  </span>
                </div>
                <div style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "#94a3b8" }}>
                  <div>Inventory: <strong>{quantity(data.total_inventory_liters)} L</strong></div>
                  <div>Daily Burn: <strong>{quantity(data.daily_demand_liters)} L/day</strong></div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Station Isolation Risk & Cover Matrix */}
      <section className="panel section-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">STATION RISK & RATIONING TARGETS</p>
            <h2>Single-Route Stations & Isolation Vulnerability</h2>
          </div>
          <span className="section-note">
            Tongi and Cox's Bazar have only 1 route (zero reroute redundancy)
          </span>
        </div>
        <div className="table-scroll">
          <table className="risk-matrix">
            <thead>
              <tr>
                <th>Station</th>
                <th>Region</th>
                <th>Network Redundancy</th>
                <th>Buffer Target</th>
                {fuels.map((f) => (
                  <th key={f}>{f} Cover</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stations.map((st) => (
                <tr key={st.station_id}>
                  <th scope="row">
                    <span className="entity-name">{st.name}</span>
                    <span className="entity-meta">{st.demand_profile}</span>
                  </th>
                  <td>{st.region_id}</td>
                  <td>
                    {st.isolation_risk ? (
                      <span
                        style={{
                          background: "#451a03",
                          color: "#f59e0b",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          border: "1px solid #78350f",
                        }}
                      >
                        ⚠️ ISOLATION RISK (1 Route)
                      </span>
                    ) : (
                      <span style={{ color: "#64748b", fontSize: "0.8rem" }}>Multiple Routes</span>
                    )}
                  </td>
                  <td style={{ fontFamily: "monospace", fontWeight: 600 }}>
                    {Math.round(st.target_buffer_ratio * 100)}%
                    {st.isolation_risk && " (Elevated)"}
                  </td>
                  {fuels.map((f) => {
                    const days = st.days_of_cover[f] ?? 0;
                    return (
                      <td key={f}>
                        <span
                          style={{
                            fontFamily: "monospace",
                            fontWeight: 600,
                            color: days < 1.0 ? "#f43f5e" : days < 2.5 ? "#f59e0b" : "#e2e8f0",
                          }}
                        >
                          {days > 100 ? ">100d" : `${days.toFixed(1)}d`}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

