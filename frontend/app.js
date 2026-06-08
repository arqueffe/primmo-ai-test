const state = {
  apiBase: localStorage.getItem("primmo_api_base") || "http://localhost:8000",
  dossiers: [],
  chatMessages: [],
  graphData: null,
  metricsHistory: [],
  ingestPollId: null,
};

const API_PREFIX = "/api/v1";

const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
const tabPanels = {
  chat: document.getElementById("tab-chat"),
  graph: document.getElementById("tab-graph"),
  metrics: document.getElementById("tab-metrics"),
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
const metricsCards = document.getElementById("metricsCards");
const openUploadDrawerBtn = document.getElementById("openUploadDrawer");
const closeUploadDrawerBtn = document.getElementById("closeUploadDrawer");
const uploadDrawer = document.getElementById("uploadDrawer");
const uploadForm = document.getElementById("uploadForm");
const uploadDossierId = document.getElementById("uploadDossierId");
const uploadFile = document.getElementById("uploadFile");
const uploadFeedback = document.getElementById("uploadFeedback");
const uploadProgress = document.getElementById("uploadProgress");

const latencyChart = document.getElementById("latencyChart");
const costChart = document.getElementById("costChart");
const strategyChart = document.getElementById("strategyChart");
const tokenChart = document.getElementById("tokenChart");

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

function apiPath(path) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_PREFIX}${normalized}`;
}

function normalizeDossiersPayload(data) {
  if (Array.isArray(data)) {
    return data.map(item => {
      if (item && typeof item === "object") {
        if ("id" in item) {
          return {
            id: String(item.id),
            document_count: safeNumber(item.document_count, 0),
          };
        }
      }
      return { id: String(item), document_count: 0 };
    });
  }

  if (data && typeof data === "object") {
    return Object.entries(data).map(([id, docs]) => ({
      id,
      document_count: Array.isArray(docs) ? docs.length : 0,
    }));
  }

  return [];
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
    setStatus(ingestStatus, `Dossiers loaded: ${state.dossiers.length}`);
  } catch (error) {
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

function drawLineChart(svg, points, color, formatter = String) {
  const width = 600;
  const height = 220;
  const padX = 36;
  const padY = 18;

  while (svg.firstChild) svg.firstChild.remove();

  if (!points.length) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", "20");
    text.setAttribute("y", "30");
    text.setAttribute("fill", "#64748b");
    text.textContent = "No history data returned.";
    svg.appendChild(text);
    return;
  }

  const maxY = Math.max(...points.map(p => p.y), 1);

  const path = points
    .map((p, i) => {
      const x = padX + (i * (width - padX * 2)) / Math.max(points.length - 1, 1);
      const y = height - padY - (p.y / maxY) * (height - padY * 2);
      return `${i === 0 ? "M" : "L"}${x} ${y}`;
    })
    .join(" ");

  const axis = document.createElementNS("http://www.w3.org/2000/svg", "line");
  axis.setAttribute("x1", String(padX));
  axis.setAttribute("y1", String(height - padY));
  axis.setAttribute("x2", String(width - padX));
  axis.setAttribute("y2", String(height - padY));
  axis.setAttribute("stroke", "#cbd5e1");
  svg.appendChild(axis);

  const pathEl = document.createElementNS("http://www.w3.org/2000/svg", "path");
  pathEl.setAttribute("d", path);
  pathEl.setAttribute("stroke", color);
  pathEl.setAttribute("stroke-width", "2.5");
  pathEl.setAttribute("fill", "none");
  svg.appendChild(pathEl);

  const latest = points[points.length - 1];
  const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
  label.setAttribute("x", String(width - 160));
  label.setAttribute("y", "20");
  label.setAttribute("fill", "#1f2937");
  label.textContent = `Latest: ${formatter(latest.y)}`;
  svg.appendChild(label);
}

function drawStrategyPie(svg, history) {
  while (svg.firstChild) svg.firstChild.remove();

  if (!history.length) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", "12");
    text.setAttribute("y", "30");
    text.setAttribute("fill", "#64748b");
    text.textContent = "No strategy data returned.";
    svg.appendChild(text);
    return;
  }

  const counts = history.reduce((acc, item) => {
    const key = item.strategy || "unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  const entries = Object.entries(counts);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);

  const colors = ["#2563eb", "#0f766e", "#b45309", "#7c3aed", "#be123c"];
  let angle = -Math.PI / 2;
  const cx = 110;
  const cy = 110;
  const r = 72;

  entries.forEach(([name, count], idx) => {
    const ratio = count / total;
    const next = angle + ratio * Math.PI * 2;

    const x1 = cx + r * Math.cos(angle);
    const y1 = cy + r * Math.sin(angle);
    const x2 = cx + r * Math.cos(next);
    const y2 = cy + r * Math.sin(next);
    const largeArc = ratio > 0.5 ? 1 : 0;

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute(
      "d",
      `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`
    );
    path.setAttribute("fill", colors[idx % colors.length]);
    svg.appendChild(path);

    const legend = document.createElementNS("http://www.w3.org/2000/svg", "text");
    legend.setAttribute("x", "210");
    legend.setAttribute("y", String(30 + idx * 20));
    legend.setAttribute("fill", "#1f2937");
    legend.textContent = `${name}: ${count}`;
    svg.appendChild(legend);

    angle = next;
  });
}

function renderMetricsCards(summary, history) {
  const totalQueries = safeNumber(summary.total_queries, history.length);
  const avgLatency = safeNumber(summary.avg_latency_ms, 0);
  const p95Latency = safeNumber(summary.p95_latency_ms, 0);
  const totalCost = safeNumber(summary.total_cost_usd, 0);
  const avgRelevance = summary.avg_relevance_score ?? "n/a";

  const cards = [
    ["Total queries", totalQueries],
    ["Average latency", `${avgLatency.toFixed(1)} ms`],
    ["P95 latency", `${p95Latency.toFixed(1)} ms`],
    ["Total cost", formatCurrency(totalCost)],
    ["Average relevance", avgRelevance],
  ];

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

async function loadMetrics() {
  let summary = {};
  let history = [];

  try {
    summary = await request(apiPath("/metrics/summary"));
  } catch (error) {
    console.warn("Metrics summary unavailable", error);
    summary = {};
  }

  try {
    const payload = await request(apiPath("/metrics/history"));
    history = Array.isArray(payload) ? payload : [];
  } catch (error) {
    console.warn("Metrics history unavailable", error);
    history = [];
  }

  state.metricsHistory = history;
  renderMetricsCards(summary, history);

  const latencyPoints = history.map((h, i) => ({ x: i, y: safeNumber(h.latency_ms, 0) }));
  drawLineChart(latencyChart, latencyPoints, "#2563eb", v => `${v.toFixed(1)} ms`);

  let runningCost = 0;
  const costPoints = history.map((h, i) => {
    runningCost += safeNumber(h.cost_usd, 0);
    return { x: i, y: runningCost };
  });
  drawLineChart(costChart, costPoints, "#0f766e", v => `$${v.toFixed(5)}`);

  drawStrategyPie(strategyChart, history);

  const tokenPoints = history.map((h, i) => ({
    x: i,
    y: safeNumber(h.prompt_tokens, 0) + safeNumber(h.completion_tokens, 0),
  }));
  drawLineChart(tokenChart, tokenPoints, "#b45309", v => `${v.toFixed(0)} tok`);
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

function renderIngestResult(statusPayload) {
  if (!statusPayload || typeof statusPayload !== "object") {
    return;
  }

  const status = normalizeJobStatus(statusPayload.status);

  if (status === "completed") {
    setStatus(uploadFeedback, `Completed. Job ${statusPayload.job_id || "n/a"}.`);
    setStatus(ingestStatus, "Ingestion completed.");
    setUploadProgress(100);
    stopIngestPolling();
    loadDossiers();
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
