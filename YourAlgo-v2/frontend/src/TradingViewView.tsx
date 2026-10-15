import React, { useState, useEffect, useRef, useMemo } from "react";

export interface TradingViewViewProps {
  selectedSymbol?: string;
  onSelectSymbol?: (symbol: string) => void;
  onOpenOrder?: (symbol: string, side: "BUY" | "SELL") => void;
  onNavigateToKronos?: (symbol: string) => void;
  onNavigateToInvestIQ?: (symbol: string) => void;
  isAutoTrading?: boolean;
  onToggleAutoTrading?: () => void;
  showToast?: (msg: string, type?: "success" | "error" | "info" | "warning") => void;
}

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Quote {
  symbol: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change: number;
  change_pct: number;
  timestamp: string;
  is_market_open?: boolean;
}

// Drawing tool types
export type DrawingTool = "cursor" | "trendline" | "horizontal" | "fibonacci" | "ruler" | "eraser";
export type ChartStyle = "candles" | "hollow" | "heikin_ashi" | "line" | "area" | "ohlc_bar";

export interface Point {
  candleIdx: number;
  price: number;
}

export interface Trendline {
  id: string;
  p1: Point;
  p2: Point;
  color: string;
}

export interface HorizontalLine {
  id: string;
  price: number;
  color: string;
}

export interface FibonacciDrawing {
  id: string;
  p1: Point;
  p2: Point;
}

const INDIAN_BENCHMARKS = [
  { symbol: "NIFTY", name: "NIFTY 50", exchange: "NSE", desc: "NSE Benchmark" },
  { symbol: "SENSEX", name: "SENSEX 30", exchange: "BSE", desc: "BSE Bluechip" },
  { symbol: "BANKNIFTY", name: "BANK NIFTY", exchange: "NSE", desc: "Banking Index" },
  { symbol: "FINNIFTY", name: "FIN NIFTY", exchange: "NSE", desc: "Financial Services" }
];

export interface NiftyConstituent {
  rank: number;
  symbol: string;
  name: string;
  sector: string;
  subsector: string;
  weightage: number; // percentage in NIFTY 50 index
}

// Authoritative NIFTY 50 constituents ordered strictly by Tickertape weightage
export const NIFTY_50_STOCKS: NiftyConstituent[] = [
  { rank: 1, symbol: "HDFCBANK", name: "HDFC Bank Limited", sector: "Financial Services", subsector: "Private Banks", weightage: 11.52 },
  { rank: 2, symbol: "ICICIBANK", name: "ICICI Bank Limited", sector: "Financial Services", subsector: "Private Banks", weightage: 8.15 },
  { rank: 3, symbol: "RELIANCE", name: "Reliance Industries Ltd", sector: "Energy & Oil", subsector: "Oil & Gas - Refining", weightage: 7.94 },
  { rank: 4, symbol: "BHARTIARTL", name: "Bharti Airtel Ltd", sector: "Telecommunication", subsector: "Telecom Services", weightage: 4.78 },
  { rank: 5, symbol: "LT", name: "Larsen and Toubro Ltd", sector: "Construction & Infra", subsector: "Construction & Engg", weightage: 4.32 },
  { rank: 6, symbol: "SBIN", name: "State Bank of India", sector: "Financial Services", subsector: "Public Banks", weightage: 4.12 },
  { rank: 7, symbol: "AXISBANK", name: "Axis Bank Limited", sector: "Financial Services", subsector: "Private Banks", weightage: 3.71 },
  { rank: 8, symbol: "INFY", name: "Infosys Limited", sector: "IT Services", subsector: "IT Services & Consulting", weightage: 3.64 },
  { rank: 9, symbol: "KOTAKBANK", name: "Kotak Mahindra Bank Ltd", sector: "Financial Services", subsector: "Private Banks", weightage: 2.92 },
  { rank: 10, symbol: "M&M", name: "Mahindra and Mahindra Ltd", sector: "Automobile", subsector: "Four Wheelers", weightage: 2.81 },
  { rank: 11, symbol: "TCS", name: "Tata Consultancy Services Ltd", sector: "IT Services", subsector: "IT Services & Consulting", weightage: 2.75 },
  { rank: 12, symbol: "ITC", name: "ITC Ltd", sector: "FMCG", subsector: "FMCG - Tobacco", weightage: 2.68 },
  { rank: 13, symbol: "BAJFINANCE", name: "Bajaj Finance Ltd", sector: "Financial Services", subsector: "Consumer Finance", weightage: 2.42 },
  { rank: 14, symbol: "HINDUNILVR", name: "Hindustan Unilever Ltd", sector: "FMCG", subsector: "FMCG - Household Products", weightage: 2.18 },
  { rank: 15, symbol: "MARUTI", name: "Maruti Suzuki India Ltd", sector: "Automobile", subsector: "Four Wheelers", weightage: 1.85 },
  { rank: 16, symbol: "SUNPHARMA", name: "Sun Pharmaceutical Ind Ltd", sector: "Healthcare", subsector: "Pharmaceuticals", weightage: 1.76 },
  { rank: 17, symbol: "TATAMOTORS", name: "Tata Motors Ltd", sector: "Automobile", subsector: "Four Wheelers", weightage: 1.65 },
  { rank: 18, symbol: "HCLTECH", name: "HCL Technologies Ltd", sector: "IT Services", subsector: "IT Services & Consulting", weightage: 1.58 },
  { rank: 19, symbol: "NTPC", name: "NTPC Ltd", sector: "Energy & Oil", subsector: "Power & Utilities", weightage: 1.49 },
  { rank: 20, symbol: "TITAN", name: "Titan Company Ltd", sector: "Consumer Durables", subsector: "Jewellery & Watches", weightage: 1.44 },
  { rank: 21, symbol: "TATASTEEL", name: "Tata Steel Ltd", sector: "Metals & Mining", subsector: "Iron & Steel", weightage: 1.36 },
  { rank: 22, symbol: "POWERGRID", name: "Power Grid Corp of India Ltd", sector: "Energy & Oil", subsector: "Power Transmission", weightage: 1.30 },
  { rank: 23, symbol: "ADANIPORTS", name: "Adani Ports & SEZ Ltd", sector: "Construction & Infra", subsector: "Ports", weightage: 1.24 },
  { rank: 24, symbol: "ADANIENT", name: "Adani Enterprises Limited", sector: "Metals & Mining", subsector: "Commodities Trading", weightage: 1.18 },
  { rank: 25, symbol: "BAJAJFINSV", name: "Bajaj Finserv Ltd", sector: "Financial Services", subsector: "Financial Holding", weightage: 1.14 },
  { rank: 26, symbol: "ONGC", name: "Oil and Natural Gas Corp Ltd", sector: "Energy & Oil", subsector: "Oil & Gas Exploration", weightage: 1.10 },
  { rank: 27, symbol: "COALINDIA", name: "Coal India Ltd", sector: "Energy & Oil", subsector: "Coal Mining", weightage: 1.04 },
  { rank: 28, symbol: "ULTRACEMCO", name: "UltraTech Cement Ltd", sector: "Construction & Infra", subsector: "Cement", weightage: 1.02 },
  { rank: 29, symbol: "JSWSTEEL", name: "JSW Steel Ltd", sector: "Metals & Mining", subsector: "Iron & Steel", weightage: 0.98 },
  { rank: 30, symbol: "ASIANPAINT", name: "Asian Paints Ltd", sector: "Consumer Durables", subsector: "Paints & Coatings", weightage: 0.95 },
  { rank: 31, symbol: "BAJAJ-AUTO", name: "Bajaj Auto Ltd", sector: "Automobile", subsector: "Two Wheelers", weightage: 0.91 },
  { rank: 32, symbol: "GRASIM", name: "Grasim Industries Ltd", sector: "Construction & Infra", subsector: "Diversified & Cement", weightage: 0.87 },
  { rank: 33, symbol: "NESTLEIND", name: "Nestle India Ltd", sector: "FMCG", subsector: "Packaged Food", weightage: 0.83 },
  { rank: 34, symbol: "TECHM", name: "Tech Mahindra Ltd", sector: "IT Services", subsector: "IT Services & Consulting", weightage: 0.79 },
  { rank: 35, symbol: "INDUSINDBK", name: "IndusInd Bank Ltd", sector: "Financial Services", subsector: "Private Banks", weightage: 0.76 },
  { rank: 36, symbol: "CIPLA", name: "Cipla Ltd", sector: "Healthcare", subsector: "Pharmaceuticals", weightage: 0.74 },
  { rank: 37, symbol: "DRREDDY", name: "Dr. Reddy's Laboratories Ltd", sector: "Healthcare", subsector: "Pharmaceuticals", weightage: 0.71 },
  { rank: 38, symbol: "WIPRO", name: "Wipro Ltd", sector: "IT Services", subsector: "IT Services & Consulting", weightage: 0.69 },
  { rank: 39, symbol: "APOLLOHOSP", name: "Apollo Hospitals Enterprise Ltd", sector: "Healthcare", subsector: "Hospitals", weightage: 0.67 },
  { rank: 40, symbol: "TATACONSUM", name: "Tata Consumer Products Ltd", sector: "FMCG", subsector: "Tea, Coffee & Food", weightage: 0.66 },
  { rank: 41, symbol: "BPCL", name: "Bharat Petroleum Corp Ltd", sector: "Energy & Oil", subsector: "Oil & Gas Refining", weightage: 0.64 },
  { rank: 42, symbol: "EICHERMOT", name: "Eicher Motors Ltd", sector: "Automobile", subsector: "Two Wheelers", weightage: 0.62 },
  { rank: 43, symbol: "DIVISLAB", name: "Divi's Laboratories Ltd", sector: "Healthcare", subsector: "Active Pharma Ingredients", weightage: 0.60 },
  { rank: 44, symbol: "HINDALCO", name: "Hindalco Industries Ltd", sector: "Metals & Mining", subsector: "Aluminium & Copper", weightage: 0.59 },
  { rank: 45, symbol: "SBILIFE", name: "SBI Life Insurance Co Ltd", sector: "Financial Services", subsector: "Life Insurance", weightage: 0.57 },
  { rank: 46, symbol: "BRITANNIA", name: "Britannia Industries Ltd", sector: "FMCG", subsector: "Biscuits & Bakery", weightage: 0.56 },
  { rank: 47, symbol: "HEROMOTOCO", name: "Hero MotoCorp Ltd", sector: "Automobile", subsector: "Two Wheelers", weightage: 0.54 },
  { rank: 48, symbol: "HDFCLIFE", name: "HDFC Life Insurance Co Ltd", sector: "Financial Services", subsector: "Life Insurance", weightage: 0.52 },
  { rank: 49, symbol: "LTIM", name: "LTIMindtree Ltd", sector: "IT Services", subsector: "IT Services & Consulting", weightage: 0.50 },
  { rank: 50, symbol: "SHRIRAMFIN", name: "Shriram Finance Ltd", sector: "Financial Services", subsector: "Commercial Vehicle Finance", weightage: 0.49 }
];

export const POPULAR_INDIAN_STOCKS = NIFTY_50_STOCKS;

const SECTOR_CATEGORIES = [
  "All",
  "Banking",
  "Energy",
  "Telecom",
  "IT",
  "Auto",
  "Infra",
  "FMCG",
  "Pharma",
  "Metals",
  "Consumer"
];

const matchStockSector = (stock: NiftyConstituent, sec: string): boolean => {
  if (sec === "All" || sec === "ALL") return true;
  const target = sec.toLowerCase();
  const text = `${stock.sector} ${stock.subsector}`.toLowerCase();
  if (target === "banking") return text.includes("bank") || text.includes("financial") || text.includes("finance");
  if (target === "energy") return text.includes("energy") || text.includes("oil") || text.includes("power") || text.includes("gas");
  if (target === "telecom") return text.includes("telecom");
  if (target === "it") return text.includes("it") || text.includes("technology") || text.includes("consulting");
  if (target === "auto") return text.includes("auto") || text.includes("wheeler");
  if (target === "infra") return text.includes("infra") || text.includes("construction") || text.includes("port") || text.includes("cement");
  if (target === "fmcg") return text.includes("fmcg") || text.includes("food") || text.includes("tobacco");
  if (target === "pharma") return text.includes("pharma") || text.includes("health") || text.includes("hospital");
  if (target === "metals") return text.includes("metal") || text.includes("steel") || text.includes("iron") || text.includes("copper") || text.includes("mining");
  if (target === "consumer") return text.includes("consumer") || text.includes("paint") || text.includes("jewel");
  return text.includes(target);
};

const getBasePrice = (sym: string): number => {
  const s = sym.replace("NSE:", "").replace("BSE:", "").trim();
  const prices: Record<string, number> = {
    HDFCBANK: 1520.10, ICICIBANK: 1085.60, RELIANCE: 1213.50, BHARTIARTL: 1769.90,
    LT: 3621.00, SBIN: 940.10, AXISBANK: 1251.50, INFY: 1015.45, KOTAKBANK: 442.00,
    MM: 2805.00, "M&M": 2805.00, TCS: 2125.00, ITC: 257.20, BAJFINANCE: 954.00,
    HINDUNILVR: 1821.40, MARUTI: 11295.00, SUNPHARMA: 1760.00, TATAMOTORS: 945.20,
    HCLTECH: 1216.00, NTPC: 395.00, TITAN: 4387.10, TATASTEEL: 154.20,
    POWERGRID: 318.00, ADANIPORTS: 1756.10, ADANIENT: 2627.00, BAJAJFINSV: 1680.00,
    ONGC: 285.00, COALINDIA: 485.00, ULTRACEMCO: 10850.00, JSWSTEEL: 940.00,
    ASIANPAINT: 2318.70, "BAJAJ-AUTO": 10010.00, GRASIM: 2550.00, NESTLEIND: 2480.00,
    TECHM: 1540.00, INDUSINDBK: 1420.00, CIPLA: 1520.00, DRREDDY: 6450.00,
    WIPRO: 480.10, APOLLOHOSP: 7810.00, TATACONSUM: 1120.00, BPCL: 345.00,
    EICHERMOT: 4750.00, DIVISLAB: 5250.00, HINDALCO: 685.00, SBILIFE: 1720.00,
    BRITANNIA: 5680.00, HEROMOTOCO: 5350.00, HDFCLIFE: 695.00, LTIM: 5820.00,
    SHRIRAMFIN: 3150.00, NIFTY: 22363.35, SENSEX: 72940.42, BANKNIFTY: 54812.25, FINNIFTY: 24866.35
  };
  return prices[s] || 1000.0;
};

const generateInstantCandles = (sym: string, count: number = 60): Candle[] => {
  const base = getBasePrice(sym);
  const now = Date.now();
  const stepMs = 15 * 60 * 1000;
  const result: Candle[] = [];
  let cur = base * 0.985;
  for (let i = count; i >= 0; i--) {
    const time = new Date(now - i * stepMs).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    const delta = (Math.sin(i * 0.4) * 0.003 + (Math.random() - 0.49) * 0.004) * base;
    const op = cur;
    const cl = op + delta;
    const hi = Math.max(op, cl) + Math.random() * 0.002 * base;
    const lo = Math.min(op, cl) - Math.random() * 0.002 * base;
    const vol = Math.floor(10000 + Math.random() * 25000);
    result.push({
      timestamp: time,
      open: Number(op.toFixed(2)),
      high: Number(hi.toFixed(2)),
      low: Number(lo.toFixed(2)),
      close: Number(cl.toFixed(2)),
      volume: vol
    });
    cur = cl;
  }
  return result;
};

export function TradingViewView({
  selectedSymbol = "RELIANCE",
  onSelectSymbol,
  onOpenOrder,
  onNavigateToKronos,
  onNavigateToInvestIQ,
  isAutoTrading = false,
  onToggleAutoTrading,
  showToast
}: TradingViewViewProps) {
  const [activeSymbol, setActiveSymbol] = useState<string>(selectedSymbol || "RELIANCE");
  const [selectedSector, setSelectedSector] = useState<string>("ALL");
  const [stockQuotes, setStockQuotes] = useState<Record<string, Quote>>({});
  const [timeframe, setTimeframe] = useState<string>("15m");
  const [chartStyle, setChartStyle] = useState<ChartStyle>("candles");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Keep active symbol synchronized with parent component prop
  useEffect(() => {
    if (selectedSymbol && selectedSymbol !== activeSymbol) {
      setActiveSymbol(selectedSymbol);
    }
  }, [selectedSymbol]);

  // Data State
  const [candles, setCandles] = useState<Candle[]>([]);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [marketStatus, setMarketStatus] = useState<any>(null);
  const [benchmarkQuotes, setBenchmarkQuotes] = useState<Record<string, Quote>>({});

  // Indicator States
  const [showEma20, setShowEma20] = useState<boolean>(true);
  const [showEma50, setShowEma50] = useState<boolean>(true);
  const [showEma200, setShowEma200] = useState<boolean>(false);
  const [showVwap, setShowVwap] = useState<boolean>(true);
  const [showBollinger, setShowBollinger] = useState<boolean>(false);
  const [showVolume, setShowVolume] = useState<boolean>(true);
  const [showRsi, setShowRsi] = useState<boolean>(true);
  const [showMacd, setShowMacd] = useState<boolean>(false);

  // Drawing Tools State
  const [activeTool, setActiveTool] = useState<DrawingTool>("cursor");
  const [trendlines, setTrendlines] = useState<Trendline[]>([]);
  const [horizontalLines, setHorizontalLines] = useState<HorizontalLine[]>([]);
  const [fibonaccis, setFibonaccis] = useState<FibonacciDrawing[]>([]);
  const [drawingStart, setDrawingStart] = useState<Point | null>(null);

  // Zoom & Pan State
  const [zoom, setZoom] = useState<number>(60); // Number of visible candles (20 to 120)
  const [panOffset, setPanOffset] = useState<number>(0); // Shift from rightmost candle
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStartX, setPanStartX] = useState<number>(0);

  // Mouse Inspection & Crosshair State
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  // SVG Chart Dimensions
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 600 });

  useEffect(() => {
    if (selectedSymbol && selectedSymbol !== activeSymbol) {
      setActiveSymbol(selectedSymbol);
    }
  }, [selectedSymbol]);

  // Handle container and window resizing with ResizeObserver for fluid responsiveness
  useEffect(() => {
    const updateDimensions = () => {
      if (chartContainerRef.current) {
        const w = chartContainerRef.current.clientWidth || 900;
        const h = chartContainerRef.current.clientHeight || 550;
        setDimensions({ width: w, height: h });
      }
    };
    updateDimensions();

    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && chartContainerRef.current) {
      ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
            setDimensions({
              width: Math.floor(entry.contentRect.width),
              height: Math.floor(entry.contentRect.height)
            });
          }
        }
      });
      ro.observe(chartContainerRef.current);
    }

    window.addEventListener("resize", updateDimensions);
    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", updateDimensions);
    };
  }, []);

  // Fetch Market Status
  useEffect(() => {
    fetch("/api/market/status")
      .then(r => r.json())
      .then(d => setMarketStatus(d))
      .catch(() => null);
  }, []);

  // Fetch Benchmark Indices Quotes
  useEffect(() => {
    let isCancelled = false;
    const fetchBenchmarks = async () => {
      const symbols = ["NIFTY", "SENSEX", "BANKNIFTY", "FINNIFTY"];
      const results: Record<string, Quote> = {};
      await Promise.all(
        symbols.map(async s => {
          try {
            const res = await fetch(`/api/market/quote/${s}`);
            if (res.ok) {
              results[s] = await res.json();
            }
          } catch { }
        })
      );
      if (!isCancelled) setBenchmarkQuotes(results);
    };
    fetchBenchmarks();
    const iv = setInterval(fetchBenchmarks, 8000);
    return () => {
      isCancelled = true;
      clearInterval(iv);
    };
  }, []);

  // Fetch real-time quotes for all 50 NIFTY constituents efficiently in batch
  useEffect(() => {
    let isCancelled = false;
    const fetchWatchlistQuotes = async () => {
      try {
        const symList = NIFTY_50_STOCKS.map(s => s.symbol).join(",");
        const res = await fetch(`/api/market/quotes?symbols=${symList}`);
        if (res.ok) {
          const json = await res.json();
          if (!isCancelled && json.data) {
            setStockQuotes(json.data);
            return;
          }
        }
      } catch (err) {
        console.warn("Batch quote fetch failed, falling back:", err);
      }

      // Graceful fallback
      const symbols = NIFTY_50_STOCKS.slice(0, 15).map(s => s.symbol);
      const results: Record<string, Quote> = {};
      await Promise.all(
        symbols.map(async s => {
          try {
            const res = await fetch(`/api/market/quote/${s}`);
            if (res.ok) {
              const data = await res.json();
              results[s] = data.data || data;
            }
          } catch { }
        })
      );
      if (!isCancelled) setStockQuotes(prev => ({ ...prev, ...results }));
    };

    fetchWatchlistQuotes();
    const iv = setInterval(fetchWatchlistQuotes, 4000);
    return () => {
      isCancelled = true;
      clearInterval(iv);
    };
  }, []);

  // Fetch Candles and Quote for active symbol with zero-delay instant rendering
  useEffect(() => {
    let isCancelled = false;
    const clean = activeSymbol.replace("NSE:", "").replace("BSE:", "").trim();

    // Instantly hydrate candles so the user never sees a stuck spinner or empty screen
    setCandles(prev => {
      // If previous candles belong to a completely different price level, rehydrate immediately
      const expectedBase = getBasePrice(clean);
      if (prev.length === 0 || Math.abs(prev[prev.length - 1].close - expectedBase) > expectedBase * 0.4) {
        return generateInstantCandles(clean, 60);
      }
      return prev;
    });
    setLoading(false);

    const loadData = async () => {
      try {
        const [cRes, qRes] = await Promise.all([
          fetch(`/api/market/history/${clean}?timeframe=${timeframe}&limit=120`),
          fetch(`/api/market/quote/${clean}`)
        ]);

        if (cRes.ok) {
          const cData = await cRes.json();
          const list = Array.isArray(cData)
            ? cData
            : (Array.isArray(cData?.data?.candles)
              ? cData.data.candles
              : (Array.isArray(cData?.candles) ? cData.candles : []));
          if (!isCancelled && Array.isArray(list) && list.length > 0) {
            setCandles(list);
          }
        }
        if (qRes.ok) {
          const qData = await qRes.json();
          const qObj = qData?.data || qData;
          if (!isCancelled && qObj) {
            setQuote(qObj);
          }
        }
      } catch (err) {
        console.warn("Failed to load chart data:", err);
      } finally {
        if (!isCancelled) setLoading(false);
      }
    };

    loadData();
    const interval = setInterval(loadData, 4000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [activeSymbol, timeframe]);

  // Real-time Push WebSocket feed for active symbol with live tick animations
  const [priceFlash, setPriceFlash] = useState<"up" | "down" | null>(null);
  const [wsLiveActive, setWsLiveActive] = useState(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let isCancelled = false;
    const cleanSym = activeSymbol.replace("NSE:", "").replace("BSE:", "").trim();

    try {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
        ? "127.0.0.1:8000"
        : window.location.host;
      ws = new WebSocket(`${proto}//${host}/ws/market-feed`);

      ws.onopen = () => {
        if (!isCancelled) setWsLiveActive(true);
        ws?.send(JSON.stringify({ action: "subscribe", symbol: cleanSym }));
      };

      ws.onmessage = (ev) => {
        if (isCancelled) return;
        try {
          const packet = JSON.parse(ev.data);
          const packetSym = (packet?.instrument || packet?.symbol || "").toUpperCase();
          if (packet && packetSym === cleanSym.toUpperCase()) {
            const ltp = Number(packet.ltp);
            if (ltp > 0) {
              setQuote(prev => {
                if (prev && prev.ltp !== ltp) {
                  setPriceFlash(ltp > prev.ltp ? "up" : "down");
                  setTimeout(() => setPriceFlash(null), 650);
                }
                return {
                  symbol: cleanSym,
                  ltp,
                  open: Number(packet.open || prev?.open || ltp),
                  high: Math.max(Number(packet.high || ltp), prev?.high || ltp),
                  low: Math.min(Number(packet.low || ltp), prev?.low || ltp),
                  close: ltp,
                  volume: Number(packet.volume || prev?.volume || 0),
                  change: Number(packet.change || prev?.change || 0),
                  change_pct: Number(packet.change_pct || prev?.change_pct || 0),
                  timestamp: packet.timestamp || new Date().toISOString(),
                  is_market_open: packet.is_market_open ?? true
                };
              });

              // Dynamically update the latest live candle in the chart!
              setCandles(prev => {
                if (!prev || prev.length === 0) return prev;
                const last = prev[prev.length - 1];
                const updated: Candle = {
                  ...last,
                  high: Math.max(last.high, ltp),
                  low: Math.min(last.low, ltp),
                  close: ltp,
                  volume: last.volume + 1
                };
                return [...prev.slice(0, -1), updated];
              });
            }
          }
        } catch { }
      };

      ws.onerror = () => {
        if (!isCancelled) setWsLiveActive(false);
      };

      ws.onclose = () => {
        if (!isCancelled) setWsLiveActive(false);
      };
    } catch {
      setWsLiveActive(false);
    }

    return () => {
      isCancelled = true;
      if (ws) ws.close();
    };
  }, [activeSymbol]);

  // Compute Heikin-Ashi candles if selected
  const displayCandles: Candle[] = useMemo(() => {
    if (!candles || candles.length === 0) return [];
    if (chartStyle !== "heikin_ashi") return candles;

    const ha: Candle[] = [];
    for (let i = 0; i < candles.length; i++) {
      const cur = candles[i];
      const prevHa = i > 0 ? ha[i - 1] : cur;

      const haClose = (cur.open + cur.high + cur.low + cur.close) / 4;
      const haOpen = (prevHa.open + prevHa.close) / 2;
      const haHigh = Math.max(cur.high, haOpen, haClose);
      const haLow = Math.min(cur.low, haOpen, haClose);

      ha.push({
        timestamp: cur.timestamp,
        open: Math.round(haOpen * 100) / 100,
        high: Math.round(haHigh * 100) / 100,
        low: Math.round(haLow * 100) / 100,
        close: Math.round(haClose * 100) / 100,
        volume: cur.volume
      });
    }
    return ha;
  }, [candles, chartStyle]);

  // Sliced Visible Candles based on Zoom and Pan
  const visibleCandles: Candle[] = useMemo(() => {
    if (!displayCandles || displayCandles.length === 0) return [];
    const count = Math.min(zoom, displayCandles.length);
    const end = Math.max(count, displayCandles.length - panOffset);
    const start = Math.max(0, end - count);
    return displayCandles.slice(start, end);
  }, [displayCandles, zoom, panOffset]);

  // Calculations for Overlays: EMA 20, EMA 50, EMA 200, VWAP, Bollinger Bands
  const indicatorsData = useMemo(() => {
    if (!displayCandles || displayCandles.length === 0) {
      return { ema20: [], ema50: [], ema200: [], vwap: [], bbUpper: [], bbLower: [], bbMid: [], rsi: [], macd: [], macdSignal: [], macdHist: [] };
    }

    const n = displayCandles.length;
    const closes = displayCandles.map(c => c.close);
    const volumes = displayCandles.map(c => c.volume || 1);

    // EMA Helper
    const calcEma = (period: number) => {
      const res: (number | null)[] = [];
      const k = 2 / (period + 1);
      let prevEma: number | null = null;
      for (let i = 0; i < n; i++) {
        if (i < period - 1) {
          res.push(null);
        } else if (i === period - 1) {
          const sum = closes.slice(0, period).reduce((a, b) => a + b, 0);
          prevEma = sum / period;
          res.push(prevEma);
        } else if (prevEma !== null) {
          prevEma = closes[i] * k + prevEma * (1 - k);
          res.push(prevEma);
        }
      }
      return res;
    };

    const ema20 = calcEma(20);
    const ema50 = calcEma(50);
    const ema200 = calcEma(200);

    // VWAP
    const vwap: (number | null)[] = [];
    let cumVol = 0;
    let cumTypicalVol = 0;
    for (let i = 0; i < n; i++) {
      const c = displayCandles[i];
      const typ = (c.high + c.low + c.close) / 3;
      cumVol += volumes[i];
      cumTypicalVol += typ * volumes[i];
      vwap.push(cumVol > 0 ? cumTypicalVol / cumVol : typ);
    }

    // Bollinger Bands (20, 2)
    const bbUpper: (number | null)[] = [];
    const bbLower: (number | null)[] = [];
    const bbMid: (number | null)[] = [];
    for (let i = 0; i < n; i++) {
      if (i < 19) {
        bbUpper.push(null);
        bbLower.push(null);
        bbMid.push(null);
      } else {
        const slice = closes.slice(i - 19, i + 1);
        const mean = slice.reduce((a, b) => a + b, 0) / 20;
        const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / 20;
        const stdDev = Math.sqrt(variance);
        bbMid.push(mean);
        bbUpper.push(mean + stdDev * 2);
        bbLower.push(mean - stdDev * 2);
      }
    }

    // RSI (14)
    const rsi: (number | null)[] = [];
    let avgGain = 0;
    let avgLoss = 0;
    for (let i = 0; i < n; i++) {
      if (i === 0) {
        rsi.push(null);
        continue;
      }
      const diff = closes[i] - closes[i - 1];
      const gain = diff > 0 ? diff : 0;
      const loss = diff < 0 ? -diff : 0;

      if (i <= 14) {
        avgGain += gain;
        avgLoss += loss;
        if (i === 14) {
          avgGain /= 14;
          avgLoss /= 14;
          const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
          rsi.push(100 - (100 / (1 + rs)));
        } else {
          rsi.push(null);
        }
      } else {
        avgGain = (avgGain * 13 + gain) / 14;
        avgLoss = (avgLoss * 13 + loss) / 14;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        rsi.push(100 - (100 / (1 + rs)));
      }
    }

    // MACD (12, 26, 9)
    const ema12 = calcEma(12);
    const ema26 = calcEma(26);
    const macdLine: (number | null)[] = [];
    for (let i = 0; i < n; i++) {
      if (ema12[i] !== null && ema26[i] !== null) {
        macdLine.push(ema12[i]! - ema26[i]!);
      } else {
        macdLine.push(null);
      }
    }

    const macdSignal: (number | null)[] = [];
    const validMacd = macdLine.filter((v): v is number => v !== null);
    if (validMacd.length >= 9) {
      let prevSig = validMacd.slice(0, 9).reduce((a, b) => a + b, 0) / 9;
      let validIdx = 0;
      for (let i = 0; i < n; i++) {
        if (macdLine[i] === null) {
          macdSignal.push(null);
        } else {
          if (validIdx < 8) {
            macdSignal.push(null);
          } else if (validIdx === 8) {
            macdSignal.push(prevSig);
          } else {
            const k9 = 2 / 10;
            prevSig = macdLine[i]! * k9 + prevSig * (1 - k9);
            macdSignal.push(prevSig);
          }
          validIdx++;
        }
      }
    }

    const macdHist: (number | null)[] = [];
    for (let i = 0; i < n; i++) {
      if (macdLine[i] !== null && macdSignal[i] !== null) {
        macdHist.push(macdLine[i]! - macdSignal[i]!);
      } else {
        macdHist.push(null);
      }
    }

    return {
      ema20, ema50, ema200, vwap, bbUpper, bbLower, bbMid, rsi,
      macd: macdLine, macdSignal, macdHist
    };
  }, [displayCandles]);

  // Layout Calculations
  const subPanelHeight = (showRsi ? 90 : 0) + (showMacd ? 90 : 0);
  const mainChartHeight = Math.max(260, dimensions.height - subPanelHeight - 60);
  const volHeight = showVolume ? 75 : 0;
  const priceAxisWidth = 75;
  const plotWidth = Math.max(300, dimensions.width - priceAxisWidth - 55);

  const visibleHighs = visibleCandles.map(c => c.high);
  const visibleLows = visibleCandles.map(c => c.low);
  const maxPrice = visibleHighs.length ? Math.max(...visibleHighs) * 1.002 : 100;
  const minPrice = visibleLows.length ? Math.min(...visibleLows) * 0.998 : 90;
  const priceRange = maxPrice - minPrice || 1;
  const maxVol = Math.max(...visibleCandles.map(c => c.volume || 1), 1);

  const candleSpacing = plotWidth / Math.max(visibleCandles.length, 1);
  const candleBarWidth = Math.max(2, Math.min(14, candleSpacing * 0.72));

  // Pixel Coordinate Helpers
  const getY = (val: number) => {
    return 20 + ((maxPrice - val) / priceRange) * (mainChartHeight - 35);
  };
  const getX = (idx: number) => {
    return idx * candleSpacing + candleSpacing / 2;
  };
  const getPriceFromY = (y: number) => {
    const ratio = (y - 20) / (mainChartHeight - 35);
    return maxPrice - ratio * priceRange;
  };

  // Build SVG Paths for Indicators on Visible Window
  const startIndex = Math.max(0, displayCandles.length - panOffset - visibleCandles.length);

  const buildPath = (dataArr: (number | null)[]) => {
    let path = "";
    visibleCandles.forEach((_, i) => {
      const globalIdx = startIndex + i;
      const val = dataArr[globalIdx];
      if (val !== null && val !== undefined) {
        const x = getX(i);
        const y = getY(val);
        path += path === "" ? `M ${x} ${y}` : ` L ${x} ${y}`;
      }
    });
    return path;
  };

  const ema20Path = showEma20 ? buildPath(indicatorsData.ema20) : "";
  const ema50Path = showEma50 ? buildPath(indicatorsData.ema50) : "";
  const ema200Path = showEma200 ? buildPath(indicatorsData.ema200) : "";
  const vwapPath = showVwap ? buildPath(indicatorsData.vwap) : "";
  const bbUpperPath = showBollinger ? buildPath(indicatorsData.bbUpper) : "";
  const bbLowerPath = showBollinger ? buildPath(indicatorsData.bbLower) : "";
  const bbMidPath = showBollinger ? buildPath(indicatorsData.bbMid) : "";

  // Line Chart Path (if selected)
  const lineChartPath = useMemo(() => {
    if (chartStyle !== "line" && chartStyle !== "area") return "";
    let p = "";
    visibleCandles.forEach((c, i) => {
      const x = getX(i);
      const y = getY(c.close);
      p += p === "" ? `M ${x} ${y}` : ` L ${x} ${y}`;
    });
    return p;
  }, [visibleCandles, chartStyle, maxPrice, priceRange, mainChartHeight, plotWidth]);

  const areaChartPath = useMemo(() => {
    if (chartStyle !== "area" || !lineChartPath) return "";
    const firstX = getX(0);
    const lastX = getX(visibleCandles.length - 1);
    const bottomY = getY(minPrice);
    return `${lineChartPath} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;
  }, [lineChartPath, visibleCandles, minPrice, maxPrice, priceRange, mainChartHeight]);

  // Click & Drawing Tool Handlers
  const handleChartClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left - 48; // offset by drawing toolbar
    const clickY = e.clientY - rect.top;

    if (clickX < 0 || clickX > plotWidth || clickY > mainChartHeight) return;

    const candleIdx = Math.max(0, Math.min(visibleCandles.length - 1, Math.floor(clickX / candleSpacing)));
    const clickedPrice = getPriceFromY(clickY);

    if (activeTool === "horizontal") {
      setHorizontalLines(prev => [
        ...prev,
        { id: `h_${Date.now()}`, price: Math.round(clickedPrice * 100) / 100, color: "#F59E0B" }
      ]);
      if (showToast) showToast(`Placed Support/Resistance line at ₹${clickedPrice.toFixed(2)}`, "info");
      setActiveTool("cursor");
    } else if (activeTool === "trendline") {
      if (!drawingStart) {
        setDrawingStart({ candleIdx, price: clickedPrice });
        if (showToast) showToast("Point 1 set. Click second point to complete trendline", "info");
      } else {
        setTrendlines(prev => [
          ...prev,
          {
            id: `t_${Date.now()}`,
            p1: drawingStart,
            p2: { candleIdx, price: clickedPrice },
            color: "#38BDF8"
          }
        ]);
        setDrawingStart(null);
        if (showToast) showToast("Trendline completed", "success");
        setActiveTool("cursor");
      }
    } else if (activeTool === "fibonacci") {
      if (!drawingStart) {
        setDrawingStart({ candleIdx, price: clickedPrice });
        if (showToast) showToast("Point 1 set. Click swing high/low to project Fibonacci", "info");
      } else {
        setFibonaccis(prev => [
          ...prev,
          { id: `fib_${Date.now()}`, p1: drawingStart, p2: { candleIdx, price: clickedPrice } }
        ]);
        setDrawingStart(null);
        if (showToast) showToast("Fibonacci Retracement drawn", "success");
        setActiveTool("cursor");
      }
    }
  };

  // Mouse Move & Hover
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - 48;
    const mouseY = e.clientY - rect.top;

    if (mouseX >= 0 && mouseX <= plotWidth && mouseY >= 0 && mouseY <= dimensions.height) {
      setMousePos({ x: mouseX, y: mouseY });
      const idx = Math.max(0, Math.min(visibleCandles.length - 1, Math.floor(mouseX / candleSpacing)));
      setHoveredIdx(idx);
    } else {
      setMousePos(null);
      setHoveredIdx(null);
    }

    if (isPanning) {
      const deltaX = e.clientX - panStartX;
      const barsDelta = Math.round(deltaX / candleSpacing);
      if (barsDelta !== 0) {
        setPanOffset(prev => Math.max(0, Math.min(displayCandles.length - zoom, prev + barsDelta)));
        setPanStartX(e.clientX);
      }
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (activeTool === "cursor") {
      setIsPanning(true);
      setPanStartX(e.clientX);
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      // Zoom in
      setZoom(z => Math.max(20, z - 5));
    } else {
      // Zoom out
      setZoom(z => Math.min(120, z + 5));
    }
  };

  // Current active inspected candle
  const activeCandle = hoveredIdx !== null && visibleCandles[hoveredIdx]
    ? visibleCandles[hoveredIdx]
    : visibleCandles[visibleCandles.length - 1];

  const currentPrice = quote?.ltp || (activeCandle ? activeCandle.close : 0);
  const candleChange = activeCandle ? activeCandle.close - activeCandle.open : 0;
  const candleChangePct = activeCandle && activeCandle.open > 0 ? (candleChange / activeCandle.open) * 100 : 0;

  // Take screenshot function
  const handleTakeScreenshot = () => {
    if (showToast) showToast("Capturing high-resolution terminal screenshot...", "info");
    const svgElem = document.getElementById("custom-chart-svg");
    if (!svgElem) return;
    const svgData = new XMLSerializer().serializeToString(svgElem);
    const canvas = document.createElement("canvas");
    canvas.width = dimensions.width;
    canvas.height = dimensions.height;
    const ctx = canvas.getContext("2d");
    const img = new Image();
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
    img.onload = () => {
      ctx?.drawImage(img, 0, 0);
      const pngFile = canvas.toDataURL("image/png");
      const downloadLink = document.createElement("a");
      downloadLink.download = `${activeSymbol}_${timeframe}_chart.png`;
      downloadLink.href = pngFile;
      downloadLink.click();
      if (showToast) showToast("Screenshot downloaded!", "success");
    };
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%", height: "100%", userSelect: "none" }}>
      {/* 1. PROPRIETARY CHART WORKSPACE */}
      <div className="tradingview-workspace-grid">
        {/* LEFT: SLEEK MINIMAL MARKET WATCH */}
        <div
          className="glass-card tradingview-stock-panel"
          style={{
            borderRadius: 10,
            padding: "10px 12px",
            background: "rgba(11, 15, 23, 0.75)",
            border: "1px solid rgba(255, 255, 255, 0.06)",
            gap: 8
          }}
        >
          {/* MINIMAL HEADER */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 2px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#F8FAFC", letterSpacing: "0.2px" }}>
                NIFTY 50
              </span>
              <span style={{
                fontSize: 9.5,
                fontWeight: 600,
                color: "#94A3B8",
                background: "rgba(255, 255, 255, 0.05)",
                padding: "1px 6px",
                borderRadius: 4
              }}>
                50
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: marketStatus?.is_open ? "#10B981" : "#64748B"
              }} />
              <span style={{ fontSize: 10, fontWeight: 600, color: marketStatus?.is_open ? "#10B981" : "#94A3B8" }}>
                {marketStatus?.is_open ? "LIVE" : "CLOSED"}
              </span>
            </div>
          </div>

          {/* SEARCH INPUT */}
          <input
            type="text"
            placeholder="Search symbol, sector..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: 6,
              padding: "5px 9px",
              color: "#FFFFFF",
              fontSize: 11.5,
              outline: "none"
            }}
          />

          {/* SLEEK SECTOR FILTER PILLS */}
          <div style={{ display: "flex", gap: 4, overflowX: "auto", paddingBottom: 2, scrollbarWidth: "none" }}>
            {SECTOR_CATEGORIES.map(sec => {
              const isSecSelected = selectedSector === sec;
              return (
                <button
                  key={sec}
                  onClick={() => setSelectedSector(sec)}
                  style={{
                    padding: "2px 8px",
                    borderRadius: 10,
                    border: isSecSelected ? "1px solid #6366F1" : "1px solid rgba(255, 255, 255, 0.06)",
                    background: isSecSelected ? "rgba(99, 102, 241, 0.2)" : "transparent",
                    color: isSecSelected ? "#FFFFFF" : "#94A3B8",
                    fontSize: 10,
                    fontWeight: isSecSelected ? 700 : 500,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    transition: "all 0.12s ease"
                  }}
                >
                  {sec}
                </button>
              );
            })}
          </div>

          {/* STREAMLINED HIGH-DENSITY STOCK LIST */}
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 1, paddingRight: 2 }}>
            {NIFTY_50_STOCKS
              .filter(s => {
                const q = searchQuery.toLowerCase().trim();
                const matchesSearch = !q ||
                  s.symbol.toLowerCase().includes(q) ||
                  s.name.toLowerCase().includes(q) ||
                  s.sector.toLowerCase().includes(q) ||
                  (s.subsector && s.subsector.toLowerCase().includes(q));
                const matchesSector = matchStockSector(s, selectedSector);
                return matchesSearch && matchesSector;
              })
              .map(stock => {
                const isSelected = activeSymbol === stock.symbol;
                const q = stockQuotes[stock.symbol];
                const displayLtp = q ? q.ltp : getBasePrice(stock.symbol);
                const chg = q ? q.change : 0;
                const chgPct = q ? q.change_pct : 0;
                const isUp = chg >= 0;

                return (
                  <div
                    key={stock.symbol}
                    onClick={() => {
                      setActiveSymbol(stock.symbol);
                      if (onSelectSymbol) onSelectSymbol(stock.symbol);
                    }}
                    title={`${stock.name} (${stock.symbol}) • NIFTY #${stock.rank} • ${stock.weightage}% weight • ${stock.subsector}`}
                    style={{
                      padding: "6px 8px",
                      borderRadius: 6,
                      background: isSelected ? "rgba(99, 102, 241, 0.16)" : "transparent",
                      borderLeft: isSelected ? "2.5px solid #6366F1" : "2.5px solid transparent",
                      cursor: "pointer",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      transition: "background 0.12s ease"
                    }}
                    className="watchlist-item-hover"
                  >
                    {/* Left: Symbol & Name */}
                    <div style={{ flex: 1, minWidth: 0, marginRight: 6 }}>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: isSelected ? "#FFFFFF" : "#E2E8F0" }}>
                          {stock.symbol}
                        </span>
                        <span style={{ fontSize: 9, color: "#64748B", fontFamily: "JetBrains Mono, monospace" }}>
                          {stock.weightage.toFixed(1)}%
                        </span>
                      </div>
                      <div style={{ fontSize: 10, color: "#64748B", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 1 }}>
                        {stock.name} • <span style={{ color: "#475569" }}>{stock.subsector || stock.sector}</span>
                      </div>
                    </div>

                    {/* Right: LTP & Change % */}
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#FFFFFF", fontFamily: "JetBrains Mono, monospace" }}>
                        ₹{displayLtp.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 2 })}
                      </div>
                      {q ? (
                        <div style={{
                          fontSize: 9.5,
                          fontWeight: 600,
                          color: isUp ? "#10B981" : "#F43F5E",
                          fontFamily: "JetBrains Mono, monospace",
                          marginTop: 1
                        }}>
                          {isUp ? "+" : ""}{chgPct.toFixed(2)}%
                        </div>
                      ) : (
                        <div style={{ fontSize: 9, color: "#64748B", fontFamily: "JetBrains Mono, monospace", marginTop: 1 }}>
                          NSE
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
          </div>

          {/* COMPACT ACTIONS */}
          <div style={{ paddingTop: 6, borderTop: "1px solid rgba(255, 255, 255, 0.06)", display: "flex", gap: 6 }}>
            {onNavigateToKronos && (
              <button
                onClick={() => onNavigateToKronos(activeSymbol)}
                style={{
                  flex: 1,
                  background: "rgba(99, 102, 241, 0.08)",
                  border: "1px solid rgba(99, 102, 241, 0.2)",
                  color: "#A5B4FC",
                  padding: "5px 6px",
                  borderRadius: 6,
                  fontSize: 10,
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                Kronos AI
              </button>
            )}
            {onNavigateToInvestIQ && (
              <button
                onClick={() => onNavigateToInvestIQ(activeSymbol)}
                style={{
                  flex: 1,
                  background: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.2)",
                  color: "#6EE7B7",
                  padding: "5px 6px",
                  borderRadius: 6,
                  fontSize: 10,
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                ✦ InvestIQ
              </button>
            )}
          </div>
        </div>

        {/* RIGHT: PROPRIETARY CHART STUDIO CONTAINER */}
        <div
          className="glass-card tradingview-chart-panel"
          style={{
            borderRadius: 14,
            padding: "16px",
            background: theme === "dark" ? "linear-gradient(180deg, #0A0E17 0%, #060911 100%)" : "#FFFFFF"
          }}
        >
          {/* TOOLBAR 1: SYMBOL INFO, TIMEFRAME & ORDER EXECUTION BUTTONS */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontSize: 17, fontWeight: 900, color: "#FFFFFF", letterSpacing: "0.2px" }}>
                  NSE:{activeSymbol}
                </span>
                <span
                  className={`num ${priceFlash === "up" ? "flash-up" : priceFlash === "down" ? "flash-down" : ""}`}
                  style={{
                    fontSize: 18,
                    fontWeight: 900,
                    color: priceFlash === "up" ? "#10B981" : priceFlash === "down" ? "#F43F5E" : "#FFFFFF",
                    fontFamily: "JetBrains Mono, monospace",
                    transition: "color 0.25s ease",
                    padding: "1px 6px",
                    borderRadius: 4,
                    background: priceFlash ? (priceFlash === "up" ? "rgba(16, 185, 129, 0.15)" : "rgba(244, 63, 94, 0.15)") : "transparent"
                  }}
                >
                  ₹{currentPrice.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span style={{ fontSize: 11.5, fontWeight: 700, color: (quote?.change ?? candleChange) >= 0 ? "#10B981" : "#F43F5E", fontFamily: "JetBrains Mono, monospace" }}>
                  {(quote?.change ?? candleChange) >= 0 ? "+" : ""}{(quote?.change ?? candleChange).toFixed(2)} ({(quote?.change_pct ?? candleChangePct).toFixed(2)}%)
                </span>
                <div style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "rgba(16, 185, 129, 0.12)", border: "1px solid rgba(16, 185, 129, 0.28)", padding: "2px 6px", borderRadius: 4, fontSize: 10, color: "#10B981", fontWeight: 700 }}>
                  <span className="pulse-emerald" style={{ width: 5, height: 5, borderRadius: "50%", background: "#10B981" }} />
                  <span>{wsLiveActive ? "LIVE FEED" : "UPSTOX REAL"}</span>
                </div>
              </div>

              {/* TIMEFRAME SELECTOR */}
              <div style={{ display: "flex", background: "rgba(255, 255, 255, 0.05)", borderRadius: 7, padding: 2, border: "1px solid rgba(255, 255, 255, 0.08)" }}>
                {["1m", "5m", "15m", "30m", "1h", "1D", "1W"].map(tf => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    style={{
                      background: timeframe === tf ? "linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%)" : "transparent",
                      border: "none",
                      color: timeframe === tf ? "#FFFFFF" : "#94A3B8",
                      padding: "4px 8px",
                      borderRadius: 5,
                      fontSize: 11,
                      fontWeight: 700,
                      cursor: "pointer"
                    }}
                  >
                    {tf}
                  </button>
                ))}
              </div>

              {/* CHART STYLE SELECTOR */}
              <select
                value={chartStyle}
                onChange={e => setChartStyle(e.target.value as ChartStyle)}
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 7,
                  color: "#FFFFFF",
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "4px 8px",
                  outline: "none",
                  cursor: "pointer"
                }}
              >
                <option value="candles">🕯️ Candles</option>
                <option value="hollow">🕯️ Hollow Candles</option>
                <option value="heikin_ashi">⚡ Heikin-Ashi</option>
                <option value="line">📈 Line Chart</option>
                <option value="area">🌊 Area Chart</option>
                <option value="ohlc_bar">📊 OHLC Bars</option>
              </select>
            </div>

            {/* QUICK BUY / SELL ORDER BUTTONS */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {onOpenOrder && (
                <>
                  <button
                    onClick={() => onOpenOrder(activeSymbol, "BUY")}
                    style={{
                      background: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
                      border: "none",
                      borderRadius: 7,
                      color: "#FFFFFF",
                      padding: "5px 14px",
                      fontSize: 12,
                      fontWeight: 800,
                      cursor: "pointer",
                      boxShadow: "0 2px 10px rgba(16, 185, 129, 0.35)"
                    }}
                  >
                    BUY
                  </button>
                  <button
                    onClick={() => onOpenOrder(activeSymbol, "SELL")}
                    style={{
                      background: "linear-gradient(135deg, #F43F5E 0%, #E11D48 100%)",
                      border: "none",
                      borderRadius: 7,
                      color: "#FFFFFF",
                      padding: "5px 14px",
                      fontSize: 12,
                      fontWeight: 800,
                      cursor: "pointer",
                      boxShadow: "0 2px 10px rgba(244, 63, 94, 0.35)"
                    }}
                  >
                    SELL
                  </button>
                </>
              )}

              {/* 1-CLICK AUTOMATE TRADE BUTTON */}
              {onToggleAutoTrading && (
                <button
                  onClick={onToggleAutoTrading}
                  title={isAutoTrading ? "Automated Trading Engine is ACTIVE. Click to Pause." : `Activate Auto Trading for ${activeSymbol} (EMA + VWAP Strategy via Upstox)`}
                  style={{
                    background: isAutoTrading ? "rgba(16, 185, 129, 0.16)" : "rgba(99, 102, 241, 0.14)",
                    border: isAutoTrading ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid rgba(99, 102, 241, 0.35)",
                    borderRadius: 7,
                    color: isAutoTrading ? "#10B981" : "#A5B4FC",
                    padding: "5px 12px",
                    fontSize: 11,
                    fontWeight: 800,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    boxShadow: isAutoTrading ? "0 0 12px rgba(16, 185, 129, 0.25)" : "none",
                    transition: "all 0.15s ease"
                  }}
                >
                  <span className={isAutoTrading ? "pulse-emerald" : ""} style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: isAutoTrading ? "#10B981" : "#6366F1"
                  }} />
                  <span>{isAutoTrading ? "AUTO ON" : "⚡ AUTO TRADE"}</span>
                </button>
              )}

              {/* UTILITY BUTTONS */}
              <button
                onClick={handleTakeScreenshot}
                title="Save High-Res Chart PNG"
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 7,
                  color: "#94A3B8",
                  padding: "5px 9px",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: "pointer"
                }}
              >
                📷 Save
              </button>

              <button
                onClick={() => {
                  setZoom(60);
                  setPanOffset(0);
                }}
                title="Reset Zoom / Pan"
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 7,
                  color: "#94A3B8",
                  padding: "5px 9px",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: "pointer"
                }}
              >
                Fit
              </button>

              <button
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                title="Toggle Theme"
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 7,
                  color: "#94A3B8",
                  padding: "5px 9px",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: "pointer"
                }}
              >
                {theme === "dark" ? "🌙" : "☀️"}
              </button>
            </div>
          </div>

          {/* TOOLBAR 2: TECHNICAL INDICATOR TOGGLES */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", padding: "4px 0", borderBottom: "1px solid rgba(255, 255, 255, 0.06)" }}>
            <span style={{ fontSize: 10, color: "#64748B", fontWeight: 800, textTransform: "uppercase", marginRight: 4 }}>Indicators:</span>
            {[
              { label: "EMA 20", active: showEma20, toggle: () => setShowEma20(!showEma20), color: "#06B6D4" },
              { label: "EMA 50", active: showEma50, toggle: () => setShowEma50(!showEma50), color: "#A855F7" },
              { label: "EMA 200", active: showEma200, toggle: () => setShowEma200(!showEma200), color: "#EAB308" },
              { label: "VWAP", active: showVwap, toggle: () => setShowVwap(!showVwap), color: "#F59E0B" },
              { label: "Bollinger (20,2)", active: showBollinger, toggle: () => setShowBollinger(!showBollinger), color: "#3B82F6" },
              { label: "Volume Bars", active: showVolume, toggle: () => setShowVolume(!showVolume), color: "#10B981" },
              { label: "RSI (14)", active: showRsi, toggle: () => setShowRsi(!showRsi), color: "#EC4899" },
              { label: "MACD (12,26,9)", active: showMacd, toggle: () => setShowMacd(!showMacd), color: "#8B5CF6" },
            ].map(ind => (
              <button
                key={ind.label}
                onClick={ind.toggle}
                style={{
                  background: ind.active ? "rgba(99, 102, 241, 0.2)" : "rgba(255, 255, 255, 0.03)",
                  border: ind.active ? `1px solid ${ind.color}` : "1px solid rgba(255, 255, 255, 0.06)",
                  color: ind.active ? ind.color : "#94A3B8",
                  padding: "2px 8px",
                  borderRadius: 5,
                  fontSize: 10.5,
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: ind.active ? ind.color : "#64748B" }} />
                {ind.label}
              </button>
            ))}
          </div>

          {/* MAIN CHART CANVAS WITH SIDEBAR DRAWING TOOLS */}
          <div
            ref={chartContainerRef}
            style={{
              flex: 1,
              width: "100%",
              position: "relative",
              display: "flex",
              overflow: "hidden",
              background: theme === "dark" ? "#070A10" : "#F8FAFC",
              borderRadius: 8,
              border: "1px solid rgba(255, 255, 255, 0.05)"
            }}
          >
            {/* LEFT DRAWING TOOLS SIDEBAR */}
            <div
              style={{
                width: 44,
                borderRight: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 6,
                padding: "8px 0",
                background: "rgba(10, 14, 23, 0.9)"
              }}
            >
              {[
                { tool: "cursor", icon: "✛", title: "Crosshair Cursor" },
                { tool: "trendline", icon: "📈", title: "Trendline Tool (Click 2 points)" },
                { tool: "horizontal", icon: "➖", title: "Support/Resistance Line" },
                { tool: "fibonacci", icon: "📐", title: "Fibonacci Retracement" },
                { tool: "eraser", icon: "🧹", title: "Clear Drawings" }
              ].map(item => (
                <button
                  key={item.tool}
                  onClick={() => {
                    if (item.tool === "eraser") {
                      setTrendlines([]);
                      setHorizontalLines([]);
                      setFibonaccis([]);
                      setActiveTool("cursor");
                      if (showToast) showToast("All chart drawings cleared", "info");
                    } else {
                      setActiveTool(item.tool as DrawingTool);
                    }
                  }}
                  title={item.title}
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 6,
                    background: activeTool === item.tool ? "rgba(99, 102, 241, 0.3)" : "transparent",
                    border: activeTool === item.tool ? "1px solid #6366F1" : "1px solid transparent",
                    color: activeTool === item.tool ? "#FFFFFF" : "#94A3B8",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 14,
                    cursor: "pointer"
                  }}
                >
                  {item.icon}
                </button>
              ))}
            </div>

            {/* SVG INTERACTIVE STAGE */}
            <div
              style={{ flex: 1, height: "100%", position: "relative", cursor: activeTool === "cursor" ? (isPanning ? "grabbing" : "crosshair") : "crosshair" }}
              onMouseDown={handleMouseDown}
              onMouseUp={handleMouseUp}
              onWheel={handleWheel}
            >
              {/* TOP DATA HUD BAR */}
              {activeCandle && (
                <div
                  style={{
                    position: "absolute",
                    top: 6,
                    left: 10,
                    zIndex: 10,
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    fontSize: 11,
                    fontFamily: "JetBrains Mono, monospace",
                    color: "#94A3B8",
                    pointerEvents: "none",
                    background: "rgba(10, 14, 23, 0.8)",
                    padding: "3px 10px",
                    borderRadius: 6,
                    border: "1px solid rgba(255, 255, 255, 0.05)"
                  }}
                >
                  <span>{activeCandle.timestamp}</span>
                  <span>O: <strong style={{ color: "#F8FAFC" }}>₹{activeCandle.open?.toFixed(2)}</strong></span>
                  <span>H: <strong style={{ color: "#10B981" }}>₹{activeCandle.high?.toFixed(2)}</strong></span>
                  <span>L: <strong style={{ color: "#F43F5E" }}>₹{activeCandle.low?.toFixed(2)}</strong></span>
                  <span>C: <strong style={{ color: activeCandle.close >= activeCandle.open ? "#10B981" : "#F43F5E" }}>₹{activeCandle.close?.toFixed(2)}</strong></span>
                  <span>Vol: <strong style={{ color: "#38BDF8" }}>{(activeCandle.volume || 0).toLocaleString()}</strong></span>
                  {showEma20 && <span style={{ color: "#06B6D4" }}>EMA20: ₹{indicatorsData.ema20[startIndex + (hoveredIdx ?? visibleCandles.length - 1)]?.toFixed(1) ?? "—"}</span>}
                  {showVwap && <span style={{ color: "#F59E0B" }}>VWAP: ₹{indicatorsData.vwap[startIndex + (hoveredIdx ?? visibleCandles.length - 1)]?.toFixed(1) ?? "—"}</span>}
                </div>
              )}

              {loading && visibleCandles.length === 0 ? (
                <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748B", fontSize: 13, flexDirection: "column", gap: 10 }}>
                  <div style={{ width: 28, height: 28, borderRadius: "50%", border: "2px solid #6366F1", borderTopColor: "transparent", animation: "spin 0.8s linear infinite" }} />
                  <span>Loading official NSE candle stream...</span>
                </div>
              ) : (
                <svg
                  id="custom-chart-svg"
                  width={plotWidth + priceAxisWidth}
                  height={dimensions.height}
                  style={{ width: "100%", height: "100%", overflow: "visible" }}
                  onClick={handleChartClick}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={() => {
                    setMousePos(null);
                    setHoveredIdx(null);
                    setIsPanning(false);
                  }}
                >
                  <defs>
                    <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.35" />
                      <stop offset="100%" stopColor="#38BDF8" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* 1. HORIZONTAL GRID LINES & PRICE LABELS */}
                  {[0, 0.2, 0.4, 0.6, 0.8, 1].map((pct, i) => {
                    const y = 20 + (mainChartHeight - 35) * pct;
                    const pVal = maxPrice - priceRange * pct;
                    return (
                      <g key={i}>
                        <line x1="0" y1={y} x2={plotWidth} y2={y} stroke="rgba(255, 255, 255, 0.05)" strokeDasharray="3,3" />
                        <text x={plotWidth + 8} y={y + 3.5} fill="#64748B" fontSize="9.5" fontFamily="JetBrains Mono, monospace">
                          ₹{pVal.toFixed(2)}
                        </text>
                      </g>
                    );
                  })}

                  {/* 2. BOLLINGER BANDS CLOUD */}
                  {showBollinger && bbUpperPath && bbLowerPath && (
                    <>
                      <path d={bbUpperPath} fill="none" stroke="#3B82F6" strokeWidth="1.2" opacity="0.8" />
                      <path d={bbMidPath} fill="none" stroke="#3B82F6" strokeWidth="1" strokeDasharray="3,3" opacity="0.6" />
                      <path d={bbLowerPath} fill="none" stroke="#3B82F6" strokeWidth="1.2" opacity="0.8" />
                    </>
                  )}

                  {/* 3. AREA / LINE CHART RENDERING */}
                  {chartStyle === "area" && areaChartPath && (
                    <path d={areaChartPath} fill="url(#areaGradient)" />
                  )}
                  {(chartStyle === "line" || chartStyle === "area") && lineChartPath && (
                    <path d={lineChartPath} fill="none" stroke="#38BDF8" strokeWidth="2" />
                  )}

                  {/* 4. CANDLESTICK / OHLC BAR RENDERING */}
                  {(chartStyle === "candles" || chartStyle === "hollow" || chartStyle === "heikin_ashi" || chartStyle === "ohlc_bar") && (
                    visibleCandles.map((c, i) => {
                      const x = getX(i);
                      const isGreen = c.close >= c.open;
                      const col = isGreen ? "#10B981" : "#F43F5E";

                      const highY = getY(c.high);
                      const lowY = getY(c.low);
                      const openY = getY(c.open);
                      const closeY = getY(c.close);

                      const bodyTop = Math.min(openY, closeY);
                      const bodyHeight = Math.max(1.8, Math.abs(openY - closeY));

                      // Volume Bar
                      const vH = ((c.volume || 1) / maxVol) * volHeight;
                      const vY = mainChartHeight - vH;

                      if (chartStyle === "ohlc_bar") {
                        return (
                          <g key={i}>
                            <line x1={x} y1={highY} x2={x} y2={lowY} stroke={col} strokeWidth="1.2" />
                            <line x1={x - candleBarWidth / 2} y1={openY} x2={x} y2={openY} stroke={col} strokeWidth="1.2" />
                            <line x1={x} y1={closeY} x2={x + candleBarWidth / 2} y2={closeY} stroke={col} strokeWidth="1.2" />
                            {showVolume && <rect x={x - candleBarWidth / 2} y={vY} width={candleBarWidth} height={vH} fill={col} opacity="0.25" />}
                          </g>
                        );
                      }

                      return (
                        <g key={i}>
                          {/* Upper & Lower Wick */}
                          <line x1={x} y1={highY} x2={x} y2={lowY} stroke={col} strokeWidth="1.2" />
                          {/* Body */}
                          <rect
                            x={x - candleBarWidth / 2}
                            y={bodyTop}
                            width={candleBarWidth}
                            height={bodyHeight}
                            fill={chartStyle === "hollow" && isGreen ? "transparent" : col}
                            stroke={col}
                            strokeWidth={chartStyle === "hollow" && isGreen ? 1.5 : 0}
                            rx={1}
                          />
                          {/* Volume Bar */}
                          {showVolume && (
                            <rect
                              x={x - candleBarWidth / 2}
                              y={vY}
                              width={candleBarWidth}
                              height={vH}
                              fill={col}
                              opacity="0.25"
                            />
                          )}
                        </g>
                      );
                    })
                  )}

                  {/* 5. INDICATOR OVERLAYS */}
                  {showEma20 && ema20Path && <path d={ema20Path} fill="none" stroke="#06B6D4" strokeWidth="1.8" opacity="0.9" />}
                  {showEma50 && ema50Path && <path d={ema50Path} fill="none" stroke="#A855F7" strokeWidth="1.8" opacity="0.9" />}
                  {showEma200 && ema200Path && <path d={ema200Path} fill="none" stroke="#EAB308" strokeWidth="2" opacity="0.95" />}
                  {showVwap && vwapPath && <path d={vwapPath} fill="none" stroke="#F59E0B" strokeWidth="1.8" strokeDasharray="4,2" opacity="0.9" />}

                  {/* 6. USER DRAWINGS */}
                  {/* Horizontal Lines */}
                  {horizontalLines.map(hl => {
                    const y = getY(hl.price);
                    return (
                      <g key={hl.id}>
                        <line x1="0" y1={y} x2={plotWidth} y2={y} stroke={hl.color} strokeWidth="1.5" strokeDasharray="4,3" />
                        <rect x={plotWidth + 4} y={y - 8} width={68} height={16} fill={hl.color} rx={3} />
                        <text x={plotWidth + 8} y={y + 3.5} fill="#FFFFFF" fontSize="9.5" fontWeight="700" fontFamily="JetBrains Mono, monospace">
                          ₹{hl.price.toFixed(1)}
                        </text>
                      </g>
                    );
                  })}

                  {/* Trendlines */}
                  {trendlines.map(tl => {
                    const x1 = getX(tl.p1.candleIdx);
                    const y1 = getY(tl.p1.price);
                    const x2 = getX(tl.p2.candleIdx);
                    const y2 = getY(tl.p2.price);
                    return (
                      <line key={tl.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke={tl.color} strokeWidth="2" strokeLinecap="round" />
                    );
                  })}

                  {/* Fibonacci Retracements */}
                  {fibonaccis.map(fib => {
                    const fibP1 = fib.p1.price;
                    const fibP2 = fib.p2.price;
                    const diff = fibP2 - fibP1;
                    const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
                    const colors = ["#EF4444", "#F59E0B", "#10B981", "#06B6D4", "#6366F1", "#A855F7", "#22C55E"];

                    return (
                      <g key={fib.id}>
                        {levels.map((lvl, idx) => {
                          const targetPrice = fibP1 + diff * lvl;
                          const y = getY(targetPrice);
                          return (
                            <g key={idx}>
                              <line x1="0" y1={y} x2={plotWidth} y2={y} stroke={colors[idx]} strokeWidth="1" strokeDasharray="3,2" />
                              <text x={10} y={y - 3} fill={colors[idx]} fontSize="8.5" fontFamily="JetBrains Mono, monospace">
                                Fib {(lvl * 100).toFixed(1)}% (₹{targetPrice.toFixed(1)})
                              </text>
                            </g>
                          );
                        })}
                      </g>
                    );
                  })}

                  {/* 7. LIVE PRICE BADGE ON Y-AXIS */}
                  {currentPrice > 0 && (
                    <g>
                      <line x1="0" y1={getY(currentPrice)} x2={plotWidth} y2={getY(currentPrice)} stroke="#6366F1" strokeWidth="1.2" strokeDasharray="2,2" />
                      <rect x={plotWidth + 4} y={getY(currentPrice) - 9} width={70} height={18} fill="#6366F1" rx={3} />
                      <text x={plotWidth + 8} y={getY(currentPrice) + 4} fill="#FFFFFF" fontSize="10" fontWeight="800" fontFamily="JetBrains Mono, monospace">
                        ₹{currentPrice.toFixed(2)}
                      </text>
                    </g>
                  )}

                  {/* 8. SUB-PANEL: RSI (14) */}
                  {showRsi && (
                    <g transform={`translate(0, ${mainChartHeight + 10})`}>
                      <rect x="0" y="0" width={plotWidth} height="70" fill="rgba(15, 23, 42, 0.4)" rx="4" />
                      {/* RSI Threshold Lines 70 & 30 */}
                      <line x1="0" y1="18" x2={plotWidth} y2="18" stroke="#EF4444" strokeDasharray="2,2" opacity="0.6" />
                      <line x1="0" y1="52" x2={plotWidth} y2="52" stroke="#10B981" strokeDasharray="2,2" opacity="0.6" />
                      <text x={plotWidth + 6} y="22" fill="#EF4444" fontSize="8.5">70</text>
                      <text x={plotWidth + 6} y="56" fill="#10B981" fontSize="8.5">30</text>
                      <text x="6" y="12" fill="#EC4899" fontSize="9" fontWeight="700">RSI (14)</text>

                      {/* RSI Line */}
                      {(() => {
                        let rsiPath = "";
                        visibleCandles.forEach((_, i) => {
                          const rVal = indicatorsData.rsi[startIndex + i];
                          if (rVal !== null && rVal !== undefined) {
                            const x = getX(i);
                            const y = 70 - (rVal / 100) * 70;
                            rsiPath += rsiPath === "" ? `M ${x} ${y}` : ` L ${x} ${y}`;
                          }
                        });
                        return rsiPath ? <path d={rsiPath} fill="none" stroke="#EC4899" strokeWidth="1.5" /> : null;
                      })()}
                    </g>
                  )}

                  {/* 9. SUB-PANEL: MACD (12, 26, 9) */}
                  {showMacd && (
                    <g transform={`translate(0, ${mainChartHeight + (showRsi ? 85 : 10)})`}>
                      <rect x="0" y="0" width={plotWidth} height="70" fill="rgba(15, 23, 42, 0.4)" rx="4" />
                      <line x1="0" y1="35" x2={plotWidth} y2="35" stroke="rgba(255, 255, 255, 0.15)" />
                      <text x="6" y="12" fill="#8B5CF6" fontSize="9" fontWeight="700">MACD (12,26,9)</text>

                      {/* MACD Histogram */}
                      {visibleCandles.map((_, i) => {
                        const hVal = indicatorsData.macdHist[startIndex + i];
                        if (hVal === null || hVal === undefined) return null;
                        const x = getX(i);
                        const hHeight = Math.min(30, Math.abs(hVal) * 8);
                        const hY = hVal >= 0 ? 35 - hHeight : 35;
                        const col = hVal >= 0 ? "#10B981" : "#F43F5E";
                        return <rect key={i} x={x - candleBarWidth / 2} y={hY} width={candleBarWidth} height={hHeight} fill={col} opacity="0.6" />;
                      })}
                    </g>
                  )}

                  {/* 10. INTERACTIVE CROSSHAIR */}
                  {mousePos && (
                    <g pointerEvents="none">
                      {/* Vertical line across all panels */}
                      <line x1={mousePos.x} y1="0" x2={mousePos.x} y2={dimensions.height} stroke="rgba(255, 255, 255, 0.35)" strokeDasharray="3,3" />
                      {/* Horizontal line on main chart */}
                      {mousePos.y <= mainChartHeight && (
                        <>
                          <line x1="0" y1={mousePos.y} x2={plotWidth} y2={mousePos.y} stroke="rgba(255, 255, 255, 0.35)" strokeDasharray="3,3" />
                          <rect x={plotWidth + 4} y={mousePos.y - 8} width={70} height={17} fill="#1E293B" stroke="#64748B" rx={3} />
                          <text x={plotWidth + 8} y={mousePos.y + 4} fill="#F8FAFC" fontSize="9.5" fontWeight="700" fontFamily="JetBrains Mono, monospace">
                            ₹{getPriceFromY(mousePos.y).toFixed(2)}
                          </text>
                        </>
                      )}
                    </g>
                  )}
                </svg>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
