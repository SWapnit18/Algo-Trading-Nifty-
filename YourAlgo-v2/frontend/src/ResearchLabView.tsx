import React, { useState, useEffect } from "react";

interface ResearchLabProps {
  api: string;
  showToast: (msg: string, type: "success" | "error" | "info" | "warning") => void;
}

export function ResearchLabView({ api, showToast }: ResearchLabProps) {
  const [underlying, setUnderlying] = useState("NIFTY");
  const [comparison, setComparison] = useState<any[]>([]);
  const [walkForwardData, setWalkForwardData] = useState<any>(null);
  const [selectedStrategy, setSelectedStrategy] = useState("STRAT_ADAPTIVE_TREND_RIDER");
  const [loadingComp, setLoadingComp] = useState(false);
  const [loadingWF, setLoadingWF] = useState(false);

  // Fetch Side-by-Side Comparison
  const loadComparison = async () => {
    setLoadingComp(true);
    try {
      const res = await fetch(`${api}/api/strategies/compare?underlying=${underlying}`);
      const data = await res.json();
      setComparison(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("Failed to load strategy comparison:", e);
    } finally {
      setLoadingComp(false);
    }
  };

  // Run Walk-Forward Analysis
  const runWalkForward = async () => {
    setLoadingWF(true);
    try {
      const res = await fetch(`${api}/api/backtest/walk_forward`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ underlying, strategy_code: selectedStrategy, capital: 100000.0 })
      });
      const data = await res.json();
      setWalkForwardData(data);
      showToast(`Walk-Forward Analysis complete for ${selectedStrategy}`, "success");
    } catch (e) {
      showToast("Walk-Forward execution failed", "error");
    } finally {
      setLoadingWF(false);
    }
  };

  useEffect(() => {
    loadComparison();
  }, [underlying, api]);

  useEffect(() => {
    runWalkForward();
  }, [underlying, selectedStrategy, api]);

  return (
    <div className="fade-in" style={{ maxWidth: 1280, margin: "0 auto", paddingBottom: 60 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 900, color: "#F8FAFC", margin: 0, letterSpacing: "-0.02em" }}>
            STRATEGY RESEARCH LAB & ANTI-OVERFITTING ENGINE
          </h1>
          <p style={{ margin: "4px 0 0 0", fontSize: 12, color: "#94A3B8" }}>
            Institutional validation across Out-of-Sample datasets, Walk-Forward Efficiency (WFE), and Indian regulatory costs.
          </p>
        </div>

        {/* Index Selector */}
        <div style={{ display: "flex", gap: 8, background: "#0B0D0F", padding: 4, borderRadius: 8, border: "1px solid #20252A" }}>
          <button
            onClick={() => setUnderlying("NIFTY")}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 800,
              cursor: "pointer",
              background: underlying === "NIFTY" ? "#1E293B" : "transparent",
              color: underlying === "NIFTY" ? "#38BDF8" : "#94A3B8",
              border: underlying === "NIFTY" ? "1px solid #38BDF8" : "none"
            }}
          >
            NIFTY 50
          </button>
          <button
            onClick={() => setUnderlying("BANKNIFTY")}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 800,
              cursor: "pointer",
              background: underlying === "BANKNIFTY" ? "#1E293B" : "transparent",
              color: underlying === "BANKNIFTY" ? "#38BDF8" : "#94A3B8",
              border: underlying === "BANKNIFTY" ? "1px solid #38BDF8" : "none"
            }}
          >
            BANK NIFTY
          </button>
        </div>
      </div>

      {/* 1. SIDE-BY-SIDE STRATEGY COMPARISON MATRIX */}
      <div className="glass-card" style={{ padding: 22, borderRadius: 12, marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 800, margin: 0, color: "#F8FAFC" }}>
              Multi-Strategy Head-to-Head Comparison ({underlying} Options)
            </h2>
            <span style={{ fontSize: 11, color: "#94A3B8" }}>
              Identical historical benchmark data. Real slippage & Indian statutory taxes deducted.
            </span>
          </div>

          <button
            onClick={loadComparison}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              background: "#1E293B",
              border: "1px solid #334155",
              color: "#38BDF8",
              fontSize: 11,
              fontWeight: 700,
              cursor: "pointer"
            }}
          >
            {loadingComp ? "Simulating..." : "↻ Re-Run Benchmark"}
          </button>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#0B0D0F", color: "#64748B", borderBottom: "1px solid #20252A", textAlign: "left" }}>
                <th style={{ padding: "10px 12px" }}>STRATEGY</th>
                <th>TRADES</th>
                <th>WIN RATE</th>
                <th>NET P&L (₹)</th>
                <th>PROFIT FACTOR</th>
                <th>EXPECTANCY</th>
                <th>SHARPE</th>
                <th>MAX DD %</th>
                <th>TOTAL CHARGES</th>
                <th>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((c: any) => (
                <tr key={c.code} style={{ borderBottom: "1px solid #1E242B" }}>
                  <td style={{ padding: "12px", fontWeight: 800, color: "#F8FAFC" }}>
                    <div>{c.name}</div>
                    <div style={{ fontSize: 10, color: "#64748B", fontWeight: 600 }}>{c.code} (v{c.version})</div>
                  </td>
                  <td className="num">{c.total_trades}</td>
                  <td className="num" style={{ fontWeight: 700, color: c.win_rate >= 50 ? "#22C55E" : "#F59E0B" }}>
                    {c.win_rate}%
                  </td>
                  <td className="num" style={{ fontWeight: 800, color: c.net_pnl >= 0 ? "#22C55E" : "#EF4444" }}>
                    ₹{c.net_pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="num" style={{ fontWeight: 700, color: c.profit_factor >= 1.5 ? "#22C55E" : "#94A3B8" }}>
                    {c.profit_factor}
                  </td>
                  <td className="num">₹{c.expectancy}</td>
                  <td className="num" style={{ fontWeight: 700, color: c.sharpe_ratio >= 1.0 ? "#38BDF8" : "#94A3B8" }}>
                    {c.sharpe_ratio}
                  </td>
                  <td className="num" style={{ color: "#EF4444" }}>{c.max_drawdown_pct}%</td>
                  <td className="num" style={{ color: "#64748B", fontSize: 11 }}>₹{c.total_costs}</td>
                  <td>
                    <span style={{
                      fontSize: 10,
                      fontWeight: 800,
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: "rgba(34, 197, 94, 0.15)",
                      color: "#22C55E",
                      border: "1px solid rgba(34, 197, 94, 0.3)"
                    }}>
                      PLUGGABLE
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 2. ANTI-OVERFITTING & WALK-FORWARD TESTING PANEL */}
      <div className="glass-card" style={{ padding: 22, borderRadius: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h2 style={{ fontSize: 15, fontWeight: 800, margin: 0, color: "#F8FAFC" }}>
                Walk-Forward Out-of-Sample Verification
              </h2>
              {walkForwardData && (
                <span style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: "3px 8px",
                  borderRadius: 4,
                  background: walkForwardData.is_robust ? "rgba(34, 197, 94, 0.15)" : "rgba(245, 158, 11, 0.15)",
                  border: walkForwardData.is_robust ? "1px solid #22C55E" : "1px solid #F59E0B",
                  color: walkForwardData.is_robust ? "#22C55E" : "#F59E0B"
                }}>
                  {walkForwardData.is_robust ? "✓ ROBUST OUT-OF-SAMPLE EDGE" : "⚠ CAUTION: CURVE-FIT SENSITIVITY"}
                </span>
              )}
            </div>
            <span style={{ fontSize: 11, color: "#94A3B8" }}>
              Splits historical data into Train (60%), Validation (20%), and Out-of-Sample (20%) to prevent curve-fitting.
            </span>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <select
              value={selectedStrategy}
              onChange={e => setSelectedStrategy(e.target.value)}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                background: "#0B0D0F",
                border: "1px solid #20252A",
                color: "#F8FAFC",
                fontSize: 11,
                fontWeight: 700
              }}
            >
              {comparison.length > 0 ? (
                comparison.map((c: any) => (
                  <option key={c.code} value={c.code}>{c.name}</option>
                ))
              ) : (
                <>
                  <option value="STRAT_ADAPTIVE_TREND_RIDER">Adaptive Trend Rider</option>
                  <option value="STRAT_FIXED_RR_13">Fixed RR 1:3</option>
                  <option value="STRAT_VOLATILITY_SQUEEZE">Volatility Squeeze</option>
                  <option value="STRAT_ORB_INDEX">Opening Range Breakout</option>
                  <option value="STRAT_MEAN_REVERSION_EXTREME">Mean Reversion Extreme</option>
                  <option value="STRAT_EXPIRY_GAMMA_SCALPER">Expiry Day Gamma Scalper</option>
                  <option value="STRAT_VWAP_PULLBACK_RIDER">Institutional VWAP Pullback Rider</option>
                  <option value="STRAT_CPR_BREAKOUT">Central Pivot Range (CPR) Breakout</option>
                </>
              )}
            </select>

            <button
              onClick={runWalkForward}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                background: "#1E293B",
                border: "1px solid #38BDF8",
                color: "#38BDF8",
                fontSize: 11,
                fontWeight: 700,
                cursor: "pointer"
              }}
            >
              {loadingWF ? "Analyzing..." : "Run Walk-Forward"}
            </button>
          </div>
        </div>

        {walkForwardData ? (
          <div>
            {/* Split Comparison Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 20 }}>
              {/* Train Split */}
              <div style={{ background: "#0B0D0F", padding: 16, borderRadius: 8, border: "1px solid #20252A" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 11, color: "#64748B", fontWeight: 800 }}>TRAINING SPLIT (60%)</span>
                  <span style={{ fontSize: 10, color: "#94A3B8" }}>In-Sample</span>
                </div>
                <div style={{ fontSize: 18, fontWeight: 900, color: walkForwardData.in_sample_train.net_pnl >= 0 ? "#22C55E" : "#EF4444" }} className="num">
                  ₹{walkForwardData.in_sample_train.net_pnl}
                </div>
                <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>
                  Win Rate: <strong>{walkForwardData.in_sample_train.win_rate}%</strong> | PF: <strong>{walkForwardData.in_sample_train.profit_factor}</strong>
                </div>
                <div style={{ fontSize: 10.5, color: "#64748B", marginTop: 2 }}>
                  Sharpe: {walkForwardData.in_sample_train.sharpe_ratio} | Trades: {walkForwardData.in_sample_train.total_trades}
                </div>
              </div>

              {/* Validation Split */}
              <div style={{ background: "#0B0D0F", padding: 16, borderRadius: 8, border: "1px solid #20252A" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 11, color: "#64748B", fontWeight: 800 }}>VALIDATION SPLIT (20%)</span>
                  <span style={{ fontSize: 10, color: "#94A3B8" }}>Parameter Test</span>
                </div>
                <div style={{ fontSize: 18, fontWeight: 900, color: walkForwardData.validation.net_pnl >= 0 ? "#22C55E" : "#EF4444" }} className="num">
                  ₹{walkForwardData.validation.net_pnl}
                </div>
                <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>
                  Win Rate: <strong>{walkForwardData.validation.win_rate}%</strong> | PF: <strong>{walkForwardData.validation.profit_factor}</strong>
                </div>
                <div style={{ fontSize: 10.5, color: "#64748B", marginTop: 2 }}>
                  Sharpe: {walkForwardData.validation.sharpe_ratio} | Trades: {walkForwardData.validation.total_trades}
                </div>
              </div>

              {/* Out-of-Sample Split */}
              <div style={{ background: "#0B0D0F", padding: 16, borderRadius: 8, border: "1px solid #20252A" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 11, color: "#38BDF8", fontWeight: 800 }}>OUT-OF-SAMPLE (20%)</span>
                  <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 4, background: "rgba(56, 189, 248, 0.15)", color: "#38BDF8", fontWeight: 700 }}>
                    Unseen Market
                  </span>
                </div>
                <div style={{ fontSize: 18, fontWeight: 900, color: walkForwardData.out_of_sample.net_pnl >= 0 ? "#22C55E" : "#EF4444" }} className="num">
                  ₹{walkForwardData.out_of_sample.net_pnl}
                </div>
                <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>
                  Win Rate: <strong>{walkForwardData.out_of_sample.win_rate}%</strong> | PF: <strong>{walkForwardData.out_of_sample.profit_factor}</strong>
                </div>
                <div style={{ fontSize: 10.5, color: "#64748B", marginTop: 2 }}>
                  Sharpe: {walkForwardData.out_of_sample.sharpe_ratio} | Trades: {walkForwardData.out_of_sample.total_trades}
                </div>
              </div>
            </div>

            {/* Exit Reason Distribution */}
            {walkForwardData.in_sample_train.exit_distribution && (
              <div style={{ background: "#0B0D0F", padding: 14, borderRadius: 8, border: "1px solid #20252A" }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#94A3B8", marginBottom: 8 }}>
                  Exit Reason Distribution (Statistical Trade Closure Breakdown):
                </div>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 11 }}>
                  {Object.entries(walkForwardData.in_sample_train.exit_distribution).map(([k, v]: any) => (
                    <div key={k} style={{ background: "#111417", padding: "4px 10px", borderRadius: 4, border: "1px solid #20252A" }}>
                      <span style={{ color: "#64748B" }}>{k}:</span> <strong style={{ color: "#F8FAFC" }}>{v}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "40px 0", color: "#64748B", fontSize: 12 }}>
            Simulating walk-forward data partitions...
          </div>
        )}
      </div>
    </div>
  );
}
