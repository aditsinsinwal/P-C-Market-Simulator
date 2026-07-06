# P-C-Market-Simulator
I’m building an insurance market simulator where different AI insurance companies compete for customers. Each company has its own pricing model, underwriting strategy, and capital constraints. Customers respond to price changes, claims develop over time, inflation shocks hit the market, and a regulator can step in if pricing becomes unstable.
Auto Insurance Market Simulator
A Streamlit prototype of a miniature auto insurance economy. Five fictional insurers compete for customers, update rates, absorb claims, respond to regulators, and try to preserve capital over a multi-year market cycle.
What It Simulates
Customers with age, vehicle, location, driving behavior, prior claims, switching behavior, price sensitivity, hidden risk, and fraud propensity.
Insurers with different pricing models, underwriting appetite, expense loads, capital buffers, fraud controls, and competitor reactions.
Claims with stochastic frequency, severity, inflation, seasonality, catastrophe shocks, fraud inflation, and reporting delay.
Rate reviews with competitor pressure, loss experience, capital stress, and regulator intervention.
Dashboard views for market share, combined ratio, capital ratio, rate levels, churn, shocks, adverse selection, event logs, and final winner.
SQLite run history saved in simulation_runs.sqlite.
