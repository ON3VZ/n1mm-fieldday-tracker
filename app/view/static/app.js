/* Field Day Tracker — static view (§10.2).
 *
 * One implementation for local use and the published GitHub Pages copy:
 * it polls snapshot.json with cache-busting and renders everything
 * client-side. The snapshot's `readonly` flag slows polling for the public
 * copy; editing hooks (overrides) arrive with the local server API and are
 * only active when the snapshot is not readonly.
 *
 * No external dependencies, no CDN fonts: the field may have no internet.
 * All UI strings live in the STRINGS table (BR-12 / §13); more languages
 * are wired in the i18n phase.
 */
"use strict";

/* ------------------------------------------------------------------ i18n */

const STRINGS = {
  en: {
    "live.loading": "Loading…",
    "live.updated": "Live — updated {s} ago",
    "live.stale": "No data — last update {s}s ago",
    "live.readonly": "Public view — updated {s} ago",
    "view.matrix": "Matrix",
    "view.towork": "Still to work",
    "view.band": "Per band",
    "view.station": "Per station",
    "view.sources": "Per source PC",
    "view.stats": "Statistics",
    "filter.search": "Search callsign…",
    "filter.status.all": "All statuses",
    "filter.status.worked": "Worked",
    "filter.status.open": "Not worked",
    "filter.status.partial": "Partially worked",
    "filter.band.all": "All bands",
    "filter.category.all": "All categories",
    "filter.section.all": "All sections",
    "col.callsign": "Callsign",
    "col.band": "Band",
    "col.category": "Category",
    "col.section": "Section",
    "col.status": "Status",
    "col.time": "Time (UTC)",
    "col.mode": "Mode",
    "col.freq": "Freq (kHz)",
    "col.source": "Source",
    "towork.none": "Nothing left to work — everything is done!",
    "towork.count": "{n} open combinations",
    "band.progress": "{worked} of {total} worked",
    "station.pick": "Pick a station",
    "station.qsos": "QSOs",
    "station.noqsos": "No QSOs yet for this station.",
    "sources.none": "No source PCs seen yet. Check the N1MM Broadcast Data settings.",
    "sources.lastseen": "Last packet",
    "sources.packets": "packets",
    "sources.fresh": "LIVE",
    "sources.stale": "STALE",
    "sources.worked": "cells worked via this PC",
    "stats.stations": "Stations",
    "stats.cells": "Combinations",
    "stats.worked": "Worked",
    "stats.open": "Open",
    "stats.excluded": "Excluded",
    "stats.manual": "Manual overrides",
    "stats.complete": "Fully worked",
    "stats.partial": "Partially worked",
    "stats.untouched": "Not worked yet",
    "stats.perband": "Per band",
    "stats.percategory": "Per category",
    "stats.progress": "Progress over time (worked cells)",
    "detail.qso": "Worked",
    "detail.manual": "Manual override",
    "detail.reason": "Reason",
    "detail.setby": "Set by",
    "detail.qsocount": "QSO count",
    "status.not_worked": "Not worked",
    "status.worked_by_n1mm": "Worked (N1MM)",
    "status.manual_worked": "Worked (manual)",
    "status.manual_not_worked": "Not worked (manual)",
    "status.excluded": "Excluded",
    "matrix.none": "No stations match the current filters.",
    "manage.open": "Manage",
    "manual.open": "Manual",
    "manual.title": "Quick manual",
    "manual.close": "Close",
    "pub.none.title": "No active field day",
    "pub.none.body": "There is currently no field day being tracked.",
    "pub.none.next": "Next planned: {name} on {date}.",
    "pub.upcoming.title": "Field day starts soon",
    "pub.upcoming.body": "{name} starts on {date}.",
    "pub.upcoming.countdown": "Starts in {d}d {h}h {m}m.",
    "pub.expired.title": "This field day has ended",
    "pub.expired.body": "The results are no longer shown here.",
    "manage.title": "Field day management",
    "manage.fielddays": "Field days",
    "manage.activate": "Open",
    "fd.export": "Export this field day to a file",
    "fd.delete": "Delete this field day",
    "fd.import": "Import field day from file…",
    "fd.imported": "Field day imported: {name} ({q} QSOs, {s} stations).",
    "fd.deleted": "Field day deleted.",
    "fd.deleteprompt": "Delete \"{name}\" and ALL its logs permanently? This cannot be undone.\n\nType DELETE to confirm:",
    "fd.deletemismatch": "Not deleted — you did not type DELETE.",
    "help.bundle": "Export writes the ENTIRE field day (settings, stations, all QSOs, manual statuses) to one .fdtracker file. Copy it to another PC and use Import there to continue working. Import always creates a NEW field day, so it never overwrites existing data.",
    "manage.newfd": "New field day",
    "manage.name": "Name",
    "manage.start": "Start (local time)",
    "manage.end": "End (local time)",
    "manage.copyfrom": "Copy from (stations, bands, settings)",
    "manage.copynone": "— start empty —",
    "manage.create": "Create field day",
    "manage.editfd": "Edit current field day",
    "manage.location": "Location",
    "manage.eventcall": "Event callsign",
    "manage.club": "Organizing club",
    "manage.bands": "Bands to track",
    "manage.save": "Save changes",
    "manage.import": "Participant list",
    "manage.importbtn": "Import Excel/CSV…",
    "manage.importmissing": "These stations are in the current list but NOT in the new file:",
    "manage.importconfirm": "Remove them and import",
    "manage.importcancel": "Cancel import",
    "manage.adif": "ADIF import (safety net)",
    "manage.adifbtn": "Import ADIF file…",
    "manage.synctitle": "Synchronisation",
    "manage.syncbtn": "Full resync now",
    "manage.done": "Done.",
    "manage.created": "Field day created and available in the list.",
    "manage.imported": "{n} stations imported.",
    "manage.adifreport": "Read {read} — new {new}, duplicates {dup}, outside period {out}, unknown station {unk}.",
    "manage.syncreport": "Resync done: {matched} of {total} QSOs count.",
    "manage.error": "That did not work: {e}",
    "ov.title": "Set status manually",
    "ov.worked": "Mark worked",
    "ov.notworked": "Mark NOT worked",
    "ov.exclude": "Exclude",
    "ov.clear": "Clear manual status",
    "ov.reason": "Reason (optional)",
    "rmst.title": "Remove station",
    "rmst.hint": "Removes this station from the participant list. Received QSOs are kept on disk; re-importing the list or re-adding the callsign brings it back.",
    "rmst.button": "Remove this station",
    "rmst.confirm": "Remove station {name} from the list?",
    "rmst.removed": "Station removed.",
    "set.title": "Settings",
    "set.language": "Language (translations follow in a later update)",
    "set.udphost": "UDP listen address (127.0.0.1 = this laptop only, 0.0.0.0 = also other PCs)",
    "set.udpport": "UDP port",
    "set.fresh": "Stale after (seconds without packets)",
    "set.strict": "Strict callsign matching (ON4BAF/P ≠ ON4BAF)",
    "set.colors": "Status colors",
    "set.savefd": "Save technical settings",
    "set.exportfolder": "Export folder (empty = default)",
    "set.saveapp": "Save app settings",
    "set.udprestarted": "Saved — UDP listener restarted on the new address.",
    "filter.clear": "Clear all filters",
    "help.udphost": "In N1MM: Config > Configure Ports... > tab 'Broadcast Data'. Tick 'Contacts' and set the destination to this laptop's address + port. Use 127.0.0.1 when N1MM runs on THIS laptop; use this laptop's network IP (and set the address here to 0.0.0.0) when N1MM runs on another PC.",
    "help.udpport": "The UDP port N1MM broadcasts to. Default 12060. It must be exactly the same number here and in N1MM's Broadcast Data settings.",
    "help.strict": "OFF (recommended): ON4BAF/P and ON4BAF count as the same station. ON: only the exact callsign as written counts, so /P, /M or a prefix make a different station. Changing this recalculates the whole matrix.",
    "help.fresh": "How many seconds a source PC may be silent before it is shown as STALE (possible cable/network problem). Default 120.",
    "help.excel": "The participant list is recognised by COLUMN HEADERS (first row), not by order — so columns may be in any order. Recognised headers: Callsign (Call / Callsign / Roepnaam) — required; Name (Naam); Club; Category (Categorie); Section (Sectie); Remarks (Opmerking). Band columns (e.g. 40m, 80m) are picked up automatically. Extra columns are ignored. Only a callsign column is mandatory.",
    "help.adifbtn": "Pulls the FULL log out of N1MM. In N1MM: File > Export > Export to ADIF, then import that .adi file here. Already-known QSOs are skipped automatically, so you can do this as often as you like — also to catch up after the tracker was switched off.",
    "help.repo": "The GitHub repository as owner/name, e.g. ON3VZ/velddag-live. Do NOT paste the full https://github.com/... link.",
    "help.token": "A fine-grained personal access token with 'Contents: Read and write' on only the publish repository. It is stored in the OS keyring, never in a file.",
    "manage.adifperiodhint": "Tip: these QSOs fall outside the field day period — check the start/end of the field day (Manage → Edit).",
    "addst.button": "+ Station",
    "addst.title": "Add station manually",
    "addst.call": "Callsign (required)",
    "addst.category": "Category",
    "addst.section": "Section",
    "addst.remarks": "Remarks",
    "addst.save": "Add station",
    "addst.added": "Station added.",
    "close.title": "Close / reopen field day",
    "close.button": "Close field day",
    "close.confirm": "Close this field day? Viewing stays possible, but no new QSOs, imports or manual changes are accepted until you reopen it.",
    "close.closed": "Field day closed.",
    "reopen.button": "Reopen field day",
    "reopen.confirm": "Reopen this field day? QSO reception and editing become possible again.",
    "reopen.done": "Field day reopened — UDP reception restarted.",
    "closed.badge": "CLOSED",
    "export.title": "Export",
    "export.pdf": "Export PDF (A4 landscape)",
    "export.csv": "Export CSV",
    "pub.title": "Publish to GitHub Pages",
    "pub.warning": "Warning: the published page is PUBLIC. Anyone with the link sees callsigns and worked status. Remarks and operator notes are omitted unless you enable the option below.",
    "pub.enabled": "Automatic publishing enabled",
    "pub.repo": "Repository (owner/name, e.g. ON3VZ/velddag-live)",
    "pub.branch": "Branch",
    "pub.path": "Folder in the repo (empty = root)",
    "pub.interval": "Publish every N minutes (0 = manual only)",
    "pub.private": "Include remarks and operator notes on the public page",
    "pub.token": "Fine-grained token (stored in the OS keyring, never shown again)",
    "pub.savetoken": "Store token",
    "pub.save": "Save publish settings",
    "pub.now": "Publish now",
    "pub.tokenok": "Token stored securely.",
    "pub.result": "Published: {up} uploaded, {skip} unchanged.",
    "pub.resulterr": "Publish failed: {e}",
    "pub.offline": "No internet connection — publishing paused. It will resume automatically when you are back online.",
    "pub.pagesurl": "Public page:",
    "pub.tokenset": "token configured",
    "pub.notoken": "no token yet",
  },
};

let lang = "en";
function t(key, vars) {
  let text = (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.en[key] || key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replace("{" + name + "}", String(value));
    }
  }
  return text;
}

/* ------------------------------------------------------------- app state */

const POLL_LOCAL_MS = 5000;
const POLL_READONLY_MS = 30000;

const state = {
  snapshot: null,
  view: "matrix",
  band: null,             // selected band in "per band" view
  stationKey: null,       // selected station in "per station" view
  lastFetchOk: null,      // Date of last successful fetch
  fetchFailed: false,
  sort: { key: "callsign", dir: 1 },
  filters: { search: "", status: "all", band: "all", category: "all", section: "all" },
};

const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

const WORKED = new Set(["worked_by_n1mm", "manual_worked"]);

/* ------------------------------------------------------------- polling */

async function fetchSnapshot() {
  try {
    const response = await fetch("snapshot.json?_=" + Date.now(), { cache: "no-store" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    state.snapshot = data;
    state.lastFetchOk = new Date();
    state.fetchFailed = false;
    render();
  } catch (err) {
    state.fetchFailed = true;
    renderLivebar();
  } finally {
    const readonly = state.snapshot && state.snapshot.readonly;
    setTimeout(fetchSnapshot, readonly ? POLL_READONLY_MS : POLL_LOCAL_MS);
  }
}

function snapshotAgeSeconds() {
  // Op de publieke pagina telt het moment waarop de TRACKER de snapshot
  // maakte/pushte, niet wanneer de browser hem ophaalde.
  const snap = state.snapshot;
  if (snap && snap.readonly && snap.generated_at_utc) {
    const made = Date.parse(snap.generated_at_utc);
    if (!isNaN(made)) return Math.max(0, Math.round((Date.now() - made) / 1000));
  }
  return state.lastFetchOk
    ? Math.round((Date.now() - state.lastFetchOk.getTime()) / 1000)
    : null;
}

function humanAge(seconds) {
  if (seconds == null) return "";
  if (seconds < 90) return seconds + "s";
  const min = Math.round(seconds / 60);
  if (min < 90) return min + " min";
  const hours = Math.round(min / 60);
  return hours + " h";
}

function renderLivebar() {
  const bar = $("livebar");
  const seconds = snapshotAgeSeconds();
  if (state.fetchFailed || seconds === null) {
    bar.className = "livebar stale";
    $("live-text").textContent =
      seconds === null ? t("live.loading") : t("live.stale", { s: seconds });
    return;
  }
  bar.className = "livebar live";
  const key = state.snapshot && state.snapshot.readonly ? "live.readonly" : "live.updated";
  $("live-text").textContent = t(key, { s: humanAge(seconds) });
}
setInterval(renderLivebar, 1000);

/* ------------------------------------------------------------------ api */

async function api(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const data = await response.json().catch(() => ({ ok: false, error: "bad response" }));
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || ("HTTP " + response.status));
  }
  return data;
}

async function refreshNow() {
  try {
    const response = await fetch("snapshot.json?_=" + Date.now(), { cache: "no-store" });
    if (response.ok) {
      state.snapshot = await response.json();
      state.lastFetchOk = new Date();
      state.fetchFailed = false;
      render();
    }
  } catch (err) { /* de polling herstelt dit vanzelf */ }
}

function fileToB64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(new Error("file read failed"));
    reader.readAsDataURL(file);
  });
}

/* -------------------------------------------------------------- helpers */

function stationStatusClass(station, bands) {
  let worked = 0, countable = 0;
  for (const band of bands) {
    const status = station.cells[band] ? station.cells[band].status : "not_worked";
    if (status === "excluded") continue;
    countable += 1;
    if (WORKED.has(status)) worked += 1;
  }
  if (countable > 0 && worked === countable) return "worked";
  if (worked === 0) return "open";
  return "partial";
}

function visibleStations() {
  const snap = state.snapshot;
  const f = state.filters;
  const needle = f.search.trim().toUpperCase();
  return snap.stations.filter((station) => {
    if (needle && !station.callsign.toUpperCase().includes(needle) &&
        !station.normalized.toUpperCase().includes(needle)) return false;
    if (f.category !== "all" && station.category !== f.category) return false;
    if (f.section !== "all" && station.section !== f.section) return false;
    if (f.status !== "all" &&
        stationStatusClass(station, snap.field_day.bands) !== f.status) return false;
    return true;
  });
}

function visibleBands() {
  const bands = state.snapshot.field_day.bands;
  return state.filters.band === "all" ? bands : bands.filter((b) => b === state.filters.band);
}

function cellColor(status) {
  return state.snapshot.colors[status] || "#ffffff";
}

function fmtUtc(iso) {
  return iso ? iso.replace("T", " ").replace("Z", "") : "";
}

/* ---------------------------------------------------------------- render */

function render() {
  if (!state.snapshot) return;
  const snap = state.snapshot;
  if (snap.ui_language && snap.ui_language !== lang) {
    lang = STRINGS[snap.ui_language] ? snap.ui_language : "en";
    applyStaticStrings();
  }

  // Block C: on the public page a non-live publication state shows a simple
  // notice instead of the matrix (no station data is present in that case).
  const pub = snap.publication;
  if (pub && pub.state && pub.state !== "live") {
    renderPublicationNotice(pub);
    return;
  }
  const notice = $("pub-notice");
  if (notice) notice.remove();

  document.title = snap.field_day.name + " — Field Day Tracker";
  $("fd-name").textContent = snap.field_day.name;
  $("fd-callsign").textContent = snap.field_day.event_callsign;
  $("fd-period").textContent =
    fmtUtc(snap.field_day.start_utc) + " → " + fmtUtc(snap.field_day.end_utc) + " UTC";

  renderLivebar();
  const manageBtn = $("manage-open");
  if (manageBtn) manageBtn.style.display = snap.readonly ? "none" : "";
  const manualBtn = $("manual-open");
  if (manualBtn) manualBtn.style.display = snap.readonly ? "none" : "";
  ensureAddButton();
  renderClosedBadge();
  renderFilterOptions();
  renderTabs();
  renderLegend();

  const root = $("view-root");
  const views = {
    matrix: renderMatrix, towork: renderToWork, band: renderBand,
    station: renderStation, sources: renderSources, stats: renderStats,
  };
  root.innerHTML = "";
  root.appendChild(views[state.view]());
}

function ensureAddButton() {
  if (state.snapshot.readonly) return;
  if (!$("addst-open")) {
    const button = document.createElement("button");
    button.id = "addst-open";
    button.className = "btn secondary";
    button.textContent = t("addst.button");
    $("filters").appendChild(button);
  }
}

function renderTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === state.view);
    tab.setAttribute("aria-selected", tab.dataset.view === state.view);
  });
}

function renderFilterOptions() {
  const snap = state.snapshot;
  fillSelect($("f-band"), "band", ["all", ...snap.field_day.bands],
    (v) => (v === "all" ? t("filter.band.all") : v));
  const categories = [...new Set(snap.stations.map((s) => s.category).filter(Boolean))].sort();
  fillSelect($("f-category"), "category", ["all", ...categories],
    (v) => (v === "all" ? t("filter.category.all") : v));
  const sections = [...new Set(snap.stations.map((s) => s.section).filter(Boolean))].sort();
  fillSelect($("f-section"), "section", ["all", ...sections],
    (v) => (v === "all" ? t("filter.section.all") : v));
}

function fillSelect(select, filterKey, values, label) {
  // Keep the visible select and the internal filter state in lockstep:
  // a stale value (e.g. a category that vanished after a re-import) must
  // reset to "all", never linger invisibly and filter everything out.
  if (!values.includes(state.filters[filterKey])) {
    state.filters[filterKey] = "all";
  }
  select.innerHTML = "";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label(value);
    select.appendChild(option);
  }
  select.value = state.filters[filterKey];
}

function anyFilterActive() {
  const f = state.filters;
  return f.search.trim() !== "" || f.status !== "all" || f.band !== "all" ||
    f.category !== "all" || f.section !== "all";
}

function clearFilters() {
  state.filters = { search: "", status: "all", band: "all",
                    category: "all", section: "all" };
  $("f-search").value = "";
  $("f-status").value = "all";
  render();
}

function emptyStateHtml(messageKey) {
  let html = '<div class="empty">' + esc(t(messageKey));
  if (anyFilterActive()) {
    html += '<br><button class="btn secondary" id="clear-filters" style="margin-top:0.7rem">' +
      esc(t("filter.clear")) + "</button>";
  }
  return html + "</div>";
}

function renderClosedBadge() {
  const closed = state.snapshot.field_day.closed;
  let badge = $("closed-badge");
  if (closed && !badge) {
    badge = document.createElement("span");
    badge.id = "closed-badge";
    badge.className = "closed-badge";
    badge.textContent = t("closed.badge");
    document.querySelector(".topbar-brand").appendChild(badge);
  } else if (!closed && badge) {
    badge.remove();
  }
}

function renderLegend() {
  const snap = state.snapshot;
  const legend = $("legend");
  legend.innerHTML = "";
  for (const status of Object.keys(snap.legend)) {
    const item = document.createElement("span");
    item.className = "key";
    const manualMark = status.startsWith("manual") || status === "excluded" ? " ✎" : "";
    item.innerHTML =
      '<span class="swatch" style="background:' + esc(cellColor(status)) + '"></span>' +
      esc(t("status." + status)) + esc(manualMark);
    legend.appendChild(item);
  }
}

/* ---- view 1: matrix ---- */

function renderMatrix() {
  const snap = state.snapshot;
  const stations = visibleStations();
  const bands = visibleBands();
  const wrap = document.createElement("div");
  wrap.className = "matrix-wrap";
  if (stations.length === 0) {
    wrap.innerHTML = emptyStateHtml("matrix.none");
    return wrap;
  }

  const perBand = snap.stats.per_band;
  let html = '<table class="matrix"><thead><tr>' +
    '<th class="col-call">' + esc(t("col.callsign")) + "</th>";
  for (const band of bands) {
    const stats = perBand[band] || { worked: 0, total: 0 };
    const pct = stats.total ? Math.round((100 * stats.worked) / stats.total) : 0;
    html += '<th class="band-head">' + esc(band) +
      '<span class="progress"><span style="width:' + pct + '%"></span></span></th>';
  }
  html += "</tr></thead><tbody>";

  for (const station of stations) {
    html += '<tr><th class="col-call mono">' + esc(station.callsign) +
      '<span class="cat">' + esc(station.category || "") + "</span></th>";
    for (const band of bands) {
      const cell = station.cells[band] || { status: "not_worked" };
      html += "<td>" + cellButton(station, band, cell) + "</td>";
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
  return wrap;
}

function cellButton(station, band, cell) {
  const status = cell.status;
  const manual = cell.manual ? " manual" : "";
  let mark = "";
  if (WORKED.has(status)) mark = "✓";
  else if (status === "excluded") mark = "—";
  else if (status === "manual_not_worked") mark = "✗";
  return (
    '<button class="cellbtn status-' + esc(status) + manual +
    '" style="background:' + esc(cellColor(status)) +
    '" data-call="' + esc(station.normalized) + '" data-band="' + esc(band) +
    '" aria-label="' + esc(station.callsign + " " + band + ": " + t("status." + status)) +
    '"><span class="mark">' + mark + "</span></button>"
  );
}

/* ---- view 2: still to work ---- */

function renderToWork() {
  const snap = state.snapshot;
  const rows = [];
  for (const station of visibleStations()) {
    for (const band of visibleBands()) {
      const cell = station.cells[band] || { status: "not_worked" };
      if (cell.status === "not_worked" || cell.status === "manual_not_worked") {
        rows.push({ callsign: station.callsign, band,
                    category: station.category, section: station.section });
      }
    }
  }
  const container = document.createElement("div");
  if (rows.length === 0) {
    container.innerHTML = emptyStateHtml("towork.none");
    return container;
  }
  const { key, dir } = state.sort;
  const bandOrder = Object.fromEntries(snap.field_day.bands.map((b, i) => [b, i]));
  rows.sort((a, b) => {
    const va = key === "band" ? bandOrder[a.band] : String(a[key]);
    const vb = key === "band" ? bandOrder[b.band] : String(b[key]);
    return (va < vb ? -1 : va > vb ? 1 : 0) * dir;
  });

  const columns = [
    ["callsign", t("col.callsign")], ["band", t("col.band")],
    ["category", t("col.category")], ["section", t("col.section")],
  ];
  let html = "<p><strong>" + esc(t("towork.count", { n: rows.length })) +
    "</strong></p><table class=\"list\"><thead><tr>";
  for (const [colKey, label] of columns) {
    const arrow = key === colKey ? (dir === 1 ? "▲" : "▼") : "";
    html += '<th data-sort="' + colKey + '">' + esc(label) +
      ' <span class="arrow">' + arrow + "</span></th>";
  }
  html += "</tr></thead><tbody>";
  for (const row of rows) {
    html += '<tr><td class="mono">' + esc(row.callsign) + "</td><td>" +
      esc(row.band) + "</td><td>" + esc(row.category) + "</td><td>" +
      esc(row.section) + "</td></tr>";
  }
  html += "</tbody></table>";
  const container2 = document.createElement("div");
  container2.innerHTML = html;
  return container2;
}

/* ---- view 3: per band ---- */

function renderBand() {
  const snap = state.snapshot;
  const bands = snap.field_day.bands;
  if (!state.band || !bands.includes(state.band)) state.band = bands[0];

  const container = document.createElement("div");
  let picker = '<div class="bandpick">';
  for (const band of bands) {
    picker += '<button data-pickband="' + esc(band) + '"' +
      (band === state.band ? ' class="active"' : "") + ">" + esc(band) + "</button>";
  }
  picker += "</div>";

  const stats = snap.stats.per_band[state.band] || { worked: 0, total: 0 };
  const pct = stats.total ? Math.round((100 * stats.worked) / stats.total) : 0;
  let html = picker +
    "<p><strong>" + esc(t("band.progress", { worked: stats.worked, total: stats.total })) +
    "</strong></p><div class=\"progressbar\"><span style=\"width:" + pct + "%\"></span></div>" +
    '<table class="list"><thead><tr><th>' + esc(t("col.callsign")) + "</th><th>" +
    esc(t("col.status")) + "</th><th>" + esc(t("col.time")) + "</th><th>" +
    esc(t("col.source")) + "</th></tr></thead><tbody>";

  for (const station of visibleStations()) {
    const cell = station.cells[state.band] || { status: "not_worked" };
    html += '<tr><td class="mono">' + esc(station.callsign) + "</td>" +
      '<td><span class="badge" style="background:' + esc(cellColor(cell.status)) +
      '">' + esc(t("status." + cell.status)) + (cell.manual ? " ✎" : "") + "</span></td>" +
      "<td>" + esc(fmtUtc(cell.at_utc || "")) + "</td>" +
      "<td>" + esc(cell.source || "") + "</td></tr>";
  }
  html += "</tbody></table>";
  container.innerHTML = html;
  return container;
}

/* ---- view 4: per station ---- */

function renderStation() {
  const snap = state.snapshot;
  const container = document.createElement("div");
  const stations = snap.stations;
  if (!state.stationKey || !stations.some((s) => s.normalized === state.stationKey)) {
    state.stationKey = stations.length ? stations[0].normalized : null;
  }
  let html = '<div class="bandpick"><select id="station-pick" aria-label="' +
    esc(t("station.pick")) + '">';
  for (const s of stations) {
    html += '<option value="' + esc(s.normalized) + '"' +
      (s.normalized === state.stationKey ? " selected" : "") + ">" +
      esc(s.callsign) + "</option>";
  }
  html += "</select></div>";

  const station = stations.find((s) => s.normalized === state.stationKey);
  if (station) {
    html += '<h2 class="mono">' + esc(station.callsign) + "</h2>" +
      "<p>" + esc(station.category || "") +
      (station.section ? " — " + esc(station.section) : "") + "</p>";
    html += '<table class="list"><thead><tr><th>' + esc(t("col.band")) + "</th><th>" +
      esc(t("col.status")) + "</th></tr></thead><tbody>";
    for (const band of snap.field_day.bands) {
      const cell = station.cells[band] || { status: "not_worked" };
      html += "<tr><td>" + esc(band) + '</td><td><span class="badge" style="background:' +
        esc(cellColor(cell.status)) + '">' + esc(t("status." + cell.status)) +
        (cell.manual ? " ✎" : "") + "</span></td></tr>";
    }
    html += "</tbody></table><h3>" + esc(t("station.qsos")) + "</h3>";
    if (!station.qsos || station.qsos.length === 0) {
      html += '<div class="empty">' + esc(t("station.noqsos")) + "</div>";
    } else {
      html += '<table class="list"><thead><tr><th>' + esc(t("col.time")) + "</th><th>" +
        esc(t("col.band")) + "</th><th>" + esc(t("col.mode")) + "</th><th>" +
        esc(t("col.freq")) + "</th><th>" + esc(t("col.source")) +
        "</th></tr></thead><tbody>";
      for (const qso of station.qsos) {
        html += "<tr><td>" + esc(fmtUtc(qso.at_utc)) + "</td><td>" + esc(qso.band) +
          "</td><td>" + esc(qso.mode) + "</td><td>" + esc(qso.freq_khz) +
          "</td><td>" + esc(qso.source) + "</td></tr>";
      }
      html += "</tbody></table>";
    }
  }
  container.innerHTML = html;
  return container;
}

/* ---- view 5: per source PC ---- */

function renderSources() {
  const snap = state.snapshot;
  const container = document.createElement("div");

  // Which cells were worked via which PC (first qualifying QSO per cell).
  const workedBy = {};
  for (const station of snap.stations) {
    for (const band of snap.field_day.bands) {
      const cell = station.cells[band];
      if (cell && WORKED.has(cell.status) && cell.source) {
        workedBy[cell.source] = (workedBy[cell.source] || 0) + 1;
      }
    }
  }

  const sources = snap.sources || [];
  const names = new Set(sources.map((s) => s.name));
  for (const name of Object.keys(workedBy)) {
    if (!names.has(name)) sources.push({ name, fresh: null });
  }

  if (sources.length === 0) {
    container.innerHTML = '<div class="empty">' + esc(t("sources.none")) + "</div>";
    return container;
  }
  let html = '<div class="cards">';
  for (const source of sources) {
    const staleClass = source.fresh === false ? " stale-card" : "";
    const tag = source.fresh === null ? "" :
      source.fresh
        ? '<span class="fresh-tag">' + esc(t("sources.fresh")) + "</span>"
        : '<span class="stale-tag">' + esc(t("sources.stale")) + "</span>";
    html += '<div class="card' + staleClass + '"><h3 class="mono">' + esc(source.name) +
      " " + tag + "</h3>" +
      '<div class="big">' + (workedBy[source.name] || 0) + "</div>" +
      "<div>" + esc(t("sources.worked")) + "</div>";
    if (source.last_seen_utc) {
      html += "<div>" + esc(t("sources.lastseen")) + ": " +
        esc(fmtUtc(source.last_seen_utc)) + " UTC</div>";
    }
    if (source.packet_count !== undefined) {
      html += "<div>" + esc(source.packet_count) + " " + esc(t("sources.packets")) + "</div>";
    }
    html += "</div>";
  }
  html += "</div>";
  container.innerHTML = html;
  return container;
}

/* ---- view 6: statistics ---- */

function renderStats() {
  const snap = state.snapshot;
  const stats = snap.stats;
  const container = document.createElement("div");

  const tiles = [
    ["stats.stations", stats.stations_total],
    ["stats.cells", stats.cells_total],
    ["stats.worked", stats.cells_worked],
    ["stats.open", stats.cells_open],
    ["stats.excluded", stats.cells_excluded],
    ["stats.manual", stats.manual_overrides],
    ["stats.complete", stats.stations_complete],
    ["stats.partial", stats.stations_partial],
    ["stats.untouched", stats.stations_untouched],
  ];
  let html = '<div class="statgrid">';
  for (const [key, value] of tiles) {
    html += '<div class="card"><div class="big">' + esc(value) + "</div><div>" +
      esc(t(key)) + "</div></div>";
  }
  html += "</div>";

  html += "<h3>" + esc(t("stats.progress")) + "</h3>" + progressSparkline(snap);

  html += "<h3>" + esc(t("stats.perband")) + '</h3><table class="list"><thead><tr><th>' +
    esc(t("col.band")) + "</th><th>" + esc(t("stats.worked")) + "</th><th>" +
    esc(t("stats.open")) + "</th><th>" + esc(t("stats.excluded")) + "</th><th>" +
    esc(t("stats.manual")) + "</th></tr></thead><tbody>";
  for (const band of snap.field_day.bands) {
    const row = stats.per_band[band];
    html += "<tr><td>" + esc(band) + "</td><td>" + row.worked + " / " + row.total +
      "</td><td>" + row.open + "</td><td>" + row.excluded + "</td><td>" +
      row.manual_overrides + "</td></tr>";
  }
  html += "</tbody></table>";

  html += "<h3>" + esc(t("stats.percategory")) + '</h3><table class="list"><thead><tr><th>' +
    esc(t("col.category")) + "</th><th>" + esc(t("stats.stations")) + "</th><th>" +
    esc(t("stats.worked")) + "</th><th>" + esc(t("stats.open")) + "</th></tr></thead><tbody>";
  for (const [category, row] of Object.entries(stats.per_category)) {
    html += "<tr><td>" + esc(category || "—") + "</td><td>" + row.stations + "</td><td>" +
      row.worked + " / " + row.total + "</td><td>" + row.open + "</td></tr>";
  }
  html += "</tbody></table>";

  container.innerHTML = html;
  return container;
}

function progressSparkline(snap) {
  // Cumulative first-worked timestamps across all cells.
  const timestamps = [];
  for (const station of snap.stations) {
    for (const band of snap.field_day.bands) {
      const cell = station.cells[band];
      if (cell && cell.at_utc && WORKED.has(cell.status)) timestamps.push(cell.at_utc);
    }
  }
  if (timestamps.length < 2) return '<div class="empty">—</div>';
  timestamps.sort();
  const start = Date.parse(snap.field_day.start_utc);
  const end = Math.max(Date.parse(timestamps[timestamps.length - 1]),
                       Math.min(Date.now(), Date.parse(snap.field_day.end_utc)));
  const width = 600, height = 110, pad = 6;
  const points = timestamps.map((iso, index) => {
    const x = pad + ((Date.parse(iso) - start) / Math.max(end - start, 1)) * (width - 2 * pad);
    const y = height - pad - ((index + 1) / timestamps.length) * (height - 2 * pad);
    return x.toFixed(1) + "," + y.toFixed(1);
  });
  return '<svg class="sparkline" viewBox="0 0 ' + width + " " + height +
    '" role="img"><line class="axis" x1="0" y1="' + (height - pad) + '" x2="' + width +
    '" y2="' + (height - pad) + '"/><polyline points="' + points.join(" ") + '"/></svg>';
}

/* ---------------------------------------------------------- detail panel */

function showCellDetail(normalized, band) {
  const snap = state.snapshot;
  const station = snap.stations.find((s) => s.normalized === normalized);
  if (!station) return;
  const cell = station.cells[band] || { status: "not_worked" };
  $("detail-title").textContent = station.callsign + " · " + band;
  let html = '<p><span class="badge" style="background:' + esc(cellColor(cell.status)) +
    '">' + esc(t("status." + cell.status)) + "</span></p>";
  if (cell.at_utc) {
    html += "<p>" + esc(t("detail.qso")) + ": " + esc(fmtUtc(cell.at_utc)) + " UTC · " +
      esc(cell.mode || "") + " · " + esc(cell.freq_khz || "") + " kHz · " +
      esc(cell.source || "") + "</p>";
    if (cell.qso_count > 1) {
      html += "<p>" + esc(t("detail.qsocount")) + ": " + esc(cell.qso_count) + "</p>";
    }
  }
  if (cell.manual) {
    html += "<p><strong>" + esc(t("detail.manual")) + "</strong>";
    if (cell.reason) html += " — " + esc(t("detail.reason")) + ": " + esc(cell.reason);
    if (cell.set_by) html += " (" + esc(t("detail.setby")) + " " + esc(cell.set_by) + ")";
    html += "</p>";
  }
  if (!state.snapshot.readonly && !state.snapshot.field_day.closed) {
    html += '<h4>' + esc(t("ov.title")) + '</h4>' +
      '<input class="reason" id="ov-reason" type="text" placeholder="' +
      esc(t("ov.reason")) + '">' +
      '<div class="ov-btns">' +
      ovButton("manual_worked", t("ov.worked"), normalized, band) +
      ovButton("manual_not_worked", t("ov.notworked"), normalized, band) +
      ovButton("excluded", t("ov.exclude"), normalized, band) +
      '<button class="btn secondary" data-ovclear data-call="' + esc(normalized) +
      '" data-band="' + esc(band) + '">' + esc(t("ov.clear")) + "</button>" +
      "</div>";
    html += '<h4>' + esc(t("rmst.title")) + "</h4>" +
      '<p class="rm-hint">' + esc(t("rmst.hint")) + "</p>" +
      '<button class="btn danger" data-rmstation="' + esc(normalized) +
      '" data-name="' + esc(station.callsign) + '">' + esc(t("rmst.button")) + "</button>";
  }
  $("detail-body").innerHTML = html;
  $("detail").hidden = false;
}

function ovButton(type, label, normalized, band) {
  return '<button class="btn" data-ovset="' + esc(type) + '" data-call="' +
    esc(normalized) + '" data-band="' + esc(band) + '">' + esc(label) + "</button>";
}

async function handleOverrideClick(target) {
  const call = target.dataset.call, band = target.dataset.band;
  try {
    if (target.dataset.ovset) {
      const reasonInput = $("ov-reason");
      await api("/api/override", {
        normalized_callsign: call, band: band,
        override_type: target.dataset.ovset,
        reason: reasonInput ? reasonInput.value : "",
      });
    } else {
      await api("/api/override/clear", { normalized_callsign: call, band: band });
    }
    $("detail").hidden = true;
    showToast("ok", t("manage.done"));
    await refreshNow();
  } catch (err) {
    showToast("warn", t("manage.error", { e: err.message }));
  }
}

/* ---------------------------------------------------------------- events */

document.addEventListener("click", (event) => {
  const tab = event.target.closest(".tab");
  if (tab) { state.view = tab.dataset.view; render(); return; }

  const cell = event.target.closest(".cellbtn");
  if (cell) { showCellDetail(cell.dataset.call, cell.dataset.band); return; }

  const sortHead = event.target.closest("th[data-sort]");
  if (sortHead) {
    const key = sortHead.dataset.sort;
    state.sort.dir = state.sort.key === key ? -state.sort.dir : 1;
    state.sort.key = key;
    render();
    return;
  }

  const bandButton = event.target.closest("[data-pickband]");
  if (bandButton) { state.band = bandButton.dataset.pickband; render(); return; }

  if (event.target.id === "clear-filters") { clearFilters(); return; }
  if (event.target.id === "detail-close") { $("detail").hidden = true; }
});

document.addEventListener("change", (event) => {
  const map = {
    "f-status": "status", "f-band": "band",
    "f-category": "category", "f-section": "section",
  };
  if (map[event.target.id]) {
    state.filters[map[event.target.id]] = event.target.value;
    render();
  }
  if (event.target.id === "station-pick") {
    state.stationKey = event.target.value;
    render();
  }
});

$("f-search").addEventListener("input", (event) => {
  state.filters.search = event.target.value;
  render();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") $("detail").hidden = true;
});

/* ------------------------------------------------------------- manual */

const MANUAL_HTML =
  "<h3>Connecting N1MM</h3>" +
  "<p>In N1MM: <b>Config &gt; Configure Ports, Mode Control, Audio, Other</b> " +
  "&gt; tab <b>Broadcast Data</b>. Tick <b>Contacts</b> (not Lookup) and set the " +
  "destination to <code>127.0.0.1:12060</code> when N1MM runs on this same laptop. " +
  "Contest type FDREG1. Log a test QSO and the cell should turn green within 5s.</p>" +
  "<h3>Windows Firewall</h3>" +
  "<p>The first time you start the tracker, Windows may ask to allow network " +
  "access. Click <b>Allow access</b> — this is needed to receive N1MM's data. " +
  "If you clicked it away, allow <code>python.exe</code> in " +
  "<b>Windows Security &gt; Firewall &amp; network protection &gt; Allow an app</b>.</p>" +
  "<h3>Catching up after the tracker was off</h3>" +
  "<p>UDP only carries live traffic, so QSOs logged while the tracker was closed " +
  "are not received automatically. To pull in the full log: in N1MM " +
  "<b>File &gt; Export &gt; Export to ADIF</b>, then in the tracker " +
  "<b>Manage &gt; ADIF import</b>. Known QSOs are skipped, so nothing doubles.</p>" +
  "<h3>Multiple field days</h3>" +
  "<p>There is always exactly one <b>active</b> field day. N1MM data is always " +
  "recorded into that active field day. A closed field day ignores incoming QSOs.</p>" +
  "<h3>Publishing</h3>" +
  "<p>Only the active field day is published. The public page is read-only and " +
  "refreshes itself. Full step-by-step setup is in the handbook, chapter 13b.</p>" +
  "<p><em>The full handbook (HANDLEIDING.md) sits in the docs folder of the " +
  "application.</em></p>";

function openManual() {
  $("manual-drawer").hidden = false;
  $("drawer-backdrop").hidden = false;
  $("manual-body").innerHTML = MANUAL_HTML;
}
function closeManual() {
  $("manual-drawer").hidden = true;
  if ($("manage-drawer").hidden) $("drawer-backdrop").hidden = true;
}

/* ---------------------------------------------------------- accordion */

function accordionize(html) {
  // Split the flat panel HTML on <h3> headers and wrap each section in a
  // collapsible <details>, so the panel reads as tidy groups instead of one
  // long scroll. A leading block before the first <h3> (e.g. a message) is
  // kept as-is on top.
  const parts = html.split(/(<h3>)/);
  let out = parts[0]; // anything before the first header (msg banner)
  let first = true;
  for (let i = 1; i < parts.length; i += 2) {
    const body = parts[i + 1] || "";
    const closeIdx = body.indexOf("</h3>");
    const title = body.slice(0, closeIdx);
    const rest = body.slice(closeIdx + 5);
    out += '<details class="acc"' + (first ? " open" : "") + ">" +
      "<summary>" + title + "</summary>" +
      '<div class="acc-body">' + rest + "</div></details>";
    first = false;
  }
  return out;
}

/* --------------------------------------------------------------- help */

function help(key) {
  // A small blue (?) that shows an instant-help tooltip on click.
  return '<button type="button" class="help-dot" data-help="' + esc(key) +
    '" aria-label="Help">?</button>';
}

function showHelp(key, anchor) {
  hideHelp();
  const box = document.createElement("div");
  box.id = "help-pop";
  box.className = "help-pop";
  box.textContent = t(key);
  document.body.appendChild(box);
  const rect = anchor.getBoundingClientRect();
  const top = window.scrollY + rect.bottom + 6;
  let left = window.scrollX + rect.left - 4;
  left = Math.min(left, window.scrollX + window.innerWidth - box.offsetWidth - 12);
  box.style.top = top + "px";
  box.style.left = Math.max(8, left) + "px";
}
function hideHelp() {
  const existing = $("help-pop");
  if (existing) existing.remove();
}
document.addEventListener("click", (event) => {
  const dot = event.target.closest("[data-help]");
  if (dot) { showHelp(dot.dataset.help, dot); event.stopPropagation(); return; }
  if (!event.target.closest("#help-pop")) hideHelp();
});

/* -------------------------------------------------- publication notice */

function renderPublicationNotice(pub) {
  document.title = "Field Day Tracker";
  // Hide the interactive chrome on these pages.
  for (const id of ["manage-open", "manual-open"]) {
    const el = $(id); if (el) el.style.display = "none";
  }
  const filters = $("filters"); if (filters) filters.style.display = "none";
  const tabs = $("tabs"); if (tabs) tabs.style.display = "none";
  $("fd-name").textContent = "Field Day Tracker";
  $("fd-callsign").textContent = "";
  $("fd-period").textContent = "";
  const livebar = $("livebar"); if (livebar) livebar.style.display = "none";

  let title = "", body = "";
  if (pub.state === "none") {
    title = t("pub.none.title");
    body = t("pub.none.body");
    if (pub.next_start_utc) {
      body += " " + t("pub.none.next",
        { name: pub.next_name, date: fmtUtc(pub.next_start_utc) });
    }
  } else if (pub.state === "upcoming") {
    title = t("pub.upcoming.title");
    body = t("pub.upcoming.body", { name: pub.next_name, date: fmtUtc(pub.next_start_utc) });
    const ms = Date.parse(pub.next_start_utc) - Date.now();
    if (ms > 0) {
      const totalMin = Math.floor(ms / 60000);
      const d = Math.floor(totalMin / 1440);
      const h = Math.floor((totalMin % 1440) / 60);
      const m = totalMin % 60;
      body += " " + t("pub.upcoming.countdown", { d, h, m });
    }
  } else if (pub.state === "expired") {
    title = t("pub.expired.title");
    body = t("pub.expired.body");
  }

  const root = $("view-root");
  root.innerHTML = '<div class="pub-notice" id="pub-notice">' +
    '<div class="pub-logo">WLD</div>' +
    "<h2>" + esc(title) + "</h2><p>" + esc(body) + "</p></div>";
}

/* ------------------------------------------------------- manage drawer */

function toLocalInput(isoUtc) {
  const date = new Date(isoUtc);
  const pad = (n) => String(n).padStart(2, "0");
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" +
    pad(date.getDate()) + "T" + pad(date.getHours()) + ":" + pad(date.getMinutes());
}
function toUtcIso(localValue) {
  return new Date(localValue).toISOString().replace(/\.\d{3}Z$/, "Z");
}

let manageMsg = null; // {kind, text}
let toastTimer = null;

function showToast(kind, text) {
  let toast = $("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    document.body.appendChild(toast);
  }
  toast.className = "toast " + kind;
  toast.textContent = text;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 8000);
}
let managePublish = { enabled: false, repo: "", branch: "main", path: "",
                      interval: "0", includePrivate: false,
                      tokenConfigured: false, pagesUrl: "" };
let manageSettings = { udpHost: "", udpPort: "", fresh: "", strict: false,
                       exportFolder: "", language: "en" };

async function loadManageSettings() {
  try {
    const data = await (await fetch("/api/settings")).json();
    const snap = state.snapshot;
    manageSettings.exportFolder = data.settings.export_folder || "";
    manageSettings.language = data.settings.ui_language || "en";
  } catch (err) { /* defaults blijven */ }
  try {
    const pub = await (await fetch("/api/publish/status")).json();
    managePublish.enabled = pub.settings.enabled;
    managePublish.repo = pub.settings.repo;
    managePublish.branch = pub.settings.branch;
    managePublish.path = pub.settings.path;
    managePublish.interval = String(pub.settings.auto_interval_minutes);
    managePublish.includePrivate = pub.settings.include_private;
    managePublish.tokenConfigured = pub.token_configured;
    managePublish.pagesUrl = pub.pages_url;
  } catch (err) { /* defaults */ }
  const tech = state.snapshot ? state.snapshot.tech : null;
  if (tech) {
    manageSettings.udpHost = tech.n1mm_udp_host;
    manageSettings.udpPort = String(tech.n1mm_udp_port);
    manageSettings.fresh = String(tech.freshness_threshold_seconds);
    manageSettings.strict = !!tech.strict_callsign_matching;
  }
}
let pendingImport = null; // {filename, content_b64, missing:[]}

async function openManage() {
  $("manage-drawer").hidden = false;
  $("drawer-backdrop").hidden = false;
  await loadManageSettings();
  await renderManage();
}
function closeManage() {
  $("manage-drawer").hidden = true;
  $("drawer-backdrop").hidden = true;
  manageMsg = null;
  pendingImport = null;
}

async function renderManage() {
  const body = $("manage-body");
  let fielddays = [];
  try {
    fielddays = (await (await fetch("/api/fielddays")).json()).fielddays || [];
  } catch (err) { /* leeg laten */ }
  const snap = state.snapshot;
  const fd = snap ? snap.field_day : null;

  let html = "";
  if (manageMsg) {
    html += '<div class="msg ' + manageMsg.kind + '">' + esc(manageMsg.text) + "</div>";
  }

  html += "<h3>" + esc(t("manage.fielddays")) + '</h3><ul class="fd-list">';
  for (const entry of fielddays) {
    html += '<li><span class="mono">' + esc(entry.name) + "</span>" +
      '<span class="fd-actions">' +
      (entry.active
        ? '<span class="active-tag">●</span>'
        : '<button class="btn secondary" data-activate="' + esc(entry.id) + '">' +
          esc(t("manage.activate")) + "</button>") +
      '<button class="btn secondary" data-export="' + esc(entry.id) +
      '" title="' + esc(t("fd.export")) + '">⭳</button>' +
      (entry.active
        ? ""
        : '<button class="btn danger" data-delete="' + esc(entry.id) +
          '" data-name="' + esc(entry.name) + '" title="' + esc(t("fd.delete")) +
          '">🗑</button>') +
      "</span></li>";
  }
  html += "</ul>" +
    '<input type="file" id="fd-import-file" accept=".fdtracker,.json" hidden>' +
    '<div class="row-btns"><button class="btn secondary" id="fd-import-pick">' +
    esc(t("fd.import")) + "</button> " + help("help.bundle") + "</div>";

  html += "<h3>" + esc(t("manage.newfd")) + "</h3>" +
    '<label>' + esc(t("manage.name")) + '</label><input type="text" id="nf-name">' +
    '<label>' + esc(t("manage.start")) + '</label><input type="datetime-local" id="nf-start">' +
    '<label>' + esc(t("manage.end")) + '</label><input type="datetime-local" id="nf-end">' +
    '<label>' + esc(t("manage.copyfrom")) + '</label><select id="nf-copy">' +
    '<option value="">' + esc(t("manage.copynone")) + "</option>";
  for (const entry of fielddays) {
    html += '<option value="' + esc(entry.id) + '">' + esc(entry.name) + "</option>";
  }
  html += '</select><div class="row-btns"><button class="btn" id="nf-create">' +
    esc(t("manage.create")) + "</button></div>";

  if (fd) {
    html += "<h3>" + esc(t("manage.editfd")) + "</h3>" +
      '<label>' + esc(t("manage.name")) + '</label><input type="text" id="ef-name" value="' + esc(fd.name) + '">' +
      '<label>' + esc(t("manage.location")) + '</label><input type="text" id="ef-location" value="' + esc(fd.location || "") + '">' +
      '<label>' + esc(t("manage.eventcall")) + '</label><input type="text" id="ef-call" value="' + esc(fd.event_callsign || "") + '">' +
      '<label>' + esc(t("manage.club")) + '</label><input type="text" id="ef-club" value="' + esc(fd.organizer_club || "") + '">' +
      '<label>' + esc(t("manage.start")) + '</label><input type="datetime-local" id="ef-start" value="' + toLocalInput(fd.start_utc) + '">' +
      '<label>' + esc(t("manage.end")) + '</label><input type="datetime-local" id="ef-end" value="' + toLocalInput(fd.end_utc) + '">' +
      '<label>' + esc(t("manage.bands")) + '</label><div class="bandboxes">';
    for (const band of (snap.all_bands || fd.bands)) {
      const checked = fd.bands.includes(band) ? " checked" : "";
      html += '<label><input type="checkbox" class="ef-band" value="' + esc(band) + '"' +
        checked + ">" + esc(band) + "</label>";
    }
    html += '</div><div class="row-btns"><button class="btn" id="ef-save">' +
      esc(t("manage.save")) + "</button></div>";
  }

  html += "<h3>" + esc(t("manage.import")) + "</h3>";
  if (pendingImport) {
    html += '<div class="msg warn">' + esc(t("manage.importmissing")) +
      '<br><span class="mono">' + pendingImport.missing.map(esc).join(", ") + "</span></div>" +
      '<div class="row-btns"><button class="btn danger" id="imp-confirm">' +
      esc(t("manage.importconfirm")) + '</button>' +
      '<button class="btn secondary" id="imp-cancel">' + esc(t("manage.importcancel")) +
      "</button></div>";
  } else {
    html += '<input type="file" id="imp-file" accept=".xlsx,.csv" hidden>' +
      '<div class="row-btns"><button class="btn secondary" id="imp-pick">' +
      esc(t("manage.importbtn")) + "</button> " + help("help.excel") + "</div>";
  }

  html += "<h3>" + esc(t("manage.adif")) + "</h3>" +
    '<input type="file" id="adif-file" accept=".adi,.adif" hidden>' +
    '<div class="row-btns"><button class="btn secondary" id="adif-pick">' +
    esc(t("manage.adifbtn")) + "</button> " + help("help.adifbtn") + "</div>";

  const fdFull = snap ? snap.field_day : null;
  if (fdFull) {
    html += "<h3>" + esc(t("set.title")) + "</h3>" +
      '<label>' + esc(t("set.language")) + '</label><select id="set-lang">';
    for (const code of ["en", "nl", "fr", "es"]) {
      html += '<option value="' + code + '"' +
        ((snap.ui_language || "en") === code ? " selected" : "") + ">" +
        code.toUpperCase() + "</option>";
    }
    html += "</select>" +
      '<label>' + esc(t("set.udphost")) + " " + help("help.udphost") + '</label>' +
      '<input type="text" id="set-udphost" class="mono" value="' + esc(manageSettings.udpHost) + '">' +
      '<label>' + esc(t("set.udpport")) + " " + help("help.udpport") + '</label>' +
      '<input type="text" id="set-udpport" class="mono" value="' + esc(manageSettings.udpPort) + '">' +
      '<label>' + esc(t("set.fresh")) + " " + help("help.fresh") + '</label>' +
      '<input type="text" id="set-fresh" class="mono" value="' + esc(manageSettings.fresh) + '">' +
      '<label><input type="checkbox" id="set-strict"' +
      (manageSettings.strict ? " checked" : "") + "> " + esc(t("set.strict")) + " " + help("help.strict") + "</label>" +
      '<label>' + esc(t("set.colors")) + '</label><div class="bandboxes">';
    for (const status of Object.keys(snap.legend)) {
      html += '<label><input type="color" class="set-color" data-status="' + esc(status) +
        '" value="' + esc((snap.colors[status] || "#ffffff")) + '"> ' +
        esc(t("status." + status)) + "</label>";
    }
    html += '</div>' +
      '<label>' + esc(t("set.exportfolder")) + '</label>' +
      '<input type="text" id="set-export" value="' + esc(manageSettings.exportFolder) + '">' +
      '<div class="row-btns"><button class="btn" id="set-save">' +
      esc(t("set.savefd")) + "</button></div>";
  }

  html += "<h3>" + esc(t("addst.title")) + "</h3>" +
    '<label>' + esc(t("addst.call")) + '</label><input type="text" id="as-call" class="mono">' +
    '<label>' + esc(t("addst.category")) + '</label><input type="text" id="as-cat">' +
    '<label>' + esc(t("addst.section")) + '</label><input type="text" id="as-sec">' +
    '<label>' + esc(t("addst.remarks")) + '</label><input type="text" id="as-rem">' +
    '<div class="row-btns"><button class="btn" id="as-save">' +
    esc(t("addst.save")) + "</button></div>";

  html += "<h3>" + esc(t("export.title")) + "</h3>" +
    '<div class="row-btns">' +
    '<button class="btn" id="exp-pdf">' + esc(t("export.pdf")) + "</button>" +
    '<button class="btn secondary" id="exp-csv">' + esc(t("export.csv")) + "</button>" +
    "</div>";

  const isClosed = snap && snap.field_day.closed;
  html += "<h3>" + esc(t("close.title")) + "</h3>" +
    '<div class="row-btns">' +
    (isClosed
      ? '<button class="btn" id="fd-reopen">' + esc(t("reopen.button")) + "</button>"
      : '<button class="btn danger" id="fd-close">' + esc(t("close.button")) + "</button>") +
    "</div>";

  html += "<h3>" + esc(t("pub.title")) + "</h3>" +
    '<div class="msg warn">' + esc(t("pub.warning")) + "</div>" +
    '<label><input type="checkbox" id="pub-enabled"' +
    (managePublish.enabled ? " checked" : "") + "> " + esc(t("pub.enabled")) + "</label>" +
    '<label>' + esc(t("pub.repo")) + " " + help("help.repo") + '</label>' +
    '<input type="text" id="pub-repo" class="mono" value="' + esc(managePublish.repo) + '">' +
    '<label>' + esc(t("pub.branch")) + '</label>' +
    '<input type="text" id="pub-branch" class="mono" value="' + esc(managePublish.branch) + '">' +
    '<label>' + esc(t("pub.path")) + '</label>' +
    '<input type="text" id="pub-path" class="mono" value="' + esc(managePublish.path) + '">' +
    '<label>' + esc(t("pub.interval")) + '</label>' +
    '<input type="text" id="pub-interval" class="mono" value="' + esc(managePublish.interval) + '">' +
    '<label><input type="checkbox" id="pub-private"' +
    (managePublish.includePrivate ? " checked" : "") + "> " + esc(t("pub.private")) + "</label>" +
    '<label>' + esc(t("pub.token")) + " " + help("help.token") + " <em>(" +
    esc(managePublish.tokenConfigured ? t("pub.tokenset") : t("pub.notoken")) + ")</em></label>" +
    '<input type="password" id="pub-token" autocomplete="off">' +
    '<div class="row-btns">' +
    '<button class="btn secondary" id="pub-savetoken">' + esc(t("pub.savetoken")) + "</button>" +
    '<button class="btn" id="pub-save">' + esc(t("pub.save")) + "</button>" +
    '<button class="btn" id="pub-now">' + esc(t("pub.now")) + "</button>" +
    "</div>" +
    (managePublish.pagesUrl
      ? "<p>" + esc(t("pub.pagesurl")) + ' <a href="' + esc(managePublish.pagesUrl) +
        '" target="_blank" class="mono">' + esc(managePublish.pagesUrl) + "</a></p>"
      : "");

  html += "<h3>" + esc(t("manage.synctitle")) + "</h3>" +
    '<div class="row-btns"><button class="btn secondary" id="sync-now">' +
    esc(t("manage.syncbtn")) + "</button></div>";

  body.innerHTML = accordionize(html);
}

async function manageAction(fn, okText) {
  try {
    const result = await fn();
    manageMsg = { kind: "ok", text: okText(result) };
  } catch (err) {
    if (err && err.offline) {
      manageMsg = { kind: "warn", text: t("pub.offline") };
    } else {
      manageMsg = { kind: "warn", text: t("manage.error", { e: err.message }) };
    }
  }
  showToast(manageMsg.kind, manageMsg.text);
  await refreshNow();
  await renderManage();
}

document.addEventListener("click", async (event) => {
  const target = event.target;
  if (target.id === "manage-open") { openManage(); return; }
  if (target.id === "manual-open") { openManual(); return; }
  if (target.id === "manual-close") { closeManual(); return; }
  if (target.id === "manage-close") { closeManage(); return; }
  if (target.id === "drawer-backdrop") { closeManage(); closeManual(); return; }

  const ovTarget = target.closest("[data-ovset],[data-ovclear]");
  if (ovTarget) { handleOverrideClick(ovTarget); return; }

  const rmStation = target.closest("[data-rmstation]");
  if (rmStation) {
    const name = rmStation.dataset.name || rmStation.dataset.rmstation;
    if (window.confirm(t("rmst.confirm", { name: name }))) {
      (async () => {
        try {
          await api("/api/station/remove",
            { normalized_callsign: rmStation.dataset.rmstation });
          $("detail").hidden = true;
          showToast("ok", t("rmst.removed"));
          await refreshNow();
        } catch (err) {
          showToast("warn", t("manage.error", { e: err.message }));
        }
      })();
    }
    return;
  }

  const exportBtn = target.closest("[data-export]");
  if (exportBtn) {
    window.open("/api/fieldday/export?id=" + encodeURIComponent(exportBtn.dataset.export), "_blank");
    return;
  }
  const deleteBtn = target.closest("[data-delete]");
  if (deleteBtn) {
    const name = deleteBtn.dataset.name || deleteBtn.dataset.delete;
    const answer = window.prompt(t("fd.deleteprompt", { name: name }));
    if (answer === null) return;
    if (answer.trim() !== "DELETE") {
      showToast("warn", t("fd.deletemismatch"));
      return;
    }
    manageAction(() => api("/api/fieldday/delete",
      { id: deleteBtn.dataset.delete, confirm: "DELETE" }),
      () => t("fd.deleted"));
    return;
  }
  if (target.id === "fd-import-pick") { $("fd-import-file").click(); return; }
  const activate = target.closest("[data-activate]");
  if (activate) {
    manageAction(() => api("/api/fieldday/activate", { id: activate.dataset.activate }),
      () => t("manage.done"));
    return;
  }
  if (target.id === "nf-create") {
    manageAction(() => api("/api/fieldday/create", {
      name: $("nf-name").value,
      start_utc: toUtcIso($("nf-start").value),
      end_utc: toUtcIso($("nf-end").value),
      copy_from: $("nf-copy").value,
    }), () => t("manage.created"));
    return;
  }
  if (target.id === "ef-save") {
    const bands = [...document.querySelectorAll(".ef-band:checked")].map((el) => el.value);
    manageAction(() => api("/api/fieldday/update", {
      name: $("ef-name").value, location: $("ef-location").value,
      event_callsign: $("ef-call").value, organizer_club: $("ef-club").value,
      start_utc: toUtcIso($("ef-start").value), end_utc: toUtcIso($("ef-end").value),
      bands: bands,
    }), () => t("manage.done"));
    return;
  }
  if (target.id === "imp-pick") { $("imp-file").click(); return; }
  if (target.id === "adif-pick") { $("adif-file").click(); return; }
  if (target.id === "imp-confirm" && pendingImport) {
    const payload = { filename: pendingImport.filename,
                      content_b64: pendingImport.content_b64, confirm_removals: true };
    pendingImport = null;
    manageAction(() => api("/api/import-stations", payload),
      (r) => t("manage.imported", { n: r.imported }));
    return;
  }
  if (target.id === "imp-cancel") { pendingImport = null; renderManage(); return; }
  if (target.id === "set-save") {
    const colors = {};
    document.querySelectorAll(".set-color").forEach((el) => {
      colors[el.dataset.status] = el.value;
    });
    manageAction(async () => {
      await api("/api/settings", {
        ui_language: $("set-lang").value,
        export_folder: $("set-export").value,
      });
      return api("/api/fieldday/update", {
        n1mm_udp_host: $("set-udphost").value,
        n1mm_udp_port: parseInt($("set-udpport").value, 10),
        freshness_threshold_seconds: parseInt($("set-fresh").value, 10),
        strict_callsign_matching: $("set-strict").checked,
        status_colors: colors,
      });
    }, (r) => (r.udp_restarted ? t("set.udprestarted") : t("manage.done")));
    return;
  }
  if (target.id === "addst-open") {
    openManage().then(() => {
      const field = $("as-call");
      if (field) { field.scrollIntoView({ block: "center" }); field.focus(); }
    });
    return;
  }
  if (target.id === "as-save") {
    manageAction(() => api("/api/station/add", {
      callsign: $("as-call").value, category: $("as-cat").value,
      section: $("as-sec").value, remarks: $("as-rem").value,
    }), () => t("addst.added"));
    return;
  }
  if (target.id === "exp-pdf") { window.open("/api/export/pdf", "_blank"); return; }
  if (target.id === "exp-csv") { window.open("/api/export/csv", "_blank"); return; }
  if (target.id === "fd-close") {
    if (window.confirm(t("close.confirm"))) {
      manageAction(() => api("/api/fieldday/close", {}), () => t("close.closed"));
    }
    return;
  }
  if (target.id === "fd-reopen") {
    if (window.confirm(t("reopen.confirm"))) {
      manageAction(() => api("/api/fieldday/reopen", {}), () => t("reopen.done"));
    }
    return;
  }
  if (target.id === "pub-savetoken") {
    manageAction(async () => {
      const result = await api("/api/publish/token", { token: $("pub-token").value });
      $("pub-token").value = "";
      return result;
    }, () => t("pub.tokenok"));
    return;
  }
  if (target.id === "pub-save") {
    manageAction(() => api("/api/settings", { publish: {
      enabled: $("pub-enabled").checked,
      repo: $("pub-repo").value.trim(),
      branch: $("pub-branch").value.trim() || "main",
      path: $("pub-path").value.trim(),
      auto_interval_minutes: parseInt($("pub-interval").value, 10) || 0,
      include_private: $("pub-private").checked,
    }}), () => t("manage.done"));
    return;
  }
  if (target.id === "pub-now") {
    manageAction(async () => {
      const result = await api("/api/publish/now", {});
      if (result.offline) { const e = new Error("offline"); e.offline = true; throw e; }
      if (!result.ok) throw new Error((result.errors || [result.error]).join("; "));
      return result;
    }, (r) => t("pub.result", { up: r.uploaded.length, skip: r.skipped.length }));
    return;
  }
  if (target.id === "sync-now") {
    manageAction(() => api("/api/sync", {}),
      (r) => t("manage.syncreport",
        { matched: r.report.qsos_matched, total: r.report.qsos_total }));
    return;
  }
});

document.addEventListener("change", async (event) => {
  if (event.target.id === "imp-file" && event.target.files.length) {
    const file = event.target.files[0];
    const content = await fileToB64(file);
    try {
      const result = await api("/api/import-stations",
        { filename: file.name, content_b64: content, confirm_removals: false });
      if (result.needs_confirmation) {
        pendingImport = { filename: file.name, content_b64: content,
                          missing: result.missing_stations };
        renderManage();
      } else {
        manageMsg = { kind: "ok", text: t("manage.imported", { n: result.imported }) };
        await refreshNow();
        renderManage();
      }
    } catch (err) {
      manageMsg = { kind: "warn", text: t("manage.error", { e: err.message }) };
      renderManage();
    }
  }
  if (event.target.id === "fd-import-file" && event.target.files.length) {
    const file = event.target.files[0];
    const content = await fileToB64(file);
    manageAction(() => api("/api/fieldday/import",
      { filename: file.name, content_b64: content }),
      (r) => t("fd.imported", { name: r.name, q: r.qsos, s: r.stations }));
    return;
  }
  if (event.target.id === "adif-file" && event.target.files.length) {
    const file = event.target.files[0];
    const content = await fileToB64(file);
    try {
      const result = await api("/api/import-adif",
        { filename: file.name, content_b64: content });
      const rep = result.report;
      const text = t("manage.adifreport", {
        read: rep.records_read, new: rep.imported, dup: rep.duplicates,
        out: rep.outside_period, unk: rep.unknown_station,
      });
      if (rep.imported === 0 && rep.records_read > 0) {
        const hint = rep.outside_period > 0 ? " " + t("manage.adifperiodhint") : "";
        manageMsg = { kind: "warn", text: text + hint };
      } else {
        manageMsg = { kind: "ok", text: text };
      }
      showToast(manageMsg.kind, manageMsg.text);
      await refreshNow();
      renderManage();
    } catch (err) {
      manageMsg = { kind: "warn", text: t("manage.error", { e: err.message }) };
      showToast("warn", manageMsg.text);
      renderManage();
    }
  }
});

/* ------------------------------------------------------------------ init */

function applyStaticStrings() {
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
}

applyStaticStrings();
fetchSnapshot();

// Debug/test handle (also useful for field diagnostics in the console).
window.__fdt = { state, render, clearFilters, showToast, showCellDetail };
