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
    if (!res.ok) throw new Error(await responseError(res));
    allCases = await res.json();
    renderCaseStrip(allCases);
    resolveDemoCardId();
  } catch (err) {
    console.error("Failed to load cases:", err);
  } finally {
    setTimeout(() => {
      const loader = document.getElementById("loading-screen");
      if (loader) loader.classList.add("hidden");
    }, 600);
  }
}

async function responseError(response) {
  const body = await response.text();
  try {
    const parsed = JSON.parse(body);
    return typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail || parsed);
  } catch (_) {
    return body || response.statusText || "Unknown API error";
  }
}

function resolveDemoCardId() {
  const cardInput = document.getElementById("sb-card");
  if (!cardInput || !allCases.length) return false;
  const caseRow = allCases.find(row => row.case_id === "HHG-011" && row.customer_id === "C11923");
  if (!caseRow || !caseRow.card_id) {
    cardInput.value = "";
    cardInput.placeholder = "HHG-011 card ID unavailable from /api/cases";
    return false;
  }
  cardInput.value = caseRow.card_id;
  cardInput.placeholder = "Resolved from /api/cases";
  return true;
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

function apiValue(value) {
  return value === null || value === undefined || value === "" ? "Not provided by API" : String(value);
}

function recommendationSafeExplanation(summary, actions) {
  const actionNames = new Set(actions.map(action => String(action.action || "").toUpperCase()));
  return String(summary || "").replace(/\bcard\s+blocked(?:\s+under\s+R\d+)?\b/gi, () =>
    actionNames.has("BLOCK_CARD") ? "BLOCK_CARD is recommended (not executed)" : "card action status is not confirmed by the API"
  ).replace(/\bcase\s+created(?:\s+under\s+R\d+)?\b/gi, () =>
    actionNames.has("CREATE_CASE") ? "CREATE_CASE is recommended (not executed)" : "case creation status is not confirmed by the API"
  );
}

function renderActionRecommendations(containerId, actions, accentColor) {
  const box = document.getElementById(containerId);
  box.replaceChildren();
  if (!actions.length) {
    box.textContent = "No recommendations returned by the API.";
    return;
  }
  actions.forEach(action => {
    const card = document.createElement("div");
    card.className = "action-card";
    const details = document.createElement("div");
    const code = document.createElement("span");
    code.className = "action-code";
    code.style.color = accentColor;
    code.textContent = apiValue(action.action);
    const reason = document.createElement("div");
    reason.style.cssText = "font-size:10px; color:#FFFBE8; margin-top:2px;";
    reason.textContent = apiValue(action.reason);
    details.append(code, reason);
    const route = document.createElement("span");
    const routeValue = String(action.route || action.approval_route || "").toUpperCase();
    route.className = `route-badge ${routeValue === "L2" ? "route-l2" : routeValue === "L1" ? "route-l1" : "route-auto"}`;
    route.textContent = routeValue || "ROUTE NOT PROVIDED";
    card.append(details, route);
    box.appendChild(card);
  });
}

function updateUI(response) {
  const inv = response.case || response.investigation || {};
  const nba = response.next_best_actions || {};
  const sar = response.sar || {};
  const evidence = Array.isArray(inv.evidence) ? inv.evidence : [];
  const transactionEvidence = evidence.find(item => item.signal === "graph_transaction");
  const transaction = transactionEvidence && transactionEvidence.value && typeof transactionEvidence.value === "object"
    ? transactionEvidence.value : {};
  const isLiveResponse = Boolean(transactionEvidence && response.next_best_actions && Array.isArray(nba.final));
  const isFraud = String(inv.verdict || "").toLowerCase() === "fraud";

  currentCase = response;
  document.getElementById("active-case-id").textContent = apiValue(response.case_id);
  const verdictBadge = document.getElementById("active-verdict-badge");
  verdictBadge.textContent = apiValue(inv.verdict).toUpperCase();
  verdictBadge.style.background = isFraud ? "#FF0080" : "#00FFA3";
  verdictBadge.style.color = isFraud ? "#FFF" : "#000";

  const sarBadge = document.getElementById("active-sar-badge");
  sarBadge.style.display = sar.file ? "inline-block" : "none";
  if (sar.file) sarBadge.textContent = "SAR RECOMMENDED (L2)";
  document.getElementById("active-pattern").textContent = apiValue(inv.pattern).toUpperCase();
  const exposure = inv.exposure_usd;
  document.getElementById("active-exposure").textContent = exposure === null || exposure === undefined
    ? "Not provided by API" : `$${Number(exposure).toLocaleString("en-US", {minimumFractionDigits: 2})} USD`;
  const fraudProbability = inv.fraud_probability;
  document.getElementById("active-prob").textContent = fraudProbability === null || fraudProbability === undefined
    ? "Not provided by API" : `${(Number(fraudProbability) * 100).toFixed(1)}%`;
  document.getElementById("active-opened").textContent = apiValue(response.opened_at);

  const memoryStatus = document.getElementById("case-memory-status");
  memoryStatus.textContent = inv.written_to_graph === false ? "CASE MEMORY: PROCESS-LOCAL" :
    (inv.written_to_graph === true ? "CASE MEMORY: GRAPH WRITE REPORTED BY API" : "CASE MEMORY: NOT REPORTED BY API");
  memoryStatus.style.color = inv.written_to_graph === false ? "#00E5FF" : "#FEE101";

  // The graph panel only renders topology included by the response. Live investigation
  // responses currently provide evidence paths but no entity topology.
  renderVisGraph(response.graph);

  const mcpEvidence = evidence.filter(item => item.source === "tigergraph_mcp");
  const provenanceRefs = [...new Set(mcpEvidence.map(item => item.ref).filter(Boolean))];
  const provenanceBox = document.getElementById("provenance-path-text");
  provenanceBox.textContent = provenanceRefs.length
    ? `${provenanceRefs[0]}${provenanceRefs.length > 1 ? ` (+${provenanceRefs.length - 1} more TigerGraph MCP references)` : ""}`
    : "No provenance references returned by the API.";

  const transactionPanel = document.getElementById("live-transaction-panel");
  transactionPanel.style.display = isLiveResponse ? "block" : "none";
  if (isLiveResponse) {
    const customerEvidence = evidence.find(item => item.signal === "graph_customer");
    const customerId = customerEvidence && customerEvidence.value ? customerEvidence.value.customer_id : undefined;
    const riskEvidence = evidence.find(item => item.signal === "risk_score_evaluation");
    const riskScore = transaction.risk_score ?? (riskEvidence ? riskEvidence.value : undefined);
    const sourceLabel = document.getElementById("evidence-source-label");
    sourceLabel.textContent = mcpEvidence.length ? "Evidence Source: TigerGraph MCP" : "Evidence Source: Not provided by API";
    document.getElementById("live-customer-id").textContent = apiValue(customerId);
    document.getElementById("live-transaction-id").textContent = apiValue(transaction.transaction_id);
    document.getElementById("live-amount").textContent = transaction.amount === undefined ? "Not provided by API" : `$${Number(transaction.amount).toFixed(2)}`;
    document.getElementById("live-timestamp").textContent = apiValue(transaction.timestamp);
    document.getElementById("live-risk-score").textContent = apiValue(riskScore);
    document.getElementById("live-channel").textContent = apiValue(transaction.channel);
    document.getElementById("live-product-cd").textContent = apiValue(transaction.ProductCD);
    document.getElementById("live-evidence-count").textContent = String(evidence.length);
    document.getElementById("live-provenance-count").textContent = `${provenanceRefs.length} references`;
  }

  const conflictValue = inv.conflict_score;
  const confScore = conflictValue !== null && conflictValue !== undefined && Number.isFinite(Number(conflictValue))
    ? Number(conflictValue) : null;
  document.getElementById("conflict-score-val").textContent = confScore === null
    ? "Not provided by API" : `${confScore.toFixed(3)} / 1.000`;
  const meterFill = document.getElementById("conflict-meter-fill");
  meterFill.style.width = confScore === null ? "0%" : `${Math.min(100, Math.max(0, Math.round(confScore * 100)))}%`;
  const uncertainty = inv.uncertainty_level;
  const uncertPill = document.getElementById("uncertainty-pill");
  uncertPill.textContent = `UNCERTAINTY: ${apiValue(uncertainty).toUpperCase()}`;
  uncertPill.style.background = String(uncertainty).toLowerCase() === "high" ? "#FF0080" :
    String(uncertainty).toLowerCase() === "medium" ? "#FEE101" : "#00FFA3";
  uncertPill.style.color = String(uncertainty).toLowerCase() === "medium" || String(uncertainty).toLowerCase() === "low" ? "#000" : "#FFF";
  document.getElementById("uncertainty-basis-display").textContent = apiValue(inv.uncertainty_basis);

  const signalsList = document.getElementById("conflict-signals-list");
  signalsList.replaceChildren();
  const conflictingPairs = inv.conflicting_signals || [];
  if (conflictingPairs.length) {
    conflictingPairs.forEach(pair => {
      const item = document.createElement("div");
      item.className = "signal-pair-badge";
      item.textContent = `[DISAGREEING SIGNAL] ${apiValue(pair.details || pair.signal)}`;
      signalsList.appendChild(item);
    });
  } else {
    signalsList.textContent = "No conflicting signals were returned by the API.";
  }

  const criticVerdict = inv.devil_advocate_verdict || (inv.devils_advocate && inv.devils_advocate.verdict);
  const criticScore = inv.innocent_explanation_score ?? (inv.devils_advocate && inv.devils_advocate.innocent_score);
  document.getElementById("devils-advocate-verdict").textContent = apiValue(criticVerdict);
  document.getElementById("innocent-score-badge").textContent = criticScore === undefined
    ? "Innocent score: Not provided by API" : `Innocent P: ${Number(criticScore).toFixed(2)}`;
  const hypotheses = inv.alternative_hypotheses || (inv.devils_advocate && inv.devils_advocate.hypotheses) || [];
  document.getElementById("devils-advocate-hypo").textContent = hypotheses.length
    ? hypotheses.join("\n") : "No alternative hypotheses were returned by the API.";

  const precList = document.getElementById("precedents-list");
  precList.replaceChildren();
  const precedents = inv.similar_precedents || inv.similar_prior_cases || [];
  if (precedents.length) {
    precedents.forEach(precedent => {
      const item = document.createElement("div");
      item.style.cssText = "background:#074424; border-left:3px solid #00E5FF; padding:8px 12px; border-radius:4px; font-size:11px;";
      item.textContent = typeof precedent === "string" ? precedent :
        `${apiValue(precedent.case_id)} · ${apiValue(precedent.pattern)} · weight ${apiValue(precedent.time_decay_weight)}`;
      precList.appendChild(item);
    });
  } else {
    precList.textContent = "No precedent records returned by the API.";
  }

  const triggerType = response.trigger_type || (response.trigger && response.trigger.type);
  document.getElementById("step-trigger-desc").textContent =
    `Trigger: ${apiValue(triggerType)} | Customer: ${isLiveResponse ? apiValue(evidence.find(item => item.signal === "graph_customer")?.value?.customer_id) : apiValue(response.trigger && response.trigger.customer_id)} | Transaction: ${apiValue(transaction.transaction_id || (response.trigger && response.trigger.flagged_txn_id))}`;
  renderActionRecommendations("step-initial-actions", nba.initial || nba.initial_recommendations || [], "#FEE101");
  renderActionRecommendations("step-final-actions", nba.final || nba.final_recommendations || [], "#00FFA3");

  const evSimBox = document.getElementById("step-evidence-sim");
  evSimBox.replaceChildren();
  const evidenceResults = response.evidence_requests || [];
  if (evidenceResults.length) {
    evidenceResults.forEach((item, index) => {
      const row = document.createElement("div");
      row.style.cssText = "background:#074424; border-left:2px solid #00E5FF; padding:6px 10px; border-radius:4px; margin-bottom:6px;";
      row.textContent = `Evidence ${index + 1} (${apiValue(item.type)}): ${apiValue(item.assumed_response)}`;
      evSimBox.appendChild(row);
    });
  } else {
    evSimBox.textContent = "No additional evidence result was returned by the API.";
  }

  const sarContainer = document.getElementById("sar-container");
  sarContainer.style.display = sar.file ? "block" : "none";
  if (sar.file) {
    document.getElementById("sar-reason-text").textContent = apiValue(sar.reason);
    document.getElementById("sar-narrative-preview").textContent = apiValue(sar.narrative);
  }

  const finalActions = nba.final || nba.final_recommendations || [];
  document.getElementById("case-summary-text").textContent = apiValue(
    recommendationSafeExplanation(inv.summary, finalActions)
  );
  document.getElementById("investigation-stop-reason").textContent = `Stop reason: ${apiValue(response.stop_reason)}`;
  document.getElementById("recommendation-change-explanation").textContent = `Recommendation explanation: ${apiValue(nba.what_changed)}`;
  document.getElementById("action-execution-msg").style.display = "none";
}

// ----------------------------------------------------------------------------
// Vis.js Interactive Network Graph
// ----------------------------------------------------------------------------
function renderVisGraph(graphData) {
  const container = document.getElementById("graph-canvas");
  const legend = document.getElementById("graph-legend");
  document.getElementById("node-inspector-box").style.display = "none";
  if (visNetwork) {
    visNetwork.destroy();
    visNetwork = null;
  }
  if (!graphData || !Array.isArray(graphData.nodes) || graphData.nodes.length === 0) {
    visNodes = null;
    visEdges = null;
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.justifyContent = "center";
    container.replaceChildren();
    container.textContent = "No graph entities were returned by the investigation API.";
    legend.replaceChildren();
    return;
  }

  container.style.display = "block";
  visNodes = new vis.DataSet(graphData.nodes || []);
  visEdges = new vis.DataSet(graphData.edges || []);
  legend.replaceChildren();
  [...new Set(graphData.nodes.map(node => node.type).filter(Boolean))].forEach(type => {
    const label = document.createElement("span");
    label.textContent = `• ${type}`;
    legend.appendChild(label);
  });
  container.replaceChildren();

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
    btn.innerText = physicsEnabled ? "[!] FREEZE" : "[>] UNFREEZE";
    btn.style.color = physicsEnabled ? "#FEE101" : "#00FFA3";
  }
}

function showToast(message) {
  const existing = document.querySelector(".hh-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "hh-toast";
  toast.innerHTML = `<span>[!]</span> <span>${message}</span>`;
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
    <div><b>Visual Label:</b> ${node.label.replace("\n", "  --  ")}</div>
    <div style="font-size:10px; color:#FFFBE8; opacity:0.8; margin-top:4px;">
      [GRAPH] <b>Graph Topology:</b> Multi-hop neighborhood active. Degrees connected: ${visEdges.get({ filter: e => e.from === node.id || e.to === node.id }).length}.
    </div>
  `;
}

// ----------------------------------------------------------------------------
// Human-in-the-Loop Analyst Action Execution
// ----------------------------------------------------------------------------
function simulateAnalystAction(actionType) {
  const msgBox = document.getElementById("action-execution-msg");
  msgBox.style.display = "block";
  msgBox.textContent = `SIMULATION ONLY: ${actionType}. No action endpoint was called; no customer or TigerGraph action was executed.`;
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
  resolveDemoCardId();
  document.getElementById("sandbox-modal").classList.add("open");
}
function closeSandboxModal() {
  document.getElementById("sandbox-modal").classList.remove("open");
}

async function ensureDemoCardId() {
  if (resolveDemoCardId()) return document.getElementById("sb-card").value;
  const response = await fetch("/api/cases");
  if (!response.ok) throw new Error(`Unable to resolve the HHG-011 card ID: ${await responseError(response)}`);
  allCases = await response.json();
  renderCaseStrip(allCases);
  if (!resolveDemoCardId()) throw new Error("The backend /api/cases response did not contain a card ID for HHG-011 / C11923.");
  return document.getElementById("sb-card").value;
}

async function runSandboxInvestigation() {
  const resDiv = document.getElementById("sandbox-results");
  const runButton = document.getElementById("run-investigation-button");
  const loading = document.getElementById("sandbox-loading");
  resDiv.style.display = "block";
  resDiv.className = "sandbox-result-status";
  resDiv.removeAttribute("role");
  resDiv.textContent = "Submitting the investigation to FastAPI…";
  runButton.disabled = true;
  runButton.textContent = "RUNNING…";
  loading.style.display = "block";

  try {
    const cardId = await ensureDemoCardId();
    const payload = {
      customer_id: document.getElementById("sb-cust").value.trim(),
      card_id: cardId,
      flagged_txn_id: document.getElementById("sb-txn").value.trim(),
      // Required compatibility fields. In MCP mode the transaction values come from TigerGraph MCP.
      amount: 0,
      risk_score: 0,
      trigger_type: document.getElementById("sb-trigger").value,
      customer_response: document.getElementById("sb-response").value
    };
    if (!payload.customer_id || !payload.flagged_txn_id) {
      throw new Error("Customer ID and transaction ID are required.");
    }
    const response = await fetch("/api/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`FastAPI returned ${response.status}: ${await responseError(response)}`);
    const result = await response.json();
    if (!result.case || !result.next_best_actions) throw new Error("FastAPI response did not contain the expected investigation fields.");
    updateUI(result);
    resDiv.textContent = `Investigation response received for ${apiValue(result.case_id)}. Result panels now show values returned by the API.`;
    closeSandboxModal();
  } catch (error) {
    resDiv.className = "sandbox-result-status sandbox-error";
    resDiv.setAttribute("role", "alert");
    resDiv.textContent = `Investigation failed: ${error.message}`;
  } finally {
    runButton.disabled = false;
    runButton.textContent = "RUN INVESTIGATION";
    loading.style.display = "none";
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
