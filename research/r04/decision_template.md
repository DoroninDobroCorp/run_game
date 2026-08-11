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
- **Target Audience Profile:** [e.g., Urban runners (5k-10k) interested in narrative immersion / audio fiction]
- **Geographic Focus:** [e.g., English-speaking metro areas / Specific test city]
- **Traffic Channels:** [e.g., Meta Ads (Instagram/Facebook), Reddit niche running communities, direct organic]

### 2.2 Price Offer & Deposit Rules
- **Offer Structure:** [e.g., $5 Refundable Deposit for Early Access / $19 Preorder Bundle]
- **Price Point:** `$ [Founder Choice: e.g. 5.00 USD]`
- **Deposit Escrow / Handling Method:** [e.g., Stripe Auth-Only / Dedicated Refundable Holding Account]
- **Guaranteed Fulfillment Window:** [e.g., 90 Days from deposit date or mandatory refund]

### 2.3 Refund & Cancellation Policy
- **Refund Policy:** 100% no-questions-asked refund policy executable by user at any time prior to product release.
- **Refund Processing SLA:** Within 3 business days of request or upon reaching campaign stop-loss/expiration.
- **Fees Covered:** 100% of payment processing fees absorbed by founder (user receives full refund amount).

### 2.4 Qualified Visitor Definition
A landing page visitor is classified as a **Qualified Visitor** iff:
1. Unique session from target geographic region.
2. Non-bot user agent with minimum session duration ≥ 15 seconds or scroll depth ≥ 50%.
3. Reached via verified campaign tracking parameters (UTM parameters).

### 2.5 Ad Spend Stop-Loss Limit
- **Maximum Campaign Budget:** `$ [Founder Choice: e.g. 250.00 USD]`
- **Hard Stop Trigger:** Automatic ad campaign termination when ad spend reaches 100% of maximum budget or after 14 calendar days, whichever occurs first.
- **Cost-Per-Qualified-Visitor Threshold:** Maximum allowed `$ [Founder Choice: e.g. 2.50 USD]` per qualified visitor before early campaign pausing.

### 2.6 Primary Conversion Metric
- **Primary KPI:** **Preorder Deposit Conversion Rate (PDCR)** = `(Completed Refundable Deposits / Qualified Visitors) * 100%`
- **Secondary KPI:** **Email Intent Conversion Rate (EICR)** = `(Qualified Email Submissions / Qualified Visitors) * 100%`

---

## 3. GO / NO-GO Decision Rules

Upon completion of the R04 smoke test (or reaching ad spend stop-loss limit), the project founder will evaluate results against the following deterministic decision matrix:

| Outcome Metric | Criteria | Status | Action |
|---|---|---|---|
| **PDCR (Preorder Conversion)** | ≥ 3.0% qualified visitors | **GO (`G0_DEMAND = GO`)** | Proceed to Phase P01 (Production Domain Contracts). |
| **PDCR (Preorder Conversion)** | 1.5% – 2.9% qualified visitors | **CONDITIONAL PIVOT** | Iterate landing copy/offer; max 1 re-test before final decision. |
| **PDCR (Preorder Conversion)** | < 1.5% qualified visitors | **NO-GO (`G0_DEMAND = NO_GO`)** | Halt product development; issue 100% refunds to all depositors. |
| **Ad Spend Stop-Loss** | Reached budget limit ($) | **CAMPAIGN COMPLETE** | Immediately pause all traffic generation and tally final metrics. |

---

## 4. Verification & Audit Trail Requirements

Before updating `G0_DEMAND` or transitioning R04 status:
1. **Deposit Audit Log:** Complete export of all transactions and confirmation of 100% refund capability.
2. **Visitor Analytics Report:** Raw campaign metrics verifying qualified visitor criteria without personal data leakage.
3. **Execution Status:** R04 status in `docs/EXECUTION_STATUS.md` remains `NOT_STARTED` during template phase and updates to `COMPLETE` only after formal execution sign-off.
