# Multi-Strategy Automated Trading System — Phase 0 Design

**Date:** 2026-06-19
**Status:** Approved for planning
**Owner:** Joey

---

## 1. Purpose

A configurable, multi-strategy automated trading system that runs several trading
strategies in parallel, aggregates their signals into one auditable decision per
asset, enforces hard risk controls that no strategy can bypass, executes through a
broker-agnostic layer (paper first), and reports portfolio status every morning and
night. Capital preservation outranks returns. The system runs in simulated/paper
mode by default; live trading is gated behind an explicit, hard-to-trip flag.

---

## 2. Confirmed decisions

| Decision | Choice |
|---|---|
| Asset class | US equities & ETFs |
| Schedule | US market hours (regular session), calendar-aware |
| Trading style | Swing / positional (multi-day holds), not intraday |
| Broker | Alpaca (paper sandbox first, then live) |
| Report delivery | Email (SMTP); notifier is pluggable (SMS/dashboard addable later) |
| Strategies (starter set) | MA crossover (trend), RSI mean-reversion (counter-trend), momentum/breakout |
| Aggregation method | Confidence-weighted vote **plus** consensus gate |
| Starting paper capital | $500 |
| Universe | Liquid large-cap + broad ETF starter list (see §6); user can override in config |

### Why swing, not intraday
At $500 the account is well under the $25,000 Pattern Day Trader (PDT) threshold,
which limits margin accounts to three day-trades per five business days. Targeting
multi-day holds avoids the PDT rule entirely and aligns with capital-preservation.
Positions are sized as dollar amounts using Alpaca fractional shares, not whole-share
counts.

---

## 3. Non-negotiable principles

- **Paper trading first.** Paper is the default mode. Live trading requires
  `LIVE_TRADING=true` *and* a separate explicit runtime confirmation.
- **Capital preservation outranks returns.** Risk controls are core, not optional.
- **Kill switch.** One CLI command and one dashboard button immediately halt all new
  orders, with an option to flatten open positions.
- **Circuit breaker.** Trading auto-halts if the configured max daily loss is breached;
  an alert is sent.
- **No secrets in code.** All credentials via `.env` / environment variables. Never
  logged, never committed. `.env` is gitignored; a committed `.env.example` documents
  required keys. A secret-scan check guards the repo so it is safe to make public.
- **Full audit trail.** Every signal, decision, order, fill, and risk-check result is
  persisted and queryable. Any trade can be reconstructed end to end.
- **Backtest before deploy.** No strategy reaches paper or live without a documented
  backtest on historical data.

---

## 4. Core architectural principle — one pipeline, swappable ends

The exact same `strategy → decision → risk` code path runs in backtest, paper, and
live. Only two things swap:

1. **Data source** — historical replay (backtest) vs live market feed (paper/live).
2. **Execution layer** — simulated fills (backtest) vs Alpaca paper API vs Alpaca live API.

This guarantees that a strategy validated in backtest behaves identically in paper and
live, eliminating the logic drift between "test" and "real" code that causes most
trading-bot failures.

```
            ┌─────────────┐
 data feed →│  Strategies │→ signals ─┐
 (hist/live)│  (parallel) │           │
            └─────────────┘           ▼
                              ┌─────────────────┐
                              │ Decision layer  │  weighted vote + consensus gate
                              │ (per asset)     │  → one action + recorded rationale
                              └─────────────────┘
                                       │ proposed order
                                       ▼
                              ┌─────────────────┐
                              │  Risk module    │  FINAL AUTHORITY
                              │  veto / resize  │  caps, exposure, stop, daily-loss
                              └─────────────────┘
                                       │ approved order
                                       ▼
                              ┌─────────────────┐
                              │ Execution layer │  sim | paper | live
                              └─────────────────┘
                                       │ fills
                                       ▼
                          Portfolio state + full audit log (SQLite)
```

---

## 5. Technology stack

- **Engine:** Python — pandas, `alpaca-py` SDK, APScheduler for the trading loop.
- **State + audit:** SQLite — single source of truth, file-based, zero-setup,
  fully queryable. Ideal for a single-user system.
- **API:** FastAPI — control endpoints (start/stop, kill switch) and read endpoints
  (positions, P&L, decisions) for the dashboard.
- **Dashboard:** React — positions, P&L, risk exposure, recent decisions, and controls.
- **Reporting:** Email via SMTP (e.g., Gmail app password or SendGrid). Pluggable
  `Notifier` interface so SMS (Twilio) or dashboard-only can be added without engine
  changes.
- **Config:** a single `config.yaml` for all financial/operational parameters; `.env`
  for secrets only.

---

## 6. Tradable universe (starter — overridable in config)

Liquid, large-cap names and broad ETFs to keep slippage low and fills reliable:

- **ETFs:** SPY, QQQ, VTI, IWM, DIA
- **Large-cap equities:** AAPL, MSFT, GOOGL, AMZN, JPM, JNJ, PG, KO, V

The universe is a config list. The system trades only within it. A screening-rule mode
(e.g., "price > $20 and avg volume > 5M") can replace the static list later without
code changes.

---

## 7. Risk controls — default config values (review and tune)

All values live in `config.yaml`; none are hardcoded.

| Control | Default | Notes |
|---|---|---|
| Max % per position | 20% (~$100) | Allows ~5 positions via fractional shares |
| Max total exposure | 80% | Keeps a 20% cash buffer |
| Stop-loss | 5% per position | Trailing variant available via config |
| Take-profit / exit | 10% target | Trailing take-profit available |
| Max daily loss (circuit breaker) | 3% | Auto-halt + alert when breached |
| Max concurrent positions | 5 | Derived from per-position cap |

The risk module runs **after** the decision layer and has final authority: it can veto
an order outright or resize it to fit the caps. No strategy or decision can override it.

---

## 8. Decision layer — weighted vote + consensus gate

Each strategy emits `{action: BUY|SELL|HOLD, confidence: 0..1, rationale: str}`.

1. **Weighted vote:** each strategy's confidence is multiplied by its configured
   weight; votes are summed per direction to produce a net signed score.
2. **Threshold:** the net score must clear a configured magnitude to act at all.
3. **Consensus gate:** a configured minimum number of strategies (e.g., 2 of 3) must
   agree on direction before any order is proposed.

Both the threshold and the consensus minimum are config values. Every strategy vote,
the computed score, the gate result, and the final action + rationale are written to
the audit log.

---

## 9. Data model (SQLite — initial tables)

- `bars` — cached OHLCV history per symbol/timeframe (backtest + indicators).
- `signals` — one row per strategy per asset per cycle: action, confidence, rationale,
  timestamp, run_id.
- `decisions` — aggregated result per asset per cycle: votes summary, net score,
  gate outcome, final action, rationale, run_id.
- `risk_checks` — per proposed order: each cap evaluated, pass/fail, resize applied,
  veto reason.
- `orders` — submitted orders: symbol, side, qty/notional, type, idempotency key,
  status, broker order id.
- `fills` — executions against orders: price, qty, fees, timestamp.
- `positions` — current holdings: symbol, qty, avg cost basis, opened_at.
- `portfolio_snapshots` — periodic cash, equity, exposure, realized/unrealized P&L.
- `events` — system + safety events: kill switch, circuit breaker, errors, health.

`run_id` ties a single scheduler cycle's signals → decisions → risk_checks → orders →
fills together, so any trade is fully reconstructable.

---

## 10. Safety mechanisms (built in from Phase 2, not later)

- **Mode gate:** paper by default; live requires `LIVE_TRADING=true` + explicit
  confirmation at startup.
- **Kill switch:** CLI command + dashboard button; halts new orders immediately,
  optional flatten-all.
- **Circuit breaker:** auto-halt on max-daily-loss breach; emits an alert.
- **Idempotency:** every order carries a client idempotency key; a restart mid-cycle
  never double-submits.
- **Restart resilience:** scheduler resumes from persisted state; reconciles positions
  against Alpaca on startup.
- **Secret hygiene:** `.env` gitignored, `.env.example` committed, secret-scan check
  before the repo goes public.

---

## 11. Testing strategy

Heaviest coverage on the two components where a bug costs real money:

- **Risk module:** unit tests for every cap (per-position, total exposure, max
  positions), stop-loss and take-profit paths, circuit-breaker trip, veto and resize
  logic, and adversarial inputs (malformed signals, NaN prices, zero cash).
- **Decision layer:** unit tests across vote/threshold/consensus combinations,
  conflicting strategies, and tie-breaking.
- **Execution layer:** idempotency, partial fills, retry behavior (against a mocked
  broker).
- **Pipeline integration:** a known historical slice replayed end-to-end with asserted
  outcomes.

---

## 12. Phased delivery plan

- **Phase 0 — Spec & decisions.** (This document.)
- **Phase 1 — Data + backtesting harness.** Market-data ingestion, history cache, and
  the replay engine, so strategies can be validated before anything else exists.
- **Phase 2 — Strategy engine + decision + risk (paper).** Implement the three
  strategies, the aggregation layer, and the risk module against the paper execution
  layer. Wire in kill switch and circuit breaker now.
- **Phase 3 — Reporting + dashboard.** Morning/nightly email reports and the React
  dashboard (positions, P&L, exposure, recent decisions, controls).
- **Phase 4 — Paper validation.** Run on live market data in paper mode for a defined
  observation window; user reviews behavior and reports.
- **Phase 5 — Limited live.** Only after explicit approval: enable live mode with small
  capped capital, kill switch and circuit breaker active.
- **Phase 6 — Hardening + monitoring.** Logging, alerting, automated tests, restart
  resilience, documentation, runbook.

---

## 13. Deliverables

- Well-structured repo with README and setup instructions.
- Config-driven design (no financial parameters hardcoded).
- Automated tests, with emphasis on the risk module and decision layer.
- Backtest reports for each strategy.
- React dashboard.
- Runbook: how to start/stop, trip the kill switch, change config, interpret reports.
- Safe to publish on public GitHub (no secrets, secret-scan guard).

---

## 14. Required configuration & secrets

`config.yaml` (committed, no secrets): universe, strategy weights, aggregation
threshold + consensus minimum, all risk parameters, schedule, starting capital, mode.

`.env` (gitignored): `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER` flag,
`LIVE_TRADING`, SMTP credentials (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`,
`REPORT_TO_EMAIL`).

---

## 15. Known constraints / open items

- **Email transport:** SMTP via Gmail app password (simplest) or SendGrid. Confirm
  choice before Phase 3.
- **Sandbox availability:** the isolated Linux build/test environment failed to start
  this session (host hypervisor issue). Not blocking for design; must be restored
  before Phase 1 backtesting work.
- **Market data entitlement:** Alpaca's free tier provides IEX data; confirm whether
  the free feed is sufficient or full SIP data is desired before paper validation.
