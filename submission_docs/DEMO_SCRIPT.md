# TigerDetect: 3-5 Minute Video Demo Script
**TigerGraph × Hacker House Goa (IEEE-CIS Fraud Investigation Edition)**

---

## Video Walkthrough Overview
- **Length**: ~3 to 4 minutes
- **Theme**: High-energy builder presentation styled in Hacker House Goa aesthetic (Goa green `#0B6839`, marigold yellow `#FEE101`, electric pink `#FF0080`)
- **Key Highlights to Show**:
  1. Dual-mode Graph Engine & 20 Benchmark Cases
  2. Case HHG-014: Device Ring Centrality (Innovation 3)
  3. Case HHG-003 / HHG-018: Devil's Advocate & Subscription Protection (Innovation 5 & Rule R7)
  4. Case HHG-012: Evidence Conflict Scoring (Innovation 2 & Rule R8)
  5. FinCEN Regulatory SAR Generator & Case Memory Persistence (Innovation 6 & 7)

---

## Scene-by-Scene Script

### [00:00 - 00:45] Intro: The Problem & The Hacker House Goa Mission
**[VISUAL]**: Screen starts on the TigerDetect Analyst Workbench. Show the "HACKER HOUSE गोवा" banner, the Goa green background, marigold yellow metrics, and the KPI strip.

**[SPEAKER (Energetic, builder tone)]**:
> "Welcome to TigerDetect—built for Hacker House Goa, IEEE-CIS Fraud Investigation Edition!
>
> In banking, fraud teams are overwhelmed. Over 50% of automated alerts are completely legitimate cardholders traveling or renewing subscriptions. Traditional if/else rules either freeze innocent customers' cards or let coordinated multi-card syndicates slip through.
>
> To solve this, we built **TigerDetect**: an autonomous AI Fraud Detective powered by TigerGraph, GraphRAG, and 7 strategic architectural innovations."

---

### [00:45 - 01:30] Innovation Spotlight 1: Case HHG-014 Device Ring & Graph Centrality
**[VISUAL]**: In the sidebar, select **HHG-014**. The UI updates instantly. Point cursor to the interactive SVG graph on the left with glowing neon paths connecting 4 cards to Device D0012, highlighting the HUB card in hot pink.

**[SPEAKER]**:
> "Let's inspect **Case HHG-014**—a critical analyst inquiry on a suspicious device fingerprint.
>
> Watch our Graph Detective Agent at work. Instead of treating this card in isolation, TigerDetect traverses the graph and discovers a 4-card device ring sharing hardware signature `D0012`.
>
> Using **Strategic Innovation 3**, the agent runs Degree Centrality and PageRank across the bipartite subgraph, identifying Card `C13487-K1` as the central hub card responsible for the cashout, and ranking peripheral victim cards.
>
> Notice the literal graph provenance path highlighted in glowing neon—tracing the entire evidence chain.
>
> Because this is an organized multi-card ring, the Policy Engine triggers Rule R6 and R9, escalating to Level 2 supervisory review and auto-generating a regulatory FinCEN Suspicious Activity Report."

---

### [01:30 - 02:15] Innovation Spotlight 2: Devil's Advocate & False Positive Defense
**[VISUAL]**: In the sidebar, select **HHG-003** ($49.00 customer dispute). Point to the Devil's Advocate critique box and the progression timeline showing `VERIFY_WITH_CUSTOMER` and `WARN_CUSTOMER`.

**[SPEAKER]**:
> "Now let's see how TigerDetect defends good customers from false positives.
>
> In **Case HHG-003**, the customer disputes a $49 charge. A naive rule engine would freeze their card immediately.
>
> But TigerDetect deploys our **Adversarial Self-Critique Agent—the Devil's Advocate (Innovation 5)**.
>
> The critic notices that $49.00 aligns exactly with a monthly software subscription cadence. Instead of card cancellation, Rule R7 fires! The agent routes an educational warning to the customer, keeping the card active. The customer acknowledges the subscription, saving the bank customer churn."

---

### [02:15 - 02:50] Innovation Spotlight 3: Quantitative Conflict Scoring (Rule R8)
**[VISUAL]**: In the sidebar, select **HHG-012**. Zoom in on the Evidence Conflict Meter (Innovation 2) showing the conflict score $C = 0.518$ and the disagreeing signal pair.

**[SPEAKER]**:
> "Here in **Case HHG-012**, we demonstrate **Innovation 2: Evidence Conflict Scoring**.
>
> The ML model flagged the transaction with a 0.55 risk score in region 494.0. But the graph reveals the customer has extensive historical purchases in that exact region.
>
> TigerDetect computes an explicit mathematical conflict score ($C \ge 0.40$), quantitatively logging the tension between the anomaly alert and historical loyalty. The Devil's Advocate resolves the tension, and the case is closed with zero fraud loss."

---

### [02:50 - 03:20] The QA Audit Suite & TigerGraph Dual-Mode Architecture
**[VISUAL]**: Switch to the sidebar tab **🛡️ 20-Case QA Audit Suite**. Click the button **🚀 EXECUTE LIVE MULTI-DIMENSIONAL QA AUDIT**. Watch all 5 checks turn green with 100% scores.

**[SPEAKER]**:
> "TigerDetect isn't just a prototype—it comes with a **Post-Run QA Audit Suite (Innovation 7)**.
>
> In one click, our verification engine audits all 20 benchmark cases:
> - 100% JSON schema conformity.
> - Full rule coverage across Rules R1 through R10.
> - 80% dynamic action evolution from initial inquiry to final approval.
> - Strict FinCEN SAR threshold integrity.
>
> And thanks to our **Dual-Mode Graph Architecture**, TigerDetect connects seamlessly to live TigerGraph Savanna Cloud or runs offline via our built-in fast GSQL graph engine."

---

### [03:20 - 03:45] Conclusion & Sign-off
**[VISUAL]**: Return to the main overview. Show the Hacker House Goa branding and GitHub repository.

**[SPEAKER]**:
> "TigerDetect transforms fraud investigation into an autonomous, explainable, graph-native intelligence engine.
>
> Built with passion in Goa. Thank you!"
