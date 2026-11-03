# Property Risk Assessment Engine

This document details the heuristic and AI-assisted risk scoring engine used to detect title defects, litigation risks, and boundary disputes.

## 1. Risk Categories and Scoring

The risk engine categorizes property vulnerabilities across 4 core dimensions:

### 1. Title Cleanliness Risk
- Missing chain of title deeds (> 30 years verification).
- Ambiguity in seller inheritance rights or minor shares.
- Non-registered agreement of sale or power of attorney transactions.

### 2. Encumbrance and Financial Risk
- Active hypothecation, mortgage, or financial institution charge.
- Overdue property municipal taxes or statutory utility arrears.

### 3. Legal and Litigation Risk
- Court stay orders, revenue authority disputes, or partition suits referenced in document text.
- Government acquisition or road-widening notices.

### 4. Regulatory and Zoning Compliance
- Non-agricultural conversion (NA order) validity.
- RERA registration status and environmental clearance compliance.

---

## 2. Risk Score Formulation

Overall Property Risk Score is computed as a weighted aggregate:

$$Risk\_Score = \sum_{i=1}^n w_i \cdot r_i$$

Where:
- $w_i$: Normalized category weight ($\sum w_i = 1.0$).
- $r_i \in [0, 100]$: Severity score evaluated per identified discrepancy.
- Ratings:
  - **Low Risk (0 - 25)**: Clear title, no active encumbrances.
  - **Moderate Risk (26 - 60)**: Missing ancillary documentation, minor boundary clarification needed.
  - **High Risk (61 - 100)**: Active litigation, pending bank mortgage, or disputed ownership.
