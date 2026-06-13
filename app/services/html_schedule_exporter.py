"""Interactive single-file HTML export for the weekly schedule."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field


@dataclass
class LessonBlock:
    """One lesson displayed inside a timetable cell."""

    subject: str
    tutor: str
    students: list[str]


@dataclass
class ScheduleSheet:
    """A printable schedule for one tutor, subject or student."""

    id: int
    name: str
    kind: str  # "tutor" | "subject" | "student"
    cells: dict[str, list[LessonBlock]] = field(default_factory=dict)
    national_id: str = ""


@dataclass
class HtmlSchedulePayload:
    """All data embedded in the exported HTML page."""

    title: str
    days: list[str]
    hours: list[int]
    sheets: list[ScheduleSheet]


def cell_key(day: int, hour: int) -> str:
    """Return a stable string key for a grid cell."""
    return f"{day},{hour}"


def payload_to_dict(payload: HtmlSchedulePayload) -> dict:
    """Convert the payload to a JSON-serializable structure."""
    return {
        "title": payload.title,
        "days": payload.days,
        "hours": payload.hours,
        "sheets": [
            {
                "id": sheet.id,
                "name": sheet.name,
                "kind": sheet.kind,
                "national_id": sheet.national_id,
                "cells": {
                    key: [asdict(block) for block in blocks]
                    for key, blocks in sheet.cells.items()
                },
            }
            for sheet in payload.sheets
        ],
    }


def build_interactive_html(payload: HtmlSchedulePayload) -> str:
    """Build a self-contained RTL HTML page with embedded data and UI."""
    data_json = json.dumps(payload_to_dict(payload), ensure_ascii=False)
    title = html.escape(payload.title)

    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg: #eef1f7;
  --surface: #ffffff;
  --text: #1f2733;
  --muted: #6b7895;
  --primary: #2d6cdf;
  --primary-dark: #1d4aa0;
  --border: #e2e6ee;
  --hour-bg: #eef2f9;
  --shadow: 0 2px 12px rgba(45, 60, 90, 0.08);
  --radius: 10px;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: "Segoe UI", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.45;
}}
header {{
  background: linear-gradient(135deg, var(--primary) 0%, #1a56c4 100%);
  color: #fff;
  padding: 28px 24px 22px;
  box-shadow: var(--shadow);
}}
header h1 {{
  margin: 0 0 6px;
  font-size: 1.75rem;
  font-weight: 700;
}}
header p {{
  margin: 0;
  opacity: 0.9;
  font-size: 0.95rem;
}}
main {{
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}}
.controls {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  box-shadow: var(--shadow);
  margin-bottom: 20px;
}}
.tabs {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}}
.tab {{
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  padding: 9px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.95rem;
  transition: all 0.15s ease;
}}
.tab:hover {{ border-color: var(--primary); color: var(--primary-dark); }}
.tab.active {{
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}}
.control-row {{
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}}
.control-row label {{
  font-weight: 600;
  color: var(--muted);
  min-width: 72px;
}}
select, input[type="search"] {{
  flex: 1;
  min-width: 220px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font: inherit;
  background: #fff;
}}
select:focus, input[type="search"]:focus {{
  outline: 2px solid rgba(45, 108, 223, 0.25);
  border-color: var(--primary);
}}
.btn-print {{
  margin-top: 14px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}}
.btn-print:hover {{ background: var(--primary-dark); }}
.schedule-panel {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow);
}}
.schedule-title {{
  margin: 0 0 16px;
  font-size: 1.35rem;
  color: var(--primary-dark);
}}
.table-wrap {{
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  min-width: 900px;
}}
th, td {{
  border: 1px solid var(--border);
  vertical-align: top;
  padding: 8px;
}}
thead th {{
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--primary);
  color: #fff;
  text-align: center;
  font-weight: 700;
  padding: 12px 8px;
}}
.hour-col {{
  position: sticky;
  right: 0;
  z-index: 1;
  background: var(--hour-bg);
  font-weight: 700;
  text-align: center;
  white-space: nowrap;
  min-width: 72px;
}}
.cell-empty {{
  background: #fafbfd;
  min-height: 56px;
}}
.lesson {{
  background: #fff;
  border-right: 4px solid var(--primary);
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 6px;
  box-shadow: 0 1px 4px rgba(30, 40, 60, 0.06);
}}
.lesson:last-child {{ margin-bottom: 0; }}
.lesson-subject {{
  font-weight: 700;
  font-size: 0.92rem;
  margin-bottom: 4px;
}}
.lesson-tutor {{
  color: var(--muted);
  font-size: 0.85rem;
  margin-bottom: 3px;
}}
.lesson-students {{
  font-size: 0.85rem;
}}
.lesson-students ul {{
  margin: 4px 0 0;
  padding-right: 18px;
}}
.empty-msg {{
  text-align: center;
  color: var(--muted);
  padding: 48px 16px;
  font-size: 1.05rem;
}}
.hidden {{ display: none !important; }}
@media print {{
  body {{ background: #fff; }}
  header, .controls, .tabs, .btn-print, .no-print {{ display: none !important; }}
  main {{ padding: 0; max-width: none; }}
  .schedule-panel {{
    box-shadow: none;
    border: none;
    padding: 0;
  }}
  .table-wrap {{ overflow: visible; }}
  thead th {{ position: static; }}
  .hour-col {{ position: static; }}
}}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p>מערכת שעות — תצוגה לפי חונכת, מקצוע או תלמיד</p>
</header>
<main>
  <section class="controls no-print">
    <div class="tabs" id="tabs">
      <button type="button" class="tab active" data-kind="tutor">חונכות</button>
      <button type="button" class="tab" data-kind="subject">מקצועות</button>
      <button type="button" class="tab" data-kind="student">תלמידים</button>
    </div>
    <div class="control-row">
      <label for="entitySelect">בחירה:</label>
      <select id="entitySelect"></select>
    </div>
    <div class="control-row hidden" id="studentSearchRow">
      <label for="studentSearch">חיפוש:</label>
      <input type="search" id="studentSearch" placeholder="הקלידו שם או ת.ז....">
    </div>
    <button type="button" class="btn-print" id="printBtn">הדפסה</button>
  </section>
  <section class="schedule-panel" id="schedulePanel">
    <h2 class="schedule-title" id="scheduleTitle"></h2>
    <div id="scheduleContent"></div>
  </section>
</main>
<script id="schedule-data" type="application/json">{data_json}</script>
<script>
(function () {{
  const DATA = JSON.parse(document.getElementById("schedule-data").textContent);
  const KIND_LABELS = {{ tutor: "חונכת", subject: "מקצוע", student: "תלמיד" }};
  let activeKind = "tutor";

  const tabsEl = document.getElementById("tabs");
  const selectEl = document.getElementById("entitySelect");
  const searchRow = document.getElementById("studentSearchRow");
  const searchEl = document.getElementById("studentSearch");
  const titleEl = document.getElementById("scheduleTitle");
  const contentEl = document.getElementById("scheduleContent");
  const printBtn = document.getElementById("printBtn");

  function subjectColor(name) {{
    let h = 0;
    for (let i = 0; i < name.length; i++) {{
      h = ((h << 5) - h + name.charCodeAt(i)) | 0;
    }}
    h = ((h % 360) + 360) % 360;
    return `hsl(${{h}}, 55%, 42%)`;
  }}

  function sheetsForKind(kind) {{
    return DATA.sheets.filter(s => s.kind === kind);
  }}

  function populateSelect() {{
    const query = (searchEl.value || "").trim().toLowerCase();
    const sheets = sheetsForKind(activeKind).filter(s =>
      activeKind !== "student" || !query
        || s.name.toLowerCase().includes(query)
        || (s.national_id || "").includes(query)
    );
    const prev = selectEl.value;
    selectEl.innerHTML = "";
    sheets.forEach(s => {{
      const opt = document.createElement("option");
      opt.value = String(s.id);
      opt.textContent = s.name;
      selectEl.appendChild(opt);
    }});
    if (sheets.length === 0) {{
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = activeKind === "student" ? "לא נמצאו תלמידים" : "אין נתונים";
      selectEl.appendChild(opt);
    }} else if (sheets.some(s => String(s.id) === prev)) {{
      selectEl.value = prev;
    }}
    renderSchedule();
  }}

  function renderStudents(block) {{
    const students = block.students || [];
    if (students.length === 0) return "";
    if (students.length <= 2) {{
      return `<div class="lesson-students">${{students.map(htmlEscape).join(" · ")}}</div>`;
    }}
    const items = students.map(s => `<li>${{htmlEscape(s)}}</li>`).join("");
    return `<div class="lesson-students"><ul>${{items}}</ul></div>`;
  }}

  function htmlEscape(text) {{
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }}

  function renderSchedule() {{
    const id = selectEl.value;
    const sheet = DATA.sheets.find(s => s.kind === activeKind && String(s.id) === id);
    if (!sheet) {{
      titleEl.textContent = "";
      contentEl.innerHTML = '<div class="empty-msg">אין שיבוצים להצגה</div>';
      return;
    }}
    titleEl.textContent = `${{KIND_LABELS[activeKind]}}: ${{sheet.name}}`;
    let hasAny = false;
    let rows = "";
    DATA.hours.forEach(hour => {{
      rows += "<tr>";
      rows += `<td class="hour-col">שעה ${{hour}}</td>`;
      DATA.days.forEach((day, dayIndex) => {{
        const key = dayIndex + "," + hour;
        const blocks = sheet.cells[key] || [];
        if (blocks.length) hasAny = true;
        let inner = "";
        blocks.forEach(block => {{
          const color = subjectColor(block.subject);
          inner += `<div class="lesson" style="border-right-color:${{color}}">`;
          inner += `<div class="lesson-subject" style="color:${{color}}">${{htmlEscape(block.subject)}}</div>`;
          inner += `<div class="lesson-tutor">חונכת: ${{htmlEscape(block.tutor)}}</div>`;
          inner += renderStudents(block);
          inner += "</div>";
        }});
        rows += `<td class="${{inner ? "" : "cell-empty"}}">${{inner}}</td>`;
      }});
      rows += "</tr>";
    }});
    if (!hasAny) {{
      contentEl.innerHTML = '<div class="empty-msg">אין שיבוצים במערכת זו</div>';
      return;
    }}
    let table = '<div class="table-wrap"><table dir="rtl"><thead><tr>';
    table += '<th class="hour-col">שעה</th>';
    DATA.days.forEach(day => {{ table += `<th>${{htmlEscape(day)}}</th>`; }});
    table += "</tr></thead><tbody>" + rows + "</tbody></table></div>";
    contentEl.innerHTML = table;
  }}

  tabsEl.addEventListener("click", e => {{
    const btn = e.target.closest(".tab");
    if (!btn) return;
    activeKind = btn.dataset.kind;
    tabsEl.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    searchRow.classList.toggle("hidden", activeKind !== "student");
    searchEl.value = "";
    populateSelect();
  }});

  selectEl.addEventListener("change", renderSchedule);
  searchEl.addEventListener("input", populateSelect);
  printBtn.addEventListener("click", () => window.print());

  searchRow.classList.add("hidden");
  populateSelect();
}})();
</script>
</body>
</html>"""
