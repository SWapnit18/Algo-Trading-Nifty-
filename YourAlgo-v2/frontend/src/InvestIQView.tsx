import React, { useState, useEffect } from "react";

interface InvestIQOverview {
  total_listed_equities: number;
  total_etfs: number;
  total_smes: number;
  credit_ratings_tracked: number;
  corporate_actions_tracked: number;
  data_source: string;
  model_version: string;
  weights: {
    market_model: number;
    financial_model: number;
    news_catalyst: number;
  };
}

interface EquityRanking {
  symbol: string;
  name: string;
  series: string;
  isin: string;
  listing_date: string;
  face_value: number;
  sector: string;
  growth_score: number;
  growth_label: "Strong" | "Positive" | "Neutral" | "Weak";
  score_momentum: number;
  score_financial_health: number;
  score_news: number;
  return_1y: number;
  roe: number;
  debt_to_equity: number;
  pe_ratio: number;
  strengths: string[];
  red_flags: string[];
  rank_overall: number;
}

interface SectorSummary {
  sector: string;
  count: number;
  avg_growth_score: number;
  avg_return_1y: number;
  strong_count: number;
  top_stock: {
    symbol: string;
    name: string;
    score: number;
  };
}

interface ETFItem {
  symbol: string;
  name: string;
  underlying: string;
  category: string;
  isin: string;
  listing_date: string;
  face_value: number;
}

interface CreditRatingItem {
  company_name: string;
  symbol: string;
  agency: string;
  rating: string;
  action: string;
  outlook: string;
  date: string;
}

interface CorporateActionItem {
  company_name: string;
  purpose: string;
  record_date: string;
  isin: string;
}

interface Props {
  onSelectSymbol: (symbol: string) => void;
  onOpenOrder: (symbol: string, side: "BUY" | "SELL") => void;
  showToast: (msg: string, type?: "success" | "error" | "info" | "warning") => void;
}

export function InvestIQView({ onSelectSymbol, onOpenOrder, showToast }: Props) {
  const [activeTab, setActiveTab] = useState<"rankings" | "sectors" | "etfs" | "credit" | "actions">("rankings");

  // Overview stats
  const [overview, setOverview] = useState<InvestIQOverview | null>(null);

  // Rankings state
  const [rankings, setRankings] = useState<EquityRanking[]>([]);
  const [labelCounts, setLabelCounts] = useState<Record<string, number>>({});
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);

  // Filters
  const [search, setSearch] = useState("");
  const [selectedSector, setSelectedSector] = useState("all");
  const [selectedLabel, setSelectedLabel] = useState("all");
  const [sortBy, setSortBy] = useState("rank");
  const [page, setPage] = useState(0);
  const pageSize = 50;

  // Sectors state
  const [sectors, setSectors] = useState<SectorSummary[]>([]);
  const [sectorsLoading, setSectorsLoading] = useState(false);

  // ETFs state
  const [etfs, setEtfs] = useState<ETFItem[]>([]);
  const [etfSearch, setEtfSearch] = useState("");
  const [etfLoading, setEtfLoading] = useState(false);

  // Credit Ratings state
  const [creditRatings, setCreditRatings] = useState<CreditRatingItem[]>([]);
  const [creditSearch, setCreditSearch] = useState("");
  const [creditLoading, setCreditLoading] = useState(false);

  // Corporate Actions state
  const [corporateActions, setCorporateActions] = useState<CorporateActionItem[]>([]);
  const [actionSearch, setActionSearch] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Company Deep-Dive Modal
  const [selectedCompany, setSelectedCompany] = useState<any | null>(null);
  const [companyModalLoading, setCompanyModalLoading] = useState(false);

  // Load Overview once
  useEffect(() => {
    fetch("/api/investiq/overview")
      .then((r) => r.json())
      .then((data) => setOverview(data))
      .catch((err) => console.error("Error loading InvestIQ overview:", err));
  }, []);

  // Fetch Rankings when filters change
  useEffect(() => {
    if (activeTab === "rankings") {
      setLoading(true);
      const params = new URLSearchParams({
        sector: selectedSector,
        label: selectedLabel,
        search: search.trim(),
        sort_by: sortBy,
        limit: String(pageSize),
        offset: String(page * pageSize),
      });

      fetch(`/api/investiq/rankings?${params.toString()}`)
        .then((r) => r.json())
        .then((res) => {
          setRankings(res.data || []);
          setTotalCount(res.total_count || 0);
          setLabelCounts(res.label_counts || {});
        })
        .catch((err) => {
          console.error("Rankings fetch error:", err);
          showToast("Failed to fetch InvestIQ rankings", "error");
        })
        .finally(() => setLoading(false));
    }
  }, [activeTab, selectedSector, selectedLabel, search, sortBy, page]);

  // Fetch Sectors
  useEffect(() => {
    if (activeTab === "sectors" && sectors.length === 0) {
      setSectorsLoading(true);
      fetch("/api/investiq/sectors")
        .then((r) => r.json())
        .then((data) => setSectors(data || []))
        .catch((err) => console.error(err))
        .finally(() => setSectorsLoading(false));
    }
  }, [activeTab, sectors.length]);

  // Fetch ETFs
  useEffect(() => {
    if (activeTab === "etfs" && etfs.length === 0) {
      setEtfLoading(true);
      fetch("/api/investiq/etfs")
        .then((r) => r.json())
        .then((data) => setEtfs(data || []))
        .catch((err) => console.error(err))
        .finally(() => setEtfLoading(false));
    }
  }, [activeTab, etfs.length]);

  // Fetch Credit Ratings
  useEffect(() => {
    if (activeTab === "credit" && creditRatings.length === 0) {
      setCreditLoading(true);
      fetch("/api/investiq/credit-ratings")
        .then((r) => r.json())
        .then((data) => setCreditRatings(data || []))
        .catch((err) => console.error(err))
        .finally(() => setCreditLoading(false));
    }
  }, [activeTab, creditRatings.length]);

  // Fetch Corporate Actions
  useEffect(() => {
    if (activeTab === "actions" && corporateActions.length === 0) {
      setActionLoading(true);
      fetch("/api/investiq/corporate-actions")
        .then((r) => r.json())
        .then((data) => setCorporateActions(data || []))
        .catch((err) => console.error(err))
        .finally(() => setActionLoading(false));
    }
  }, [activeTab, corporateActions.length]);

  const openCompanyModal = (sym: string) => {
    setCompanyModalLoading(true);
    fetch(`/api/investiq/company/${encodeURIComponent(sym)}`)
      .then((r) => {
        if (!r.ok) throw new Error("Company not found");
        return r.json();
      })
      .then((comp) => setSelectedCompany(comp))
      .catch(() => showToast(`Could not load details for ${sym}`, "error"))
      .finally(() => setCompanyModalLoading(false));
  };

  const getLabelColor = (label: string) => {
    switch (label) {
      case "Strong":
        return "#10B981"; // Emerald
      case "Positive":
        return "#38BDF8"; // Sky Blue
      case "Neutral":
        return "#94A3B8"; // Slate Gray
      case "Weak":
        return "#EF4444"; // Crimson Red
      default:
        return "#6366F1";
    }
  };

  const getLabelBg = (label: string) => {
    switch (label) {
      case "Strong":
        return "rgba(16, 185, 129, 0.15)";
      case "Positive":
        return "rgba(56, 189, 248, 0.15)";
      case "Neutral":
        return "rgba(148, 163, 184, 0.12)";
      case "Weak":
        return "rgba(239, 68, 68, 0.15)";
      default:
        return "rgba(99, 102, 241, 0.15)";
    }
  };

  const SECTOR_OPTIONS = [
    "all",
    "Banking & Finance",
    "Information Technology",
    "Automobile & Auto Ancillary",
    "Energy & Utilities",
    "Pharmaceuticals & Healthcare",
    "Consumer Goods & FMCG",
    "Metals & Mining",
    "Infrastructure & Industrials",
    "Telecommunications",
    "Chemicals & Fertilizers",
    "Diversified Industrials",
  ];

  return (
    <div style={{ maxWidth: 1240, margin: "0 auto", paddingBottom: 60 }} className="fade-in">
      {/* 1. HERO BANNER */}
      <div
        className="glass-card"
        style={{
          borderRadius: 16,
          padding: "24px 28px",
          marginBottom: 20,
          background: "linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%)",
          border: "1px solid rgba(99, 102, 241, 0.25)",
          boxShadow: "0 10px 40px rgba(0, 0, 0, 0.4)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "relative", zIndex: 1, display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  background: "linear-gradient(135deg, #6366F1, #8B5CF6)",
                  color: "#FFFFFF",
                  padding: "4px 10px",
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.5px",
                }}
              >
                INVESTIQ AI v1
              </span>
              <span style={{ fontSize: 11, color: "#10B981", fontWeight: 700 }}>
                ● Official National Stock Exchange of India (NSE) Engine
              </span>
            </div>
            <h1 style={{ fontSize: 24, fontWeight: 900, color: "#F8FAFC", margin: "10px 0 6px 0", letterSpacing: "-0.5px" }}>
              InvestIQ AI Growth & Fundamental Screener
            </h1>
            <p style={{ fontSize: 13, color: "#94A3B8", maxWidth: 680, lineHeight: 1.5, margin: 0 }}>
              Screen 2,600+ NSE main-board equities, 350+ ETFs and 570+ SMEs using institutional multi-factor models.
              Combining price trend momentum (65%), financial health filings (25%), and corporate event catalysts (10%).
            </p>
          </div>

          {/* MODEL WEIGHTS BADGE */}
          <div
            style={{
              background: "rgba(10, 14, 23, 0.8)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: 12,
              padding: "12px 18px",
              minWidth: 260,
            }}
          >
            <div style={{ fontSize: 10, color: "#64748B", fontWeight: 700, letterSpacing: "0.5px", textTransform: "uppercase" }}>
              InvestIQ Model Formula
            </div>
            <div className="num" style={{ fontSize: 13, color: "#F8FAFC", fontWeight: 800, marginTop: 4 }}>
              <span style={{ color: "#38BDF8" }}>0.65 Mkt</span> + <span style={{ color: "#10B981" }}>0.25 Fin</span> + <span style={{ color: "#F59E0B" }}>0.10 News</span>
            </div>
            <div style={{ fontSize: 10.5, color: "#94A3B8", marginTop: 6, display: "flex", gap: 10 }}>
              <span>🟢 Strong ≥ 75</span>
              <span>🔵 Pos ≥ 60</span>
              <span>🔴 Weak &lt; 40</span>
            </div>
          </div>
        </div>

        {/* STATS COUNTERS */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 12,
            marginTop: 22,
            paddingTop: 18,
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          }}
        >
          <div>
            <div style={{ fontSize: 10.5, color: "#64748B", fontWeight: 600 }}>Listed Equities</div>
            <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#F8FAFC" }}>
              {overview?.total_listed_equities?.toLocaleString() || "2,603"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10.5, color: "#64748B", fontWeight: 600 }}>NSE ETFs Tracked</div>
            <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#38BDF8" }}>
              {overview?.total_etfs?.toLocaleString() || "352"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10.5, color: "#64748B", fontWeight: 600 }}>SME Equities</div>
            <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#A78BFA" }}>
              {overview?.total_smes?.toLocaleString() || "579"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10.5, color: "#64748B", fontWeight: 600 }}>Credit Rating Actions</div>
            <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#F59E0B" }}>
              {overview?.credit_ratings_tracked?.toLocaleString() || "250"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10.5, color: "#64748B", fontWeight: 600 }}>Corporate Record Dates</div>
            <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#10B981" }}>
              {overview?.corporate_actions_tracked?.toLocaleString() || "150"}
            </div>
          </div>
        </div>
      </div>

      {/* 2. SUB-NAVIGATION TABS */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, borderBottom: "1px solid rgba(255, 255, 255, 0.08)", paddingBottom: 10 }}>
        {[
          { id: "rankings", label: "🤖 AI Growth Rankings", badge: totalCount ? `${totalCount}` : undefined },
          { id: "sectors", label: "🏢 Sector Heatmap & Top Picks", badge: "11 Sectors" },
          { id: "etfs", label: "📊 NSE ETFs Screener", badge: "352 ETFs" },
          { id: "credit", label: "📰 Credit Rating Actions", badge: "CRISIL/ICRA" },
          { id: "actions", label: "📅 Record Dates & Catalysts", badge: "CDC Dates" },
        ].map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => {
                setActiveTab(t.id as any);
                setPage(0);
              }}
              style={{
                padding: "8px 16px",
                background: active ? "rgba(99, 102, 241, 0.2)" : "rgba(255, 255, 255, 0.03)",
                border: active ? "1px solid #6366F1" : "1px solid rgba(255, 255, 255, 0.06)",
                borderRadius: 8,
                color: active ? "#FFFFFF" : "#94A3B8",
                fontSize: 12.5,
                fontWeight: active ? 800 : 500,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                transition: "all 0.15s ease",
              }}
            >
              <span>{t.label}</span>
              {t.badge && (
                <span
                  style={{
                    fontSize: 9.5,
                    padding: "1px 6px",
                    borderRadius: 4,
                    background: active ? "#6366F1" : "rgba(255, 255, 255, 0.08)",
                    color: active ? "#FFFFFF" : "#CBD5E1",
                    fontWeight: 700,
                  }}
                >
                  {t.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* 3. TAB CONTENT */}
      {/* -------------------- TAB 1: AI RANKINGS -------------------- */}
      {activeTab === "rankings" && (
        <div>
          {/* FILTER CONTROLS BAR */}
          <div
            className="glass-card"
            style={{
              padding: "16px 20px",
              borderRadius: 12,
              marginBottom: 16,
              display: "flex",
              flexWrap: "wrap",
              gap: 14,
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            {/* Search Input */}
            <div style={{ flex: "1 1 240px", minWidth: 200, position: "relative" }}>
              <input
                type="text"
                placeholder="Search symbol (e.g. RELIANCE, TCS) or name..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
                style={{
                  width: "100%",
                  padding: "9px 14px",
                  background: "rgba(10, 14, 23, 0.8)",
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  borderRadius: 8,
                  color: "#F8FAFC",
                  fontSize: 12.5,
                  outline: "none",
                }}
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  style={{ position: "absolute", right: 10, top: 10, background: "transparent", border: "none", color: "#64748B", cursor: "pointer" }}
                >
                  ✕
                </button>
              )}
            </div>

            {/* Sector Dropdown */}
            <div style={{ flex: "0 1 200px" }}>
              <select
                value={selectedSector}
                onChange={(e) => {
                  setSelectedSector(e.target.value);
                  setPage(0);
                }}
                style={{
                  width: "100%",
                  padding: "9px 12px",
                  background: "rgba(10, 14, 23, 0.8)",
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  borderRadius: 8,
                  color: "#F8FAFC",
                  fontSize: 12,
                  outline: "none",
                  cursor: "pointer",
                }}
              >
                {SECTOR_OPTIONS.map((sec) => (
                  <option key={sec} value={sec} style={{ background: "#0F172A", color: "#F8FAFC" }}>
                    {sec === "all" ? "All Sectors" : sec}
                  </option>
                ))}
              </select>
            </div>

            {/* Growth Label Filter Pills */}
            <div style={{ display: "flex", gap: 6 }}>
              {[
                { id: "all", label: "All" },
                { id: "Strong", label: `Strong (${labelCounts["Strong"] || 0})`, color: "#10B981" },
                { id: "Positive", label: `Positive (${labelCounts["Positive"] || 0})`, color: "#38BDF8" },
                { id: "Neutral", label: `Neutral (${labelCounts["Neutral"] || 0})`, color: "#94A3B8" },
                { id: "Weak", label: `Weak (${labelCounts["Weak"] || 0})`, color: "#EF4444" },
              ].map((lbl) => {
                const active = selectedLabel === lbl.id;
                return (
                  <button
                    key={lbl.id}
                    onClick={() => {
                      setSelectedLabel(lbl.id);
                      setPage(0);
                    }}
                    style={{
                      padding: "6px 12px",
                      background: active ? (lbl.color ? `${lbl.color}25` : "rgba(255,255,255,0.15)") : "rgba(255,255,255,0.03)",
                      border: active ? `1px solid ${lbl.color || "#FFFFFF"}` : "1px solid rgba(255,255,255,0.08)",
                      borderRadius: 6,
                      color: active ? "#FFFFFF" : lbl.color || "#94A3B8",
                      fontSize: 11.5,
                      fontWeight: active ? 800 : 500,
                      cursor: "pointer",
                    }}
                  >
                    {lbl.label}
                  </button>
                );
              })}
            </div>

            {/* Sort Select */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, color: "#64748B", fontWeight: 600 }}>Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                style={{
                  padding: "7px 10px",
                  background: "rgba(10, 14, 23, 0.8)",
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  borderRadius: 6,
                  color: "#F8FAFC",
                  fontSize: 11.5,
                  outline: "none",
                  cursor: "pointer",
                }}
              >
                <option value="rank" style={{ background: "#0F172A" }}>InvestIQ Rank (#1...)</option>
                <option value="score" style={{ background: "#0F172A" }}>Growth Score (High-Low)</option>
                <option value="momentum" style={{ background: "#0F172A" }}>Momentum Score</option>
                <option value="return_1y" style={{ background: "#0F172A" }}>1-Year Return %</option>
              </select>
            </div>
          </div>

          {/* TABLE CONTAINER */}
          <div className="glass-card" style={{ borderRadius: 12, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
                <thead>
                  <tr style={{ background: "rgba(255, 255, 255, 0.02)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    <th style={{ padding: "12px 16px" }}>Rank</th>
                    <th style={{ padding: "12px 16px" }}>Company / Symbol</th>
                    <th style={{ padding: "12px 16px" }}>Sector</th>
                    <th style={{ padding: "12px 16px" }}>Growth Score</th>
                    <th style={{ padding: "12px 16px" }}>Classification</th>
                    <th style={{ padding: "12px 16px" }}>Factor Split (Mom / Fin / News)</th>
                    <th style={{ padding: "12px 16px" }}>1Y Return</th>
                    <th style={{ padding: "12px 16px" }}>ROE %</th>
                    <th style={{ padding: "12px 16px", textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={9} style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>
                        <div style={{ display: "inline-block", width: 24, height: 24, border: "2px solid #6366F1", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                        <div style={{ marginTop: 10, fontSize: 12 }}>Evaluating 2,600+ equities through InvestIQ models...</div>
                      </td>
                    </tr>
                  ) : rankings.length === 0 ? (
                    <tr>
                      <td colSpan={9} style={{ padding: 40, textAlign: "center", color: "#64748B" }}>
                        No companies matched the current filter criteria.
                      </td>
                    </tr>
                  ) : (
                    rankings.map((eq) => {
                      const color = getLabelColor(eq.growth_label);
                      const bg = getLabelBg(eq.growth_label);
                      return (
                        <tr
                          key={eq.symbol}
                          style={{
                            borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                            transition: "background 0.15s ease",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                        >
                          {/* Rank */}
                          <td style={{ padding: "14px 16px" }}>
                            <span
                              className="num"
                              style={{
                                background: eq.rank_overall <= 10 ? "rgba(245, 158, 11, 0.2)" : "rgba(255, 255, 255, 0.06)",
                                color: eq.rank_overall <= 10 ? "#F59E0B" : "#94A3B8",
                                padding: "3px 8px",
                                borderRadius: 6,
                                fontWeight: 800,
                                fontSize: 11,
                              }}
                            >
                              #{eq.rank_overall}
                            </span>
                          </td>

                          {/* Symbol & Name */}
                          <td style={{ padding: "14px 16px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <span
                                onClick={() => openCompanyModal(eq.symbol)}
                                style={{ fontWeight: 800, color: "#F8FAFC", cursor: "pointer", textDecoration: "underline", textDecorationColor: "rgba(99, 102, 241, 0.4)" }}
                              >
                                {eq.symbol}
                              </span>
                              <span style={{ fontSize: 10, color: "#64748B", background: "rgba(255,255,255,0.05)", padding: "1px 5px", borderRadius: 4 }}>
                                {eq.series}
                              </span>
                            </div>
                            <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 2, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {eq.name}
                            </div>
                          </td>

                          {/* Sector */}
                          <td style={{ padding: "14px 16px", color: "#CBD5E1", fontSize: 12 }}>
                            {eq.sector}
                          </td>

                          {/* Growth Score */}
                          <td style={{ padding: "14px 16px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <span className="num" style={{ fontSize: 15, fontWeight: 900, color: color }}>
                                {eq.growth_score.toFixed(1)}
                              </span>
                              <div style={{ width: 50, height: 6, background: "rgba(255, 255, 255, 0.08)", borderRadius: 3, overflow: "hidden" }}>
                                <div style={{ width: `${Math.min(100, eq.growth_score)}%`, height: "100%", background: color }} />
                              </div>
                            </div>
                          </td>

                          {/* Label Badge */}
                          <td style={{ padding: "14px 16px" }}>
                            <span
                              style={{
                                background: bg,
                                color: color,
                                border: `1px solid ${color}40`,
                                padding: "2px 8px",
                                borderRadius: 6,
                                fontSize: 11,
                                fontWeight: 800,
                              }}
                            >
                              {eq.growth_label}
                            </span>
                          </td>

                          {/* Factor Split */}
                          <td style={{ padding: "14px 16px" }}>
                            <div className="num" style={{ fontSize: 11, color: "#94A3B8", display: "flex", gap: 6 }}>
                              <span title="Momentum Score" style={{ color: "#38BDF8" }}>M:{eq.score_momentum}</span>
                              <span>•</span>
                              <span title="Financial Health Score" style={{ color: "#10B981" }}>F:{eq.score_financial_health}</span>
                              <span>•</span>
                              <span title="News Catalyst Score" style={{ color: "#F59E0B" }}>N:{eq.score_news}</span>
                            </div>
                          </td>

                          {/* 1Y Return */}
                          <td style={{ padding: "14px 16px" }}>
                            <span
                              className="num"
                              style={{
                                color: eq.return_1y >= 0 ? "#10B981" : "#EF4444",
                                fontWeight: 700,
                              }}
                            >
                              {eq.return_1y >= 0 ? `+${eq.return_1y}%` : `${eq.return_1y}%`}
                            </span>
                          </td>

                          {/* ROE */}
                          <td style={{ padding: "14px 16px" }}>
                            <span className="num" style={{ color: "#F8FAFC", fontWeight: 600 }}>
                              {eq.roe}%
                            </span>
                          </td>

                          {/* Actions */}
                          <td style={{ padding: "14px 16px", textAlign: "right" }}>
                            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                              <button
                                onClick={() => openCompanyModal(eq.symbol)}
                                title="Detailed Analysis & Red Flags"
                                style={{
                                  padding: "5px 10px",
                                  background: "rgba(99, 102, 241, 0.15)",
                                  border: "1px solid rgba(99, 102, 241, 0.3)",
                                  borderRadius: 6,
                                  color: "#A5B4FC",
                                  fontSize: 11,
                                  fontWeight: 700,
                                  cursor: "pointer",
                                }}
                              >
                                View
                              </button>
                              <button
                                onClick={() => onSelectSymbol(eq.symbol)}
                                title="Open Live Chart in Market View"
                                style={{
                                  padding: "5px 10px",
                                  background: "rgba(255, 255, 255, 0.05)",
                                  border: "1px solid rgba(255, 255, 255, 0.1)",
                                  borderRadius: 6,
                                  color: "#CBD5E1",
                                  fontSize: 11,
                                  cursor: "pointer",
                                }}
                              >
                                Chart ↗
                              </button>
                              <button
                                onClick={() => onOpenOrder(eq.symbol, "BUY")}
                                title="Execute Upstox / Paper Order"
                                style={{
                                  padding: "5px 10px",
                                  background: "rgba(16, 185, 129, 0.15)",
                                  border: "1px solid rgba(16, 185, 129, 0.3)",
                                  borderRadius: 6,
                                  color: "#10B981",
                                  fontSize: 11,
                                  fontWeight: 800,
                                  cursor: "pointer",
                                }}
                              >
                                Trade
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* PAGINATION */}
            <div
              style={{
                padding: "14px 20px",
                borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "rgba(10, 14, 23, 0.5)",
              }}
            >
              <div style={{ fontSize: 12, color: "#64748B" }}>
                Showing <strong style={{ color: "#F8FAFC" }}>{rankings.length ? page * pageSize + 1 : 0}</strong> to{" "}
                <strong style={{ color: "#F8FAFC" }}>{page * pageSize + rankings.length}</strong> of{" "}
                <strong style={{ color: "#F8FAFC" }}>{totalCount.toLocaleString()}</strong> companies
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  style={{
                    padding: "6px 14px",
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: 6,
                    color: page === 0 ? "#475569" : "#CBD5E1",
                    fontSize: 12,
                    cursor: page === 0 ? "not-allowed" : "pointer",
                  }}
                >
                  ◀ Previous
                </button>
                <button
                  disabled={(page + 1) * pageSize >= totalCount}
                  onClick={() => setPage((p) => p + 1)}
                  style={{
                    padding: "6px 14px",
                    background: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: 6,
                    color: (page + 1) * pageSize >= totalCount ? "#475569" : "#CBD5E1",
                    fontSize: 12,
                    cursor: (page + 1) * pageSize >= totalCount ? "not-allowed" : "pointer",
                  }}
                >
                  Next ▶
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* -------------------- TAB 2: SECTORS -------------------- */}
      {activeTab === "sectors" && (
        <div>
          {sectorsLoading ? (
            <div style={{ padding: 60, textAlign: "center", color: "#94A3B8" }}>
              Computing aggregate sector models...
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
              {sectors.map((sec) => (
                <div
                  key={sec.sector}
                  className="glass-card"
                  style={{
                    padding: "20px 22px",
                    borderRadius: 14,
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 800, color: "#F8FAFC" }}>{sec.sector}</div>
                        <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>{sec.count} companies listed</div>
                      </div>
                      <span
                        className="num"
                        style={{
                          fontSize: 18,
                          fontWeight: 900,
                          color: sec.avg_growth_score >= 65 ? "#10B981" : "#38BDF8",
                        }}
                      >
                        {sec.avg_growth_score}
                      </span>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 16, background: "rgba(10, 14, 23, 0.6)", padding: 12, borderRadius: 8 }}>
                      <div>
                        <div style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase" }}>Avg 1Y Return</div>
                        <div className="num" style={{ fontSize: 13, fontWeight: 700, color: sec.avg_return_1y >= 0 ? "#10B981" : "#EF4444" }}>
                          {sec.avg_return_1y >= 0 ? `+${sec.avg_return_1y}%` : `${sec.avg_return_1y}%`}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase" }}>Strong Pick Count</div>
                        <div className="num" style={{ fontSize: 13, fontWeight: 700, color: "#10B981" }}>
                          {sec.strong_count} stocks
                        </div>
                      </div>
                    </div>

                    {sec.top_stock && (
                      <div style={{ marginTop: 14, fontSize: 11.5, color: "#94A3B8" }}>
                        Top Ranked: <strong style={{ color: "#F8FAFC" }}>{sec.top_stock.symbol}</strong> ({sec.top_stock.score} score)
                      </div>
                    )}
                  </div>

                  <div style={{ marginTop: 18, paddingTop: 12, borderTop: "1px solid rgba(255, 255, 255, 0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <button
                      onClick={() => {
                        setSelectedSector(sec.sector);
                        setActiveTab("rankings");
                      }}
                      style={{
                        padding: "6px 14px",
                        background: "rgba(99, 102, 241, 0.15)",
                        border: "1px solid rgba(99, 102, 241, 0.3)",
                        borderRadius: 6,
                        color: "#818CF8",
                        fontSize: 11.5,
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      Filter Sector Equities →
                    </button>
                    {sec.top_stock && (
                      <button
                        onClick={() => openCompanyModal(sec.top_stock.symbol)}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: "#94A3B8",
                          fontSize: 11,
                          cursor: "pointer",
                          textDecoration: "underline",
                        }}
                      >
                        Inspect Top Pick
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* -------------------- TAB 3: ETFS -------------------- */}
      {activeTab === "etfs" && (
        <div>
          <div className="glass-card" style={{ padding: "14px 20px", borderRadius: 12, marginBottom: 16, display: "flex", gap: 14 }}>
            <input
              type="text"
              placeholder="Search ETFs by symbol, asset, or category..."
              value={etfSearch}
              onChange={(e) => setEtfSearch(e.target.value)}
              style={{
                flex: 1,
                padding: "9px 14px",
                background: "rgba(10, 14, 23, 0.8)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                borderRadius: 8,
                color: "#F8FAFC",
                fontSize: 12.5,
                outline: "none",
              }}
            />
          </div>

          <div className="glass-card" style={{ borderRadius: 12, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
                <thead>
                  <tr style={{ background: "rgba(255, 255, 255, 0.02)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: 11, textTransform: "uppercase" }}>
                    <th style={{ padding: "12px 16px" }}>Symbol</th>
                    <th style={{ padding: "12px 16px" }}>Security Name</th>
                    <th style={{ padding: "12px 16px" }}>Underlying Asset</th>
                    <th style={{ padding: "12px 16px" }}>Category</th>
                    <th style={{ padding: "12px 16px" }}>ISIN</th>
                    <th style={{ padding: "12px 16px" }}>Listing Date</th>
                    <th style={{ padding: "12px 16px", textAlign: "right" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {etfLoading ? (
                    <tr>
                      <td colSpan={7} style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>Loading ETFs...</td>
                    </tr>
                  ) : (
                    etfs
                      .filter((e) => {
                        const q = etfSearch.toLowerCase();
                        return !q || e.symbol.toLowerCase().includes(q) || e.name.toLowerCase().includes(q) || e.underlying.toLowerCase().includes(q);
                      })
                      .slice(0, 100)
                      .map((etf) => (
                        <tr key={etf.symbol} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "12px 16px", fontWeight: 800, color: "#38BDF8" }}>{etf.symbol}</td>
                          <td style={{ padding: "12px 16px", color: "#F8FAFC" }}>{etf.name}</td>
                          <td style={{ padding: "12px 16px", color: "#CBD5E1" }}>{etf.underlying}</td>
                          <td style={{ padding: "12px 16px" }}>
                            <span style={{ background: "rgba(56, 189, 248, 0.15)", color: "#38BDF8", padding: "2px 6px", borderRadius: 4, fontSize: 10.5, fontWeight: 700 }}>
                              {etf.category}
                            </span>
                          </td>
                          <td style={{ padding: "12px 16px", color: "#64748B", fontSize: 11 }}>{etf.isin}</td>
                          <td style={{ padding: "12px 16px", color: "#94A3B8", fontSize: 11 }}>{etf.listing_date}</td>
                          <td style={{ padding: "12px 16px", textAlign: "right" }}>
                            <button
                              onClick={() => onSelectSymbol(etf.symbol)}
                              style={{
                                padding: "4px 8px",
                                background: "rgba(255, 255, 255, 0.05)",
                                border: "1px solid rgba(255, 255, 255, 0.1)",
                                borderRadius: 6,
                                color: "#CBD5E1",
                                fontSize: 11,
                                cursor: "pointer",
                              }}
                            >
                              Chart
                            </button>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* -------------------- TAB 4: CREDIT RATINGS -------------------- */}
      {activeTab === "credit" && (
        <div>
          <div className="glass-card" style={{ padding: "14px 20px", borderRadius: 12, marginBottom: 16, display: "flex", gap: 14 }}>
            <input
              type="text"
              placeholder="Search credit actions by company, rating, or agency (CRISIL, ICRA, CARE...)..."
              value={creditSearch}
              onChange={(e) => setCreditSearch(e.target.value)}
              style={{
                flex: 1,
                padding: "9px 14px",
                background: "rgba(10, 14, 23, 0.8)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                borderRadius: 8,
                color: "#F8FAFC",
                fontSize: 12.5,
                outline: "none",
              }}
            />
          </div>

          <div className="glass-card" style={{ borderRadius: 12, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
                <thead>
                  <tr style={{ background: "rgba(255, 255, 255, 0.02)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: 11, textTransform: "uppercase" }}>
                    <th style={{ padding: "12px 16px" }}>Company</th>
                    <th style={{ padding: "12px 16px" }}>Symbol</th>
                    <th style={{ padding: "12px 16px" }}>Rating Agency</th>
                    <th style={{ padding: "12px 16px" }}>Assigned Rating</th>
                    <th style={{ padding: "12px 16px" }}>Rating Action</th>
                    <th style={{ padding: "12px 16px" }}>Outlook</th>
                    <th style={{ padding: "12px 16px" }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {creditLoading ? (
                    <tr>
                      <td colSpan={7} style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>Loading Credit Actions...</td>
                    </tr>
                  ) : (
                    creditRatings
                      .filter((c) => {
                        const q = creditSearch.toLowerCase();
                        return !q || c.company_name.toLowerCase().includes(q) || c.agency.toLowerCase().includes(q) || c.rating.toLowerCase().includes(q);
                      })
                      .slice(0, 150)
                      .map((cr, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "12px 16px", fontWeight: 700, color: "#F8FAFC" }}>{cr.company_name}</td>
                          <td style={{ padding: "12px 16px", color: "#38BDF8", fontWeight: 700 }}>{cr.symbol || "—"}</td>
                          <td style={{ padding: "12px 16px", color: "#A78BFA" }}>{cr.agency}</td>
                          <td style={{ padding: "12px 16px" }}>
                            <span style={{ background: "rgba(16, 185, 129, 0.15)", color: "#10B981", padding: "2px 8px", borderRadius: 4, fontWeight: 800, fontSize: 11 }}>
                              {cr.rating}
                            </span>
                          </td>
                          <td style={{ padding: "12px 16px", color: "#CBD5E1" }}>{cr.action}</td>
                          <td style={{ padding: "12px 16px", color: cr.outlook.toLowerCase() === "positive" ? "#10B981" : "#94A3B8" }}>{cr.outlook}</td>
                          <td style={{ padding: "12px 16px", color: "#64748B", fontSize: 11 }}>{cr.date}</td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* -------------------- TAB 5: CORPORATE ACTIONS / RECORD DATES -------------------- */}
      {activeTab === "actions" && (
        <div>
          <div className="glass-card" style={{ padding: "14px 20px", borderRadius: 12, marginBottom: 16, display: "flex", gap: 14 }}>
            <input
              type="text"
              placeholder="Search corporate catalysts by company or purpose (Dividend, Bonus, Split, Rights)..."
              value={actionSearch}
              onChange={(e) => setActionSearch(e.target.value)}
              style={{
                flex: 1,
                padding: "9px 14px",
                background: "rgba(10, 14, 23, 0.8)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                borderRadius: 8,
                color: "#F8FAFC",
                fontSize: 12.5,
                outline: "none",
              }}
            />
          </div>

          <div className="glass-card" style={{ borderRadius: 12, overflow: "hidden" }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5, textAlign: "left" }}>
                <thead>
                  <tr style={{ background: "rgba(255, 255, 255, 0.02)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: 11, textTransform: "uppercase" }}>
                    <th style={{ padding: "12px 16px" }}>Company</th>
                    <th style={{ padding: "12px 16px" }}>Purpose / Catalyst Event</th>
                    <th style={{ padding: "12px 16px" }}>Record Date</th>
                    <th style={{ padding: "12px 16px" }}>ISIN</th>
                  </tr>
                </thead>
                <tbody>
                  {actionLoading ? (
                    <tr>
                      <td colSpan={4} style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>Loading Corporate Actions...</td>
                    </tr>
                  ) : (
                    corporateActions
                      .filter((ca) => {
                        const q = actionSearch.toLowerCase();
                        return !q || ca.company_name.toLowerCase().includes(q) || ca.purpose.toLowerCase().includes(q);
                      })
                      .slice(0, 150)
                      .map((act, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                          <td style={{ padding: "12px 16px", fontWeight: 700, color: "#F8FAFC" }}>{act.company_name}</td>
                          <td style={{ padding: "12px 16px", color: "#F59E0B", fontWeight: 600 }}>{act.purpose}</td>
                          <td style={{ padding: "12px 16px", color: "#38BDF8", fontWeight: 700 }}>{act.record_date}</td>
                          <td style={{ padding: "12px 16px", color: "#64748B", fontSize: 11 }}>{act.isin}</td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 4. COMPANY DEEP-DIVE MODAL */}
      {selectedCompany && (
        <div
          onClick={() => setSelectedCompany(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            backdropFilter: "blur(10px)",
            zIndex: 999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="fade-in glass-card"
            style={{
              width: "100%",
              maxWidth: 720,
              maxHeight: "90vh",
              overflowY: "auto",
              borderRadius: 16,
              padding: 28,
              border: "1px solid rgba(99, 102, 241, 0.3)",
              boxShadow: "0 25px 70px rgba(0, 0, 0, 0.8)",
            }}
          >
            {/* Modal Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <h2 style={{ fontSize: 22, fontWeight: 900, color: "#F8FAFC", margin: 0 }}>
                    {selectedCompany.symbol}
                  </h2>
                  <span
                    style={{
                      background: getLabelBg(selectedCompany.growth_label),
                      color: getLabelColor(selectedCompany.growth_label),
                      border: `1px solid ${getLabelColor(selectedCompany.growth_label)}40`,
                      padding: "2px 8px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 800,
                    }}
                  >
                    {selectedCompany.growth_label}
                  </span>
                  <span className="num" style={{ background: "rgba(255,255,255,0.06)", padding: "2px 7px", borderRadius: 6, color: "#94A3B8", fontSize: 11, fontWeight: 700 }}>
                    Rank #{selectedCompany.rank_overall}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: "#94A3B8", marginTop: 4 }}>
                  {selectedCompany.name} • {selectedCompany.sector}
                </div>
              </div>

              <button
                onClick={() => setSelectedCompany(null)}
                style={{
                  background: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 6,
                  color: "#94A3B8",
                  padding: "5px 9px",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>

            {/* Score Overview */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: 10,
                background: "rgba(10, 14, 23, 0.7)",
                padding: 16,
                borderRadius: 12,
                border: "1px solid rgba(255, 255, 255, 0.08)",
                marginBottom: 20,
              }}
            >
              <div>
                <div style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase" }}>InvestIQ Growth Score</div>
                <div className="num" style={{ fontSize: 22, fontWeight: 900, color: getLabelColor(selectedCompany.growth_label), marginTop: 2 }}>
                  {selectedCompany.growth_score}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase" }}>Market Trend</div>
                <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#38BDF8", marginTop: 2 }}>
                  {selectedCompany.score_momentum} / 100
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase" }}>Financial Health</div>
                <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#10B981", marginTop: 2 }}>
                  {selectedCompany.score_financial_health} / 100
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase" }}>News Catalyst</div>
                <div className="num" style={{ fontSize: 18, fontWeight: 800, color: "#F59E0B", marginTop: 2 }}>
                  {selectedCompany.score_news} / 100
                </div>
              </div>
            </div>

            {/* Fundamental Metrics */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
              <div style={{ background: "rgba(255,255,255,0.02)", padding: "10px 14px", borderRadius: 8 }}>
                <div style={{ fontSize: 10.5, color: "#64748B" }}>1-Year Return</div>
                <div className="num" style={{ fontSize: 14, fontWeight: 700, color: selectedCompany.return_1y >= 0 ? "#10B981" : "#EF4444", marginTop: 4 }}>
                  {selectedCompany.return_1y >= 0 ? `+${selectedCompany.return_1y}%` : `${selectedCompany.return_1y}%`}
                </div>
              </div>
              <div style={{ background: "rgba(255,255,255,0.02)", padding: "10px 14px", borderRadius: 8 }}>
                <div style={{ fontSize: 10.5, color: "#64748B" }}>ROE</div>
                <div className="num" style={{ fontSize: 14, fontWeight: 700, color: "#F8FAFC", marginTop: 4 }}>
                  {selectedCompany.roe}%
                </div>
              </div>
              <div style={{ background: "rgba(255,255,255,0.02)", padding: "10px 14px", borderRadius: 8 }}>
                <div style={{ fontSize: 10.5, color: "#64748B" }}>Debt to Equity</div>
                <div className="num" style={{ fontSize: 14, fontWeight: 700, color: "#F8FAFC", marginTop: 4 }}>
                  {selectedCompany.debt_to_equity}x
                </div>
              </div>
              <div style={{ background: "rgba(255,255,255,0.02)", padding: "10px 14px", borderRadius: 8 }}>
                <div style={{ fontSize: 10.5, color: "#64748B" }}>P/E Ratio</div>
                <div className="num" style={{ fontSize: 14, fontWeight: 700, color: "#F8FAFC", marginTop: 4 }}>
                  {selectedCompany.pe_ratio}
                </div>
              </div>
            </div>

            {/* Strengths & Red Flags */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 20 }}>
              <div style={{ background: "rgba(16, 185, 129, 0.05)", border: "1px solid rgba(16, 185, 129, 0.2)", borderRadius: 10, padding: 14 }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: "#10B981", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                  <span>✓</span> Strengths
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#CBD5E1", lineHeight: 1.6 }}>
                  {selectedCompany.strengths?.map((s: string, i: number) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>

              <div style={{ background: "rgba(239, 68, 68, 0.05)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: 10, padding: 14 }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: "#EF4444", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                  <span>!</span> Watchpoints & Red Flags
                </div>
                {selectedCompany.red_flags?.length ? (
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#CBD5E1", lineHeight: 1.6 }}>
                    {selectedCompany.red_flags.map((rf: string, i: number) => (
                      <li key={i}>{rf}</li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ fontSize: 12, color: "#64748B" }}>No elevated structural red flags detected.</div>
                )}
              </div>
            </div>

            {/* Credit Ratings if present */}
            {selectedCompany.credit_ratings?.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: "#F8FAFC", marginBottom: 8 }}>Credit Rating Filings</div>
                <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: 8, padding: 10 }}>
                  {selectedCompany.credit_ratings.map((cr: any, i: number) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, padding: "4px 0", borderBottom: i < selectedCompany.credit_ratings.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none" }}>
                      <span style={{ color: "#CBD5E1" }}>{cr.agency}: <strong style={{ color: "#10B981" }}>{cr.rating}</strong> ({cr.action})</span>
                      <span style={{ color: "#64748B" }}>{cr.date}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions Bar */}
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <button
                onClick={() => {
                  setSelectedCompany(null);
                  onSelectSymbol(selectedCompany.symbol);
                }}
                style={{
                  flex: 1,
                  padding: "10px",
                  background: "rgba(255, 255, 255, 0.08)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: 8,
                  color: "#F8FAFC",
                  fontSize: 12.5,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Open in Chart View ↗
              </button>
              <button
                onClick={() => {
                  const sym = selectedCompany.symbol;
                  setSelectedCompany(null);
                  onOpenOrder(sym, "BUY");
                }}
                style={{
                  flex: 1,
                  padding: "10px",
                  background: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
                  border: "none",
                  borderRadius: 8,
                  color: "#FFFFFF",
                  fontSize: 12.5,
                  fontWeight: 800,
                  cursor: "pointer",
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.3)",
                }}
              >
                Place Upstox / Paper Order
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
