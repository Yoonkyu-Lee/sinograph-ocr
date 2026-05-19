import "./styles.css";
import { invoke } from "@tauri-apps/api/core";

const queryInput = document.querySelector("#query");
const goButton = document.querySelector("#go");
const homeLink = document.querySelector("#home-link");
const crumbEl = document.querySelector("#crumb");
const statusEl = document.querySelector("#status");
const homeEl = document.querySelector("#home");
const resultsEl = document.querySelector("#results");
const entryEl = document.querySelector("#entry");

const READING_LABELS = [
  ["mandarin", "표준중국어"],
  ["cantonese", "광동어"],
  ["onyomi", "일본 음독"],
  ["kunyomi", "일본 훈독"],
  ["vietnamese", "베트남어"],
];
const RECENT_KEY = "sino.recent";

let backStack = [];
let currentCp = null;
let homeData = null; // cached for the session

// ---------- helpers ----------

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function charToCp(ch) {
  return "U+" + ch.codePointAt(0).toString(16).toUpperCase().padStart(4, "0");
}

function isLookupQuery(q) {
  q = q.trim();
  if (/^u\+?[0-9a-fA-F]{4,}$/.test(q)) return true;
  const chars = [...q];
  return chars.length === 1 && /\p{Script=Han}/u.test(chars[0]);
}

function hanjaLink(cp, ch, extraClass = "") {
  const glyph = ch && ch.length ? ch : "?";
  return `<button class="hanja-link ${extraClass}" data-cp="${escapeHtml(cp)}"
    >${escapeHtml(glyph)}</button>`;
}

function setStatus(msg, isError = false) {
  statusEl.textContent = msg || "";
  statusEl.classList.toggle("error", Boolean(isError));
}

function showView(name) {
  homeEl.classList.toggle("hidden", name !== "home");
  resultsEl.classList.toggle("hidden", name !== "results");
  entryEl.classList.toggle("hidden", name !== "entry");
}

function getRecent() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY)) || [];
  } catch {
    return [];
  }
}

function pushRecent(cp, ch) {
  const recent = getRecent().filter((x) => x.cp !== cp);
  recent.unshift({ cp, ch });
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, 14)));
}

// ---------- crumb ----------

function renderCrumb() {
  if (!backStack.length) {
    crumbEl.classList.add("hidden");
    crumbEl.innerHTML = "";
    return;
  }
  crumbEl.classList.remove("hidden");
  const trail = backStack
    .slice(-8)
    .map((cp) => escapeHtml(cp))
    .join("  ›  ");
  crumbEl.innerHTML = `<button id="back-btn">← 뒤로</button>
    <button id="home-btn">홈</button>
    <span class="crumb-trail">${trail}</span>`;
  document.querySelector("#back-btn").addEventListener("click", goBack);
  document.querySelector("#home-btn").addEventListener("click", loadHome);
}

// ---------- home ----------

function renderHome(data) {
  const d = data.daily;
  const dailyHtml = d
    ? `<button class="daily-card nav-card" data-cp="${escapeHtml(d.codepoint)}">
        <div class="daily-glyph">${escapeHtml(d.character)}</div>
        <div class="daily-info">
          <div class="daily-label">오늘의 한자</div>
          ${d.hunum ? `<div class="daily-hunum">${escapeHtml(d.hunum)}</div>` : ""}
          <div class="daily-gloss">${escapeHtml(d.gloss || "(뜻 정보 없음)")}</div>
          <div class="daily-meta">${escapeHtml(d.codepoint)}${
        d.primary_ids ? " · " + escapeHtml(d.primary_ids) : ""
      }${d.total_strokes != null ? " · " + d.total_strokes + "획" : ""}</div>
        </div>
      </button>`
    : "";

  const recent = getRecent();
  const recentHtml = recent.length
    ? recent.map((x) => hanjaLink(x.cp, x.ch)).join("")
    : `<span class="muted">아직 본 글자가 없습니다.</span>`;

  const radicalCells = data.radicals
    .map((r) => {
      const ch = r.character || "?";
      const name = (r.name_ko || "").replace(/部$/, "");
      return `<button class="radical-cell" data-idx="${r.radical_idx}"
        data-char="${escapeHtml(ch)}" data-name="${escapeHtml(r.name_ko || "")}">
        <span class="rad-char">${escapeHtml(ch)}</span>
        <span class="rad-meta">${r.radical_idx} · ${escapeHtml(name)}</span>
        <span class="rad-count">${r.char_count.toLocaleString()}</span>
      </button>`;
    })
    .join("");

  const s = data.stats;
  homeEl.innerHTML = `
    <div class="home-top">
      ${dailyHtml}
      <div class="home-recent">
        <h2>최근 본 글자</h2>
        <div class="chip-row">${recentHtml}</div>
        <h2 class="stat-head">데이터베이스</h2>
        <ul class="stat-list">
          <li>한자 <b>${s.characters.toLocaleString()}</b>자</li>
          <li>발음 보유 <b>${s.with_reading.toLocaleString()}</b>자</li>
          <li>뜻 보유 <b>${s.with_meaning.toLocaleString()}</b>자</li>
          <li>이체자 family <b>${s.variant_families.toLocaleString()}</b>개</li>
        </ul>
      </div>
    </div>
    <div class="home-radicals">
      <h2>부수로 찾기 · 214</h2>
      <div class="radical-grid">${radicalCells}</div>
    </div>
  `;
}

async function loadHome() {
  try {
    setStatus("");
    if (!homeData) homeData = await invoke("home_data");
    renderHome(homeData);
    showView("home");
    currentCp = null;
    backStack = [];
    crumbEl.classList.add("hidden");
    queryInput.value = "";
  } catch (err) {
    setStatus(String(err), true);
  }
}

// ---------- entry rendering ----------

function panel(title, bodyHtml) {
  return `<section class="panel">
    <h2>${escapeHtml(title)}</h2>
    <div class="panel-body">${bodyHtml}</div>
  </section>`;
}

function renderStructure(e) {
  const s = e.structure;
  const rows = [];
  if (s.primary_ids) {
    const components = new Set(e.ids_components.map((c) => c.codepoint));
    const ids = [...s.primary_ids]
      .map((ch) => {
        const cp = charToCp(ch);
        return components.has(cp)
          ? hanjaLink(cp, ch)
          : `<span class="idc">${escapeHtml(ch)}</span>`;
      })
      .join("");
    const idc = s.ids_top_idc
      ? ` <span class="muted">(${escapeHtml(s.ids_top_idc)})</span>`
      : "";
    rows.push(`<div class="kv"><span class="k">분해</span>
      <span class="v ids-line">${ids}${idc}</span></div>`);
  }
  if (s.radical_idx != null) {
    let rad = String(s.radical_idx);
    if (s.radical_char) {
      rad += " " + hanjaLink(charToCp(s.radical_char), s.radical_char, "small");
    }
    if (s.radical_name) rad += ` <span class="muted">${escapeHtml(s.radical_name)}</span>`;
    if (s.radical_strokes != null) rad += ` <span class="muted">· ${s.radical_strokes}획</span>`;
    rows.push(`<div class="kv"><span class="k">부수</span><span class="v">${rad}</span></div>`);
  }
  const strokes = [];
  if (s.total_strokes != null) strokes.push(`총 ${s.total_strokes}획`);
  if (s.residual_strokes != null) strokes.push(`잔여 ${s.residual_strokes}획`);
  if (strokes.length) {
    rows.push(`<div class="kv"><span class="k">획수</span>
      <span class="v">${escapeHtml(strokes.join(" · "))}</span></div>`);
  }
  return rows.length ? rows.join("") : `<p class="muted">구조 정보 없음</p>`;
}

function renderReadings(e) {
  const rows = READING_LABELS.flatMap(([key, label]) => {
    const vals = e.readings[key] || [];
    if (!vals.length) return [];
    return [`<div class="kv"><span class="k">${escapeHtml(label)}</span>
      <span class="v">${escapeHtml(vals.join(" / "))}</span></div>`];
  });
  return rows.length ? rows.join("") : `<p class="muted">발음 정보 없음</p>`;
}

function renderHunum(e) {
  if (!e.hunum.length) return `<p class="muted">훈음 정보 없음</p>`;
  const pairs = e.hunum
    .map((h) => {
      const jahun = h.jahun ? `<span class="jahun">${escapeHtml(h.jahun)}</span> ` : "";
      return `<li>${jahun}<span class="dokeum">${escapeHtml(h.dokeum)}</span></li>`;
    })
    .join("");
  return `<ul class="hunum-list">${pairs}</ul>`;
}

function renderMeanings(e) {
  const rows = [];
  if (e.meanings.ko && e.meanings.ko.length) {
    rows.push(`<div class="kv"><span class="k">한국어</span>
      <span class="v">${escapeHtml(e.meanings.ko.join(" / "))}</span></div>`);
  }
  if (e.meanings.en && e.meanings.en.length) {
    rows.push(`<div class="kv"><span class="k">영어</span>
      <span class="v">${escapeHtml(e.meanings.en.join("; "))}</span></div>`);
  }
  return rows.length ? rows.join("") : `<p class="muted">뜻 정보 없음</p>`;
}

function renderVariants(e) {
  const blocks = [];
  if (e.family && e.family.size > 1) {
    const chips = e.family.members
      .map((m) =>
        hanjaLink(m.codepoint, m.character, m.codepoint === e.codepoint ? "self" : "")
      )
      .join("");
    blocks.push(`<div class="kv"><span class="k">family (${e.family.size})</span>
      <span class="v chip-row">${chips}</span></div>`);
  }
  const edgeLine = (edges) =>
    edges
      .map(
        (v) => `<span class="edge">${hanjaLink(v.target_codepoint, v.target_character)}
        <span class="rel">${escapeHtml(v.relation.replace(/^ehanja_/, ""))}</span></span>`
      )
      .join("");
  const variantEdges = e.variants.filter((v) => v.category === "variant");
  const semanticEdges = e.variants.filter((v) => v.category === "semantic");
  if (variantEdges.length) {
    blocks.push(`<div class="kv"><span class="k">이체 관계</span>
      <span class="v chip-row">${edgeLine(variantEdges)}</span></div>`);
  }
  if (semanticEdges.length) {
    blocks.push(`<div class="kv"><span class="k">관련어</span>
      <span class="v chip-row">${edgeLine(semanticEdges)}</span></div>`);
  }
  return blocks.length ? blocks.join("") : `<p class="muted">이체자 정보 없음</p>`;
}

function renderGrades(e) {
  const g = e.grades;
  if (!g) return `<p class="muted">급수 정보 없음</p>`;
  const rows = [];
  const add = (k, v) =>
    rows.push(`<div class="kv"><span class="k">${escapeHtml(k)}</span>
      <span class="v">${escapeHtml(v)}</span></div>`);
  if (g.kr_grade) add("한자검정", g.kr_grade);
  if (g.kr_education) add("한문 교육용", g.kr_education);
  if (g.cn_tonggyong != null) add("중국 통용규범", g.cn_tonggyong + "급");
  if (g.jp_grade != null) {
    let label;
    if (g.jp_grade <= 6) label = g.jp_grade + "학년 (교육한자)";
    else if (g.jp_grade >= 9) label = "인명용한자";
    else label = "상용한자 (중등)";
    add("일본 학년", label);
  }
  if (g.jp_freq != null) add("일본 빈도", "신문 " + g.jp_freq + "위");
  if (g.jp_jlpt != null) add("JLPT", "구 " + g.jp_jlpt + "급");
  if (g.unihan_core) add("Unihan core", "포함 · " + g.unihan_core);
  return rows.length ? rows.join("") : `<p class="muted">급수 정보 없음</p>`;
}

function renderEntry(e) {
  entryEl.innerHTML = `
    <div class="hero">
      <div class="hero-glyph">${escapeHtml(e.character)}</div>
      <div class="hero-meta">
        <div class="hero-cp">${escapeHtml(e.codepoint)}</div>
        ${e.block ? `<div class="hero-block">${escapeHtml(e.block)}</div>` : ""}
      </div>
    </div>
    <div class="panel-grid">
      ${panel("구조", renderStructure(e))}
      ${panel("발음", renderReadings(e))}
      ${panel("훈음 (한국)", renderHunum(e))}
      ${panel("뜻", renderMeanings(e))}
      ${panel("이체자", renderVariants(e))}
      ${panel("급수", renderGrades(e))}
    </div>
  `;
  showView("entry");
}

function renderResults(label, hits) {
  if (!hits.length) {
    resultsEl.innerHTML = `<p class="muted">${escapeHtml(label)} — 결과 없음.</p>`;
    showView("results");
    return;
  }
  const items = hits
    .map(
      (h) => `<li class="result-item" data-cp="${escapeHtml(h.codepoint)}">
        <span class="result-glyph">${escapeHtml(h.character)}</span>
        <span class="result-cp">${escapeHtml(h.codepoint)}</span>
        <span class="result-gloss">${escapeHtml(h.gloss)}</span>
      </li>`
    )
    .join("");
  resultsEl.innerHTML = `<p class="results-head">${escapeHtml(label)}</p>
    <ul class="result-list">${items}</ul>`;
  showView("results");
}

// ---------- actions ----------

async function openEntry(query, { fromNav = false } = {}) {
  try {
    setStatus("조회 중…");
    const entry = await invoke("lookup", { query });
    if (currentCp && !fromNav && currentCp !== entry.codepoint) {
      backStack.push(currentCp);
    }
    currentCp = entry.codepoint;
    renderEntry(entry);
    renderCrumb();
    pushRecent(entry.codepoint, entry.character);
    setStatus("");
  } catch (err) {
    setStatus(String(err), true);
  }
}

async function runSearch(query) {
  try {
    setStatus("검색 중…");
    const hits = await invoke("search", { query, limit: 80 });
    renderResults(`"${query}" 검색 — ${hits.length}건`, hits);
    renderCrumb();
    setStatus("");
  } catch (err) {
    setStatus(String(err), true);
  }
}

async function openRadical(idx, char, name) {
  try {
    setStatus("부수 글자 조회 중…");
    const hits = await invoke("radical_chars", { radicalIdx: idx, limit: 400 });
    renderResults(`부수 ${idx} ${char} ${name} — ${hits.length}자`, hits);
    renderCrumb();
    setStatus(hits.length >= 400 ? "획수 적은 순 400자까지 표시." : "");
  } catch (err) {
    setStatus(String(err), true);
  }
}

function submitQuery() {
  const q = queryInput.value.trim();
  if (!q) return;
  if (isLookupQuery(q)) openEntry(q);
  else runSearch(q);
}

function goBack() {
  const prev = backStack.pop();
  if (prev) openEntry(prev, { fromNav: true });
}

// ---------- events ----------

goButton.addEventListener("click", submitQuery);
queryInput.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") submitQuery();
});
homeLink.addEventListener("click", loadHome);

document.addEventListener("click", (ev) => {
  const rad = ev.target.closest(".radical-cell");
  if (rad) {
    openRadical(Number(rad.dataset.idx), rad.dataset.char, rad.dataset.name);
    return;
  }
  const nav = ev.target.closest(".hanja-link, .result-item, .nav-card");
  if (nav && nav.dataset.cp) openEntry(nav.dataset.cp);
});

// initial view — the home screen
loadHome();
