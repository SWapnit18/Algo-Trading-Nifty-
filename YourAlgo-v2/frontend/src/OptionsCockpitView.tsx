import React, { useState, useEffect } from "react";

interface OptionsCockpitProps {
  api: string;
  token: string | null;
  authHeaders: Record<string, string>;
  showToast: (msg: string, type: "success" | "error" | "info" | "warning") => void;
}

export function OptionsCockpitView({ api, token, authHeaders, showToast }: OptionsCockpitProps) {
  const [underlying, setUnderlying] = useState<"NIFTY" | "BANKNIFTY">("NIFTY");
  const [regimeData, setRegimeData] = useState<any>(null);
  const [optionChain, setOptionChain] = useState<any>(null);
  const [selectedContract, setSelectedContract] = useState<any>(null);
  const [selectedStrategy, setSelectedStrategy] = useState("STRAT_ADAPTIVE_TREND_RIDER");
  const [strategies, setStrategies] = useState<any[]>([]);
  const [killSwitch, setKillSwitch] = useState({ stop_new_trades_active: false, emergency_exit_active: false });
  const [loading, setLoading] = useState(false);
  const [executingOrder, setExecutingOrder] = useState(false);

  // Capital & Risk settings
  const [capital, setCapital] = useState(100000);
  const [riskPct, setRiskPct] = useState(1.0);
  const [threshold, setThreshold] = useState(75);

  // Load Strategies Catalog
  useEffect(() => {
    fetch(`${api}/api/strategies/catalog`)
      .then(r => r.json())
      .then(d => setStrategies(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, [api]);

  // Load Killswitch status
  const fetchKillSwitch = () => {
    fetch(`${api}/api/killswitch/status`)
      .then(r => r.json())
      .then(d => setKillSwitch(d))
      .catch(() => {});
  };

  useEffect(() => {
    fetchKillSwitch();
  }, [api]);

  // Load Regime & Option Chain
  const loadMarketData = async () => {
    setLoading(true);
    try {
      const [regRes, chainRes] = await Promise.all([
        fetch(`${api}/api/regime/status/${underlying}`),
        fetch(`${api}/api/options/chain/${underlying}`)
      ]);
      const reg = await regRes.json();
      const chain = await chainRes.json();
      setRegimeData(reg);
      setOptionChain(chain);

      // Auto-evaluate best contract based on MTF direction
      const dir = reg?.mtf_alignment?.recommended_direction;
      if (dir && dir !== "NO_TRADE") {
        const selRes = await fetch(`${api}/api/options/select`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ underlying, direction: dir })
        });
        const selData = await selRes.json();
        if (selData?.contract) setSelectedContract(selData.contract);
      } else {
        // Default select ATM CE for preview
        const selRes = await fetch(`${api}/api/options/select`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ underlying, direction: "BUY_CE" })
        });
        const selData = await selRes.json();
        if (selData?.contract) setSelectedContract(selData.contract);
      }
    } catch (e) {
      console.warn("Options cockpit fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMarketData();
    const interval = setInterval(loadMarketData, 10000);
    return () => clearInterval(interval);
  }, [underlying, api]);

  // Toggle Stop Trades Kill Switch
  const toggleStopTrades = async () => {
    try {
      const nextState = !killSwitch.stop_new_trades_active;
      const res = await fetch(`${api}/api/killswitch/stop_trades`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ active: nextState })
      });
      const data = await res.json();
      setKillSwitch(prev => ({ ...prev, stop_new_trades_active: data.kill_switch_active }));
      showToast(data.message, nextState ? "warning" : "success");
    } catch (e) {
      showToast("Failed to toggle kill switch", "error");
    }
  };

  // Trigger Emergency Exit All
  const triggerEmergencyExit = async () => {
    if (!window.confirm("⚠️ EMERGENCY EXIT CONFIRMATION:\nAre you sure you want to immediately SELL ALL open long option positions and HALT automated trading?")) {
      return;
    }
    try {
      const res = await fetch(`${api}/api/killswitch/emergency_exit`, {
        method: "POST",
        headers: authHeaders
      });
      const data = await res.json();
      fetchKillSwitch();
      showToast(`Emergency Exit Completed: ${data.positions_closed} positions liquidated`, "error");
    } catch (e) {
      showToast("Emergency exit request failed", "error");
    }
  };

  // Place Options Order
  const handlePlaceOrder = async (side: "BUY" | "SELL") => {
    if (!selectedContract) {
      showToast("No option contract selected", "warning");
      return;
    }
    setExecutingOrder(true);
    try {
      const res = await fetch(`${api}/api/orders/paper`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          symbol: selectedContract.symbol,
          side: side,
          order_type: "MARKET",
          quantity: selectedContract.lot_size * 2,
          price: selectedContract.ltp,
          stop_loss: roundNum(selectedContract.ltp * 0.82),
          target: roundNum(selectedContract.ltp * 1.54)
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Order submission failed");
      showToast(`Option ${side} Executed: ${selectedContract.symbol} @ ₹${data.execution_price}`, "success");
    } catch (e: any) {
      showToast(e.message || "Execution error", "error");
    } finally {
      setExecutingOrder(false);
    }
  };

  const roundNum = (n?: number) => (n !== undefined && !isNaN(n) ? Math.round(n * 100) / 100 : 0);

  const mtfDir = regimeData?.mtf_alignment?.recommended_direction || "NO_TRADE";
  const scoreVal = regimeData?.signal_quality_score?.total_score || 0;
  const regime15 = regimeData?.regime_15m?.regime || "NEUTRAL";
  const spotPrice = regimeData?.spot || (underlying === "NIFTY" ? 24850 : 51200);

  return (
    <div className="fade-in" style={{ maxWidth: 1280, margin: "0 auto", paddingBottom: 60 }}>
      {/* 1. TOP HEADER & KILL SWITCH CONTROLS */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 14 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h1 style={{ fontSize: 22, fontWeight: 900, color: "#F8FAFC", margin: 0, letterSpacing: "-0.02em" }}>
              YOURALGO INDEX OPTIONS BUYER
            </h1>
            <span style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "3px 8px",
              borderRadius: 4,
              background: "rgba(59, 130, 246, 0.15)",
              border: "1px solid rgba(59, 130, 246, 0.35)",
              color: "#60A5FA",
              textTransform: "uppercase"
            }}>
              Options Buying Only
            </span>
          </div>
          <p style={{ margin: "4px 0 0 0", fontSize: 12, color: "#94A3B8" }}>
            Automated Indian Index Derivatives Cockpit: NIFTY 50 & BANK NIFTY (CE/PE Longs Only, Zero Naked Selling)
          </p>
        </div>

        {/* Dual Kill Switch Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={toggleStopTrades}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
              cursor: "pointer",
              transition: "all 0.2s",
              background: killSwitch.stop_new_trades_active
                ? "linear-gradient(135deg, #F59E0B, #D97706)"
                : "rgba(30, 41, 59, 0.8)",
              border: killSwitch.stop_new_trades_active ? "1px solid #F59E0B" : "1px solid rgba(255, 255, 255, 0.12)",
              color: killSwitch.stop_new_trades_active ? "#0F172A" : "#F59E0B",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            <span>🛑</span>
            {killSwitch.stop_new_trades_active ? "STOP TRADES (ARMED)" : "STOP NEW TRADES"}
          </button>

          <button
            onClick={triggerEmergencyExit}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
              cursor: "pointer",
              transition: "all 0.2s",
              background: "linear-gradient(135deg, #EF4444, #B91C1C)",
              border: "1px solid #EF4444",
              color: "#FFFFFF",
              boxShadow: "0 0 14px rgba(239, 68, 68, 0.3)",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            <span>⚡</span>
            EMERGENCY EXIT ALL
          </button>
        </div>
      </div>

      {/* 2. INDEX SWITCHER & REGIME SUMMARY BAR */}
      <div className="glass-card" style={{ padding: "16px 20px", borderRadius: 12, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
          {/* Index Selector Tabs */}
          <div style={{ display: "flex", gap: 8, background: "#0B0D0F", padding: 4, borderRadius: 8, border: "1px solid #20252A" }}>
            <button
              onClick={() => setUnderlying("NIFTY")}
              style={{
                padding: "8px 20px",
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
                background: underlying === "NIFTY" ? "#1E293B" : "transparent",
                color: underlying === "NIFTY" ? "#38BDF8" : "#94A3B8",
                border: underlying === "NIFTY" ? "1px solid #38BDF8" : "none"
              }}
            >
              NIFTY 50 (Lot 25)
            </button>
            <button
              onClick={() => setUnderlying("BANKNIFTY")}
              style={{
                padding: "8px 20px",
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
                background: underlying === "BANKNIFTY" ? "#1E293B" : "transparent",
                color: underlying === "BANKNIFTY" ? "#38BDF8" : "#94A3B8",
                border: underlying === "BANKNIFTY" ? "1px solid #38BDF8" : "none"
              }}
            >
              BANK NIFTY (Lot 15)
            </button>
          </div>

          {/* Live Underlying Spot & Regime Badge */}
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <div>
              <span style={{ fontSize: 10, color: "#64748B", fontWeight: 700, textTransform: "uppercase" }}>Current Spot LTP</span>
              <div style={{ fontSize: 20, fontWeight: 900, color: "#F8FAFC" }} className="num">
                ₹{spotPrice.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div>
              <span style={{ fontSize: 10, color: "#64748B", fontWeight: 700, textTransform: "uppercase" }}>15m Market Regime</span>
              <div>
                <span style={{
                  fontSize: 11,
                  fontWeight: 800,
                  padding: "4px 10px",
                  borderRadius: 6,
                  background: regime15.includes("BULL") ? "rgba(34, 197, 94, 0.15)" : (regime15.includes("BEAR") ? "rgba(239, 68, 68, 0.15)" : "rgba(148, 163, 184, 0.15)"),
                  border: regime15.includes("BULL") ? "1px solid #22C55E" : (regime15.includes("BEAR") ? "1px solid #EF4444" : "1px solid #64748B"),
                  color: regime15.includes("BULL") ? "#22C55E" : (regime15.includes("BEAR") ? "#EF4444" : "#94A3B8")
                }}>
                  {regime15}
                </span>
              </div>
            </div>

            <div>
              <span style={{ fontSize: 10, color: "#64748B", fontWeight: 700, textTransform: "uppercase" }}>MTF Consensus</span>
              <div>
                <span style={{
                  fontSize: 11,
                  fontWeight: 800,
                  padding: "4px 10px",
                  borderRadius: 6,
                  background: mtfDir === "BUY_CE" ? "rgba(34, 197, 94, 0.2)" : (mtfDir === "BUY_PE" ? "rgba(239, 68, 68, 0.2)" : "rgba(100, 116, 139, 0.2)"),
                  border: mtfDir === "BUY_CE" ? "1px solid #22C55E" : (mtfDir === "BUY_PE" ? "1px solid #EF4444" : "1px solid #64748B"),
                  color: mtfDir === "BUY_CE" ? "#22C55E" : (mtfDir === "BUY_PE" ? "#EF4444" : "#94A3B8")
                }}>
                  {mtfDir === "BUY_CE" ? "🟢 BUY CE (BULLISH)" : (mtfDir === "BUY_PE" ? "🔴 BUY PE (BEARISH)" : "⏸ NO TRADE (SIDEWAYS)")}
                </span>
              </div>
            </div>

            <div>
              <span style={{ fontSize: 10, color: "#64748B", fontWeight: 700, textTransform: "uppercase" }}>Signal Quality Score</span>
              <div style={{ fontSize: 20, fontWeight: 900, color: scoreVal >= threshold ? "#22C55E" : (scoreVal >= 60 ? "#F59E0B" : "#EF4444") }} className="num">
                {scoreVal.toFixed(1)}<span style={{ fontSize: 12, color: "#64748B" }}>/100</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. COCKPIT GRID: STRATEGY SELECTOR & SIGNAL RADAR & OPTIMAL CONTRACT */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* Left: Strategy Selector & Multi-Timeframe Alignment */}
        <div className="glass-card" style={{ padding: 20, borderRadius: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 800, margin: "0 0 12px 0", color: "#F8FAFC", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            1. Strategy Configuration & Multi-Timeframe Engine
          </h2>

          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600, display: "block", marginBottom: 6 }}>
              Select Active Algorithmic Options Strategy:
            </label>
            <select
              value={selectedStrategy}
              onChange={e => setSelectedStrategy(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: 8,
                background: "#0B0D0F",
                border: "1px solid #20252A",
                color: "#F8FAFC",
                fontSize: 12,
                fontWeight: 700
              }}
            >
              {strategies.map(s => (
                <option key={s.code} value={s.code}>
                  {s.name} (v{s.version})
                </option>
              ))}
            </select>
            <p style={{ margin: "6px 0 0 0", fontSize: 11, color: "#64748B" }}>
              {strategies.find(s => s.code === selectedStrategy)?.description || "Evaluates momentum and options Greek dynamics."}
            </p>
          </div>

          {/* Multi-Timeframe Status Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, background: "#0B0D0F", padding: 12, borderRadius: 8, border: "1px solid #20252A" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 10, color: "#64748B", fontWeight: 700 }}>15m (Regime)</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: regimeData?.regime_15m?.regime.includes("BULL") ? "#22C55E" : (regimeData?.regime_15m?.regime.includes("BEAR") ? "#EF4444" : "#94A3B8"), marginTop: 4 }}>
                {regimeData?.regime_15m?.regime || "—"}
              </div>
              <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>RSI: {regimeData?.regime_15m?.rsi ?? "—"}</div>
            </div>

            <div style={{ textAlign: "center", borderLeft: "1px solid #20252A", borderRight: "1px solid #20252A" }}>
              <div style={{ fontSize: 10, color: "#64748B", fontWeight: 700 }}>5m (Setup)</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: regimeData?.regime_5m?.regime.includes("BULL") ? "#22C55E" : (regimeData?.regime_5m?.regime.includes("BEAR") ? "#EF4444" : "#94A3B8"), marginTop: 4 }}>
                {regimeData?.regime_5m?.regime || "—"}
              </div>
              <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>ADX: {regimeData?.regime_5m?.adx ?? "—"}</div>
            </div>

            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 10, color: "#64748B", fontWeight: 700 }}>1m (Timing)</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: regimeData?.regime_1m?.regime.includes("BULL") ? "#22C55E" : (regimeData?.regime_1m?.regime.includes("BEAR") ? "#EF4444" : "#94A3B8"), marginTop: 4 }}>
                {regimeData?.regime_1m?.regime || "—"}
              </div>
              <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>VWAP: {regimeData?.regime_1m?.vwap_relation ?? "—"}</div>
            </div>
          </div>

          {/* Signal Score Breakdown */}
          <div style={{ marginTop: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontWeight: 700, color: "#94A3B8", marginBottom: 6 }}>
              <span>Signal Quality Sub-Scores</span>
              <span>Threshold: {threshold}/100</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, fontSize: 10 }}>
              <div style={{ background: "#0B0D0F", padding: "6px 8px", borderRadius: 6, border: "1px solid #20252A" }}>
                <span style={{ color: "#64748B" }}>Trend (25):</span> <strong style={{ color: "#F8FAFC" }}>{regimeData?.signal_quality_score?.trend_score ?? 0}</strong>
              </div>
              <div style={{ background: "#0B0D0F", padding: "6px 8px", borderRadius: 6, border: "1px solid #20252A" }}>
                <span style={{ color: "#64748B" }}>Mom (20):</span> <strong style={{ color: "#F8FAFC" }}>{regimeData?.signal_quality_score?.momentum_score ?? 0}</strong>
              </div>
              <div style={{ background: "#0B0D0F", padding: "6px 8px", borderRadius: 6, border: "1px solid #20252A" }}>
                <span style={{ color: "#64748B" }}>VWAP (15):</span> <strong style={{ color: "#F8FAFC" }}>{regimeData?.signal_quality_score?.vwap_score ?? 0}</strong>
              </div>
              <div style={{ background: "#0B0D0F", padding: "6px 8px", borderRadius: 6, border: "1px solid #20252A" }}>
                <span style={{ color: "#64748B" }}>Struct (15):</span> <strong style={{ color: "#F8FAFC" }}>{regimeData?.signal_quality_score?.structure_score ?? 0}</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Selected Contract & Adaptive Trailing Visualizer */}
        <div className="glass-card" style={{ padding: 20, borderRadius: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 800, margin: "0 0 12px 0", color: "#F8FAFC", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            2. Selected Option Contract & Trailing Stops
          </h2>

          {selectedContract ? (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#0B0D0F", padding: "12px 14px", borderRadius: 8, border: "1px solid #20252A", marginBottom: 14 }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 900, color: selectedContract.option_type === "CE" ? "#22C55E" : "#EF4444" }}>
                      {selectedContract.symbol}
                    </span>
                    <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "#1E293B", color: "#38BDF8", fontWeight: 700 }}>
                      {selectedContract.moneyness}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 4 }}>
                    Delta: {selectedContract.delta} | IV: {selectedContract.iv}% | Spread: {selectedContract.spread_pct}% | Lot: {selectedContract.lot_size}
                  </div>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 20, fontWeight: 900, color: "#F8FAFC" }} className="num">
                    ₹{selectedContract.ltp}
                  </div>
                  <div style={{ fontSize: 10, color: "#64748B" }}>
                    Bid: ₹{selectedContract.bid} | Ask: ₹{selectedContract.ask}
                  </div>
                </div>
              </div>

              {/* Trailing Stop Levels Visualizer */}
              <div style={{ background: "#0B0D0F", padding: 12, borderRadius: 8, border: "1px solid #20252A", marginBottom: 14 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#94A3B8", marginBottom: 8 }}>
                  Adaptive Trailing Stop Execution Pathway:
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, fontSize: 11 }}>
                  <div style={{ padding: "6px 8px", borderRadius: 6, background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)" }}>
                    <div style={{ fontSize: 9.5, color: "#EF4444", fontWeight: 700 }}>HARD INITIAL STOP</div>
                    <div style={{ fontWeight: 800, color: "#F8FAFC", marginTop: 2 }}>₹{roundNum(selectedContract.ltp * 0.82)}</div>
                  </div>

                  <div style={{ padding: "6px 8px", borderRadius: 6, background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
                    <div style={{ fontSize: 9.5, color: "#F59E0B", fontWeight: 700 }}>BREAKEVEN @ 1.5R</div>
                    <div style={{ fontWeight: 800, color: "#F8FAFC", marginTop: 2 }}>₹{roundNum(selectedContract.ltp * 1.02)}</div>
                  </div>

                  <div style={{ padding: "6px 8px", borderRadius: 6, background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.3)" }}>
                    <div style={{ fontSize: 9.5, color: "#22C55E", fontWeight: 700 }}>PROFIT LOCK @ 2.0R</div>
                    <div style={{ fontWeight: 800, color: "#F8FAFC", marginTop: 2 }}>₹{roundNum(selectedContract.ltp * 1.18)}</div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  onClick={() => handlePlaceOrder("BUY")}
                  disabled={executingOrder || killSwitch.stop_new_trades_active}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: killSwitch.stop_new_trades_active ? "not-allowed" : "pointer",
                    background: selectedContract.option_type === "CE" ? "linear-gradient(135deg, #10B981, #059669)" : "linear-gradient(135deg, #EF4444, #B91C1C)",
                    color: "#FFFFFF",
                    border: "none",
                    boxShadow: "0 4px 12px rgba(16, 185, 129, 0.25)"
                  }}
                >
                  {executingOrder ? "Executing..." : `Buy ${selectedContract.option_type} (${selectedContract.lot_size * 2} qty) →`}
                </button>

                <button
                  onClick={() => handlePlaceOrder("SELL")}
                  disabled={executingOrder}
                  style={{
                    padding: "10px 18px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    background: "#1E293B",
                    color: "#94A3B8",
                    border: "1px solid #334155"
                  }}
                >
                  Close Position
                </button>
              </div>
            </div>
          ) : (
            <div style={{ padding: "30px 0", textAlign: "center", color: "#64748B", fontSize: 12 }}>
              Loading optimal index option contract...
            </div>
          )}
        </div>
      </div>

      {/* 4. ACTIVE OPTION CHAIN MATRIX */}
      <div className="glass-card" style={{ padding: 20, borderRadius: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <h2 style={{ fontSize: 15, fontWeight: 800, margin: 0, color: "#F8FAFC" }}>
              Active {underlying} Option Chain (Near-Term Expiry)
            </h2>
            <span style={{ fontSize: 11, color: "#94A3B8" }}>
              Real-time strikes, Greek Deltas, Implied Volatilities, and execution spreads.
            </span>
          </div>

          <button
            onClick={loadMarketData}
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
            {loading ? "Refreshing..." : "↻ Refresh Chain"}
          </button>
        </div>

        {optionChain?.chain && optionChain.chain.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
              <thead>
                <tr style={{ background: "#0B0D0F", color: "#64748B", borderBottom: "1px solid #20252A" }}>
                  <th style={{ padding: "8px 10px", color: "#22C55E" }}>CALL LTP</th>
                  <th style={{ padding: "8px 10px", color: "#22C55E" }}>DELTA</th>
                  <th style={{ padding: "8px 10px", color: "#22C55E" }}>IV %</th>
                  <th style={{ padding: "8px 10px", color: "#22C55E" }}>SPREAD</th>
                  <th style={{ padding: "8px 10px", textAlign: "center", color: "#F8FAFC", background: "#111417" }}>STRIKE</th>
                  <th style={{ padding: "8px 10px", color: "#EF4444" }}>PUT LTP</th>
                  <th style={{ padding: "8px 10px", color: "#EF4444" }}>DELTA</th>
                  <th style={{ padding: "8px 10px", color: "#EF4444" }}>IV %</th>
                  <th style={{ padding: "8px 10px", color: "#EF4444" }}>SPREAD</th>
                  <th style={{ padding: "8px 10px", textAlign: "center" }}>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {optionChain.chain.map((row: any) => {
                  const isAtm = row.is_atm;
                  return (
                    <tr
                      key={row.strike}
                      style={{
                        borderBottom: "1px solid #1E242B",
                        background: isAtm ? "rgba(56, 189, 248, 0.08)" : "transparent"
                      }}
                    >
                      {/* CE Data */}
                      <td style={{ padding: "8px 10px", fontWeight: 700, color: "#22C55E" }} className="num">
                        ₹{row.ce.ltp}
                      </td>
                      <td style={{ padding: "8px 10px", color: "#94A3B8" }} className="num">{row.ce.delta}</td>
                      <td style={{ padding: "8px 10px", color: "#94A3B8" }} className="num">{row.ce.iv}%</td>
                      <td style={{ padding: "8px 10px", color: row.ce.spread_pct > 1.5 ? "#F59E0B" : "#64748B" }} className="num">
                        {row.ce.spread_pct}%
                      </td>

                      {/* STRIKE */}
                      <td style={{
                        padding: "8px 14px",
                        textAlign: "center",
                        fontWeight: 900,
                        color: isAtm ? "#38BDF8" : "#F8FAFC",
                        background: isAtm ? "rgba(56, 189, 248, 0.15)" : "#0B0D0F",
                        borderLeft: "1px solid #20252A",
                        borderRight: "1px solid #20252A"
                      }} className="num">
                        {row.strike} {isAtm && <span style={{ fontSize: 9, color: "#38BDF8" }}>(ATM)</span>}
                      </td>

                      {/* PE Data */}
                      <td style={{ padding: "8px 10px", fontWeight: 700, color: "#EF4444" }} className="num">
                        ₹{row.pe.ltp}
                      </td>
                      <td style={{ padding: "8px 10px", color: "#94A3B8" }} className="num">{row.pe.delta}</td>
                      <td style={{ padding: "8px 10px", color: "#94A3B8" }} className="num">{row.pe.iv}%</td>
                      <td style={{ padding: "8px 10px", color: row.pe.spread_pct > 1.5 ? "#F59E0B" : "#64748B" }} className="num">
                        {row.pe.spread_pct}%
                      </td>

                      {/* Select Action */}
                      <td style={{ padding: "8px 10px", textAlign: "center" }}>
                        <div style={{ display: "flex", gap: 4, justifyContent: "center" }}>
                          <button
                            onClick={() => setSelectedContract(row.ce)}
                            style={{
                              padding: "3px 6px",
                              borderRadius: 4,
                              background: "rgba(34, 197, 94, 0.15)",
                              border: "1px solid rgba(34, 197, 94, 0.35)",
                              color: "#22C55E",
                              fontSize: 10,
                              fontWeight: 700,
                              cursor: "pointer"
                            }}
                          >
                            CE
                          </button>
                          <button
                            onClick={() => setSelectedContract(row.pe)}
                            style={{
                              padding: "3px 6px",
                              borderRadius: 4,
                              background: "rgba(239, 68, 68, 0.15)",
                              border: "1px solid rgba(239, 68, 68, 0.35)",
                              color: "#EF4444",
                              fontSize: 10,
                              fontWeight: 700,
                              cursor: "pointer"
                            }}
                          >
                            PE
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: "center", padding: "40px 0", color: "#64748B", fontSize: 12 }}>
            Loading live option strikes...
          </div>
        )}
      </div>
    </div>
  );
}
