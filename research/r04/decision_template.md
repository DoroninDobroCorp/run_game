# R04 Decision-Ready Evaluation Template: Preorder / Refundable Deposit Smoke Test

> **Status:** Template Specification Only (R04 Status remains `NOT_STARTED` in `EXECUTION_STATUS.md`).
>
> **FAIL-CLOSED GUARDRAILS:**
> - Requiring explicit founder choices (pricing, stop-loss, conversion metrics) **prior to landing publication**.
> - Does **NOT** publish landing pages, accept payments, or alter R04 status in `EXECUTION_STATUS.md`.
> - No landing page published. No payments accepted. No funds collected.

---

## 1. Overview & Demand Gate Objectives

Phase R04 specifies the demand evaluation gate (`G0_DEMAND`) for Run Game. Prior to committing full engineering resources to production domain contracts (P01–P22), this phase provides a decision-ready framework to evaluate real user demand via a refundable deposit or preorder smoke test.

### Core Principles
1. **Honest Value Demonstration:** The smoke test must present actual capabilities derived from R02/R03 narrative and audio research, without promising non-existent features.
2. **Zero Pre-Approval Exposure:** No web page, advertising campaign, or payment processing may be initiated until all founder parameters in this document are explicitly chosen, dated, and signed off by the project founder.
3. **Fail-Closed Risk Control:** Strict spend stop-losses and refund policies ensure financial exposure is bounded and zero user funds are retained without explicit fulfillment or immediate refund.

---

## 2. Mandatory Founder Choice Parameters

*All parameters in this section must be explicitly specified by the founder before landing page publication or marketing expenditure.*

### 2.1 Target Audience & Scope
- **Target Audience Profile:** `UNSET`
- **Geographic Focus:** `UNSET`
- **Traffic Channels:** `UNSET`

### 2.2 Price Offer & Deposit Rules
- **Offer Structure:** `UNSET`
- **Price Point:** `UNSET`
- **Deposit Escrow / Handling Method:** `UNSET`
- **Guaranteed Fulfillment Window:** `UNSET`

### 2.3 Refund & Cancellation Policy
- **Refund Policy:** `UNSET`
- **Refund Processing SLA:** `UNSET`
- **Fees Covered:** `UNSET`

### 2.4 Qualified Visitor Definition
A landing page visitor is classified as a **Qualified Visitor** iff:
1. Unique session from target geographic region (`UNSET`).
2. Non-bot user agent with minimum session duration ≥ `UNSET` seconds or scroll depth ≥ `UNSET`%.
3. Reached via verified campaign tracking parameters (UTM parameters: `UNSET`).

### 2.5 Ad Spend Stop-Loss Limit
- **Maximum Campaign Budget:** `UNSET`
- **Hard Stop Trigger:** Automatic ad campaign termination when ad spend reaches 100% of maximum budget or after `UNSET` calendar days, whichever occurs first.
- **Cost-Per-Qualified-Visitor Threshold:** Maximum allowed `UNSET` per qualified visitor before early campaign pausing.

### 2.6 Primary Conversion Metric
- **Primary KPI:** **Preorder Deposit Conversion Rate (PDCR)** = `(Completed Refundable Deposits / Qualified Visitors) * 100%` (Target: `UNSET`)
- **Secondary KPI:** **Email Intent Conversion Rate (EICR)** = `(Qualified Email Submissions / Qualified Visitors) * 100%` (Target: `UNSET`)

### 2.7 Observed Operational Metrics
*All observed metrics recorded during test execution default to UNSET baseline prior to test execution.*
- **Qualified Visitor Count:** `UNSET`
- **Completed Refundable Deposits Count:** `UNSET`
- **Actual Preorder Deposit Conversion Rate (PDCR):** `UNSET`
- **Total Ad Spend USD:** `UNSET`

---

## 3. GO / NO-GO Decision Rules

Upon completion of the R04 smoke test (or reaching ad spend stop-loss limit), the project founder will evaluate results against the following deterministic decision matrix:

| Outcome Metric | Criteria | Status | Action |
|---|---|---|---|
| **PDCR (Preorder Conversion)** | ≥ `go_threshold_pdcr_percent` (`UNSET`) | **GO (`G0_DEMAND = GO`)** | Proceed to Phase P01 (Production Domain Contracts). |
| **PDCR (Preorder Conversion)** | `conditional_pivot_min_pdcr_percent` (`UNSET`) – < `go_threshold_pdcr_percent` (`UNSET`) | **CONDITIONAL PIVOT** | Iterate landing copy/offer; max 1 re-test before final decision. |
| **PDCR (Preorder Conversion)** | < `no_go_threshold_pdcr_percent` (`UNSET`) | **NO-GO (`G0_DEMAND = NO_GO`)** | Halt product development; issue 100% refunds to all depositors. |
| **Ad Spend Stop-Loss** | Reached budget limit (`UNSET`) | **CAMPAIGN COMPLETE** | Immediately pause all traffic generation and tally final metrics. |

---

## 4. Verification & Audit Trail Requirements

Before updating `G0_DEMAND` or transitioning R04 status:
1. **Deposit Audit Log:** Complete export of all transactions and confirmation of 100% refund capability.
2. **Visitor Analytics Report:** Raw campaign metrics verifying qualified visitor criteria without personal data leakage.
3. **Execution Status:** R04 status in `docs/EXECUTION_STATUS.md` remains `NOT_STARTED` during template phase and updates to `COMPLETE` only after formal execution sign-off.
