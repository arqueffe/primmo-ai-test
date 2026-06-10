const state = {
  apiBase: localStorage.getItem("primmo_api_base") || "http://localhost:8000",
  dossiers: [],
  chatMessages: [],
  graphData: null,
  metricsHistory: [],
  metricsOperations: [],
  ingestPollId: null,
};

const API_PREFIX = "/api/v1";

const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabPanels = {
  chat: document.getElementById("tab-chat"),
  graph: document.getElementById("tab-graph"),
  metrics: document.getElementById("tab-metrics"),
  judge: document.getElementById("tab-judge"),
};

const apiInput = document.getElementById("apiBaseUrl");
const globalDossierSelect = document.getElementById("globalDossierSelect");
const ingestStatus = document.getElementById("ingestStatus");
const chatTimeline = document.getElementById("chatTimeline");
const chatForm = document.getElementById("chatForm");
const chatQuestion = document.getElementById("chatQuestion");
const refreshDossiersBtn = document.getElementById("refreshDossiers");
const graphDossierSelect = document.getElementById("graphDossierSelect");
const graphSearch = document.getElementById("graphSearch");
const loadGraphBtn = document.getElementById("loadGraph");
const graphLegend = document.getElementById("graphLegend");
const graphCanvas = document.getElementById("graphCanvas");
const graphDetails = document.getElementById("graphDetails");
const refreshMetricsBtn = document.getElementById("refreshMetrics");
const metricsOperationType = document.getElementById("metricsOperationType");
const metricsCards = document.getElementById("metricsCards");
const operationsList = document.getElementById("operationsList");
const refreshJudgeReviewsBtn = document.getElementById("refreshJudgeReviews");
const judgeVerdictFilter = document.getElementById("judgeVerdictFilter");
const judgeSummaryCards = document.getElementById("judgeSummaryCards");
const judgeReviewsList = document.getElementById("judgeReviewsList");
const openUploadDrawerBtn = document.getElementById("openUploadDrawer");
const closeUploadDrawerBtn = document.getElementById("closeUploadDrawer");
const uploadDrawer = document.getElementById("uploadDrawer");
const uploadForm = document.getElementById("uploadForm");
const uploadDossierId = document.getElementById("uploadDossierId");
const uploadFile = document.getElementById("uploadFile");
const uploadFeedback = document.getElementById("uploadFeedback");
const uploadProgress = document.getElementById("uploadProgress");
const ingestedDocuments = document.getElementById("ingestedDocuments");

const DOSSIER_NODE_COLORS = [
  "#2563eb",
  "#0f766e",
  "#9f1239",
  "#d97706",
  "#6d28d9",
  "#0e7490",
  "#b45309",
  "#be123c",
];

const MULTI_DOSSIER_NODE_COLOR = "#111827";

function setStatus(el, text) {
  el.textContent = text;
}

function currentDossierId() {
  return globalDossierSelect.value || undefined;
}

function currentGraphDossierId() {
  if (!graphDossierSelect) {
    return currentDossierId();
  }
  return graphDossierSelect.value || undefined;
}

function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  return `$${Number(value).toFixed(5)}`;
}

function safeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function percentile95(values) {
  if (!Array.isArray(values) || !values.length) {
    return 0;
  }
  const sorted = values
    .map(v => safeNumber(v, 0))
    .sort((a, b) => a - b);
  const index = Math.max(0, Math.ceil(sorted.length * 0.95) - 1);
  return safeNumber(sorted[index], 0);
}

function operationTypeKey(op) {
  if (op?.name) {
    return String(op.name);
  }
  if (op?.category) {
    return String(op.category);
  }
  return "unknown";
}

function summarizeOperations(operations) {
  const rows = Array.isArray(operations) ? operations : [];
  const latencies = rows.map(item => safeNumber(item.latency_ms, 0));
  const total = rows.length;
  const avgLatency = total ? latencies.reduce((sum, value) => sum + value, 0) / total : 0;
  const p95Latency = percentile95(latencies);
  const totalCost = rows.reduce((sum, item) => sum + safeNumber(item.cost_usd, 0), 0);

  return {
    total,
    avg_latency_ms: avgLatency,
    p95_latency_ms: p95Latency,
    total_cost_usd: totalCost,
  };
}

function updateOperationTypeOptions(operations) {
  if (!metricsOperationType) {
    return;
  }

  const current = metricsOperationType.value;
  const counts = new Map();
  (Array.isArray(operations) ? operations : []).forEach(op => {
    const key = operationTypeKey(op);
    counts.set(key, (counts.get(key) || 0) + 1);
  });

  const options = Array.from(counts.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  metricsOperationType.innerHTML = "";

  const all = document.createElement("option");
  all.value = "";
  all.textContent = "All operation types";
  metricsOperationType.appendChild(all);

  options.forEach(([name, count]) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = `${name} (${count})`;
    metricsOperationType.appendChild(option);
  });

  if (current && counts.has(current)) {
    metricsOperationType.value = current;
  } else {
    metricsOperationType.value = "";
  }
}

function filteredOperations() {
  const selected = metricsOperationType ? metricsOperationType.value : "";
  const operations = Array.isArray(state.metricsOperations) ? state.metricsOperations : [];
  if (!selected) {
    return operations;
  }
  return operations.filter(op => operationTypeKey(op) === selected);
}

function apiPath(path) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_PREFIX}${normalized}`;
}

function normalizeDossiersPayload(data) {
  if (Array.isArray(data)) {
    return data.map(item => {
      if (item && typeof item === "object") {
        if ("id" in item) {
          const documents = Array.isArray(item.documents)
            ? item.documents.map(String)
            : [];
          return {
            id: String(item.id),
            document_count: safeNumber(item.document_count, 0),
            documents,
          };
        }
      }
      return { id: String(item), document_count: 0, documents: [] };
    });
  }

  if (data && typeof data === "object") {
    return Object.entries(data).map(([id, docs]) => ({
      id,
      document_count: Array.isArray(docs) ? docs.length : 0,
      documents: Array.isArray(docs) ? docs.map(String) : [],
    }));
  }

  return [];
}

function renderIngestedDocuments() {
  if (!ingestedDocuments) {
    return;
  }

  ingestedDocuments.innerHTML = "";

  const title = document.createElement("p");
  title.className = "ingested-docs-title";
  title.textContent = "Already ingested";
  ingestedDocuments.appendChild(title);

  if (!state.dossiers.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No ingested documents yet.";
    ingestedDocuments.appendChild(empty);
    return;
  }

  state.dossiers.forEach(item => {
    const block = document.createElement("div");
    block.className = "ingested-dossier";

    const head = document.createElement("p");
    head.className = "ingested-dossier-head";
    head.textContent = `Dossier ${item.id} (${safeNumber(item.document_count, 0)})`;
    block.appendChild(head);

    const docs = Array.isArray(item.documents) ? item.documents : [];
    if (docs.length === 0) {
      const none = document.createElement("p");
      none.className = "muted";
      none.textContent = "No files listed.";
      block.appendChild(none);
    } else {
      const list = document.createElement("ul");
      list.className = "ingested-file-list";
      docs.forEach(name => {
        const li = document.createElement("li");
        li.textContent = name;
        list.appendChild(li);
      });
      block.appendChild(list);
    }

    ingestedDocuments.appendChild(block);
  });
}

function normalizeJobStatus(value) {
  if (value === null || value === undefined) return "unknown";

  const raw = String(value).toLowerCase();
  if (raw === "1" || raw.includes("in_progress") || raw.includes("progress")) {
    return "in_progress";
  }
  if (raw === "2" || raw.includes("completed") || raw.includes("complete")) {
    return "completed";
  }
  if (raw === "3" || raw.includes("failed") || raw.includes("error")) {
    return "failed";
  }

  return raw;
}

async function request(path, options = {}) {
  const url = `${state.apiBase.replace(/\/$/, "")}${path}`;
  const response = await fetch(url, options);
  const bodyText = await response.text();
  let payload = null;

  if (bodyText) {
    try {
      payload = JSON.parse(bodyText);
    } catch (parseError) {
      console.warn("Response is not JSON", parseError);
      payload = bodyText;
    }
  }

  if (!response.ok) {
    const detail = payload?.detail || response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }

  return payload;
}

function setActiveTab(tabName) {
  tabButtons.forEach(btn => {
    const active = btn.dataset.tab === tabName;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  });

  Object.entries(tabPanels).forEach(([name, panel]) => {
    panel.classList.toggle("active", name === tabName);
  });

  if (tabName === "graph") {
    loadGraph();
  }
  if (tabName === "judge") {
    renderJudgeViews();
  }
}

function judgeMetadata(op) {
  return op?.metadata && typeof op.metadata === "object" ? op.metadata : {};
}

function judgeVerdict(op) {
  const metadata = judgeMetadata(op);
  if (metadata.status === "failed") {
    return "failed";
  }
  return String(metadata.verdict || "unknown");
}

function judgeReviewOperations() {
  const dossierId = currentDossierId();
  const operations = Array.isArray(state.metricsOperations) ? state.metricsOperations : [];
  return operations.filter(op => {
    if (operationTypeKey(op) !== "kg_judge") {
      return false;
    }
    if (!dossierId) {
      return true;
    }
    return String(judgeMetadata(op).dossier_id || "") === dossierId;
  });
}

function filteredJudgeReviews() {
  const selectedVerdict = judgeVerdictFilter ? judgeVerdictFilter.value : "";
  const reviews = judgeReviewOperations();
  if (!selectedVerdict) {
    return reviews;
  }
  return reviews.filter(op => judgeVerdict(op) === selectedVerdict);
}

function formatTimestamp(value) {
  if (!value) {
    return "Unknown time";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString();
}

function renderJudgeSummary(reviews) {
  if (!judgeSummaryCards) {
    return;
  }

  const rows = Array.isArray(reviews) ? reviews : [];
  const successful = rows.filter(op => judgeVerdict(op) !== "failed");
  const avgScore = successful.length
    ? successful.reduce((sum, op) => sum + safeNumber(judgeMetadata(op).score, 0), 0) / successful.length
    : 0;
  const passCount = rows.filter(op => judgeVerdict(op) === "pass").length;
  const attentionCount = rows.filter(op => {
    const verdict = judgeVerdict(op);
    return verdict === "needs_review" || verdict === "fail" || verdict === "failed";
  }).length;

  const cards = [
    ["Total reviews", rows.length],
    ["Average score", successful.length ? avgScore.toFixed(2) : "n/a"],
    ["Passed", passCount],
    ["Needs attention", attentionCount],
  ];

  judgeSummaryCards.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "metric-card";

    const p1 = document.createElement("p");
    p1.className = "metric-label";
    p1.textContent = label;

    const p2 = document.createElement("p");
    p2.className = "metric-value";
    p2.textContent = String(value);

    card.appendChild(p1);
    card.appendChild(p2);
    judgeSummaryCards.appendChild(card);
  });
}

function renderJudgeReviews(reviews) {
  if (!judgeReviewsList) {
    return;
  }

  judgeReviewsList.innerHTML = "";

  const rows = Array.isArray(reviews) ? reviews.slice().reverse() : [];
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No judge reviews recorded yet for the current filters.";
    judgeReviewsList.appendChild(empty);
    return;
  }

  rows.forEach(op => {
    const metadata = judgeMetadata(op);
    const verdict = judgeVerdict(op);
    const review = document.createElement("article");
    review.className = "judge-review-card";

    const head = document.createElement("div");
    head.className = "judge-review-head";

    const titleWrap = document.createElement("div");
    titleWrap.className = "judge-review-title";

    const title = document.createElement("strong");
    title.textContent = metadata.file_name || `Dossier ${metadata.dossier_id || "n/a"}`;

    const meta = document.createElement("span");
    meta.className = "operation-meta";
    meta.textContent = `${formatTimestamp(op.ts)} | dossier ${metadata.dossier_id || "n/a"} | ${op.model || "no-model"}`;

    titleWrap.appendChild(title);
    titleWrap.appendChild(meta);

    const badges = document.createElement("div");
    badges.className = "judge-review-badges";

    const verdictBadge = document.createElement("span");
    verdictBadge.className = `pill judge-badge ${verdict.replaceAll("_", "-")}`;
    verdictBadge.textContent = verdict.replaceAll("_", " ");
    badges.appendChild(verdictBadge);

    if (metadata.score !== undefined && metadata.score !== null && verdict !== "failed") {
      const scoreBadge = document.createElement("span");
      scoreBadge.className = "pill metrics";
      scoreBadge.textContent = `score ${safeNumber(metadata.score, 0).toFixed(2)}`;
      badges.appendChild(scoreBadge);
    }

    head.appendChild(titleWrap);
    head.appendChild(badges);
    review.appendChild(head);

    const summary = document.createElement("p");
    summary.className = "judge-review-summary";
    summary.textContent = metadata.summary || metadata.error_message || "No review summary recorded.";
    review.appendChild(summary);

    const stats = document.createElement("p");
    stats.className = "operation-meta";
    stats.textContent = `${safeNumber(op.latency_ms, 0).toFixed(1)} ms | ${safeNumber(op.total_tokens, 0)} tok | ${formatCurrency(op.cost_usd)}`;
    review.appendChild(stats);

    const flags = [];
    if (metadata.job_id) {
      flags.push(`job ${metadata.job_id}`);
    }
    if (metadata.document_text_truncated) {
      flags.push("document truncated");
    }
    if (metadata.graph_truncated) {
      flags.push("graph truncated");
    }
    if (flags.length) {
      const flagLine = document.createElement("p");
      flagLine.className = "judge-review-flags";
      flagLine.textContent = flags.join(" | ");
      review.appendChild(flagLine);
    }

    const strengths = Array.isArray(metadata.strengths) ? metadata.strengths : [];
    if (strengths.length) {
      const strengthsTitle = document.createElement("p");
      strengthsTitle.className = "judge-review-section-title";
      strengthsTitle.textContent = "Strengths";
      review.appendChild(strengthsTitle);

      const strengthsList = document.createElement("ul");
      strengthsList.className = "judge-review-points";
      strengths.forEach(item => {
        const li = document.createElement("li");
        li.textContent = String(item);
        strengthsList.appendChild(li);
      });
      review.appendChild(strengthsList);
    }

    const issues = Array.isArray(metadata.issues) ? metadata.issues : [];
    if (issues.length) {
      const issuesTitle = document.createElement("p");
      issuesTitle.className = "judge-review-section-title";
      issuesTitle.textContent = "Issues";
      review.appendChild(issuesTitle);

      const issuesList = document.createElement("ul");
      issuesList.className = "judge-review-points";
      issues.forEach(item => {
        const li = document.createElement("li");
        li.textContent = String(item);
        issuesList.appendChild(li);
      });
      review.appendChild(issuesList);
    }

    judgeReviewsList.appendChild(review);
  });
}

function renderJudgeViews() {
  const reviews = filteredJudgeReviews();
  renderJudgeSummary(reviews);
  renderJudgeReviews(reviews);
}

function renderDossierOptions() {
  const currentGlobal = globalDossierSelect.value;
  const currentGraph = graphDossierSelect ? graphDossierSelect.value : "";

  const fill = (selectEl, selectedValue) => {
    if (!selectEl) return;
    selectEl.innerHTML = `<option value="">All dossiers</option>`;
    state.dossiers.forEach(item => {
      const option = document.createElement("option");
      option.value = String(item.id);
      option.textContent = `Dossier ${item.id}`;
      selectEl.appendChild(option);
    });

    if (selectedValue && state.dossiers.some(d => String(d.id) === selectedValue)) {
      selectEl.value = selectedValue;
    }
  };

  fill(globalDossierSelect, currentGlobal);
  fill(graphDossierSelect, currentGraph);

  if (graphDossierSelect && !graphDossierSelect.value && globalDossierSelect.value) {
    graphDossierSelect.value = globalDossierSelect.value;
  }
}

async function loadDossiers() {
  try {
    const data = await request(apiPath("/dossiers/"));
    state.dossiers = normalizeDossiersPayload(data);
    renderDossierOptions();
    renderIngestedDocuments();
    setStatus(ingestStatus, `Dossiers loaded: ${state.dossiers.length}`);
  } catch (error) {
    if (ingestedDocuments) {
      ingestedDocuments.innerHTML = "";
      const unavailable = document.createElement("p");
      unavailable.className = "muted";
      unavailable.textContent = `Ingested documents unavailable: ${error.message}`;
      ingestedDocuments.appendChild(unavailable);
    }
    setStatus(ingestStatus, `Dossiers unavailable: ${error.message}`);
  }
}

function createMessageNode(role, content, meta = {}) {
  const message = document.createElement("article");
  message.className = `message ${role}`;

  const head = document.createElement("div");
  head.className = "message-head";

  const title = document.createElement("strong");
  title.textContent = role === "user" ? "You" : "Assistant";

  const metaWrap = document.createElement("div");
  metaWrap.className = "message-meta";

  if (meta.strategy) {
    const strategy = document.createElement("span");
    strategy.className = "pill";
    strategy.textContent = meta.strategy;
    metaWrap.appendChild(strategy);
  }

  if (meta.metrics) {
    const m = document.createElement("span");
    m.className = "pill metrics";
    const latency = safeNumber(meta.metrics.latency_ms, 0);
    const cost = formatCurrency(meta.metrics.cost_usd);
    m.textContent = `${latency} ms | ${cost}`;
    metaWrap.appendChild(m);
  }

  if (Array.isArray(meta.ocr_warnings) && meta.ocr_warnings.length) {
    const w = document.createElement("span");
    w.className = "pill warn";
    w.textContent = `OCR warnings: ${meta.ocr_warnings.length}`;
    metaWrap.appendChild(w);
  }

  head.appendChild(title);
  head.appendChild(metaWrap);

  const body = document.createElement("p");
  body.textContent = content || "No content returned.";

  message.appendChild(head);
  message.appendChild(body);

  if (Array.isArray(meta.sources) && meta.sources.length) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `Sources (${meta.sources.length})`;
    details.appendChild(summary);

    const list = document.createElement("ul");
    meta.sources.forEach(src => {
      const li = document.createElement("li");
      const filename = src.filename || "unknown";
      const dossier = src.dossier_id || "n/a";
      const docType = src.doc_type || "n/a";
      li.textContent = `${filename} | dossier ${dossier} | ${docType}`;
      list.appendChild(li);
    });

    details.appendChild(list);
    message.appendChild(details);
  }

  if (Array.isArray(meta.ocr_warnings) && meta.ocr_warnings.length) {
    const warning = document.createElement("p");
    warning.className = "muted";
    warning.textContent = meta.ocr_warnings.join(" | ");
    message.appendChild(warning);
  }

  return message;
}

function pushMessage(role, content, meta = {}) {
  const node = createMessageNode(role, content, meta);
  chatTimeline.appendChild(node);
  chatTimeline.scrollTop = chatTimeline.scrollHeight;
}

async function submitQuestion(event) {
  event.preventDefault();
  const question = chatQuestion.value.trim();
  if (!question) {
    return;
  }

  const dossierId = currentDossierId();
  pushMessage("user", question);
  chatQuestion.value = "";

  try {
    const payload = await request(apiPath("/query"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, dossier_id: dossierId }),
    });

    pushMessage("assistant", payload.answer || "", {
      strategy: payload.strategy,
      metrics: payload.metrics,
      sources: payload.sources,
      ocr_warnings: payload.ocr_warnings,
    });
  } catch (error) {
    pushMessage("assistant", `Request failed: ${error.message}`);
  }
}

function normalizeGraph(raw) {
  if (!raw || typeof raw !== "object") {
    return { nodes: [], links: [] };
  }

  const normalizeDossierValues = value => {
    if (Array.isArray(value)) {
      return value.map(String).filter(Boolean);
    }
    if (value === null || value === undefined) {
      return [];
    }
    return [String(value)];
  };

  const toNode = value => {
    if (value === null || value === undefined) {
      return null;
    }
    if (typeof value === "object") {
      const rawId = value.id ?? value.name ?? value.label;
      if (rawId === null || rawId === undefined) {
        return null;
      }
      const id = String(rawId);
      return {
        ...value,
        id,
        label: value.label || value.name || id,
      };
    }
    const id = String(value);
    return { id, label: id };
  };

  const nodeMap = new Map();
  const ensureNode = value => {
    const node = toNode(value);
    if (!node) return null;
    if (!nodeMap.has(node.id)) {
      nodeMap.set(node.id, node);
    }
    return node.id;
  };

  // Handle KGGen payloads: { entities: string[], relations: [[subj, pred, obj], ...] }
  const hasEntities = Array.isArray(raw.entities);
  const hasRelations = Array.isArray(raw.relations);
  if (hasEntities || hasRelations) {
    const entityMetadata = raw.entity_metadata && typeof raw.entity_metadata === "object"
      ? raw.entity_metadata
      : {};

    (raw.entities || []).forEach(entity => {
      const id = ensureNode(entity);
      if (id) {
        const existing = nodeMap.get(id);
        const dossiers = normalizeDossierValues(entityMetadata[id]);
        nodeMap.set(id, {
          ...existing,
          type: existing.type || "Entity",
          dossiers,
          dossier_id: dossiers.length === 1 ? dossiers[0] : undefined,
        });
      }
    });

    const links = (raw.relations || [])
      .map((triple, index) => {
        if (!Array.isArray(triple) || triple.length < 3) {
          return null;
        }
        const [subject, predicate, object] = triple;
        const source = ensureNode(subject);
        const target = ensureNode(object);
        if (!source || !target) {
          return null;
        }
        const relation = predicate === null || predicate === undefined
          ? "related_to"
          : String(predicate);
        return {
          id: `rel-${index}`,
          source,
          target,
          relation,
          label: relation,
        };
      })
      .filter(Boolean);

    return { nodes: Array.from(nodeMap.values()), links };
  }

  (raw.nodes || []).forEach(ensureNode);

  if (raw.entity_metadata && typeof raw.entity_metadata === "object") {
    Object.entries(raw.entity_metadata).forEach(([entityId, meta]) => {
      if (!nodeMap.has(entityId)) return;
      const existing = nodeMap.get(entityId);
      const dossiers = normalizeDossierValues(meta);
      nodeMap.set(entityId, {
        ...existing,
        dossiers,
        dossier_id: dossiers.length === 1 ? dossiers[0] : existing?.dossier_id,
      });
    });
  }

  let edgeCandidates = [];
  if (Array.isArray(raw.links)) {
    edgeCandidates = raw.links;
  } else if (Array.isArray(raw.edges)) {
    edgeCandidates = raw.edges;
  }

  const links = edgeCandidates
    .map((edge, index) => {
      if (!edge || typeof edge !== "object") {
        return null;
      }
      const sourceRaw =
        typeof edge.source === "object"
          ? edge.source.id ?? edge.source.name
          : edge.source;
      const targetRaw =
        typeof edge.target === "object"
          ? edge.target.id ?? edge.target.name
          : edge.target;

      if (sourceRaw === null || sourceRaw === undefined || targetRaw === null || targetRaw === undefined) {
        return null;
      }

      const source = ensureNode(sourceRaw);
      const target = ensureNode(targetRaw);
      if (!source || !target) {
        return null;
      }

      return {
        ...edge,
        id: edge.id || `edge-${index}`,
        source,
        target,
      };
    })
    .filter(Boolean);

  return { nodes: Array.from(nodeMap.values()), links };
}

function buildDossierColorMap(nodes) {
  const dossierIds = Array.from(
    new Set(
      (nodes || [])
        .flatMap(node => (Array.isArray(node.dossiers) ? node.dossiers : []))
        .map(String)
        .filter(Boolean)
    )
  ).sort((a, b) => a.localeCompare(b));

  const colorMap = {};
  dossierIds.forEach((dossierId, idx) => {
    colorMap[dossierId] = DOSSIER_NODE_COLORS[idx % DOSSIER_NODE_COLORS.length];
  });
  return colorMap;
}

function renderGraphLegend(dossierColorMap) {
  if (!graphLegend) {
    return;
  }

  graphLegend.innerHTML = "";

  const title = document.createElement("h3");
  title.textContent = "Legend";
  graphLegend.appendChild(title);

  const itemsWrap = document.createElement("div");
  itemsWrap.className = "legend-items";

  const entries = Object.entries(dossierColorMap || {});

  if (!entries.length) {
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = "No dossier metadata available in the current graph.";
    graphLegend.appendChild(note);
    return;
  }

  entries.forEach(([dossierId, color]) => {
    const item = document.createElement("span");
    item.className = "legend-item";

    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.backgroundColor = color;

    const text = document.createElement("span");
    text.textContent = `Dossier ${dossierId}`;

    item.appendChild(swatch);
    item.appendChild(text);
    itemsWrap.appendChild(item);
  });

  const sharedItem = document.createElement("span");
  sharedItem.className = "legend-item";

  const sharedSwatch = document.createElement("span");
  sharedSwatch.className = "legend-swatch";
  sharedSwatch.style.backgroundColor = MULTI_DOSSIER_NODE_COLOR;

  const sharedText = document.createElement("span");
  sharedText.textContent = "Shared entity (multiple dossiers)";

  sharedItem.appendChild(sharedSwatch);
  sharedItem.appendChild(sharedText);
  itemsWrap.appendChild(sharedItem);

  graphLegend.appendChild(itemsWrap);
}

function renderSelection(label, payload) {
  graphDetails.innerHTML = "";
  const title = document.createElement("h3");
  title.textContent = label;
  graphDetails.appendChild(title);

  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(payload, null, 2);
  graphDetails.appendChild(pre);
}

function renderGraph(data) {
  const { nodes, links } = normalizeGraph(data);
  graphCanvas.innerHTML = "";

  if (!nodes.length) {
    graphCanvas.textContent = "No graph nodes returned.";
    return;
  }

  const dossierColorMap = buildDossierColorMap(
    (state.graphData && Array.isArray(state.graphData.nodes) && state.graphData.nodes.length)
      ? state.graphData.nodes
      : nodes
  );

  const width = graphCanvas.clientWidth || 760;
  const height = graphCanvas.clientHeight || 520;

  const svg = d3
    .select(graphCanvas)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const root = svg.append("g");
  svg.call(
    d3.zoom().scaleExtent([0.25, 3]).on("zoom", event => {
      root.attr("transform", event.transform);
    })
  );

  const simulation = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(links)
        .id(d => d.id || d.name)
        .distance(86)
    )
    .force("charge", d3.forceManyBody().strength(-220))
    .force("center", d3.forceCenter(width / 2, height / 2));

  const link = root
    .append("g")
    .attr("stroke", "#b0b7bd")
    .attr("stroke-opacity", 0.7)
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke-width", 1.4)
    .on("click", (_, d) => renderSelection("Relation", d));

  const linkLabels = root
    .append("g")
    .selectAll("text")
    .data(links)
    .join("text")
    .text(d => d.label || d.relation || d.type || "")
    .attr("font-size", 10)
    .attr("fill", "#4b5563")
    .attr("text-anchor", "middle")
    .attr("pointer-events", "none");

  const node = root
    .append("g")
    .selectAll("circle")
    .data(nodes)
    .join("circle")
    .attr("r", d => (d.type === "Document" ? 6 : 8))
    .attr("fill", d => {
      if (d.inconsistency || d.inconsistencies) {
        return "#b91c1c";
      }
      if (Array.isArray(d.dossiers) && d.dossiers.length === 1) {
        return dossierColorMap[d.dossiers[0]] || "#374151";
      }
      if (Array.isArray(d.dossiers) && d.dossiers.length > 1) {
        return MULTI_DOSSIER_NODE_COLOR;
      }
      const type = (d.type || "").toString().toLowerCase();
      if (type.includes("person")) return "#2563eb";
      if (type.includes("property")) return "#0f766e";
      if (type.includes("transaction")) return "#9f1239";
      if (type.includes("document")) return "#92400e";
      if (type.includes("dossier")) return "#6d28d9";
      return "#374151";
    })
    .call(
      d3
        .drag()
        .on("start", event => {
          if (!event.active) simulation.alphaTarget(0.25).restart();
          event.subject.fx = event.subject.x;
          event.subject.fy = event.subject.y;
        })
        .on("drag", event => {
          event.subject.fx = event.x;
          event.subject.fy = event.y;
        })
        .on("end", event => {
          if (!event.active) simulation.alphaTarget(0);
          event.subject.fx = null;
          event.subject.fy = null;
        })
    )
    .on("click", (_, d) => renderSelection("Node", d));

  node.append("title").text(d => d.label || d.id || d.name || "node");

  const labels = root
    .append("g")
    .selectAll("text")
    .data(nodes)
    .join("text")
    .text(d => d.label || d.id || d.name || "")
    .attr("font-size", 11)
    .attr("fill", "#1f2937")
    .attr("dx", 10)
    .attr("dy", 3);

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    linkLabels
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2);

    node.attr("cx", d => d.x).attr("cy", d => d.y);
    labels.attr("x", d => d.x).attr("y", d => d.y);
  });

}

function filterGraphBySearch(term) {
  if (!state.graphData || !term) {
    renderGraph(state.graphData || { nodes: [], links: [] });
    return;
  }

  const q = term.trim().toLowerCase();
  const selectedNodeIds = new Set(
    state.graphData.nodes
      .filter(n => (n.label || n.id || n.name || "").toString().toLowerCase().includes(q))
      .map(n => n.id || n.name)
  );

  const links = state.graphData.links.filter(l => {
    const sourceId = typeof l.source === "object" ? l.source.id || l.source.name : l.source;
    const targetId = typeof l.target === "object" ? l.target.id || l.target.name : l.target;
    return selectedNodeIds.has(sourceId) || selectedNodeIds.has(targetId);
  });

  const nodes = state.graphData.nodes.filter(n => {
    const id = n.id || n.name;
    return selectedNodeIds.has(id) || links.some(l => {
      const sourceId = typeof l.source === "object" ? l.source.id || l.source.name : l.source;
      const targetId = typeof l.target === "object" ? l.target.id || l.target.name : l.target;
      return sourceId === id || targetId === id;
    });
  });

  renderGraph({ nodes, links });
}

async function loadGraph() {
  const dossierId = currentGraphDossierId();
  let path = apiPath("/graph/");
  if (dossierId) {
    path = `${path}?dossier_id=${encodeURIComponent(dossierId)}`;
  }

  try {
    const payload = await request(path);
    const graphSummary = normalizeGraph(payload);
    state.graphData = graphSummary;
    renderGraph(graphSummary);
    const dossierColorMap = buildDossierColorMap(graphSummary.nodes);
    renderGraphLegend(dossierColorMap);
    renderSelection("Graph Scope", {
      dossier_id: dossierId || "all",
      node_count: graphSummary.nodes.length,
      relation_count: graphSummary.links.length,
      dossier_color_legend: dossierColorMap,
      shared_entity_color: MULTI_DOSSIER_NODE_COLOR,
    });
  } catch (error) {
    graphCanvas.textContent = `Graph request failed: ${error.message}`;
    renderGraphLegend({});
  }
}

function renderMetricsCards(operations) {
  const selectedType = metricsOperationType ? metricsOperationType.value : "";
  const stats = summarizeOperations(operations);
  const totalLabel = selectedType ? `Total operations (${selectedType})` : "Total operations";
  const judgeOperations = (Array.isArray(operations) ? operations : []).filter(
    op => String(op?.name || "") === "kg_judge"
  );
  const judgeStats = summarizeOperations(judgeOperations);

  const cards = [
    [totalLabel, stats.total],
    ["Average latency", `${safeNumber(stats.avg_latency_ms, 0).toFixed(1)} ms`],
    ["P95 latency", `${safeNumber(stats.p95_latency_ms, 0).toFixed(1)} ms`],
    ["Total cost", formatCurrency(stats.total_cost_usd)],
  ];

  if (!selectedType && judgeOperations.length) {
    cards.push(
      ["Judge reviews", judgeStats.total],
      ["Judge avg latency", `${safeNumber(judgeStats.avg_latency_ms, 0).toFixed(1)} ms`],
      ["Judge total cost", formatCurrency(judgeStats.total_cost_usd)],
    );
  }

  metricsCards.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "metric-card";

    const p1 = document.createElement("p");
    p1.className = "metric-label";
    p1.textContent = label;

    const p2 = document.createElement("p");
    p2.className = "metric-value";
    p2.textContent = String(value);

    card.appendChild(p1);
    card.appendChild(p2);
    metricsCards.appendChild(card);
  });
}

function renderOperations(operations) {
  if (!operationsList) {
    return;
  }

  operationsList.innerHTML = "";

  const rows = Array.isArray(operations) ? operations.slice(-30).reverse() : [];
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No operation metrics recorded yet.";
    operationsList.appendChild(empty);
    return;
  }

  rows.forEach(op => {
    const row = document.createElement("article");
    row.className = "operation-row";

    const main = document.createElement("div");
    main.className = "operation-main";

    const name = document.createElement("span");
    name.className = "operation-name";
    name.textContent = `${op.name || "operation"}`;

    const meta = document.createElement("span");
    meta.className = "operation-meta";
    meta.textContent = `${op.category || "n/a"} | ${(op.model || "no-model")}`;

    main.appendChild(name);
    main.appendChild(meta);

    const stats = document.createElement("span");
    stats.className = "operation-stats";
    const latency = safeNumber(op.latency_ms, 0);
    const tokens = safeNumber(op.total_tokens, 0);
    const cost = formatCurrency(op.cost_usd);
    stats.textContent = `${latency.toFixed(1)} ms | ${tokens} tok | ${cost}`;

    row.appendChild(main);
    row.appendChild(stats);
    operationsList.appendChild(row);
  });
}

async function loadMetrics() {
  let operations = [];

  try {
    const payload = await request(apiPath("/metrics/operations"));
    operations = Array.isArray(payload) ? payload : [];
  } catch (error) {
    console.warn("Metrics operations unavailable", error);
    operations = [];
  }

  state.metricsOperations = operations;

  updateOperationTypeOptions(operations);

  const scopedOperations = filteredOperations();
  renderMetricsCards(scopedOperations);
  renderOperations(scopedOperations);
  renderJudgeViews();
}

function toggleUploadDrawer(open) {
  uploadDrawer.classList.toggle("open", open);
  uploadDrawer.setAttribute("aria-hidden", String(!open));
}

function setUploadProgress(percent) {
  const clamped = Math.max(0, Math.min(100, percent));
  uploadProgress.style.width = `${clamped}%`;
}

function stopIngestPolling() {
  if (state.ingestPollId) {
    clearInterval(state.ingestPollId);
    state.ingestPollId = null;
  }
}

function formatJudgeResult(statusPayload) {
  const judge = statusPayload?.kg_judge;
  if (!judge || typeof judge !== "object") {
    if (statusPayload?.kg_judge_error) {
      return `Judge unavailable: ${statusPayload.kg_judge_error}`;
    }
    return "";
  }

  const verdict = String(judge.verdict || "needs_review").replaceAll("_", " ");
  const score = safeNumber(judge.score, 0);
  const summary = judge.summary ? String(judge.summary) : "No summary returned.";
  return `KG judge: ${verdict} (${score.toFixed(2)}). ${summary}`;
}

function renderIngestResult(statusPayload) {
  if (!statusPayload || typeof statusPayload !== "object") {
    return;
  }

  const status = normalizeJobStatus(statusPayload.status);

  if (status === "completed") {
    const judgeMessage = formatJudgeResult(statusPayload);
    const completedMessage = `Completed. Job ${statusPayload.job_id || "n/a"}.`;
    setStatus(uploadFeedback, judgeMessage ? `${completedMessage} ${judgeMessage}` : completedMessage);
    setStatus(ingestStatus, "Ingestion completed.");
    setUploadProgress(100);
    stopIngestPolling();
    loadDossiers();
    loadMetrics();
    return;
  }

  if (status === "failed") {
    setStatus(uploadFeedback, `Failed: ${statusPayload.error_message || "Unknown error"}`);
    setStatus(ingestStatus, "Ingestion failed.");
    setUploadProgress(100);
    stopIngestPolling();
    return;
  }

  setUploadProgress(40);
  setStatus(uploadFeedback, `Status: ${status}.`);
  setStatus(ingestStatus, "Ingestion running.");
}

function beginIngestPolling(jobId) {
  stopIngestPolling();

  state.ingestPollId = setInterval(async () => {
    try {
      const statusPayload = await request(apiPath(`/ingest/status/${encodeURIComponent(jobId)}`));
      renderIngestResult(statusPayload);
    } catch (error) {
      setStatus(uploadFeedback, `Status check failed: ${error.message}`);
    }
  }, 2000);
}

async function submitUpload(event) {
  event.preventDefault();

  const dossierId = uploadDossierId.value.trim();
  const file = uploadFile.files[0];

  if (!dossierId || !file) {
    setStatus(uploadFeedback, "Dossier ID and file are required.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("dossier_id", dossierId);

  try {
    setStatus(uploadFeedback, "Submitting ingestion job...");
    setUploadProgress(5);

    const payload = await request(apiPath("/ingest/"), {
      method: "POST",
      body: formData,
    });

    const jobId = payload?.job_id;
    if (!jobId) {
      throw new Error("No job_id returned");
    }

    setStatus(uploadFeedback, `Job accepted: ${jobId}`);
    setStatus(ingestStatus, `Ingestion job ${jobId} started.`);
    beginIngestPolling(jobId);
  } catch (error) {
    setStatus(uploadFeedback, `Upload failed: ${error.message}`);
    setStatus(ingestStatus, "Ingestion request failed.");
    setUploadProgress(0);
  }
}

function bindEvents() {
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
  });

  document.getElementById("saveApiBase").addEventListener("click", () => {
    state.apiBase = apiInput.value.trim() || "http://localhost:8000";
    localStorage.setItem("primmo_api_base", state.apiBase);
    loadDossiers();
    loadMetrics();
  });

  refreshDossiersBtn.addEventListener("click", loadDossiers);
  globalDossierSelect.addEventListener("change", () => {
    if (graphDossierSelect) {
      graphDossierSelect.value = globalDossierSelect.value;
    }
    if (tabPanels.graph.classList.contains("active")) {
      loadGraph();
    }
    renderJudgeViews();
  });
  chatForm.addEventListener("submit", submitQuestion);
  loadGraphBtn.addEventListener("click", loadGraph);
  if (graphDossierSelect) {
    graphDossierSelect.addEventListener("change", () => {
      if (tabPanels.graph.classList.contains("active")) {
        loadGraph();
      }
    });
  }
  refreshMetricsBtn.addEventListener("click", loadMetrics);
  if (metricsOperationType) {
    metricsOperationType.addEventListener("change", () => {
      const scopedOperations = filteredOperations();
      renderMetricsCards(scopedOperations);
      renderOperations(scopedOperations);
    });
  }
  if (refreshJudgeReviewsBtn) {
    refreshJudgeReviewsBtn.addEventListener("click", loadMetrics);
  }
  if (judgeVerdictFilter) {
    judgeVerdictFilter.addEventListener("change", renderJudgeViews);
  }

  graphSearch.addEventListener("input", event => {
    filterGraphBySearch(event.target.value || "");
  });

  openUploadDrawerBtn.addEventListener("click", () => toggleUploadDrawer(true));
  closeUploadDrawerBtn.addEventListener("click", () => toggleUploadDrawer(false));
  uploadForm.addEventListener("submit", submitUpload);
}

async function init() {
  apiInput.value = state.apiBase;
  bindEvents();

  pushMessage(
    "assistant",
    "Ready. This frontend targets /api/v1 on your configured API base and displays only returned data."
  );

  await loadDossiers();
  await loadMetrics();
}

await init();
