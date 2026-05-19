//! Sinograph Dictionary — Tauri backend over canonical_v3.sqlite.
//!
//! The database (10 tables + 1 view, ~94 MB) is bundled as a Tauri resource.
//! It is opened read-only once at startup and shared through managed state.
//! Two commands are exposed: `lookup` (one character -> full entry) and
//! `search` (FTS5 reverse lookup by meaning / reading).

use std::sync::{Arc, Mutex};

use rusqlite::{params, Connection, OpenFlags, OptionalExtension};
use serde::Serialize;
use tauri::{Emitter, Manager, State};

pub mod recognize;
use recognize::{Candidate, Recognizer};

/// Managed state — the single read-only connection to canonical_v3.sqlite.
struct Db(Mutex<Connection>);

// ---------- response types ----------

#[derive(Serialize)]
struct NamedChar {
    codepoint: String,
    character: String,
}

#[derive(Serialize)]
struct Structure {
    radical_idx: Option<i64>,
    radical_char: Option<String>,
    radical_name: Option<String>,
    radical_strokes: Option<i64>,
    total_strokes: Option<i64>,
    residual_strokes: Option<i64>,
    primary_ids: Option<String>,
    ids_top_idc: Option<String>,
}

#[derive(Serialize, Default)]
struct Readings {
    mandarin: Vec<String>,
    cantonese: Vec<String>,
    onyomi: Vec<String>,
    kunyomi: Vec<String>,
    vietnamese: Vec<String>,
}

#[derive(Serialize)]
struct Hunum {
    seq: i64,
    jahun: Option<String>,
    dokeum: String,
}

/// A 자훈 / 독음 pair without the sequence index — used for the daily card.
#[derive(Serialize)]
struct HunumPair {
    jahun: Option<String>,
    dokeum: String,
}

#[derive(Serialize, Default)]
struct Meanings {
    ko: Vec<String>,
    en: Vec<String>,
}

#[derive(Serialize)]
struct VariantEdge {
    target_codepoint: String,
    target_character: String,
    relation: String,
    category: String,
}

#[derive(Serialize)]
struct Family {
    size: i64,
    representative: String,
    members: Vec<NamedChar>,
}

#[derive(Serialize)]
struct Grades {
    kr_grade: Option<String>,
    kr_education: Option<String>,
    cn_tonggyong: Option<i64>,
    jp_grade: Option<i64>,
    jp_freq: Option<i64>,
    jp_jlpt: Option<i64>,
    unihan_core: Option<String>,
}

#[derive(Serialize)]
struct CharacterEntry {
    codepoint: String,
    character: String,
    block: Option<String>,
    structure: Structure,
    ids_components: Vec<NamedChar>,
    readings: Readings,
    hunum: Vec<Hunum>,
    meanings: Meanings,
    variants: Vec<VariantEdge>,
    family: Option<Family>,
    grades: Option<Grades>,
}

#[derive(Serialize)]
struct SearchHit {
    codepoint: String,
    character: String,
    gloss: String,
}

#[derive(Serialize)]
struct NamedCharGloss {
    codepoint: String,
    character: String,
    gloss: String,
}

#[derive(Serialize)]
struct DbStats {
    characters: i64,
    with_reading: i64,
    with_meaning: i64,
    variant_families: i64,
}

#[derive(Serialize)]
struct RadicalInfo {
    radical_idx: i64,
    character: Option<String>,
    name_ko: Option<String>,
    strokes: Option<i64>,
    char_count: i64,
}

#[derive(Serialize)]
struct DailyChar {
    codepoint: String,
    character: String,
    gloss: String,
    hunum: Option<HunumPair>,
    primary_ids: Option<String>,
    total_strokes: Option<i64>,
}

#[derive(Serialize)]
struct HomeData {
    stats: DbStats,
    radicals: Vec<RadicalInfo>,
    daily: Option<DailyChar>,
}

// ---------- helpers ----------

/// `U+XXXX` for a scalar value.
fn fmt_cp(value: u32) -> String {
    format!("U+{value:04X}")
}

/// The literal character for a `U+XXXX` codepoint.
fn cp_to_char(cp: &str) -> String {
    cp.strip_prefix("U+")
        .and_then(|h| u32::from_str_radix(h, 16).ok())
        .and_then(char::from_u32)
        .map(|c| c.to_string())
        .unwrap_or_default()
}

/// Normalize a lookup query (one literal character, `U+XXXX`, or bare hex)
/// into a `U+XXXX` codepoint string.
fn normalize_query(q: &str) -> Result<String, String> {
    let q = q.trim();
    if q.is_empty() {
        return Err("입력이 비어 있습니다.".into());
    }
    let upper = q.to_uppercase();
    let hex = if let Some(rest) = upper.strip_prefix("U+") {
        Some(rest.to_string())
    } else if upper.len() >= 4 && upper.chars().all(|c| c.is_ascii_hexdigit()) {
        Some(upper.clone())
    } else {
        None
    };
    if let Some(h) = hex {
        let value = u32::from_str_radix(&h, 16)
            .map_err(|_| format!("잘못된 코드포인트: {q}"))?;
        return Ok(fmt_cp(value));
    }
    let ch = q.chars().next().expect("non-empty checked above");
    Ok(fmt_cp(ch as u32))
}

/// Is this char an Ideographic Description Character (a structure operator,
/// not a component)?
fn is_idc(c: char) -> bool {
    matches!(c as u32, 0x2FF0..=0x2FFF | 0x31EF)
}

/// Whole days since the Unix epoch — used to pick a stable "daily" character.
fn day_number() -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| (d.as_secs() / 86_400) as i64)
        .unwrap_or(0)
}

// ---------- lookup ----------

fn build_entry(conn: &Connection, cp: &str) -> Result<CharacterEntry, String> {
    let summary = conn
        .query_row(
            "SELECT character, block, radical_idx, total_strokes, \
             residual_strokes, primary_ids, ids_top_idc \
             FROM character_summary WHERE codepoint = ?1",
            params![cp],
            |r| {
                Ok((
                    r.get::<_, Option<String>>(0)?,
                    r.get::<_, Option<String>>(1)?,
                    r.get::<_, Option<i64>>(2)?,
                    r.get::<_, Option<i64>>(3)?,
                    r.get::<_, Option<i64>>(4)?,
                    r.get::<_, Option<String>>(5)?,
                    r.get::<_, Option<String>>(6)?,
                ))
            },
        )
        .optional()
        .map_err(|e| e.to_string())?;
    let (character, block, radical_idx, total_strokes, residual_strokes, primary_ids, ids_top_idc) =
        summary.ok_or_else(|| format!("{cp} 는 canonical_v3 universe 에 없습니다."))?;
    let character = match character {
        Some(c) if !c.is_empty() => c,
        _ => cp_to_char(cp),
    };

    // radical reference row
    let (radical_char, radical_name, radical_strokes) = match radical_idx {
        Some(idx) => conn
            .query_row(
                "SELECT char, name_ko, strokes FROM radicals WHERE radical_idx = ?1",
                params![idx],
                |r| {
                    Ok((
                        r.get::<_, Option<String>>(0)?,
                        r.get::<_, Option<String>>(1)?,
                        r.get::<_, Option<i64>>(2)?,
                    ))
                },
            )
            .optional()
            .map_err(|e| e.to_string())?
            .unwrap_or((None, None, None)),
        None => (None, None, None),
    };

    // ids component characters that are navigable (present in the universe)
    let mut ids_components = Vec::new();
    if let Some(ids) = &primary_ids {
        let mut member = conn
            .prepare("SELECT 1 FROM characters_ids WHERE codepoint = ?1")
            .map_err(|e| e.to_string())?;
        let mut seen = std::collections::HashSet::new();
        for ch in ids.chars() {
            if ch.is_ascii() || is_idc(ch) {
                continue;
            }
            let comp_cp = fmt_cp(ch as u32);
            if !seen.insert(comp_cp.clone()) {
                continue;
            }
            let exists = member
                .exists(params![comp_cp])
                .map_err(|e| e.to_string())?;
            if exists {
                ids_components.push(NamedChar {
                    codepoint: comp_cp,
                    character: ch.to_string(),
                });
            }
        }
    }

    // readings (five non-Korean languages)
    let mut readings = Readings::default();
    {
        let mut stmt = conn
            .prepare("SELECT reading_type, value FROM character_readings WHERE codepoint = ?1")
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![cp], |r| {
                Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))
            })
            .map_err(|e| e.to_string())?;
        for row in rows {
            let (rt, value) = row.map_err(|e| e.to_string())?;
            match rt.as_str() {
                "mandarin" => readings.mandarin.push(value),
                "cantonese" => readings.cantonese.push(value),
                "onyomi" => readings.onyomi.push(value),
                "kunyomi" => readings.kunyomi.push(value),
                "vietnamese" => readings.vietnamese.push(value),
                _ => {}
            }
        }
    }

    // Korean 훈음 (jahun + dokeum pairs)
    let hunum = {
        let mut stmt = conn
            .prepare(
                "SELECT seq, jahun, dokeum FROM character_hunum \
                 WHERE codepoint = ?1 ORDER BY seq",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![cp], |r| {
                Ok(Hunum {
                    seq: r.get(0)?,
                    jahun: r.get(1)?,
                    dokeum: r.get(2)?,
                })
            })
            .map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?
    };

    // meanings (ko / en)
    let mut meanings = Meanings::default();
    {
        let mut stmt = conn
            .prepare("SELECT language, value FROM character_meanings WHERE codepoint = ?1")
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![cp], |r| {
                Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))
            })
            .map_err(|e| e.to_string())?;
        for row in rows {
            let (lang, value) = row.map_err(|e| e.to_string())?;
            match lang.as_str() {
                "ko" => meanings.ko.push(value),
                "en" => meanings.en.push(value),
                _ => {}
            }
        }
    }

    // variant edges
    let variants = {
        let mut stmt = conn
            .prepare(
                "SELECT target_codepoint, target_character, relation, relation_category \
                 FROM variant_edges WHERE source_codepoint = ?1 \
                 ORDER BY relation_category, relation",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![cp], |r| {
                Ok(VariantEdge {
                    target_codepoint: r.get(0)?,
                    target_character: r.get(1)?,
                    relation: r.get(2)?,
                    category: r.get(3)?,
                })
            })
            .map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?
    };

    // variant family
    let family_row = conn
        .query_row(
            "SELECT component_size, representative, family_members_json \
             FROM variant_family WHERE codepoint = ?1",
            params![cp],
            |r| {
                Ok((
                    r.get::<_, i64>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                ))
            },
        )
        .optional()
        .map_err(|e| e.to_string())?;
    let family = match family_row {
        Some((size, representative, members_json)) if size > 1 => {
            let cps: Vec<String> =
                serde_json::from_str(&members_json).map_err(|e| e.to_string())?;
            let members = cps
                .into_iter()
                .map(|c| NamedChar {
                    character: cp_to_char(&c),
                    codepoint: c,
                })
                .collect();
            Some(Family {
                size,
                representative,
                members,
            })
        }
        _ => None,
    };

    // 급수 — grade / level across the four standard sets
    let grades = conn
        .query_row(
            "SELECT kr_grade, kr_education, cn_tonggyong, jp_grade, \
             jp_freq, jp_jlpt, unihan_core \
             FROM character_grades WHERE codepoint = ?1",
            params![cp],
            |r| {
                Ok(Grades {
                    kr_grade: r.get(0)?,
                    kr_education: r.get(1)?,
                    cn_tonggyong: r.get(2)?,
                    jp_grade: r.get(3)?,
                    jp_freq: r.get(4)?,
                    jp_jlpt: r.get(5)?,
                    unihan_core: r.get(6)?,
                })
            },
        )
        .optional()
        .map_err(|e| e.to_string())?;

    Ok(CharacterEntry {
        codepoint: cp.to_string(),
        character,
        block,
        structure: Structure {
            radical_idx,
            radical_char,
            radical_name,
            radical_strokes,
            total_strokes,
            residual_strokes,
            primary_ids,
            ids_top_idc,
        },
        ids_components,
        readings,
        hunum,
        meanings,
        variants,
        family,
        grades,
    })
}

#[tauri::command]
fn lookup(db: State<Db>, query: String) -> Result<CharacterEntry, String> {
    let cp = normalize_query(&query)?;
    let conn = db.0.lock().map_err(|e| e.to_string())?;
    build_entry(&conn, &cp)
}

// ---------- search ----------

#[tauri::command]
fn search(db: State<Db>, query: String, limit: i64) -> Result<Vec<SearchHit>, String> {
    let q = query.trim();
    if q.is_empty() {
        return Ok(Vec::new());
    }
    // quote the query so FTS5 treats it as a literal phrase, not syntax.
    let match_expr = format!("\"{}\"", q.replace('"', " "));
    let limit = if (1..=200).contains(&limit) { limit } else { 50 };

    let conn = db.0.lock().map_err(|e| e.to_string())?;
    let pairs: Vec<(String, String)> = {
        let mut stmt = conn
            .prepare(
                "SELECT codepoint, hanja FROM fts_search \
                 WHERE fts_search MATCH ?1 LIMIT ?2",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![match_expr, limit], |r| {
                Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))
            })
            .map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?
    };

    let mut hits = Vec::with_capacity(pairs.len());
    for (codepoint, character) in pairs {
        let gloss: Option<String> = conn
            .query_row(
                "SELECT value FROM character_meanings \
                 WHERE codepoint = ?1 AND language = 'ko' LIMIT 1",
                params![codepoint],
                |r| r.get(0),
            )
            .optional()
            .map_err(|e| e.to_string())?;
        hits.push(SearchHit {
            codepoint,
            character,
            gloss: gloss.unwrap_or_default(),
        });
    }
    Ok(hits)
}

// ---------- variant graph ----------

#[derive(Serialize)]
struct GraphNode {
    codepoint: String,
    character: String,
    focus: bool,
}

#[derive(Serialize)]
struct GraphEdge {
    source: String,
    target: String,
    relation: String,
    category: String,
}

#[derive(Serialize)]
struct VariantGraph {
    nodes: Vec<GraphNode>,
    edges: Vec<GraphEdge>,
}

/// The variant family of one character as a graph: family members are nodes,
/// variant_edges among those members are (undirected, de-duplicated) edges.
#[tauri::command]
fn variant_graph(db: State<Db>, query: String) -> Result<VariantGraph, String> {
    let cp = normalize_query(&query)?;
    let conn = db.0.lock().map_err(|e| e.to_string())?;

    let members_json: Option<String> = conn
        .query_row(
            "SELECT family_members_json FROM variant_family WHERE codepoint = ?1",
            params![cp],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    let members: Vec<String> = match members_json {
        Some(j) => serde_json::from_str(&j).map_err(|e| e.to_string())?,
        None => vec![cp.clone()],
    };
    let member_set: std::collections::HashSet<&str> =
        members.iter().map(String::as_str).collect();

    let nodes = members
        .iter()
        .map(|m| GraphNode {
            character: cp_to_char(m),
            focus: *m == cp,
            codepoint: m.clone(),
        })
        .collect();

    let mut edges = Vec::new();
    let mut seen = std::collections::HashSet::new();
    {
        let mut stmt = conn
            .prepare(
                "SELECT source_codepoint, target_codepoint, relation, \
                 relation_category FROM variant_edges WHERE source_codepoint = ?1",
            )
            .map_err(|e| e.to_string())?;
        for m in &members {
            let rows = stmt
                .query_map(params![m], |r| {
                    Ok((
                        r.get::<_, String>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, String>(2)?,
                        r.get::<_, String>(3)?,
                    ))
                })
                .map_err(|e| e.to_string())?;
            for row in rows {
                let (s, t, relation, category) = row.map_err(|e| e.to_string())?;
                if !member_set.contains(t.as_str()) {
                    continue;
                }
                // de-duplicate to one undirected edge per (pair, relation)
                let pair = if s < t {
                    (s.clone(), t.clone(), relation.clone())
                } else {
                    (t.clone(), s.clone(), relation.clone())
                };
                if seen.insert(pair) {
                    edges.push(GraphEdge {
                        source: s,
                        target: t,
                        relation,
                        category,
                    });
                }
            }
        }
    }

    Ok(VariantGraph { nodes, edges })
}

// ---------- home screen ----------

fn daily_char(conn: &Connection, cp: &str) -> Result<DailyChar, String> {
    let (character, primary_ids, total_strokes) = conn
        .query_row(
            "SELECT character, primary_ids, total_strokes \
             FROM character_summary WHERE codepoint = ?1",
            params![cp],
            |r| {
                Ok((
                    r.get::<_, Option<String>>(0)?,
                    r.get::<_, Option<String>>(1)?,
                    r.get::<_, Option<i64>>(2)?,
                ))
            },
        )
        .map_err(|e| e.to_string())?;
    let gloss: String = conn
        .query_row(
            "SELECT value FROM character_meanings \
             WHERE codepoint = ?1 AND language = 'ko' LIMIT 1",
            params![cp],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?
        .unwrap_or_default();
    let hunum: Option<HunumPair> = conn
        .query_row(
            "SELECT jahun, dokeum FROM character_hunum \
             WHERE codepoint = ?1 ORDER BY seq LIMIT 1",
            params![cp],
            |r| {
                Ok(HunumPair {
                    jahun: r.get(0)?,
                    dokeum: r.get(1)?,
                })
            },
        )
        .optional()
        .map_err(|e| e.to_string())?;
    Ok(DailyChar {
        codepoint: cp.to_string(),
        character: character.filter(|c| !c.is_empty()).unwrap_or_else(|| cp_to_char(cp)),
        gloss,
        hunum,
        primary_ids,
        total_strokes,
    })
}

#[tauri::command]
fn home_data(db: State<Db>) -> Result<HomeData, String> {
    let conn = db.0.lock().map_err(|e| e.to_string())?;
    let count = |sql: &str| -> Result<i64, String> {
        conn.query_row(sql, [], |r| r.get(0)).map_err(|e| e.to_string())
    };

    let stats = DbStats {
        characters: count("SELECT count(*) FROM characters_ids")?,
        with_reading: count("SELECT count(DISTINCT codepoint) FROM character_readings")?,
        with_meaning: count("SELECT count(DISTINCT codepoint) FROM character_meanings")?,
        variant_families: count(
            "SELECT count(*) FROM variant_family WHERE component_size > 1",
        )?,
    };

    let radicals = {
        let mut stmt = conn
            .prepare(
                "SELECT r.radical_idx, r.char, r.name_ko, r.strokes, \
                 (SELECT count(*) FROM characters_structure s \
                  WHERE s.radical_idx = r.radical_idx) \
                 FROM radicals r ORDER BY r.radical_idx",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |r| {
                Ok(RadicalInfo {
                    radical_idx: r.get(0)?,
                    character: r.get(1)?,
                    name_ko: r.get(2)?,
                    strokes: r.get(3)?,
                    char_count: r.get(4)?,
                })
            })
            .map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?
    };

    // daily character — stable per day, drawn from CJK Unified characters
    // that carry a Korean meaning (so it is a "normal" dictionary entry).
    const DAILY_POOL: &str = "SELECT DISTINCT m.codepoint FROM character_meanings m \
         JOIN characters_core c ON m.codepoint = c.codepoint \
         WHERE m.language = 'ko' AND c.block = 'CJK Unified'";
    let pool: i64 = count(&format!("SELECT count(*) FROM ({DAILY_POOL})"))?;
    let daily = if pool > 0 {
        let offset = day_number().rem_euclid(pool);
        let cp: String = conn
            .query_row(
                &format!("{DAILY_POOL} ORDER BY m.codepoint LIMIT 1 OFFSET ?1"),
                params![offset],
                |r| r.get(0),
            )
            .map_err(|e| e.to_string())?;
        Some(daily_char(&conn, &cp)?)
    } else {
        None
    };

    Ok(HomeData {
        stats,
        radicals,
        daily,
    })
}

#[tauri::command]
fn radical_chars(
    db: State<Db>,
    radical_idx: i64,
    limit: i64,
) -> Result<Vec<NamedCharGloss>, String> {
    let limit = if (1..=2000).contains(&limit) { limit } else { 500 };
    let conn = db.0.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare(
            "SELECT s.codepoint, c.character, \
             (SELECT value FROM character_meanings m \
              WHERE m.codepoint = s.codepoint AND m.language = 'ko' LIMIT 1) \
             FROM characters_structure s \
             JOIN characters_core c ON s.codepoint = c.codepoint \
             WHERE s.radical_idx = ?1 \
             ORDER BY s.total_strokes, s.codepoint LIMIT ?2",
        )
        .map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map(params![radical_idx, limit], |r| {
            Ok(NamedCharGloss {
                codepoint: r.get(0)?,
                character: r.get::<_, Option<String>>(1)?.unwrap_or_default(),
                gloss: r.get::<_, Option<String>>(2)?.unwrap_or_default(),
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
}

// ---------- recognition ----------

/// Recognize a glyph image on disk — used by the M1 headless gate and as a
/// debug entry point. Heavy work (image decode + ONNX inference) runs off the
/// UI thread via `spawn_blocking`.
#[tauri::command]
async fn recognize_image_file(
    rec: State<'_, Arc<Recognizer>>,
    path: String,
    k: usize,
) -> Result<Vec<Candidate>, String> {
    let rec = rec.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let img = image::open(&path)
            .map_err(|e| format!("image open: {e}"))?
            .to_rgb8();
        rec.recognize(&img, k)
    })
    .await
    .map_err(|e| e.to_string())?
}

/// Live recognition for the capture overlay — captures the screen square
/// under the cursor and returns the top-`k` hanzi candidates. doc/39 M5.
/// Cursor position is read in Rust (physical px); the overlay passes only the
/// rectangle size in CSS pixels.
#[tauri::command]
async fn recognize_under_cursor(
    app: tauri::AppHandle,
    rec: State<'_, Arc<Recognizer>>,
    size: f64,
    k: usize,
) -> Result<Vec<Candidate>, String> {
    let rec = rec.inner().clone();
    let cursor = app.cursor_position().map_err(|e| e.to_string())?;
    tauri::async_runtime::spawn_blocking(move || {
        let crop = recognize::capture_square(cursor.x, cursor.y, size)?;
        rec.recognize(&crop, k)
    })
    .await
    .map_err(|e| e.to_string())?
}

// ---------- capture overlay ----------

/// The monitor whose physical bounds contain the point (x, y).
fn monitor_at(app: &tauri::AppHandle, x: f64, y: f64) -> Option<tauri::Monitor> {
    let (px, py) = (x as i32, y as i32);
    app.available_monitors().ok()?.into_iter().find(|m| {
        let p = m.position();
        let s = m.size();
        px >= p.x
            && px < p.x + s.width as i32
            && py >= p.y
            && py < p.y + s.height as i32
    })
}

/// Open the full-screen transparent capture overlay on the monitor under the
/// cursor. The window is created dynamically because its target monitor is
/// only known at trigger time. Sized/positioned in physical pixels.
/// Exclude a window from screen capture (`SetWindowDisplayAffinity` /
/// `WDA_EXCLUDEFROMCAPTURE`). The overlay stays visible to the user but is
/// invisible to `xcap`, so the live capture loop never grabs its own
/// rectangle. doc/39 M7.
#[cfg(windows)]
fn exclude_from_capture(win: &tauri::WebviewWindow) -> Result<(), String> {
    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{
        SetWindowDisplayAffinity, WDA_EXCLUDEFROMCAPTURE,
    };
    let hwnd = HWND(win.hwnd().map_err(|e| e.to_string())?.0 as _);
    unsafe { SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE) }
        .map_err(|e| e.to_string())
}

/// Build and show the capture overlay. Shared by the toolbar command and the
/// global hotkey. `async` so it runs off the main thread — building a
/// WebView2 window from a synchronous (main-thread) command deadlocks.
async fn open_overlay(app: tauri::AppHandle) -> Result<(), String> {
    use tauri::{WebviewUrl, WebviewWindowBuilder};

    eprintln!("[overlay] open requested");
    if let Some(w) = app.get_webview_window("capture-overlay") {
        eprintln!("[overlay] already open — focusing");
        w.set_focus().map_err(|e| e.to_string())?;
        return Ok(());
    }

    let cursor = app.cursor_position().map_err(|e| e.to_string())?;
    let monitor = monitor_at(&app, cursor.x, cursor.y)
        .or(app.primary_monitor().map_err(|e| e.to_string())?)
        .ok_or("연결된 모니터를 찾을 수 없습니다.")?;
    let pos = *monitor.position();
    let size = *monitor.size();
    eprintln!(
        "[overlay] cursor=({:.0},{:.0}) monitor pos=({},{}) size=({}x{})",
        cursor.x, cursor.y, pos.x, pos.y, size.width, size.height
    );

    let win = WebviewWindowBuilder::new(
        &app,
        "capture-overlay",
        WebviewUrl::App("overlay.html".into()),
    )
    .title("한자 인식")
    .inner_size(size.width as f64, size.height as f64)
    .position(pos.x as f64, pos.y as f64)
    .transparent(true)
    .decorations(false)
    .always_on_top(true)
    .skip_taskbar(true)
    .resizable(false)
    .shadow(false)
    .visible(false)
    .build()
    .map_err(|e| {
        eprintln!("[overlay] build FAILED: {e}");
        format!("overlay build: {e}")
    })?;
    eprintln!("[overlay] window built");

    // hide the overlay from screen capture before it is ever shown
    #[cfg(windows)]
    if let Err(e) = exclude_from_capture(&win) {
        eprintln!("[overlay] exclude_from_capture failed: {e}");
    }

    win.set_position(tauri::PhysicalPosition::new(pos.x, pos.y))
        .map_err(|e| e.to_string())?;
    win.set_size(tauri::PhysicalSize::new(size.width, size.height))
        .map_err(|e| e.to_string())?;
    win.show().map_err(|e| e.to_string())?;
    win.set_focus().map_err(|e| e.to_string())?;
    eprintln!("[overlay] shown + focused");
    Ok(())
}

/// Toolbar / IPC entry point for opening the capture overlay.
#[tauri::command]
async fn open_capture_overlay(app: tauri::AppHandle) -> Result<(), String> {
    open_overlay(app).await
}

/// Close the capture overlay, if it is open.
#[tauri::command]
fn close_capture_overlay(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window("capture-overlay") {
        w.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// A candidate was picked in the overlay: close the overlay, bring the main
/// window forward, and hand the codepoint to it for a dictionary lookup.
#[tauri::command]
fn focus_main_with_lookup(
    app: tauri::AppHandle,
    codepoint: String,
) -> Result<(), String> {
    if let Some(overlay) = app.get_webview_window("capture-overlay") {
        let _ = overlay.close();
    }
    if let Some(main) = app.get_webview_window("main") {
        let _ = main.unminimize();
        main.show().map_err(|e| e.to_string())?;
        main.set_focus().map_err(|e| e.to_string())?;
        main.emit("lookup-request", codepoint)
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

// ---------- app entry ----------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    use tauri_plugin_global_shortcut::ShortcutState;
                    if event.state() == ShortcutState::Pressed {
                        let app = app.clone();
                        tauri::async_runtime::spawn(async move {
                            if let Err(e) = open_overlay(app).await {
                                eprintln!("[hotkey] open overlay failed: {e}");
                            }
                        });
                    }
                })
                .build(),
        )
        .setup(|app| {
            let resource = |name: &str| {
                app.path()
                    .resolve(
                        format!("resources/{name}"),
                        tauri::path::BaseDirectory::Resource,
                    )
                    .unwrap_or_else(|e| panic!("resolve resource {name}: {e}"))
            };

            let db_path = resource("canonical_v3.sqlite");
            let conn = Connection::open_with_flags(
                &db_path,
                OpenFlags::SQLITE_OPEN_READ_ONLY,
            )
            .unwrap_or_else(|e| {
                panic!("failed to open {}: {e}", db_path.display())
            });
            app.manage(Db(Mutex::new(conn)));

            // SCER recognition engine (doc/39)
            let recognizer = Recognizer::load(
                &resource("scer_v4.onnx"),
                &resource("scer_anchor_db_v20.npy"),
                &resource("class_index.json"),
            )
            .unwrap_or_else(|e| panic!("failed to load SCER recognizer: {e}"));
            app.manage(Arc::new(recognizer));

            // global hotkey — Ctrl+Shift+H opens the capture overlay
            {
                use tauri_plugin_global_shortcut::{
                    Code, GlobalShortcutExt, Modifiers, Shortcut,
                };
                let hotkey = Shortcut::new(
                    Some(Modifiers::CONTROL | Modifiers::SHIFT),
                    Code::KeyH,
                );
                if let Err(e) = app.global_shortcut().register(hotkey) {
                    eprintln!("[setup] hotkey register failed: {e}");
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            lookup,
            search,
            home_data,
            radical_chars,
            variant_graph,
            recognize_image_file,
            recognize_under_cursor,
            open_capture_overlay,
            close_capture_overlay,
            focus_main_with_lookup
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
