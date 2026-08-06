import { useState, useEffect, useMemo } from "react";
import "./App.css";

const AGENT_ORDER = [
  { key: "finance", label: "Finance", eyebrow: "Budget & Cost" },
  { key: "inventory", label: "Inventory", eyebrow: "Stock & Demand" },
  { key: "logistics", label: "Logistics", eyebrow: "Carrier & Delivery" },
  { key: "risk", label: "Risk Management", eyebrow: "Exposure & Policy" },
];

function positionTone(position) {
  if (!position) return "neutral";
  if (position.includes("REJECT")) return "reject";
  if (position.includes("WARNING") || position.includes("CONDITIONS")) return "warning";
  return "approve";
}

function formatMetricLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\bpct\b/g, "%")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatMetricValue(key, value) {
  if (typeof value === "number") {
    if (key.toLowerCase().includes("cost") || key.toLowerCase().includes("budget")) {
      return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    }
    if (key.toLowerCase().includes("pct")) {
      return `${value}%`;
    }
    return value.toLocaleString();
  }
  return String(value);
}

function ForecastChart({ forecast }) {
  if (!forecast || !forecast.points?.length) return null;

  const width = 640;
  const height = 140;
  const padding = 24;
  const values = forecast.points.map((p) => p.predicted_demand);
  const max = Math.max(...values, forecast.recent_actual_avg) * 1.15 || 1;
  const min = 0;

  const stepX = (width - padding * 2) / (values.length - 1 || 1);
  const scaleY = (v) => height - padding - ((v - min) / (max - min || 1)) * (height - padding * 2);

  const pathD = values
    .map((v, i) => `${i === 0 ? "M" : "L"} ${padding + i * stepX} ${scaleY(v)}`)
    .join(" ");

  const areaD =
    pathD +
    ` L ${padding + (values.length - 1) * stepX} ${height - padding} L ${padding} ${height - padding} Z`;

  const baselineY = scaleY(forecast.recent_actual_avg);

  return (
    <div className="forecast-panel">
      <div className="forecast-head">
        <div>
          <span className="forecast-eyebrow">Demand Forecast &middot; Next {forecast.horizon_days} Days</span>
          <h3>LightGBM Model Projection</h3>
        </div>
        <div className={`trend-chip trend-${forecast.trend}`}>
          {forecast.trend === "increasing" && "\u2191 Rising"}
          {forecast.trend === "decreasing" && "\u2193 Declining"}
          {forecast.trend === "stable" && "\u2192 Stable"}
        </div>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="forecast-svg" preserveAspectRatio="none">
        <line
          x1={padding}
          y1={baselineY}
          x2={width - padding}
          y2={baselineY}
          className="forecast-baseline"
          strokeDasharray="4 4"
        />
        <path d={areaD} className="forecast-area" />
        <path d={pathD} className="forecast-line" />
      </svg>

      <div className="forecast-stats">
        <div>
          <span className="context-label">Forecasted Avg</span>
          <span className="context-value mono">{forecast.avg_forecasted_demand} / day</span>
        </div>
        <div>
          <span className="context-label">Recent Actual Avg</span>
          <span className="context-value mono">{forecast.recent_actual_avg} / day</span>
        </div>
      </div>
      <p className="panel-explainer">
        A machine-learning model trained on this product&rsquo;s sales
        history predicts demand day-by-day for the next {forecast.horizon_days}{" "}
        days. The dashed line marks the recent historical average, so you
        can see at a glance whether the forecast expects demand to pull
        away from it.
      </p>
    </div>
  );
}

function PricingPanel({ pricing, priceChangePct, onChangePct }) {
  if (!pricing) return null;

  if (!pricing.available) {
    return (
      <div className="pricing-panel">
        <span className="forecast-eyebrow">Price Simulation</span>
        <h3>Not enough data</h3>
        <p className="pricing-unavailable">{pricing.reason}</p>
      </div>
    );
  }

  const revenueUp = pricing.predicted_revenue_change_pct >= 0;

  return (
    <div className="pricing-panel">
      <div className="forecast-head">
        <div>
          <span className="forecast-eyebrow">
            Price Simulation &middot; Elasticity {pricing.elasticity}
          </span>
          <h3>What if we change the price?</h3>
        </div>
        <div className={`confidence-chip ${pricing.reliability !== "reliable" ? "is-low" : ""}`}>
          {pricing.reliability === "exploratory_only" && "Exploratory only"}
          {pricing.reliability === "low_reliability" && "Low reliability"}
          {pricing.reliability === "reliable" && "Reliable"}
          {" "}&middot; {Math.round(pricing.confidence * 100)}%
        </div>
      </div>

      <div className="pricing-slider-row">
        <input
          type="range"
          min={-30}
          max={30}
          step={1}
          value={priceChangePct}
          onChange={(e) => onChangePct(Number(e.target.value))}
          className="pricing-slider"
        />
        <span className={`pricing-pct mono ${priceChangePct >= 0 ? "is-up" : "is-down"}`}>
          {priceChangePct > 0 ? "+" : ""}
          {priceChangePct}%
        </span>
      </div>

      <div className="pricing-results">
        <div className="pricing-result-cell">
          <span className="context-label">New Price</span>
          <span className="context-value mono">${pricing.proposed_price}</span>
          <span className="pricing-sub">was ${pricing.current_avg_price}</span>
        </div>
        <div className="pricing-result-cell">
          <span className="context-label">Predicted Demand Change</span>
          <span className={`context-value mono ${pricing.predicted_quantity_change_pct >= 0 ? "is-up" : "is-down"}`}>
            {pricing.predicted_quantity_change_pct > 0 ? "+" : ""}
            {pricing.predicted_quantity_change_pct}%
          </span>
        </div>
        <div className="pricing-result-cell">
          <span className="context-label">Predicted Revenue Change</span>
          <span className={`context-value mono ${revenueUp ? "is-up" : "is-down"}`}>
            {revenueUp ? "+" : ""}
            {pricing.predicted_revenue_change_pct}%
          </span>
        </div>
      </div>

      {pricing.adjusted_requested_quantity !== undefined && (
        <div className="pricing-quantity-link">
          <span className="context-label">Effect on This Order</span>
          <p>
            At the current price, you&rsquo;d order{" "}
            <strong className="mono">{pricing.baseline_requested_quantity}</strong> units.
            At this simulated price, you&rsquo;d need{" "}
            <strong className="mono">{pricing.adjusted_requested_quantity}</strong> units
            {pricing.quantity_change !== 0 && (
              <span className={pricing.quantity_change < 0 ? "is-down" : "is-up"}>
                {" "}({pricing.quantity_change > 0 ? "+" : ""}
                {pricing.quantity_change})
              </span>
            )}
            {" "}&mdash; this is what actually changes if you adjust the price,
            not just the revenue estimate above.
          </p>
        </div>
      )}

      <p className="panel-explainer">
        This estimates how sales would respond to a price change, based on
        how demand actually moved during past discounts for this product.
        An elasticity of {pricing.elasticity} means a 1% price change is
        associated with roughly a {Math.abs(pricing.elasticity)}% change in
        units sold, in the {pricing.elasticity < 0 ? "opposite" : "same"}{" "}
        direction.
      </p>

      <ul className="pricing-caveats">
        {pricing.caveats.map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
    </div>
  );
}

function TrendDiagnosticPanel({ diagnostic }) {
  if (!diagnostic) return null;

  if (!diagnostic.available) {
    return (
      <div className="trend-diag-panel">
        <span className="forecast-eyebrow">Sales Trend Diagnostic</span>
        <h3>Not enough data</h3>
        <p className="pricing-unavailable">{diagnostic.reason}</p>
      </div>
    );
  }

  const tone =
    diagnostic.direction === "increasing" ? "approve" :
    diagnostic.direction === "decreasing" ? "reject" : "neutral";

  const misleading =
    Math.sign(diagnostic.raw_change_pct) !== Math.sign(diagnostic.underlying_trend_change_pct) &&
    Math.abs(diagnostic.raw_change_pct) > 5;

  return (
    <div className="trend-diag-panel">
      <span className="forecast-eyebrow">Sales Trend Diagnostic &middot; STL Decomposition</span>
      <h3>Why is demand changing?</h3>
      <p className="panel-explainer">
        Raw sales numbers can look misleading because of normal weekly
        ups and downs (e.g. weekend spikes). This separates that noise
        out statistically to reveal the real underlying direction.
      </p>

      <div className="trend-diag-numbers">
        <div>
          <span className="context-label">Raw Period-over-Period Change</span>
          <span className="context-value mono">
            {diagnostic.raw_change_pct > 0 ? "+" : ""}
            {diagnostic.raw_change_pct}%
          </span>
        </div>
        <div>
          <span className="context-label">Underlying Trend (seasonality removed)</span>
          <span className={`context-value mono trend-tone-${tone}`}>
            {diagnostic.underlying_trend_change_pct > 0 ? "+" : ""}
            {diagnostic.underlying_trend_change_pct}%
          </span>
        </div>
      </div>

      {misleading && (
        <p className="trend-diag-flag">
          &#9888; The raw change is misleading here &mdash; once normal weekly
          seasonality is removed, the underlying trend actually points the
          opposite direction.
        </p>
      )}

      {diagnostic.category_verdict && (
        <p className="trend-diag-category">
          {diagnostic.category_verdict === "category_wide" ? (
            <>
              <strong>{diagnostic.category}</strong> category overall moved{" "}
              {diagnostic.category_change_pct > 0 ? "+" : ""}
              {diagnostic.category_change_pct}% in the same direction &mdash;
              this looks like a <strong>category-wide</strong> pattern, not
              something specific to this product.
            </>
          ) : (
            <>
              The <strong>{diagnostic.category}</strong> category overall
              didn&rsquo;t move the same way &mdash; this looks{" "}
              <strong>product-specific</strong>, not part of a broader
              market shift.
            </>
          )}
        </p>
      )}

      {diagnostic.correlated_factors.length > 0 ? (
        <div className="trend-diag-factors">
          <span className="context-label">Correlated Factors</span>
          {diagnostic.correlated_factors.map((f, i) => (
            <div className="factor-row" key={i}>
              <span>{f.factor}</span>
              <span className="mono">
                r = {f.correlation} ({f.direction}){" "}
                {f.significant ? "\u2713 significant" : "not significant"}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="pricing-unavailable">
          No factors in the available data (discount level, delivery
          performance) showed a meaningful correlation with this product's
          demand.
        </p>
      )}

      <p className="trend-diag-methodology">{diagnostic.methodology_note}</p>
    </div>
  );
}

function AboutPage() {
  return (
    <div className="about-page">
      <section className="about-section">
        <span className="forecast-eyebrow">Overview</span>
        <h2>What this platform does</h2>
        <p>
          Most business software answers <em>"what happened?"</em> This
          platform is built to answer a harder question: <em>"what should
          we do next, and why?"</em> It focuses on one concrete decision --
          inventory replenishment -- and treats it the way a real
          management team would: by convening specialists from different
          departments, letting them disagree, and resolving that
          disagreement into one accountable recommendation, rather than
          asking a single model for an answer.
        </p>
        <p>
          The manager doesn&rsquo;t type in sales figures, budgets, or
          supplier lead times. That data already exists in the company&rsquo;s
          own records. The manager only chooses <strong>what</strong> to
          decide about (a product) and <strong>what matters most</strong>{" "}
          (the business objective) -- everything else is drawn from real
          operational data.
        </p>
      </section>

      <section className="about-section">
        <span className="forecast-eyebrow">Data Source</span>
        <h2>Where the numbers come from</h2>
        <p>
          Products, daily sales, and carrier reliability are derived from
          the <strong>DataCo Smart Supply Chain dataset</strong> (Constante,
          Silva &amp; Pereira, 2019) -- 180,519 real order records. Carrier
          reliability, in particular, is not an assumed number: it&rsquo;s
          computed directly from real observed on-time delivery rates for
          each shipping mode.
        </p>
        <p>
          Inventory levels and budget figures are <strong>calibrated
          assumptions</strong>, scaled off real demand and revenue in the
          dataset, since no public dataset contains a specific company&rsquo;s
          live stock or internal financial data. This is stated here
          plainly rather than left implicit.
        </p>
      </section>

      <section className="about-section">
        <span className="forecast-eyebrow">Architecture</span>
        <h2>How a decision gets made</h2>
        <ol className="about-steps">
          <li>
            <strong>Product &amp; Objective Selected</strong> &mdash; you pick
            a product and what the business is optimizing for (avoiding
            stock-outs, minimizing holding cost, or a balance).
          </li>
          <li>
            <strong>Context Built</strong> &mdash; the system pulls this
            product&rsquo;s real inventory, sales history, and supplier
            options, and forecasts expected demand over the full supplier
            lead time using a trained model.
          </li>
          <li>
            <strong>Four Departments Analyze Independently</strong> &mdash;
            Finance, Inventory, Logistics, and Risk each evaluate the same
            situation from their own priorities, using real calculations
            (not just an opinion), and each states a position and a
            confidence level grounded in the numbers.
          </li>
          <li>
            <strong>Deliberation</strong> &mdash; Finance and Risk hold veto
            power over unsafe or unaffordable decisions. When nobody
            vetoes, the four confidence scores are combined using the
            organization&rsquo;s own department-weighting policy into one
            resolved recommendation.
          </li>
          <li>
            <strong>Executive Summary</strong> &mdash; the final
            recommendation is written by combining that department
            decision with the demand forecast and the sales trend
            diagnostic -- every sentence traces back to a number you can
            see elsewhere on the page.
          </li>
        </ol>
      </section>

      <section className="about-section">
        <span className="forecast-eyebrow">Analytical Methods</span>
        <h2>What powers each panel</h2>
        <dl className="about-methods">
          <div>
            <dt>Demand Forecast</dt>
            <dd>
              A LightGBM gradient-boosted model trained on each product&rsquo;s
              own lag and rolling-window sales features, evaluated with a
              time-based (not random) train/test split to avoid leaking
              future data into training.
            </dd>
          </div>
          <div>
            <dt>Price Simulation</dt>
            <dd>
              Price elasticity estimated via log-log regression on real
              historical discount-driven price changes -- the standard
              microeconomic method for estimating a demand curve.
              Confidence is tied directly to the regression&rsquo;s R&sup2;,
              so a weak historical relationship is shown as weak, not
              hidden behind a confident-looking number.
            </dd>
          </div>
          <div>
            <dt>Sales Trend Diagnostic</dt>
            <dd>
              STL decomposition (Cleveland et al., 1990) separates a
              product&rsquo;s genuine trend from ordinary weekly seasonality.
              Correlation (not causation) with discount level and delivery
              performance is then tested statistically, and a category-wide
              comparison distinguishes a product-specific issue from a
              market-wide shift.
            </dd>
          </div>
        </dl>
      </section>

      <section className="about-section">
        <span className="forecast-eyebrow">Design Decisions</span>
        <h2>Questions this platform can answer about itself</h2>
        <div className="about-faq">
          <div>
            <p className="faq-q">Why a time-based split instead of a random one?</p>
            <p className="faq-a">
              Random splits let information from adjacent days leak into
              training through rolling-average features, producing
              artificially good accuracy that wouldn&rsquo;t hold on genuinely
              future data. Every model in this project is evaluated the
              way it would actually be used: predicting forward in time.
            </p>
          </div>
          <div>
            <p className="faq-q">Why is the price elasticity confidence sometimes low?</p>
            <p className="faq-a">
              Because it genuinely is, for many products -- R&sup2; values of
              0.03&ndash;0.09 mean price explains only a small share of
              historical demand variation. That&rsquo;s reported honestly
              rather than smoothed over, because a system that hides its
              own uncertainty is less trustworthy, not more.
            </p>
          </div>
          <div>
            <p className="faq-q">Why do agents sometimes disagree with the final recommendation?</p>
            <p className="faq-a">
              Because real departments do too. The Inventory Agent can
              flag REJECT on its own metrics while the final,
              policy-weighted recommendation still approves -- reflecting
              that Finance, Logistics, and a strong demand trend
              outweighed that single concern, exactly as a real
              management discussion would.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("analyze");
  const [products, setProducts] = useState([]);
  const [objectives, setObjectives] = useState([]);
  const [selectedObjective, setSelectedObjective] = useState("Avoid Stock-out");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [result, setResult] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [pricing, setPricing] = useState(null);
  const [priceChangePct, setPriceChangePct] = useState(10);
  const [trendDiagnostic, setTrendDiagnostic] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [productsError, setProductsError] = useState(null);

  useEffect(() => {
    fetch("/api/v2/demo-company/products")
      .then((r) => {
        if (!r.ok) throw new Error(`Status ${r.status}`);
        return r.json();
      })
      .then((data) => setProducts(data))
      .catch((err) => setProductsError(err.message));

    fetch("/api/v2/demo-company/objectives")
      .then((r) => r.json())
      .then(setObjectives)
      .catch(() => setObjectives([]));
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) return products.slice(0, 12);
    const q = query.toLowerCase();
    return products
      .filter(
        (p) =>
          p.product_name.toLowerCase().includes(q) ||
          p.category.toLowerCase().includes(q) ||
          p.product_id.toLowerCase().includes(q)
      )
      .slice(0, 12);
  }, [products, query]);

  const selectedProduct = products.find((p) => p.product_id === selectedId);

  useEffect(() => {
    if (!selectedId) return;
    const timeout = setTimeout(() => {
      fetch(
        `/api/v2/demo-company/pricing?product_id=${encodeURIComponent(
          selectedId
        )}&price_change_pct=${priceChangePct}`
      )
        .then((r) => r.json())
        .then(setPricing)
        .catch(() => setPricing(null));
    }, 250);
    return () => clearTimeout(timeout);
  }, [selectedId, priceChangePct]);

  async function runAnalysis(productId, objective) {
    const objectiveToUse = objective || selectedObjective;
    setSelectedId(productId);
    setLoading(true);
    setError(null);
    setResult(null);
    setForecast(null);
    setPricing(null);
    setTrendDiagnostic(null);
    try {
      const [decisionRes, forecastRes, trendRes] = await Promise.all([
        fetch(
          `/api/v2/demo-company/?product_id=${encodeURIComponent(
            productId
          )}&business_objective=${encodeURIComponent(objectiveToUse)}`
        ),
        fetch(
          `/api/v2/demo-company/forecast?product_id=${encodeURIComponent(productId)}&days=14`
        ),
        fetch(
          `/api/v2/demo-company/trend-diagnostic?product_id=${encodeURIComponent(productId)}`
        ),
      ]);
      if (!decisionRes.ok) throw new Error(`Request failed with status ${decisionRes.status}`);
      const data = await decisionRes.json();
      setResult(data);

      if (forecastRes.ok) {
        setForecast(await forecastRes.json());
      }
      if (trendRes.ok) {
        setTrendDiagnostic(await trendRes.json());
      }
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function handleObjectiveChange(newObjective) {
    setSelectedObjective(newObjective);
    if (selectedId) {
      runAnalysis(selectedId, newObjective);
    }
  }

  const finalDecision = result?.final_decision;
  const tone = positionTone(finalDecision?.final_position);

  return (
    <div className="shell">
      <header className="masthead">
        <div className="masthead-top">
          <div>
            <div className="masthead-eyebrow">Smart Distribution &middot; Decision Workspace</div>
            <h1>AI Decision Laboratory</h1>
          </div>
          <nav className="view-toggle">
            <button
              className={view === "analyze" ? "is-active" : ""}
              onClick={() => setView("analyze")}
            >
              Analyze
            </button>
            <button
              className={view === "about" ? "is-active" : ""}
              onClick={() => setView("about")}
            >
              How It Works
            </button>
          </nav>
        </div>
        <p className="masthead-sub">
          Select a product to convene the department review &mdash; Finance,
          Inventory, Logistics, and Risk each weigh in before a final
          recommendation is issued.
        </p>
      </header>

      {view === "about" && <AboutPage />}

      {view === "analyze" && (
      <div className="layout">
        <aside className="picker">
          <label className="picker-label" htmlFor="product-search">
            Choose a product
          </label>
          <input
            id="product-search"
            className="picker-input"
            type="text"
            placeholder="Search by name, category, or ID&hellip;"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />

          {productsError && (
            <p className="picker-error">
              Couldn&rsquo;t load products ({productsError}). Is the backend
              running on port 8000?
            </p>
          )}

          <ul className="picker-list">
            {filtered.map((p) => (
              <li key={p.product_id}>
                <button
                  className={
                    "picker-item" + (selectedId === p.product_id ? " is-selected" : "")
                  }
                  onClick={() => runAnalysis(p.product_id)}
                >
                  <span className="picker-item-name">{p.product_name}</span>
                  <span className="picker-item-meta">
                    {p.category} &middot; {p.product_id}
                  </span>
                </button>
              </li>
            ))}
            {filtered.length === 0 && !productsError && (
              <li className="picker-empty">No matching products.</li>
            )}
          </ul>
        </aside>

        <main className="workspace">
          {!selectedId && !loading && (
            <div className="empty-state">
              <span className="empty-mark">&mdash;</span>
              <p>
                Pick a product from the list to start a replenishment
                review.
              </p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <span className="empty-mark loading-mark">&hellip;</span>
              <p>Convening the department review for {selectedProduct?.product_name}&hellip;</p>
            </div>
          )}

          {error && (
            <div className="empty-state error-state">
              <p>Analysis failed: {error}</p>
            </div>
          )}

          {result && !loading && (
            <>
              <div className="context-strip">
                <div>
                  <span className="context-label">Product</span>
                  <span className="context-value">
                    {selectedProduct?.product_name}
                  </span>
                </div>
                <div>
                  <span className="context-label">Objective</span>
                  <select
                    className="objective-select"
                    value={selectedObjective}
                    onChange={(e) => handleObjectiveChange(e.target.value)}
                  >
                    {objectives.map((o) => (
                      <option key={o.objective} value={o.objective}>
                        {o.objective}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <span className="context-label">Requested Qty</span>
                  <span className="context-value mono">
                    {result.decision_context.requested_quantity} units
                  </span>
                </div>
                <div>
                  <span className="context-label">Target Service Level</span>
                  <span className="context-value mono">
                    {Math.round(result.decision_context.target_service_level * 100)}%
                  </span>
                </div>
              </div>

              <ForecastChart forecast={forecast} />

              <PricingPanel
                pricing={pricing}
                priceChangePct={priceChangePct}
                onChangePct={setPriceChangePct}
              />

              <TrendDiagnosticPanel diagnostic={trendDiagnostic} />

              <div className="agent-row">
                {AGENT_ORDER.map(({ key, label, eyebrow }, i) => {
                  const opinion = result.organizational_analysis[key];
                  if (!opinion) return null;
                  const agentTone = positionTone(opinion.position);
                  return (
                    <article
                      key={key}
                      className={`agent-card tone-${agentTone}`}
                      style={{ animationDelay: `${i * 70}ms` }}
                    >
                      <div className="agent-card-head">
                        <span className="agent-eyebrow">{eyebrow}</span>
                        <h3>{label}</h3>
                      </div>
                      <div className={`position-badge tone-${agentTone}`}>
                        {opinion.position}
                      </div>
                      <div className="confidence-row">
                        <span>Confidence</span>
                        <span className="mono">
                          {Math.round(opinion.confidence * 100)}%
                        </span>
                      </div>
                      <div className="confidence-track">
                        <div
                          className={`confidence-fill tone-${agentTone}`}
                          style={{ width: `${opinion.confidence * 100}%` }}
                        />
                      </div>

                      <dl className="metric-list">
                        {Object.entries(opinion.metrics)
                          .slice(0, 4)
                          .map(([k, v]) => (
                            <div className="metric-row" key={k}>
                              <dt>{formatMetricLabel(k)}</dt>
                              <dd className="mono">{formatMetricValue(k, v)}</dd>
                            </div>
                          ))}
                      </dl>

                      {opinion.reasons?.length > 0 && (
                        <p className="agent-reason">{opinion.reasons[0]}</p>
                      )}
                      {opinion.concerns?.length > 0 && (
                        <p className="agent-concern">&#9888; {opinion.concerns[0]}</p>
                      )}
                    </article>
                  );
                })}
              </div>

              <section className={`verdict tone-${tone}`}>
                <div className="verdict-body">
                  <span className="verdict-eyebrow">Final Recommendation</span>
                  <h2>{finalDecision.final_position}</h2>
                  <p className="verdict-reason">
                    {result.executive_summary?.summary || finalDecision.reason}
                  </p>
                  {result.executive_summary && (
                    <p className="verdict-basis">
                      Based on: department review
                      {result.executive_summary.based_on.demand_forecast && " · demand forecast"}
                      {result.executive_summary.based_on.trend_diagnostic && " · sales trend diagnostic"}
                    </p>
                  )}

                  <div className="verdict-votes">
                    {AGENT_ORDER.map(({ key, label }) => (
                      <div className="vote-chip" key={key}>
                        <span
                          className={`vote-dot tone-${positionTone(
                            finalDecision.department_votes[key]
                          )}`}
                        />
                        <span>{label}</span>
                        <span className="vote-position">
                          {finalDecision.department_votes[key]}
                        </span>
                      </div>
                    ))}
                  </div>

                  {finalDecision.concerns?.length > 0 && (
                    <ul className="verdict-concerns">
                      {finalDecision.concerns.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className={`seal tone-${tone}`}>
                  <span className="seal-position">{finalDecision.final_position}</span>
                  <span className="seal-confidence mono">
                    {Math.round(finalDecision.confidence * 100)}% confidence
                  </span>
                </div>
              </section>
            </>
          )}
        </main>
      </div>
      )}
    </div>
  );
}
