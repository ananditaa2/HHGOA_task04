/**
 * TigerDetect × Hacker House Goa Frontend Application Logic
 * Integrates Vis.js Network force-directed graph, real-time case progression,
 * evidence conflict gauges, FinCEN SAR form modals, and live action approval controls.
 */

let allCases = [];
let currentCase = null;
let visNetwork = null;
let visNodes = null;
let visEdges = null;

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  fetchCases();
});

async function fetchCases() {
  try {
    const res = await fetch("/api/cases");
    allCases = await res.json();
    renderCaseStrip(allCases);
    if (allCases.length > 0) {
      await selectCase(allCases[0].case_id);
    }
  } catch (err) {
    console.error("Failed to load cases:", err);
  } finally {
    setTimeout(() => {
      const loader = document.getElementById("loading-screen");
      if (loader) loader.classList.add("hidden");
    }, 600);
  }
}

function renderCaseStrip(cases) {
  const container = document.getElementById("cases-strip");
  container.innerHTML = "";
  cases.forEach(c => {
    const chip = document.createElement("div");
    chip.className = `case-chip ${currentCase && currentCase.case_id === c.case_id ? "active" : ""}`;
    chip.id = `chip-${c.case_id}`;
    chip.onclick = () => selectCase(c.case_id);

    const isFraud = c.verdict === "FRAUD";
    const tagClass = isFraud ? "tag-fraud" : "tag-legit";
    const sarBadge = c.sar_filed ? `<span class="chip-tag tag-sar">SAR</span>` : "";

    chip.innerHTML = `
      <div class="chip-id">${c.case_id}</div>
      <div class="chip-meta">${c.trigger_type} · $${Number(c.amount).toFixed(2)}</div>
      <div style="display:flex; gap:3px;">
        <span class="chip-tag ${tagClass}">${c.verdict}</span>
        ${sarBadge}
      </div>
    `;
    container.appendChild(chip);
  });
}

function filterCases(filterType, btnElement) {
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  if (btnElement) btnElement.classList.add("active");

  let filtered = allCases;
  if (filterType === "fraud") {
    filtered = allCases.filter(c => c.verdict === "FRAUD");
  } else if (filterType === "legit") {
    filtered = allCases.filter(c => c.verdict === "LEGITIMATE");
  } else if (filterType === "sar") {
    filtered = allCases.filter(c => c.sar_filed);
  } else if (filterType === "ring") {
    filtered = allCases.filter(c => c.case_id === "HHG-014" || c.pattern === "device_ring_compromise");
  }
  renderCaseStrip(filtered);
}

async function selectCase(caseId) {
  document.querySelectorAll(".case-chip").forEach(c => c.classList.remove("active"));
  const activeChip = document.getElementById(`chip-${caseId}`);
  if (activeChip) activeChip.classList.add("active");

  try {
    const res = await fetch(`/api/case/${caseId}`);
    currentCase = await res.json();
    updateUI(currentCase);
  } catch (err) {
    console.error("Error loading case:", err);
  }
}

function updateUI(caseData) {
  const trig = caseData.trigger || {};
  const inv = caseData.investigation || {};
  const nba = caseData.next_best_actions || {};
  const sar = caseData.sar || {};
  const isFraud = inv.verdict === "FRAUD";

  // 1. Hero Banner
  document.getElementById("active-case-id").innerText = caseData.case_id;
  const verdictBadge = document.getElementById("active-verdict-badge");
  verdictBadge.innerText = inv.verdict;
  verdictBadge.style.background = isFraud ? "#FF0080" : "#00FFA3";
  verdictBadge.style.color = isFraud ? "#FFF" : "#000";

  const sarBadge = document.getElementById("active-sar-badge");
  if (sar.file) {
    sarBadge.style.display = "inline-block";
    sarBadge.innerText = "SAR REQUIRED (L2)";
  } else {
    sarBadge.style.display = "none";
  }

  document.getElementById("active-pattern").innerText = (inv.pattern || "ANOMALY").toUpperCase();
  document.getElementById("active-exposure").innerText = `$${Number(inv.exposure_usd || 0).toLocaleString("en-US", {minimumFractionDigits: 2})} USD`;
  document.getElementById("active-prob").innerText = `${((inv.fraud_probability || 0) * 100).toFixed(1)}%`;
  document.getElementById("active-opened").innerText = caseData.opened_at ? caseData.opened_at.split("T")[0] : "2016-12-05";

  // 2. Vis.js Force-Directed Interactive Graph
  renderVisGraph(caseData.graph);

  // 3. Provenance Path Display (Innovation 6)
  const paths = inv.provenance_paths || [];
  document.getElementById("provenance-path-text").innerText = paths[0] || "(Customer)-[:OWNS]->(Card)-[:MADE]->(Txn)";

  // 4. Evidence Conflict Meter (Rule R8 / Innovation 2)
  const confScore = Number(inv.conflict_score || 0);
  document.getElementById("conflict-score-val").innerText = `${confScore.toFixed(3)} / 1.000`;
  const meterFill = document.getElementById("conflict-meter-fill");
  meterFill.style.width = `${Math.min(100, Math.round(confScore * 100))}%`;

  const uncertPill = document.getElementById("uncertainty-pill");
  uncertPill.innerText = `UNCERTAINTY: ${(inv.uncertainty_level || "low").toUpperCase()}`;
  if (confScore >= 0.40) {
    uncertPill.style.background = "#FF0080";
  } else if (confScore >= 0.20) {
    uncertPill.style.background = "#FEE101";
    uncertPill.style.color = "#000";
  } else {
    uncertPill.style.background = "#00FFA3";
    uncertPill.style.color = "#000";
  }

  const signalsList = document.getElementById("conflict-signals-list");
  signalsList.innerHTML = "";
  const conflictingPairs = inv.conflicting_signals || [];
  if (conflictingPairs.length > 0) {
    conflictingPairs.forEach(p => {
      const div = document.createElement("div");
      div.className = "signal-pair-badge";
      div.innerHTML = `<span style="color:#FF0080; font-weight:bold;">[DISAGREEING SIGNAL]</span> ${p.details || ""}`;
      signalsList.appendChild(div);
    });
  } else {
    signalsList.innerHTML = `<div style="color:#FFFBE8; font-size:11px; opacity:0.8;">No significant signal discordance. Signals converge harmoniously.</div>`;
  }

  // 5. Devil's Advocate Adversarial Critique (Innovation 5)
  const da = inv.devils_advocate || {};
  document.getElementById("innocent-score-badge").innerText = `Innocent P: ${Number(da.innocent_score || 0).toFixed(2)}`;
  const daHypo = document.getElementById("devils-advocate-hypo");
  if (da.hypotheses && da.hypotheses.length > 0) {
    daHypo.innerText = `"${da.hypotheses[0]}"`;
  } else {
    daHypo.innerText = "Evidence of deliberate criminal compromise is robust. No benign explanation viable.";
  }

  // 6. Time-Decay Precedents (Innovation 4)
  const precList = document.getElementById("precedents-list");
  precList.innerHTML = "";
  const precedents = inv.similar_precedents || [];
  if (precedents.length > 0) {
    precedents.forEach(pr => {
      const pDiv = document.createElement("div");
      pDiv.style.cssText = "background: #074424; border-left: 3px solid #00E5FF; padding: 8px 12px; border-radius: 4px; font-size: 11px;";
      pDiv.innerHTML = `
        <div style="display:flex; justify-content:space-between;">
          <span style="color:#00E5FF; font-weight:bold;">${pr.case_id} (${pr.outcome})</span>
          <span style="color:#FEE101; font-weight:bold;">Weight: ${Number(pr.time_decay_weight || 1).toFixed(4)}</span>
        </div>
        <div style="color:#FFFBE8; margin-top:2px;">Pattern: ${pr.pattern} | Exposure: $${Number(pr.exposure_usd || 0).toFixed(2)} | Closed: ${pr.days_prior || 30} days prior</div>
      `;
      precList.appendChild(pDiv);
    });
  } else {
    precList.innerHTML = `<div style="font-size:11px; color:#FFFBE8; opacity:0.8;">No matching historical cases in retrieval window.</div>`;
  }

  // 7. Next-Best Action Progression Stepper
  // Step 1: Trigger
  document.getElementById("step-trigger-desc").innerHTML = `
    Trigger Event: <b style="color:#FF0080;">${trig.type}</b> | Flagged Txn: <b style="color:#00FFA3;">${trig.flagged_txn_id}</b><br/>
    Card: <b style="color:#FEE101;">${trig.card_id}</b> | Customer: ${trig.customer_id} | Risk Score: ${trig.risk_score}
  `;

  // Step 2: Recommendations BEFORE Evidence
  const initActionsBox = document.getElementById("step-initial-actions");
  initActionsBox.innerHTML = "";
  (nba.initial_recommendations || []).forEach(a => {
    const actCard = document.createElement("div");
    actCard.className = "action-card";
    const routeClass = a.approval_route === "L2" ? "route-l2" : (a.approval_route === "L1" ? "route-l1" : "route-auto");
    actCard.innerHTML = `
      <div>
        <span class="action-code">${a.action}</span>
        <div style="font-size:10px; color:#FFFBE8; margin-top:2px;">${a.reason}</div>
      </div>
      <span class="route-badge ${routeClass}">${a.approval_route.toUpperCase()}</span>
    `;
    initActionsBox.appendChild(actCard);
  });

  // Step 3: Controlled Evidence Request & Response Simulation
  const evSimBox = document.getElementById("step-evidence-sim");
  evSimBox.innerHTML = "";
  const resps = nba.simulated_responses || [];
  if (resps.length > 0) {
    resps.forEach(r => {
      const rDiv = document.createElement("div");
      rDiv.style.cssText = "background: #074424; border-left: 2px solid #00E5FF; padding: 6px 10px; border-radius: 4px; margin-bottom: 6px;";
      rDiv.innerHTML = `
        <div style="color:#00E5FF; font-weight:bold; font-size:10px;">${r.responder.toUpperCase()} RESPONSE (${r.status}):</div>
        <div style="color:#FFFBE8; font-size:11px; margin-top:2px;">${r.message}</div>
      `;
      evSimBox.appendChild(rDiv);
    });
  } else {
    evSimBox.innerHTML = `<div style="color:#FFFBE8; font-size:11px;">Sufficient deterministic signals gathered; no out-of-band step-up needed.</div>`;
  }

  // Step 4: Recommendations AFTER Evidence (Final)
  const finalActionsBox = document.getElementById("step-final-actions");
  finalActionsBox.innerHTML = "";
  (nba.final_recommendations || []).forEach(a => {
    const actCard = document.createElement("div");
    actCard.className = "action-card";
    const routeClass = a.approval_route === "L2" ? "route-l2" : (a.approval_route === "L1" ? "route-l1" : "route-auto");
    actCard.innerHTML = `
      <div>
        <span class="action-code" style="color:#00FFA3;">${a.action}</span>
        <div style="font-size:10px; color:#FFFBE8; margin-top:2px;">${a.reason}</div>
      </div>
      <span class="route-badge ${routeClass}">${a.approval_route.toUpperCase()}</span>
    `;
    finalActionsBox.appendChild(actCard);
  });

  // 8. FinCEN SAR Panel
  const sarContainer = document.getElementById("sar-container");
  if (sar.file) {
    sarContainer.style.display = "block";
    document.getElementById("sar-reason-text").innerText = sar.reason || "";
    document.getElementById("sar-narrative-preview").innerText = sar.narrative || "";
  } else {
    sarContainer.style.display = "none";
  }

  // 9. Case Summary Text
  document.getElementById("case-summary-text").innerText = caseData.summary || "Investigation concluded.";
  document.getElementById("action-execution-msg").style.display = "none";
}

// ----------------------------------------------------------------------------
// Vis.js Interactive Network Graph
// ----------------------------------------------------------------------------
function renderVisGraph(graphData) {
  if (!graphData) return;
  const container = document.getElementById("graph-canvas");

  visNodes = new vis.DataSet(graphData.nodes || []);
  visEdges = new vis.DataSet(graphData.edges || []);

  const data = { nodes: visNodes, edges: visEdges };
  const options = {
    nodes: {
      borderWidth: 2,
      borderWidthSelected: 4,
      shadow: { enabled: true, color: "rgba(254, 225, 1, 0.4)", size: 10 }
    },
    edges: {
      width: 2,
      smooth: { type: "continuous" },
      font: { color: "#FFFBE8", size: 10, face: "Victor Mono" },
      shadow: { enabled: true, color: "rgba(0, 0, 0, 0.6)", size: 5 }
    },
    physics: {
      stabilization: { iterations: 100 },
      barnesHut: { gravitationalConstant: -3500, centralGravity: 0.3, springLength: 95 }
    },
    interaction: {
      hover: true,
      zoomView: true,
      dragView: true
    }
  };

  visNetwork = new vis.Network(container, data, options);

  // Click event: Node Inspector
  visNetwork.on("click", (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0];
      const clickedNode = visNodes.get(nodeId);
      showNodeInspector(clickedNode);
    } else {
      document.getElementById("node-inspector-box").style.display = "none";
    }
  });
}

let physicsEnabled = true;

function zoomInGraph() {
  if (!visNetwork) return;
  const scale = visNetwork.getScale();
  visNetwork.moveTo({ scale: scale * 1.3, animation: { duration: 300 } });
}

function zoomOutGraph() {
  if (!visNetwork) return;
  const scale = visNetwork.getScale();
  visNetwork.moveTo({ scale: scale * 0.7, animation: { duration: 300 } });
}

function fitGraph() {
  if (!visNetwork) return;
  visNetwork.fit({ animation: { duration: 500 } });
}

function toggleGraphPhysics() {
  if (!visNetwork) return;
  physicsEnabled = !physicsEnabled;
  visNetwork.setOptions({ physics: { enabled: physicsEnabled } });
  const btn = document.getElementById("btn-physics-toggle");
  if (btn) {
    btn.innerText = physicsEnabled ? "⚡ FREEZE" : "▶ UNFREEZE";
    btn.style.color = physicsEnabled ? "#FEE101" : "#00FFA3";
  }
}

function showToast(message) {
  const existing = document.querySelector(".hh-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "hh-toast";
  toast.innerHTML = `<span>⚡</span> <span>${message}</span>`;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(120%)";
    toast.style.transition = "all 0.4s ease";
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

function showNodeInspector(node) {
  const box = document.getElementById("node-inspector-box");
  const details = document.getElementById("node-inspector-details");
  box.style.display = "block";
  const typeColor = node.type === "Transaction" ? "#FF0080" : (node.type === "Card" ? "#FEE101" : "#00FFA3");
  details.innerHTML = `
    <div><b>Node ID:</b> <span style="color:#FEE101;">${node.id}</span></div>
    <div><b>Entity Type:</b> <span style="color:${typeColor}; font-weight:bold;">${node.type || "Entity"}</span></div>
    <div><b>Visual Label:</b> ${node.label.replace("\n", " — ")}</div>
    <div style="font-size:10px; color:#FFFBE8; opacity:0.8; margin-top:4px;">
      🔗 <b>Graph Topology:</b> Multi-hop neighborhood active. Degrees connected: ${visEdges.get({ filter: e => e.from === node.id || e.to === node.id }).length}.
    </div>
  `;
}

// ----------------------------------------------------------------------------
// Human-in-the-Loop Analyst Action Execution
// ----------------------------------------------------------------------------
async function executeAnalystAction(actionType) {
  if (!currentCase) return;
  const msgBox = document.getElementById("action-execution-msg");
  msgBox.style.display = "block";

  try {
    const res = await fetch("/api/action/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: actionType,
        case_id: currentCase.case_id,
        approval_route: actionType === "ESCALATE_SUPERVISOR" ? "L2" : "L1"
      })
    });
    const result = await res.json();
    msgBox.innerHTML = `✓ <b>${result.status}:</b> ${result.message}`;
    showToast(`${result.status}: ${result.action} on ${result.case_id} (${result.approval_route})`);
  } catch (err) {
    msgBox.innerHTML = `⚠️ Execution failed: ${err.message}`;
    showToast(`Failed: ${err.message}`);
  }
}

// ----------------------------------------------------------------------------
// Modals Handling
// ----------------------------------------------------------------------------
function openSARModal() {
  if (!currentCase || !currentCase.sar) return;
  const sar = currentCase.sar;
  const modal = document.getElementById("sar-modal");
  const body = document.getElementById("sar-modal-body");

  body.innerHTML = `
    <div style="background:#000; border:1px solid #FF0080; border-radius:6px; padding:14px; margin-bottom:12px;">
      <div style="color:#FF0080; font-weight:bold; font-size:13px; margin-bottom:6px;">FINCEN SAR FORM 111 - ELECTRONIC FILING RECORD</div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:11px; margin-bottom:10px;">
        <div><b>Case Reference:</b> ${currentCase.case_id}</div>
        <div><b>Jurisdiction:</b> ${sar.jurisdiction || "FinCEN (US)"}</div>
        <div><b>Filing Deadline:</b> 30 Days from detection</div>
        <div><b>Filing Tier:</b> Level 2 BSA/AML Compliance Officer</div>
      </div>
      <div><b>Filing Reason:</b> <span style="color:#FEE101;">${sar.reason || "Exceeds regulatory criteria"}</span></div>
    </div>
    <div style="background:#074424; border:1px solid #FEE101; border-radius:6px; padding:14px;">
      <div style="color:#FEE101; font-weight:bold; margin-bottom:8px; font-size:12px;">SECTION V · SUSPICIOUS ACTIVITY NARRATIVE:</div>
      <div id="sar-narrative-copy-target" style="line-height:1.7; font-size:11.5px; color:#FFFBE8;">
        ${sar.narrative || "No narrative available."}
      </div>
    </div>
  `;
  modal.classList.add("open");
}

function closeSARModal() {
  document.getElementById("sar-modal").classList.remove("open");
}

function copySARNarrative() {
  const target = document.getElementById("sar-narrative-copy-target");
  if (target) {
    navigator.clipboard.writeText(target.innerText);
    alert("FinCEN SAR Narrative copied to clipboard!");
  }
}

function openSandboxModal() {
  document.getElementById("sandbox-modal").classList.add("open");
}
function closeSandboxModal() {
  document.getElementById("sandbox-modal").classList.remove("open");
}

async function runSandboxInvestigation() {
  const resDiv = document.getElementById("sandbox-results");
  resDiv.style.display = "block";
  resDiv.innerHTML = "Executing Multi-Agent Detective on custom transaction parameters...";

  const payload = {
    customer_id: document.getElementById("sb-cust").value,
    card_id: document.getElementById("sb-card").value,
    flagged_txn_id: document.getElementById("sb-txn").value,
    amount: parseFloat(document.getElementById("sb-amt").value),
    risk_score: parseFloat(document.getElementById("sb-risk").value),
    trigger_type: document.getElementById("sb-trigger").value,
    is_proxy: document.getElementById("sb-proxy").checked,
    is_recurring: document.getElementById("sb-rec").checked,
    customer_response: document.getElementById("sb-response").value
  };

  try {
    const res = await fetch("/api/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    resDiv.innerHTML = `
      <div style="background:#000; border:2px solid #FEE101; border-radius:8px; padding:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:bold; font-size:14px; color:#FEE101;">VERDICT: ${result.investigation.verdict}</span>
          <span class="badge-goa">${result.sar.file ? "SAR FILED" : "NO SAR"}</span>
        </div>
        <div style="margin-top:6px; font-size:11px; color:#FFFBE8;">
          Pattern: <b>${result.investigation.pattern}</b> | Exposure: <b>$${result.investigation.exposure_usd}</b> | Conflict: <b>${result.investigation.conflict_score}</b>
        </div>
        <div style="margin-top:6px; font-size:11px; color:#00FFA3;">
          Final Actions: ${result.next_best_actions.final_recommendations.map(a => `${a.action} (${a.approval_route})`).join(", ")}
        </div>
      </div>
    `;
  } catch (err) {
    resDiv.innerHTML = `Error executing investigation: ${err.message}`;
  }
}

async function runQAAuditModal() {
  const modal = document.getElementById("qa-modal");
  const body = document.getElementById("qa-modal-body");
  modal.classList.add("open");
  body.innerText = "Executing 5-point QA audit suite over all 20 cases...\n- JSON Schema Adherence\n- Rule Coverage (R1 - R10)\n- Initial-vs-Final Action Evolution\n- FinCEN SAR Regulatory Consistency\n- Exposure Mathematics";

  try {
    const res = await fetch("/api/qa_audit");
    const data = await res.json();
    body.innerText = data.log || "Audit completed successfully.";
  } catch (err) {
    body.innerText = `Error running audit: ${err.message}`;
  }
}

function closeQAModal() {
  document.getElementById("qa-modal").classList.remove("open");
}

function openPolicyModal() {
  const modal = document.getElementById("policy-modal");
  const container = document.getElementById("policy-rules-container");
  modal.classList.add("open");

  const rules = [
    { id: "R1", name: "Weak Anomaly Verification", action: "VERIFY_WITH_CUSTOMER", route: "auto", desc: "Risk score anomaly under 0.70 with no prior complaints requires customer contact prior to adverse actions." },
    { id: "R2", name: "Customer Denial Immediate Containment", action: "BLOCK_CARD, CREATE_CASE", route: "L1", desc: "Cardholder disputes transaction or explicitly denies authorizing charge. Overrides R1 weak verify." },
    { id: "R3", name: "Legitimate Transaction Clearance", action: "CLOSE_NO_FRAUD", route: "auto", desc: "When customer validates transaction or travel is verified, alert must be closed with no adverse impact. Overrides R1." },
    { id: "R4", name: "Rapid Merchant Velocity Mitigation", action: "DECLINE_TRANSACTION", route: "L1", desc: "High frequency cross-merchant transaction burst within 1 hour triggers selective transaction decline." },
    { id: "R5", name: "Micro-Auth Card Testing Protection", action: "BLOCK_CARD, CREATE_CASE", route: "L1", desc: "Preceding sequence of sub-$5 authorizations followed by high-dollar spend indicates card testing bot." },
    { id: "R6", name: "Device Ring Multi-Card Compromise", action: "MONITOR_CONNECTED_CARDS", route: "L2", desc: "Device profile linked to >= 3 distinct cards requires ring monitoring and supervisory escalation." },
    { id: "R7", name: "Recurring Subscription False Alarm", action: "WARN_CUSTOMER, CREATE_CASE", route: "auto", desc: "Dispute matches monthly recurring billing interval (gym, software). Warn customer rather than cancel card. Overrides R2 block." },
    { id: "R8", name: "High Exposure Evidence Conflict", action: "CREATE_CASE", route: "L1", desc: "Evidence Conflict Score C >= 0.40. Unresolved tension between risk score and historical baseline." },
    { id: "R9", name: "FinCEN Regulatory Reporting Threshold", action: "FILE_REPORT", route: "L2", desc: "Aggregate fraud exposure > $1,000, multi-card syndicate, or undocumented pattern mandates filing FinCEN SAR." },
    { id: "R10", name: "Supervisory Second-Line Concurrence", action: "ANALYST_CONFIRMATION", route: "L2", desc: "High consequence multi-action execution plans require Level 2 supervisor sign-off before settlement." }
  ];

  container.innerHTML = "";
  rules.forEach(r => {
    const rDiv = document.createElement("div");
    rDiv.style.cssText = "background:#074424; border:1px solid #FEE101; border-radius:6px; padding:8px 12px;";
    rDiv.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="color:#FEE101; font-weight:bold;">Rule ${r.id}: ${r.name}</span>
        <span class="route-badge ${r.route === 'L2' ? 'route-l2' : (r.route === 'L1' ? 'route-l1' : 'route-auto')}">${r.route.toUpperCase()}</span>
      </div>
      <div style="color:#00FFA3; font-weight:bold; margin-top:2px;">Action: ${r.action}</div>
      <div style="color:#FFFBE8; font-size:10px; margin-top:2px;">${r.desc}</div>
    `;
    container.appendChild(rDiv);
  });
}

function closePolicyModal() {
  document.getElementById("policy-modal").classList.remove("open");
}
