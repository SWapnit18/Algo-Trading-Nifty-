import React, { useState, useEffect, useRef } from "react";

interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface KronosForecast {
  start_price: number;
  end_predicted_price: number;
  expected_return_pct: number;
  bullish_probability: number;
  bearish_probability: number;
  predicted_volatility_pct: number;
  atr: number;
  horizon_bars: number;
  predicted_candles: Candle[];
  upper_band_85: number[];
  lower_band_15: number[];
}

interface KronosSignal {
  symbol: string;
  direction: "BUY" | "SELL" | "HOLD";
  confidence: number;
  entry_price: number;
  stop_loss: number;
  target: number;
  risk_reward: number;
  expected_return_pct: number;
  reason: string;
  timestamp: string;
}

interface KronosForecastResponse {
  symbol: string;
  timeframe: string;
  historical_candles: Candle[];
  forecast: KronosForecast;
  signal: KronosSignal;
  model_meta: {
    name: string;
    inference_time_ms: number;
  };
}

interface BacktestTrade {
  entry_time: string;
  exit_time: string;
  symbol: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  confidence: number;
}

interface BacktestResult {
  symbol: string;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  benchmark_return_pct: number;
  alpha: number;
  total_trades: number;
  win_rate: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  equity_curve: { time: string; equity: number; benchmark: number }[];
  trades: BacktestTrade[];
}

interface ScreenerItem {
  symbol: string;
  current_price: number;
  predicted_price: number;
  expected_return_pct: number;
  bullish_probability: number;
  direction: "BUY" | "SELL" | "HOLD";
  confidence: number;
  risk_reward: number;
  target: number;
  stop_loss: number;
  reason: string;
}

interface KronosViewProps {
  onSelectSymbol?: (symbol: string) => void;
  onOpenOrder?: (symbol: string, side: "BUY" | "SELL") => void;
  showToast?: (msg: string, type?: "success" | "error" | "info") => void;
}

const POPULAR_NSE_STOCKS = [
  "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
  "SBIN", "BHARTIARTL", "ITC", "LT", "TATAMOTORS",
  "BAJFINANCE", "SUNPHARMA", "MARUTI", "KOTAKBANK", "AXISBANK", "WIPRO"
];

export function KronosView({ onSelectSymbol, onOpenOrder, showToast }: KronosViewProps) {
  const [activeTab, setActiveTab] = useState<"forecast" | "screener" | "backtest">("forecast");
  const [selectedSymbol, setSelectedSymbol] = useState("RELIANCE");
  const [timeframe, setTimeframe] = useState("15m");
  const [horizon, setHorizon] = useState(5);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [forecastData, setForecastData] = useState<KronosForecastResponse | null>(null);

  // Screener state
  const [loadingScreener, setLoadingScreener] = useState(false);
  const [screenerList, setScreenerList] = useState<ScreenerItem[]>([]);

  // Backtest state
  const [loadingBacktest, setLoadingBacktest] = useState(false);
  const [backtestData, setBacktestData] = useState<BacktestResult | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Fetch forecast
  const fetchForecast = async (sym: string = selectedSymbol, tf: string = timeframe, hor: number = horizon) => {
    setLoadingForecast(true);
    try {
      const res = await fetch(`/api/kronos/forecast?symbol=${encodeURIComponent(sym)}&timeframe=${tf}&horizon=${hor}&simulations=20&temperature=0.8`);
      if (!res.ok) throw new Error("Failed to load trajectory forecast");
      const data: KronosForecastResponse = await res.json();
      setForecastData(data);
    } catch (err: any) {
      console.error(err);
      if (showToast) showToast(err.message || "Failed to load forecast", "error");
    } finally {
      setLoadingForecast(false);
    }
  };

  // Run screener
  const fetchScreener = async () => {
    setLoadingScreener(true);
    try {
      const res = await fetch(`/api/kronos/screener?timeframe=${timeframe}`);
      if (!res.ok) throw new Error("Failed to scan market opportunities");
      const data = await res.json();
      setScreenerList(data.rankings || []);
      if (showToast) showToast(`Scanned ${data.scanned_count} NSE leaders`, "success");
    } catch (err: any) {
      console.error(err);
      if (showToast) showToast(err.message || "Screener scan failed", "error");
    } finally {
      setLoadingScreener(false);
    }
  };

  // Run backtest
  const runBacktest = async (sym: string = selectedSymbol) => {
    setLoadingBacktest(true);
    try {
      const res = await fetch("/api/kronos/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: sym,
          timeframe,
          initial_capital: 100000,
          risk_per_trade_pct: 1.0
        })
      });
      if (!res.ok) throw new Error("Backtest simulation failed");
      const data: BacktestResult = await res.json();
      setBacktestData(data);
      if (showToast) showToast(`Backtest completed for ${sym}`, "success");
    } catch (err: any) {
      console.error(err);
      if (showToast) showToast(err.message || "Backtest failed", "error");
    } finally {
      setLoadingBacktest(false);
    }
  };

  useEffect(() => {
    fetchForecast(selectedSymbol, timeframe, horizon);
  }, [selectedSymbol, timeframe, horizon]);

  useEffect(() => {
    if (activeTab === "screener" && screenerList.length === 0) {
      fetchScreener();
    }
    if (activeTab === "backtest" && !backtestData) {
      runBacktest(selectedSymbol);
    }
  }, [activeTab]);

  // Redraw canvas on window resize
  const [resizeKey, setResizeKey] = useState(0);
  useEffect(() => {
    const handleResize = () => setResizeKey(k => k + 1);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Draw Minimalist Candlestick & Trajectory Canvas
  useEffect(() => {
    if (!forecastData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;

    // Clean background
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, w, h);

    const histCandles = forecastData.historical_candles || [];
    const predCandles = forecastData.forecast?.predicted_candles || [];
    const allCandles = [...histCandles, ...predCandles];
    const totalBars = allCandles.length;
    if (totalBars === 0) return;

    const upperBands = forecastData.forecast?.upper_band_85 || [];
    const lowerBands = forecastData.forecast?.lower_band_15 || [];

    let minP = Math.min(
      ...allCandles.map(c => c.low),
      ...(lowerBands.length ? lowerBands : [999999])
    );
    let maxP = Math.max(
      ...allCandles.map(c => c.high),
      ...(upperBands.length ? upperBands : [-999999])
    );
    const pad = (maxP - minP) * 0.12 || 1.0;
    minP -= pad;
    maxP += pad;

    const priceToY = (p: number) => h - ((p - minP) / (maxP - minP)) * (h - 40) - 20;

    // Draw Subtle Grid Lines
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.fillStyle = "#6e7681";
    ctx.font = "11px Inter, system-ui, sans-serif";
    ctx.textAlign = "right";

    const steps = 5;
    for (let i = 0; i <= steps; i++) {
      const p = minP + ((maxP - minP) / steps) * i;
      const y = priceToY(p);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w - 70, y);
      ctx.stroke();
      ctx.fillText(`₹${p.toFixed(1)}`, w - 10, y + 4);
    }

    const chartW = w - 80;
    const barSpacing = chartW / totalBars;
    const candleWidth = Math.max(3, barSpacing * 0.65);

    // Draw Uncertainty Cone for Predicted Candles
    if (predCandles.length > 0 && upperBands.length > 0 && lowerBands.length > 0) {
      const startIndex = histCandles.length;
      ctx.beginPath();
      for (let i = 0; i < predCandles.length; i++) {
        const x = (startIndex + i) * barSpacing + barSpacing / 2;
        const yTop = priceToY(upperBands[i] || predCandles[i].high);
        if (i === 0) ctx.moveTo(x, yTop);
        else ctx.lineTo(x, yTop);
      }
      for (let i = predCandles.length - 1; i >= 0; i--) {
        const x = (startIndex + i) * barSpacing + barSpacing / 2;
        const yBottom = priceToY(lowerBands[i] || predCandles[i].low);
        ctx.lineTo(x, yBottom);
      }
      ctx.closePath();
      ctx.fillStyle = "rgba(0, 242, 254, 0.08)";
      ctx.fill();
      ctx.strokeStyle = "rgba(0, 242, 254, 0.25)";
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Draw Forecast Transition Divider Line
    if (histCandles.length > 0 && predCandles.length > 0) {
      const divX = histCandles.length * barSpacing;
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(0, 242, 254, 0.4)";
      ctx.moveTo(divX, 15);
      ctx.lineTo(divX, h - 25);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "#00f2fe";
      ctx.textAlign = "left";
      ctx.font = "bold 10px Inter, system-ui, sans-serif";
      ctx.fillText("PREDICTION HORIZON →", divX + 6, 25);
    }

    // Draw Target and Stop Loss Levels
    if (forecastData.signal) {
      const sig = forecastData.signal;
      if (sig.target > 0) {
        const tgtY = priceToY(sig.target);
        ctx.beginPath();
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = "rgba(16, 185, 129, 0.7)";
        ctx.moveTo(0, tgtY);
        ctx.lineTo(chartW, tgtY);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#10b981";
        ctx.textAlign = "left";
        ctx.font = "10px Inter, sans-serif";
        ctx.fillText(`Target: ₹${sig.target.toFixed(1)}`, 12, tgtY - 4);
      }

      if (sig.stop_loss > 0) {
        const slY = priceToY(sig.stop_loss);
        ctx.beginPath();
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = "rgba(244, 63, 94, 0.7)";
        ctx.moveTo(0, slY);
        ctx.lineTo(chartW, slY);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#f43f5e";
        ctx.textAlign = "left";
        ctx.font = "10px Inter, sans-serif";
        ctx.fillText(`Stop: ₹${sig.stop_loss.toFixed(1)}`, 12, slY - 4);
      }
    }

    // Render Candlesticks
    allCandles.forEach((c, idx) => {
      const isPred = idx >= histCandles.length;
      const xCenter = idx * barSpacing + barSpacing / 2;
      const yOpen = priceToY(c.open);
      const yClose = priceToY(c.close);
      const yHigh = priceToY(c.high);
      const yLow = priceToY(c.low);
      const isBull = c.close >= c.open;

      // Color selection
      let strokeColor = isBull ? "#10b981" : "#f43f5e";
      let fillColor = isBull ? "#10b981" : "#f43f5e";

      if (isPred) {
        strokeColor = isBull ? "#00f2fe" : "#ec4899";
        fillColor = isBull ? "rgba(0, 242, 254, 0.6)" : "rgba(236, 72, 153, 0.6)";
      }

      // Wick
      ctx.beginPath();
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1.2;
      ctx.moveTo(xCenter, yHigh);
      ctx.lineTo(xCenter, yLow);
      ctx.stroke();

      // Body
      const topY = Math.min(yOpen, yClose);
      const bodyH = Math.max(2, Math.abs(yClose - yOpen));
      ctx.fillStyle = fillColor;
      ctx.fillRect(xCenter - candleWidth / 2, topY, candleWidth, bodyH);

      if (isPred) {
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 1;
        ctx.strokeRect(xCenter - candleWidth / 2, topY, candleWidth, bodyH);
      }
    });

  }, [forecastData, resizeKey]);

  return (
    <div style={{ padding: "18px 24px", color: "#f0f6fc", maxWidth: "1500px", margin: "0 auto" }}>
      
      {/* MINIMALIST HEADER & CONTROLS */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "20px",
          paddingBottom: "18px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)"
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h1 style={{ margin: 0, fontSize: "20px", fontWeight: 700, color: "#fff", letterSpacing: "-0.3px" }}>
              AI Predictive Forecast
            </h1>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 600,
                color: "#10b981",
                background: "rgba(16, 185, 129, 0.12)",
                padding: "2px 8px",
                borderRadius: "12px",
                border: "1px solid rgba(16, 185, 129, 0.25)"
              }}
            >
              ● Probabilistic Trajectory
            </span>
          </div>
          <p style={{ margin: "4px 0 0", fontSize: "12.5px", color: "#8b949e" }}>
            Multi-horizon K-line projection and algorithmic signal ranking across NSE equities.
          </p>
        </div>

        {/* CONTROLS */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {/* Symbol Select */}
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            style={{
              background: "#161b22",
              color: "#fff",
              border: "1px solid #30363d",
              padding: "7px 14px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer"
            }}
          >
            {POPULAR_NSE_STOCKS.map((s) => (
              <option key={s} value={s}>
                {s} (NSE)
              </option>
            ))}
          </select>

          {/* Timeframe Pills */}
          <div style={{ display: "flex", background: "#161b22", borderRadius: "8px", border: "1px solid #30363d", padding: "2px" }}>
            {["5m", "15m", "1h", "1D"].map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                style={{
                  background: timeframe === tf ? "#21262d" : "transparent",
                  color: timeframe === tf ? "#00f2fe" : "#8b949e",
                  border: "none",
                  padding: "5px 11px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s ease"
                }}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Horizon Pills */}
          <div style={{ display: "flex", background: "#161b22", borderRadius: "8px", border: "1px solid #30363d", padding: "2px" }}>
            {[3, 5, 10].map((hVal) => (
              <button
                key={hVal}
                onClick={() => setHorizon(hVal)}
                style={{
                  background: horizon === hVal ? "#21262d" : "transparent",
                  color: horizon === hVal ? "#00f2fe" : "#8b949e",
                  border: "none",
                  padding: "5px 10px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s ease"
                }}
              >
                {hVal} Bars
              </button>
            ))}
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => fetchForecast()}
            disabled={loadingForecast}
            style={{
              background: "linear-gradient(135deg, #00f2fe, #4facfe)",
              color: "#050505",
              border: "none",
              padding: "7px 16px",
              borderRadius: "8px",
              fontWeight: 700,
              fontSize: "12.5px",
              cursor: loadingForecast ? "not-allowed" : "pointer",
              opacity: loadingForecast ? 0.7 : 1,
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            {loadingForecast ? (
              <>
                <span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>⏳</span>
                <span>Calculating...</span>
              </>
            ) : (
              <>
                <span>⚡</span>
                <span>Run Forecast</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* MINIMALIST TABS */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        <button
          onClick={() => setActiveTab("forecast")}
          style={{
            background: activeTab === "forecast" ? "#161b22" : "transparent",
            color: activeTab === "forecast" ? "#fff" : "#8b949e",
            border: activeTab === "forecast" ? "1px solid #30363d" : "1px solid transparent",
            padding: "6px 16px",
            borderRadius: "6px",
            fontWeight: 600,
            fontSize: "13px",
            cursor: "pointer"
          }}
        >
          📈 Trajectory Forecast
        </button>
        <button
          onClick={() => setActiveTab("screener")}
          style={{
            background: activeTab === "screener" ? "#161b22" : "transparent",
            color: activeTab === "screener" ? "#fff" : "#8b949e",
            border: activeTab === "screener" ? "1px solid #30363d" : "1px solid transparent",
            padding: "6px 16px",
            borderRadius: "6px",
            fontWeight: 600,
            fontSize: "13px",
            cursor: "pointer"
          }}
        >
          🎯 Top AI Signals (Screener)
        </button>
        <button
          onClick={() => setActiveTab("backtest")}
          style={{
            background: activeTab === "backtest" ? "#161b22" : "transparent",
            color: activeTab === "backtest" ? "#fff" : "#8b949e",
            border: activeTab === "backtest" ? "1px solid #30363d" : "1px solid transparent",
            padding: "6px 16px",
            borderRadius: "6px",
            fontWeight: 600,
            fontSize: "13px",
            cursor: "pointer"
          }}
        >
          📊 Walk-Forward Backtest
        </button>
      </div>

      {/* 1. FORECAST TAB */}
      {activeTab === "forecast" && (
        <div>
          {/* METRIC STRIP */}
          {forecastData && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "12px",
                marginBottom: "16px"
              }}
            >
              {/* Signal Badge */}
              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600, textTransform: "uppercase" }}>AI Signal</div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                  <span
                    style={{
                      fontSize: "18px",
                      fontWeight: 800,
                      color: forecastData.signal.direction === "BUY" ? "#10b981" : forecastData.signal.direction === "SELL" ? "#f43f5e" : "#8b949e"
                    }}
                  >
                    {forecastData.signal.direction}
                  </span>
                  <span style={{ fontSize: "11px", color: "#8b949e" }}>
                    ({(forecastData.signal.confidence > 1 ? forecastData.signal.confidence : forecastData.signal.confidence * 100).toFixed(0)}% conf)
                  </span>
                </div>
              </div>

              {/* Current Price */}
              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600, textTransform: "uppercase" }}>Current Price</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#fff", marginTop: "4px" }}>
                  ₹{forecastData.forecast.start_price.toFixed(2)}
                </div>
              </div>

              {/* Projected Target */}
              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600, textTransform: "uppercase" }}>Target Price</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#10b981", marginTop: "4px" }}>
                  ₹{forecastData.signal.target.toFixed(2)}
                </div>
              </div>

              {/* Stop Loss */}
              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600, textTransform: "uppercase" }}>Stop Loss</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#f43f5e", marginTop: "4px" }}>
                  ₹{forecastData.signal.stop_loss.toFixed(2)}
                </div>
              </div>

              {/* Expected Alpha */}
              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600, textTransform: "uppercase" }}>Expected Return</div>
                <div
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    color: forecastData.forecast.expected_return_pct >= 0 ? "#10b981" : "#f43f5e",
                    marginTop: "4px"
                  }}
                >
                  {forecastData.forecast.expected_return_pct >= 0 ? "+" : ""}{forecastData.forecast.expected_return_pct}%
                </div>
              </div>

              {/* Quick Trade Button */}
              {onOpenOrder && (
                <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                  <button
                    onClick={() => onOpenOrder(selectedSymbol, forecastData.signal.direction === "SELL" ? "SELL" : "BUY")}
                    style={{
                      background: forecastData.signal.direction === "SELL" ? "#f43f5e" : "#10b981",
                      color: "#fff",
                      border: "none",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      fontWeight: 700,
                      fontSize: "12px",
                      cursor: "pointer"
                    }}
                  >
                    Quick {forecastData.signal.direction === "SELL" ? "Sell" : "Buy"} Order
                  </button>
                </div>
              )}
            </div>
          )}

          {/* CHART CONTAINER */}
          <div
            style={{
              background: "#0d1117",
              border: "1px solid #30363d",
              borderRadius: "12px",
              padding: "16px 20px",
              position: "relative"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <div style={{ fontSize: "13px", fontWeight: 600, color: "#c9d1d9" }}>
                {selectedSymbol} • {timeframe} Trajectory (+{horizon} Bars Forward)
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: "11.5px", color: "#8b949e" }}>
                <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "10px", height: "10px", background: "#10b981", borderRadius: "2px" }} /> Historical
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "10px", height: "10px", background: "#00f2fe", borderRadius: "2px" }} /> AI Prediction
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "10px", height: "6px", background: "rgba(0, 242, 254, 0.25)", borderRadius: "2px" }} /> 85% Cone
                </span>
              </div>
            </div>

            <div style={{ width: "100%", height: "420px", position: "relative" }}>
              <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
            </div>

            {/* Signal Reasoning Note */}
            {forecastData?.signal?.reason && (
              <div
                style={{
                  marginTop: "12px",
                  padding: "8px 14px",
                  background: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "6px",
                  fontSize: "12px",
                  color: "#8b949e",
                  borderLeft: "3px solid #00f2fe"
                }}
              >
                <strong style={{ color: "#c9d1d9" }}>Model Analysis:</strong> {forecastData.signal.reason}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. SCREENER TAB */}
      {activeTab === "screener" && (
        <div style={{ background: "#0d1117", border: "1px solid #30363d", borderRadius: "12px", padding: "16px 20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
            <div>
              <h2 style={{ fontSize: "15px", fontWeight: 700, margin: 0, color: "#fff" }}>
                Top AI Opportunities ({timeframe})
              </h2>
              <div style={{ fontSize: "12px", color: "#8b949e", marginTop: "2px" }}>
                Ranked by expected percentage alpha
              </div>
            </div>
            <button
              onClick={fetchScreener}
              disabled={loadingScreener}
              style={{
                background: "#21262d",
                color: "#c9d1d9",
                border: "1px solid #30363d",
                padding: "6px 14px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer"
              }}
            >
              {loadingScreener ? "Scanning..." : "↻ Refresh Screener"}
            </button>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #30363d", color: "#8b949e", textAlign: "left" }}>
                  <th style={{ padding: "10px 12px" }}>Symbol</th>
                  <th style={{ padding: "10px 12px" }}>LTP</th>
                  <th style={{ padding: "10px 12px" }}>Target</th>
                  <th style={{ padding: "10px 12px" }}>Expected Return</th>
                  <th style={{ padding: "10px 12px" }}>Signal</th>
                  <th style={{ padding: "10px 12px" }}>Confidence</th>
                  <th style={{ padding: "10px 12px", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {screenerList.map((item) => (
                  <tr
                    key={item.symbol}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      cursor: "pointer"
                    }}
                    onClick={() => {
                      setSelectedSymbol(item.symbol);
                      setActiveTab("forecast");
                    }}
                  >
                    <td style={{ padding: "12px", fontWeight: 700, color: "#fff" }}>{item.symbol}</td>
                    <td style={{ padding: "12px" }}>₹{item.current_price.toFixed(2)}</td>
                    <td style={{ padding: "12px", color: "#10b981" }}>₹{item.target.toFixed(2)}</td>
                    <td style={{ padding: "12px", fontWeight: 700, color: item.expected_return_pct >= 0 ? "#10b981" : "#f43f5e" }}>
                      {item.expected_return_pct >= 0 ? "+" : ""}{item.expected_return_pct}%
                    </td>
                    <td style={{ padding: "12px" }}>
                      <span
                        style={{
                          padding: "2px 8px",
                          borderRadius: "4px",
                          fontWeight: 700,
                          fontSize: "11px",
                          background: item.direction === "BUY" ? "rgba(16, 185, 129, 0.15)" : item.direction === "SELL" ? "rgba(244, 63, 94, 0.15)" : "rgba(255, 255, 255, 0.05)",
                          color: item.direction === "BUY" ? "#10b981" : item.direction === "SELL" ? "#f43f5e" : "#8b949e"
                        }}
                      >
                        {item.direction}
                      </span>
                    </td>
                    <td style={{ padding: "12px", fontFamily: "JetBrains Mono, monospace" }}>
                      {(item.confidence > 1 ? item.confidence : item.confidence * 100).toFixed(0)}%
                    </td>
                    <td style={{ padding: "12px", textAlign: "right" }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSymbol(item.symbol);
                          setActiveTab("forecast");
                        }}
                        style={{
                          background: "#21262d",
                          color: "#00f2fe",
                          border: "1px solid rgba(0, 242, 254, 0.3)",
                          padding: "4px 10px",
                          borderRadius: "6px",
                          fontSize: "11.5px",
                          fontWeight: 600,
                          cursor: "pointer"
                        }}
                      >
                        View Chart
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. BACKTEST TAB */}
      {activeTab === "backtest" && (
        <div style={{ background: "#0d1117", border: "1px solid #30363d", borderRadius: "12px", padding: "16px 20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div>
              <h2 style={{ fontSize: "15px", fontWeight: 700, margin: 0, color: "#fff" }}>
                Walk-Forward Strategy Edge: {selectedSymbol}
              </h2>
              <div style={{ fontSize: "12px", color: "#8b949e", marginTop: "2px" }}>
                Simulation based on probabilistic signal verification
              </div>
            </div>
            <button
              onClick={() => runBacktest(selectedSymbol)}
              disabled={loadingBacktest}
              style={{
                background: "#21262d",
                color: "#c9d1d9",
                border: "1px solid #30363d",
                padding: "6px 14px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer"
              }}
            >
              {loadingBacktest ? "Running..." : "↻ Rerun Simulation"}
            </button>
          </div>

          {backtestData && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "12px",
                marginBottom: "20px"
              }}
            >
              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600 }}>Total Return</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: backtestData.total_return_pct >= 0 ? "#10b981" : "#f43f5e", marginTop: "4px" }}>
                  {backtestData.total_return_pct >= 0 ? "+" : ""}{backtestData.total_return_pct}%
                </div>
              </div>

              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600 }}>Win Rate</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#00f2fe", marginTop: "4px" }}>
                  {backtestData.win_rate}%
                </div>
              </div>

              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600 }}>Total Trades</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#fff", marginTop: "4px" }}>
                  {backtestData.total_trades}
                </div>
              </div>

              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600 }}>Sharpe Ratio</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#fff", marginTop: "4px" }}>
                  {backtestData.sharpe_ratio}
                </div>
              </div>

              <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: "10px", padding: "12px 16px" }}>
                <div style={{ fontSize: "11px", color: "#8b949e", fontWeight: 600 }}>Max Drawdown</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#f43f5e", marginTop: "4px" }}>
                  {backtestData.max_drawdown_pct}%
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
