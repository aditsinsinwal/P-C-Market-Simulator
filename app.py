    elif np.isfinite(key_delta) and key_delta < -4:
        verdict = "Do not proceed as designed"
    elif worsens > improves:
        verdict = "Needs redesign"

    lines = [
        f"# Strategy Decision Memo: {strategy_name}",
        "",
        f"Company tested: **{company}**",
        "",
        f"Decision read: **{verdict}**.",
        "",
        "## Executive Summary",
        "",
        (
            f"The strategy changes franchise score by {key_delta:+.1f} points, market share by "
            f"{share_delta:+.1%}, recent combined ratio by {combined_delta:+.1%}, and capital ratio by "
            f"{capital_delta:+.2f}x versus the baseline."
        ),
        "",
        (
            f"Across the scorecard, {improves} metric(s) improve and {worsens} metric(s) worsen. "
            "Use this as a directional strategy screen before moving to production actuarial review."
        ),
        "",
        "## KPI Scorecard",
        "",
    ]

    for _, row in comparison.iterrows():
        lines.append(
            f"- {row['metric']}: baseline {row['baseline']:.4g}, strategy {row['strategy']:.4g}, "
            f"delta {row['delta']:+.4g} ({row['read']})"
        )

    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- This is a strategic simulator, not a filed rating plan or reserving model.",
            "- Results depend on synthetic customers and stochastic claims.",
            "- Business use should pair this with real portfolio data, actuarial validation, governance review, and sensitivity testing.",
        ]
    )
    return "\n".join(lines)


def plot_strategy_metric_comparison(
    baseline: dict[str, Any],
    variant: dict[str, Any],
    company: str,
    metric: str,
) -> go.Figure:
    base = baseline["history"][baseline["history"]["company"].eq(company)].copy()
    test = variant["history"][variant["history"]["company"].eq(company)].copy()
    base["case"] = "Baseline"
    test["case"] = "Strategy"
    show = pd.concat([base, test], ignore_index=True)
    fig = px.line(
        show,
        x="year",
        y=metric,
        color="case",
        labels={"year": "Year", metric: metric.replace("_", " ").title(), "case": ""},
        color_discrete_map={"Baseline": "#596273", "Strategy": COLORS.get(company, "#3A5FCD")},
    )
    if metric in {"market_share", "combined_ratio", "loss_ratio", "insolvency_risk"}:
        fig.update_yaxes(tickformat=".0%")
    if metric == "combined_ratio":
        fig.add_hline(y=1.0, line_dash="dash", line_color="#555")
    fig.update_layout(hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10))
    return fig


def sqlite_type_for(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series) or pd.api.types.is_bool_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "REAL"
    return "TEXT"


def ensure_sqlite_columns(con: sqlite3.Connection, table_name: str, df: pd.DataFrame) -> None:
    existing = pd.read_sql_query(f'PRAGMA table_info("{table_name}")', con)
    if existing.empty:
        return

    existing_cols = set(existing["name"])
    for col in df.columns:
        if col not in existing_cols:
            col_type = sqlite_type_for(df[col])
            con.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" {col_type}')


def save_run_to_sqlite(result: dict[str, Any]) -> str:
    run_id = f"run_{int(time.time())}_{result['params']['seed']}"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS run_meta (
                run_id TEXT PRIMARY KEY,
                created_at TEXT,
                n_customers INTEGER,
                years INTEGER,
                seed INTEGER,
                regulator_on INTEGER,
                annual_inflation REAL,
                fraud_pressure REAL,
                catastrophe_volatility REAL,
                competition_intensity REAL,
                winner TEXT
            )
            """
        )
        params = result["params"]
        winner = str(result["final"].iloc[0]["company"])
        con.execute(
            """
            INSERT OR REPLACE INTO run_meta
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                params["n_customers"],
                params["years"],
                params["seed"],
                int(params["regulator_on"]),
                params["annual_inflation"],
                params["fraud_pressure"],
                params["catastrophe_volatility"],
                params["competition_intensity"],
                winner,
            ),
        )

        for key, table_name in [
            ("history", "monthly_company_metrics"),
            ("market", "monthly_market_metrics"),
            ("events", "market_events"),
            ("final", "final_company_summary"),
        ]:
            df = result[key].copy()
            df.insert(0, "run_id", run_id)
            ensure_sqlite_columns(con, table_name, df)
            df.to_sql(table_name, con, if_exists="append", index=False)

        con.commit()
    finally:
        con.close()
    return run_id


def recent_runs() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(
            "SELECT * FROM run_meta ORDER BY created_at DESC LIMIT 8",
            con,
        )
    finally:
        con.close()


def format_money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def format_kpi_value(metric: str, value: float, signed: bool = False) -> str:
    if not np.isfinite(value):
        return "N/A"

    sign = "+" if signed and value > 0 else ""
    if metric in {"Market share", "Recent combined ratio", "Insolvency risk", "Rate movement"}:
        return f"{sign}{value:.1%}"
    if metric in {"Recent premium", "Recent claims", "Hidden loss cost"}:
        if signed:
            return f"{sign}{format_money(value)}"
        return format_money(value)
    if metric == "Policies":
        return f"{sign}{value:,.0f}"
    if metric == "Capital ratio":
        return f"{sign}{value:.2f}x"
    if metric == "Regulator actions":
        return f"{sign}{value:,.0f}"
    return f"{sign}{value:.1f}"


def plot_market_share(history: pd.DataFrame) -> go.Figure:
    fig = px.area(
        history,
        x="year",
        y="market_share",
        color="company",
        color_discrete_map=COLORS,
        category_orders={"company": COMPANY_ORDER},
        labels={"year": "Year", "market_share": "Market share", "company": "Company"},
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend_title_text="", hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10))
    return fig


def plot_combined_ratio(history: pd.DataFrame) -> go.Figure:
    fig = px.line(
        history,
        x="year",
        y="combined_ratio",
        color="company",
        color_discrete_map=COLORS,
        category_orders={"company": COMPANY_ORDER},
        labels={"year": "Year", "combined_ratio": "Combined ratio", "company": "Company"},
    )
    fig.add_hline(y=1.0, line_dash="dash", line_color="#555", annotation_text="100%")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend_title_text="", hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10))
    return fig


def plot_capital(history: pd.DataFrame) -> go.Figure:
    fig = px.line(
        history,
        x="year",
        y="capital_ratio",
        color="company",
        color_discrete_map=COLORS,
        category_orders={"company": COMPANY_ORDER},
        labels={"year": "Year", "capital_ratio": "Capital ratio", "company": "Company"},
    )
    fig.add_hline(y=1.0, line_dash="dash", line_color="#555", annotation_text="1.0x")
    fig.update_layout(legend_title_text="", hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10))
    return fig


def plot_rates(history: pd.DataFrame) -> go.Figure:
    fig = px.line(
        history,
        x="year",
        y="rate_level",
        color="company",
        color_discrete_map=COLORS,
        category_orders={"company": COMPANY_ORDER},
