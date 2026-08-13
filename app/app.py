import sys
import json
import re
import ast
import uuid
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.pipeline import RAGProviderError, generate_answer, retrieve_chunks
from ingest.geo_metadata import geographic_metadata, normalize_country
sys.path.insert(0, str(Path(__file__).parent))
from drive_request_uploader import upload_case_request_to_drive
from sheets_logger import log_query


def _ensure_embedding_index_built():
    """Ensure the hosted app has a usable precomputed embedding index.

    Keep this intentionally lightweight. Building embeddings imports torch and
    sentence-transformers, which can make tiny hosted instances stall before
    the first page renders.
    """
    precomputed = Path("data/extracted/precomputed_embeddings.json")
    if not precomputed.exists():
        raise FileNotFoundError(
            f"Precomputed embeddings not found at {precomputed}. "
            "Run python ingest/embed_and_index.py before deploying."
        )

    pre = json.loads(precomputed.read_text())
    required = ("ids", "texts", "metadatas", "embeddings")
    missing = [key for key in required if key not in pre]
    if missing:
        raise ValueError(
            "precomputed_embeddings.json is missing required fields: "
            + ", ".join(missing)
        )
    print(f"Embeddings index available ({len(pre.get('ids', []))} chunks).")

QUESTIONS_PATH = Path("questionnaire/questions.json")
DATA_RAW = Path("data/raw")
MAX_HISTORY_ITEMS = 20


def _history_dir() -> Path:
    configured = os.getenv("RFR_HISTORY_DIR")
    if configured:
        return Path(configured)

    bucket_mount = Path("/data")
    if bucket_mount.exists() and os.access(bucket_mount, os.W_OK):
        return bucket_mount / "streamlit_history"

    return Path(".streamlit_history")


@st.cache_data
def load_case_meta() -> dict[str, dict]:
    """Load case metadata for all case studies with local case_meta.json files."""
    meta = {}
    if not DATA_RAW.exists():
        return meta
    for folder in DATA_RAW.iterdir():
        m = __import__("re").match(r"^(CS\d+)", folder.name)
        if m:
            meta_path = folder / "case_meta.json"
            if meta_path.exists():
                cid = m.group(1)
                meta[cid] = json.loads(meta_path.read_text())
    return meta


def load_questions() -> list[dict]:
    return json.loads(QUESTIONS_PATH.read_text())["questions"]


def _section_label(section: str) -> str:
    label = section.replace("_", " ").title()
    return label if len(label) < 60 else label[:57] + "..."


def _clean_excerpt(text: str, max_chars: int = 800) -> str:
    text = re.sub(r'^Case study:.*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Section:.*?\n', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0] + ' ...'
    return text


def _parse_source_links(raw) -> list[dict]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(raw)
            except Exception:
                continue
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
    return []


def _render_source_links(raw_links, limit: int = 5) -> None:
    links = _parse_source_links(raw_links)
    if not links:
        return
    st.markdown("**Paper/source links:**")
    for link in links[:limit]:
        title = link.get("title") or link.get("doi") or link.get("url") or "Source"
        url = link.get("url") or (f"https://doi.org/{link['doi']}" if link.get("doi") else "")
        if url:
            st.markdown(f"- [{title}]({url})")
        else:
            st.markdown(f"- {title}")
        if link.get("pdf_url"):
            st.markdown(f"  - [PDF]({link['pdf_url']})")


def _render_apa_source_links(raw_links, limit: int | None = None) -> None:
    links = _parse_source_links(raw_links)
    if not links:
        st.caption("No source links available for this case yet.")
        return

    selected = links if limit is None else links[:limit]
    for link in selected:
        title = link.get("title") or link.get("doi") or link.get("url") or "Source"
        url = link.get("url") or (f"https://doi.org/{link['doi']}" if link.get("doi") else "")
        if url:
            st.markdown(f"- [{title}]({url})")
        else:
            st.markdown(f"- {title}")
        if link.get("pdf_url"):
            st.markdown(f"  - [PDF]({link['pdf_url']})")

def _render_navigation(current_page: str, conversation_id: str) -> None:
    nav_items = [
        ("ask", "Ask"),
        ("previous_responses", "Previous Responses"),
        ("how_to_use", "How to Use"),
        ("new_case_requests", "New Case Study Requests"),
        ("case_studies", "Case Studies"),
        ("about", "About"),
    ]
    hidden_params = {
        "disclaimer_accepted": "true",
        "conversation_id": conversation_id,
    }
    hidden_inputs = "\n".join(
        f'<input type="hidden" name="{escape(key)}" value="{escape(value)}">'
        for key, value in hidden_params.items()
    )
    buttons = []
    for page, label in nav_items:
        classes = "rfr-nav-button is-active" if page == current_page else "rfr-nav-button"
        disabled = " disabled" if page == current_page else ""
        buttons.append(
            f'<button class="{classes}" type="submit" name="page" '
            f'value="{escape(page)}"{disabled}>{escape(label)}</button>'
        )

    st.markdown(
        f"""
        <style>
        .rfr-nav {{
            display: flex;
            align-items: center;
            gap: 0.9rem 1.4rem;
            width: 100%;
        }}
        .rfr-nav-brand {{
            color: #17324d;
            font-weight: 700;
            font-size: 1.05rem;
            white-space: nowrap;
            margin-right: auto;
        }}
        .rfr-nav-form {{
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            align-items: center;
            gap: 0.55rem 0.7rem;
            margin: 0;
            min-width: 0;
        }}
        .rfr-nav-button {{
            min-height: 2.25rem;
            padding: 0.45rem 0.8rem;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            background: #ffffff;
            color: #2f3340;
            font: inherit;
            line-height: 1.15;
            white-space: nowrap;
            cursor: pointer;
        }}
        .rfr-nav-button:hover:not(:disabled) {{
            border-color: #aeb6c2;
            background: #f8fafc;
            color: #17324d;
        }}
        .rfr-nav-button.is-active {{
            background: #edf4f8;
            border-color: #d6e3ea;
            color: #17324d;
            font-weight: 600;
            cursor: default;
        }}
        .rfr-nav-rule {{
            border-bottom: 1px solid #dfe4ea;
            margin: 0.25rem 0 1.5rem 0;
        }}
        @media (max-width: 980px) {{
            .rfr-nav {{
                align-items: flex-start;
                flex-direction: column;
                gap: 0.65rem;
            }}
            .rfr-nav-brand {{
                margin-right: 0;
            }}
            .rfr-nav-form {{
                justify-content: flex-start;
                gap: 0.45rem 0.55rem;
            }}
            .rfr-nav-button {{
                padding: 0.42rem 0.7rem;
            }}
        }}
        </style>
        <nav class="rfr-nav" aria-label="Primary navigation">
            <div class="rfr-nav-brand">RFR Knowledge Platform</div>
            <form class="rfr-nav-form" method="get" target="_self">
                {hidden_inputs}
                {"".join(buttons)}
            </form>
        </nav>
        <div class="rfr-nav-rule"></div>
        """,
        unsafe_allow_html=True,
    )


def _case_sort_key(case_id: str) -> int:
    m = re.search(r"\d+", case_id or "")
    return int(m.group()) if m else 10_000


def _indexed_case_records() -> list[dict]:
    extracted_dir = Path("data/extracted")
    records = []
    for f in sorted(extracted_dir.glob("CS*.json"), key=lambda p: _case_sort_key(p.stem)):
        try:
            chunks = json.loads(f.read_text())
        except Exception:
            continue
        if not chunks:
            continue

        first = chunks[0]
        cid = first.get("case_id", f.stem)
        location = first.get("location", "")
        raw_country = first.get("country", "")
        geo = geographic_metadata(location, raw_country)
        records.append({
            "case_id": cid,
            "name": load_case_meta().get(cid, {}).get("name", cid),
            "location": location,
            "country": normalize_country(raw_country),
            "continent": first.get("continent") or geo["continent"],
            "admin_area": first.get("admin_area") or geo["admin_area"],
        })
    return records


def _metadata_query_kind(query: str) -> str | None:
    q = query.lower()
    mentions_geo = re.search(
        r"\b(continent|country|countries|region|area|province|state|location|europe|asia|africa|north america|south america|oceania)\b",
        q,
    )
    mentions_cases = re.search(r"\bcase stud(?:y|ies)\b|\bcases\b", q)
    asks_counts = re.search(r"\b(count|counts|frequency|frequencies|breakdown|how many|number of|table)\b", q)
    asks_list = re.search(r"\b(list|show|which|what)\b", q)
    asks_summarize = re.search(r"\b(summarize|summary|summaries)\b", q)

    if mentions_cases and asks_counts and mentions_geo:
        return "geo_counts"
    if mentions_cases and asks_summarize and mentions_geo:
        return "geo_summary"
    if mentions_cases and asks_list and mentions_geo:
        return "geo_list"
    return None


def _markdown_table(headers: list[str], rows: list[list[str | int]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join("---:" if h.lower() == "count" else "---" for h in headers) + " |"
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def _frequency_rows(records: list[dict], field: str) -> list[list[str | int]]:
    counts = {}
    for record in records:
        value = record.get(field) or "Unknown"
        counts[value] = counts.get(value, 0) + 1
    return [[value, count] for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _requested_geo_value(query: str, records: list[dict]) -> tuple[str, str] | None:
    q = query.lower()
    fields = ("continent", "country", "admin_area")
    for field in fields:
        values = sorted({r.get(field, "") for r in records if r.get(field)}, key=len, reverse=True)
        for value in values:
            if value and value.lower() in q:
                return field, value
    return None


def _metadata_answer_markdown(query: str) -> str | None:
    q = query.lower()
    asks_all_case_summary = (
        re.search(r"\b(summarize|summary|summaries|overview)\b", q)
        and re.search(r"\b(all|every|the)\b.{0,20}\bcase stud(?:y|ies)\b", q)
    )
    if asks_all_case_summary:
        summary_chunks = _load_case_summary_chunks()
        if not summary_chunks:
            return "No case-study summaries were found."

        meta = load_case_meta()
        rows = []
        for chunk in sorted(summary_chunks, key=lambda c: _case_sort_key(c.get("case_id", ""))):
            cid = chunk.get("case_id", "")
            rows.append([
                cid,
                meta.get(cid, {}).get("name") or cid,
                chunk.get("location", ""),
                normalize_country(chunk.get("country", "")),
                _clean_excerpt(chunk.get("text", ""), max_chars=260),
            ])
        return "\n\n".join([
            "### Summary of Indexed Case Studies",
            _markdown_table(["Case ID", "Name", "Location", "Country", "Short Summary"], rows),
            f"Total: {len(rows)} case studies summarized.",
        ])

    kind = _metadata_query_kind(query)
    if not kind:
        return None

    records = _indexed_case_records()
    if not records:
        return "No indexed case studies were found."

    wants_only_tables = "only include" in q and "table" in q

    if kind == "geo_counts":
        tables = []
        if "continent" in q or "region" in q or "area" in q or "country" not in q:
            tables.append(_markdown_table(["Continent", "Count"], _frequency_rows(records, "continent")))
        if "country" in q or "countries" in q or "region" in q or "area" in q:
            tables.append(_markdown_table(["Country", "Count"], _frequency_rows(records, "country")))
        if "province" in q or "state" in q:
            rows = [row for row in _frequency_rows(records, "admin_area") if row[0] != "Unknown"]
            tables.append(_markdown_table(["State/Province/Area", "Count"], rows))
        return "\n\n".join(tables)

    requested = _requested_geo_value(query, records)
    filtered = records
    label = ""
    if requested:
        field, value = requested
        filtered = [record for record in records if record.get(field) == value]
        label = value

    if kind == "geo_summary":
        outside_count = len(records) - len(filtered) if requested else 0
        rows = [
            [record["case_id"], record["name"], record["location"], record["country"]]
            for record in filtered
        ]
        pieces = []
        if not wants_only_tables:
            pieces.append(f"### Case studies in {label}" if label else "### Matching case studies")
        pieces.append(_markdown_table(["Case ID", "Name", "Location", "Country"], rows))
        if requested:
            pieces.append(_markdown_table([f"Outside {label}", "Count"], [[f"Outside {label}", outside_count]]))
        return "\n\n".join(pieces)

    if kind == "geo_list":
        rows = [
            [record["case_id"], record["name"], record["location"], record["country"], record["continent"]]
            for record in filtered
        ]
        return _markdown_table(["Case ID", "Name", "Location", "Country", "Continent"], rows)

    return None


def _current_page() -> str:
    page = _get_query_param("page") or "ask"
    allowed = {"ask", "how_to_use", "new_case_requests", "case_studies", "previous_responses", "about"}
    return page if page in allowed else "ask"


@st.cache_data
def _load_case_summary_chunks() -> list[dict]:
    path = Path("data/extracted/case_summaries.json")
    if not path.exists():
        return []
    try:
        chunks = json.loads(path.read_text())
    except Exception:
        return []
    return chunks if isinstance(chunks, list) else []


def _case_summary_records() -> list[dict]:
    meta = load_case_meta()
    records = []
    for chunk in _load_case_summary_chunks():
        cid = chunk.get("case_id", "")
        case_meta = meta.get(cid, {})
        records.append({
            "case_id": cid,
            "name": case_meta.get("name") or cid,
            "location": chunk.get("location", ""),
            "country": normalize_country(chunk.get("country", "")),
            "continent": chunk.get("continent", ""),
            "summary": _clean_excerpt(chunk.get("text", ""), max_chars=900),
            "source_links": chunk.get("source_links"),
        })
    return sorted(records, key=lambda record: _case_sort_key(record["case_id"]))


def _render_case_studies_page() -> None:
    st.title("Case Studies")
    st.caption("Indexed managed retreat case studies with summary notes and paper/source links.")

    records = _case_summary_records()
    if not records:
        st.warning("No case-study summaries were found. Run the ingest and summary chunk scripts first.")
        return

    countries = sorted({record["country"] for record in records if record["country"]})
    continents = sorted({record["continent"] for record in records if record["continent"]})
    filter_col, country_col = st.columns([1, 1])
    with filter_col:
        continent_filter = st.selectbox("Continent", ["All"] + continents)
    with country_col:
        country_filter = st.selectbox("Country", ["All"] + countries)

    filtered = [
        record for record in records
        if (continent_filter == "All" or record["continent"] == continent_filter)
        and (country_filter == "All" or record["country"] == country_filter)
    ]
    st.caption(f"Showing {len(filtered)} of {len(records)} indexed case studies.")

    for record in filtered:
        with st.expander(f"{record['case_id']} — {record['name']} ({record['country']})", expanded=False):
            st.markdown(f"**Location:** {record['location']}")
            if record["continent"]:
                st.markdown(f"**Continent:** {record['continent']}")
            st.markdown("**Summary:**")
            st.markdown(record["summary"])
            st.markdown("**Sources:**")
            _render_apa_source_links(record["source_links"], limit=None)


def _render_previous_responses_page(conversation_id: str, questions: list[dict]) -> None:
    st.title("Previous Responses")
    st.caption("Full responses saved for this browser conversation.")

    history = _load_history(conversation_id)
    if not history:
        st.info("No previous responses are saved for this conversation yet.")
        return

    if st.button("Clear previous responses", type="secondary"):
        st.session_state.history = []
        _save_history(conversation_id, st.session_state.history)
        st.rerun()

    for i, entry in enumerate(history):
        response_number = len(history) - i
        st.markdown(f"## Response {response_number}")
        st.markdown(f"**Question:** {entry.get('query', '')}")

        context = entry.get("context") or {}
        if context:
            with st.expander("Context used", expanded=False):
                for qid, val in context.items():
                    q_text = next((q["text"] for q in questions if q["id"] == qid), qid)
                    st.markdown(f"**{q_text}** {val}")

        st.markdown(entry.get("answer", ""))

        chunks = entry.get("chunks") or []
        if chunks:
            with st.expander("Case studies and sources used", expanded=False):
                seen_ids = set()
                for chunk in chunks:
                    metadata = chunk.get("metadata", {})
                    cid = metadata.get("case_id", "")
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    st.markdown(f"**{cid} — {metadata.get('source', '')}**")
                    _render_apa_source_links(metadata.get("source_links"), limit=5)

        st.divider()


def _render_about_page() -> None:
    st.title("About")
    st.markdown(
        """
        This AI-assisted knowledge platform supports exploration of managed retreat
        case-study literature from the Retreat From Risk project by
        [Anna Zhou](https://uwaterloo.ca/retreating-from-risk/profiles/anna-zhou)
        from the University of Waterloo.

        For background from the RFR team, see
        [Managed Retreat 101](https://uwaterloo.ca/retreating-from-risk/managed-retreat-101).
        You can also meet the
        [Retreating From Risk team](https://uwaterloo.ca/retreating-from-risk/meet-retreating-risk-team).
        This website was supervised by
        [Dr. Rodrigo Costa](https://uwaterloo.ca/retreating-from-risk/profiles/rodrigo-costa),
        with PhD collaboration from
        [Ana Carolina Dalla Valle](https://uwaterloo.ca/retreating-from-risk/profiles/ana-carolina-dalla-valle).

        The tool retrieves evidence from indexed case-study summaries and sections,
        then generates a grounded response for planning, policy, and research use.
        It is a research aid only and does not replace professional planning, legal,
        engineering, or policy advice.
        """
    )


def _render_how_to_use_page() -> None:
    st.title("How to Use This Tool")
    st.caption("Guidelines for asking stronger questions and reading the answers responsibly.")

    st.markdown(
        """
        ### 1. Add context in the sidebar

        The sidebar questions are optional, but they help tailor the answer to your situation.
        Use them to describe who you are, the type of hazard you are thinking about, where your
        community is in the managed retreat process, and what concerns matter most.

        ### 2. Ask one focused question at a time

        Good questions usually name the topic you care about and the kind of answer you need.

        **Examples:**
        - What funding models have worked for floodplain buyout programs?
        - How did communities maintain social cohesion after relocation?
        - What barriers appeared in Indigenous or culturally distinct communities?
        - Which cases involved strong public opposition, and how was it handled?
        - What lessons from North American cases apply to municipal planners?

        ### 3. Use case IDs when you want a specific case

        If you ask about a case ID, the tool retrieves that case directly.

        **Examples:**
        - Summarize CS42.
        - What were the equity issues in CS41?
        - Compare CS8 and CS28.

        ### 4. Use metadata questions for fast counts and lists

        The tool answers geography and catalog questions directly from indexed metadata,
        rather than asking the AI model to guess.

        **Examples:**
        - Give frequency tables by continent and country.
        - Which case studies are in Europe?
        - How many cases are outside North America?
        - List all case studies in North Carolina.

        ### 5. Check the case studies and source links

        Open the **Case Studies** tab to review every indexed case. Each case includes a short
        summary and clickable paper/source links in APA-style labels where available.

        ### 6. Review previous answers

        Open the **Previous Responses** tab to see the full answer history for your current
        browser conversation. This is useful when comparing several questions or copying a
        complete response with formatting. To preserve this history across restarts, the tool
        may store previous questions and answers in the app's private storage. Do not enter
        sensitive personal, legal, medical, financial, or confidential community information.

        ### 7. Treat answers as research support

        The responses are generated from managed retreat case-study literature and may contain
        omissions or interpretation errors. Verify important claims against the cited papers or
        source links before using an answer in planning, policy, legal, engineering, or public
        engagement work.
        """
    )


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "uploaded_file"


def _safe_slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return cleaned[:60] or fallback


def _render_new_case_requests_page() -> None:
    st.title("New Case Study Requests")
    st.caption(
        "Submit candidate managed retreat case studies and source papers for the RFR team to review. "
        "This intake form stores files only; it does not call an AI model or process the case automatically."
    )

    st.info(
        "Do not upload sensitive or confidential material. Submitted files and request notes are "
        "saved to the project team's Google Drive intake folder for review."
    )

    with st.form("new_case_request_form", clear_on_submit=False):
        case_title = st.text_input("Case study name or short title", placeholder="Example: Coastal buyout program in ...")
        location = st.text_input("Location", placeholder="City/region, province/state")
        country = st.text_input("Country")
        source_links = st.text_area(
            "Paper/source links",
            placeholder="Paste DOIs, URLs, Google Drive links, or citation notes. One source per line is easiest.",
            height=120,
        )
        notes = st.text_area(
            "Why should this case be added?",
            placeholder="Briefly describe why this case is relevant to managed retreat, relocation, buyouts, resettlement, or flood risk.",
            height=120,
        )
        submitter = st.text_input("Your name or email (optional)")
        uploaded_files = st.file_uploader(
            "Upload papers or supporting files",
            type=["pdf", "txt", "md", "doc", "docx"],
            accept_multiple_files=True,
            help="PDFs are preferred. Keep uploads to papers and public supporting documents.",
        )

        submitted = st.form_submit_button("Submit case study request", type="primary")

    if not submitted:
        with st.expander("How the team processes submitted requests", expanded=False):
            st.markdown(
                """
                1. Review the request files in the Google Drive intake folder.
                2. Create a new `CSxx` folder under `data/raw/` on a team machine.
                3. Move accepted papers into that folder and add or update `case_meta.json`.
                4. Run the one-provider extraction pipeline locally.
                5. Ingest, embed, commit, and push the updated index.
                """
            )
        return

    if not case_title.strip() and not source_links.strip() and not uploaded_files:
        st.warning("Please add at least a case title, source link, or uploaded file.")
        return

    created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    request_id = f"{created_at}_{uuid.uuid4().hex[:8]}"
    request_slug = _safe_slug(case_title or location or "new-case-request", "new-case-request")
    request_folder_name = f"{request_id}_{request_slug}"

    record = {
        "request_id": request_id,
        "created_at_utc": created_at,
        "case_title": case_title.strip(),
        "location": location.strip(),
        "country": country.strip(),
        "source_links": source_links.strip(),
        "notes": notes.strip(),
        "submitter": submitter.strip(),
        "submitted_files": [_safe_filename(uploaded.name) for uploaded in uploaded_files or []],
        "status": "new",
    }
    try:
        drive_record = upload_case_request_to_drive(
            request_folder_name=request_folder_name,
            request_record=record,
            uploaded_files=list(uploaded_files or []),
        )
    except Exception as exc:
        st.error(
            "The request could not be saved to Google Drive. Please try again later "
            "or contact the RFR team."
        )
        st.caption(f"Drive upload error: {exc}")
        return

    st.success("Request submitted. The RFR team can now review it in the Google Drive intake folder.")
    st.markdown(f"**Request ID:** `{request_id}`")
    if drive_record.get("drive_folder_url"):
        st.markdown(f"**Drive folder:** [Open request folder]({drive_record['drive_folder_url']})")
    saved_files = drive_record.get("saved_files") or []
    if saved_files:
        st.markdown("**Files saved:**")
        for filename in saved_files:
            st.markdown(f"- `{filename}`")


def _query_param_is_true(key: str) -> bool:
    if hasattr(st, "query_params"):
        value = st.query_params.get(key)
        if isinstance(value, list):
            value = value[0] if value else ""
        return str(value).lower() in {"1", "true", "yes"}

    values = st.experimental_get_query_params()
    value = values.get(key, [""])
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).lower() in {"1", "true", "yes"}


def _set_query_param(key: str, value: str) -> None:
    if hasattr(st, "query_params"):
        st.query_params[key] = value
        return

    params = st.experimental_get_query_params()
    params[key] = value
    st.experimental_set_query_params(**params)


def _get_query_param(key: str) -> str:
    if hasattr(st, "query_params"):
        value = st.query_params.get(key, "")
        if isinstance(value, list):
            value = value[0] if value else ""
        return str(value)

    values = st.experimental_get_query_params()
    value = values.get(key, [""])
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value)


def _get_or_create_conversation_id() -> str:
    existing = _get_query_param("conversation_id")
    if re.fullmatch(r"[0-9a-f]{32}", existing or ""):
        return existing

    conversation_id = uuid.uuid4().hex
    _set_query_param("conversation_id", conversation_id)
    return conversation_id


def _history_path(conversation_id: str) -> Path:
    history_dir = _history_dir()
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / f"{conversation_id}.json"


def _load_history(conversation_id: str) -> list[dict]:
    path = _history_path(conversation_id)
    if not path.exists():
        return []
    try:
        history = json.loads(path.read_text())
    except Exception:
        return []
    return history if isinstance(history, list) else []


def _save_history(conversation_id: str, history: list[dict]) -> None:
    path = _history_path(conversation_id)
    serializable_history = history[:MAX_HISTORY_ITEMS]
    path.write_text(json.dumps(serializable_history, indent=2))


def _followup_context(history: list[dict], limit: int = 3) -> str:
    if not history:
        return ""

    pieces = []
    for entry in history[:limit]:
        answer = re.sub(r"\s+", " ", entry.get("answer", "")).strip()
        if len(answer) > 900:
            answer = answer[:900].rsplit(" ", 1)[0] + " ..."
        pieces.append(
            f"Previous question: {entry.get('query', '')}\n"
            f"Previous answer summary: {answer}"
        )
    return "\n\n".join(pieces)


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI-Assisted Knowledge Platform for Managed Retreat", layout="wide")

# ── Build embedding index after Streamlit page setup ─────────────────────────
_ensure_embedding_index_built()

st.markdown(
    """
    <style>
    div[data-testid="InputInstructions"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────
conversation_id = _get_or_create_conversation_id()
if "history" not in st.session_state:
    st.session_state.history = _load_history(conversation_id)
if "disclaimer_accepted" not in st.session_state:
    st.session_state.disclaimer_accepted = _query_param_is_true("disclaimer_accepted")
elif not st.session_state.disclaimer_accepted and _query_param_is_true("disclaimer_accepted"):
    st.session_state.disclaimer_accepted = True

# ── Disclaimer modal ──────────────────────────────────────────────────────────
if not st.session_state.disclaimer_accepted:
    st.markdown("""
    <style>
    .disclaimer-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        max-width: 720px;
        margin: 4rem auto 0 auto;
    }
    .disclaimer-wrap h1 {
        font-size: 2rem;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .disclaimer-box {
        background: #fffff0;
        border: 1px solid #e6c84a;
        border-radius: 6px;
        padding: 1.5rem 2rem 1.5rem 2rem;
        text-align: left;
        color: #5a4a00;
        font-size: 0.95rem;
        line-height: 1.6;
        width: 100%;
    }
    </style>
    <div class="disclaimer-wrap">
        <h1>AI-Assisted Knowledge Platform for Managed Retreat</h1>
        <div class="disclaimer-box">
            <p><strong>Important Notice — Research Tool Disclaimer</strong></p>
            <p>This tool is intended to support informed decision-making by providing access to
            synthesised insights from peer-reviewed managed retreat case study literature.
            It is designed as a decision-support resource only.</p>
            <p><strong>This tool does not constitute professional planning, legal, engineering, or policy advice.</strong>
            Responses are generated by an AI system and may contain errors, omissions, or
            information that does not apply to your specific context. All outputs should be
            critically evaluated and verified against primary sources before use in any
            planning or policy process.</p>
            <p><strong>The responsibility for any decision remains entirely with the user and their organisation.</strong>
            The researchers and institutions associated with the Retreat From Risk (RFR) project
            accept no liability for decisions made on the basis of information provided by this tool.</p>
            <p><strong>Privacy and saved responses:</strong> To preserve your Previous Responses within
            this browser conversation, the tool may store your questions, selected context, generated
            answers, and retrieved source references in the app's private storage. Do not enter
            sensitive personal, legal, medical, financial, or confidential community information.</p>
            <p>By continuing, you acknowledge that you have read and understood this notice.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    _, continue_col, _ = st.columns([1, 1, 1])
    with continue_col:
        if st.button("I understand — continue to the tool", type="primary", use_container_width=True):
            st.session_state.disclaimer_accepted = True
            _set_query_param("disclaimer_accepted", "true")
            st.rerun()
    st.stop()

current_page = _current_page()
_render_navigation(current_page, conversation_id)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<span id="about"></span>', unsafe_allow_html=True)
    st.header("About You & Your Community")
    st.caption("Optional context for tailoring answers. Skip any question that does not apply.")

    questions = load_questions()
    answers = {}
    for q in questions:
        answer = st.selectbox(q["text"], options=["(skip)"] + q["options"], key=q["id"])
        if answer != "(skip)":
            answers[q["id"]] = answer

    st.divider()
    answered = len(answers)
    total = len(questions)
    if answered == 0:
        st.caption("No context provided — answers will be general.")
    elif answered < total:
        st.caption(f"{answered} of {total} questions answered.")
    else:
        st.caption("✓ Full context provided.")

    model_choice = "claude"

if current_page == "how_to_use":
    _render_how_to_use_page()
    st.stop()

if current_page == "new_case_requests":
    _render_new_case_requests_page()
    st.stop()

if current_page == "case_studies":
    _render_case_studies_page()
    st.stop()

if current_page == "previous_responses":
    _render_previous_responses_page(conversation_id, questions)
    st.stop()

if current_page == "about":
    _render_about_page()
    st.stop()

# ── Two-column layout ─────────────────────────────────────────────────────────
main_col, history_col = st.columns([2, 1], gap="large")

# ── Main panel ────────────────────────────────────────────────────────────────
with main_col:
    st.title("AI-Assisted Knowledge Platform for Managed Retreat")
    st.caption("Powered by RFR research — answers grounded in real managed retreat case studies from around the world.")

    st.markdown('<span id="ask"></span>', unsafe_allow_html=True)
    st.subheader("Ask a question")
    st.markdown(
        "Examples: *What funding models have worked for coastal buyout programs?* · "
        "*How did communities maintain social cohesion after relocation?* · "
        "*What are the biggest barriers to managed retreat in Indigenous communities?*"
    )
    st.caption(
        "⚠️ This tool is a research aid only. Responses are AI-generated from case study literature "
        "and may contain errors or omissions. They do not constitute professional advice. "
        "All decisions remain the sole responsibility of the user."
    )
    has_history = bool(st.session_state.history)
    use_followup_context = False
    if has_history:
        use_followup_context = st.checkbox(
            "Use previous responses as context for this question",
            value=True,
            help="Adds the last few questions and answers to the prompt so you can ask natural follow-ups.",
        )

    query_label = "Your follow-up question:" if use_followup_context else "Your question:"
    st.caption("Ask about a case, location, funding model, policy issue, or community concern.")
    query = st.text_area(query_label, height=100, placeholder="Type your question about managed retreat here... Avoid entering sensitive or confidential information")

    if st.button("Get answer", type="primary"):
        if not query.strip():
            st.warning("Please enter a question.")
        elif metadata_answer := _metadata_answer_markdown(query):
            chunks = []
            st.session_state.history.insert(0, {
                "query":   query,
                "answer":  metadata_answer,
                "chunks":  chunks,
                "context": dict(answers),
            })
            st.session_state.history = st.session_state.history[:MAX_HISTORY_ITEMS]
            _save_history(conversation_id, st.session_state.history)

            st.markdown(metadata_answer)
        elif re.search(r"\b(what|which|list|show|how many).{0,30}case stud", query, re.I):
            # Meta question — list all case studies directly from extracted JSONs
            cs_meta = load_case_meta()
            extracted_dir = Path("data/extracted")
            all_cases = []
            for f in sorted(extracted_dir.glob("CS*.json"), key=lambda p: int(re.search(r'\d+', p.stem).group())):
                cid = f.stem
                if cid in cs_meta:
                    m = cs_meta[cid]
                    all_cases.append(f"**{cid}** — {m.get('name', cid)}, {m.get('location', '')}, {m.get('country', '')}")
                else:
                    data = json.loads(f.read_text())
                    if data:
                        loc = data[0].get("location", "")
                        country = data[0].get("country", "")
                        all_cases.append(f"**{cid}** — {loc}, {country}" if loc else f"**{cid}**")
            st.markdown("### Case Studies in the Knowledge Base")
            for line in all_cases:
                st.markdown(line)
            st.caption(f"Total: {len(all_cases)} case studies indexed.")
            chunks = []
        else:
            status = st.empty()
            try:
                status.info("Searching case studies...")
                chunks = retrieve_chunks(query)
                status.info(f"Found {len(chunks)} relevant case-study excerpts. Generating response...")

                prompt_context = dict(answers)
                if use_followup_context:
                    prompt_context["Recent conversation context"] = _followup_context(st.session_state.history)

                answer = generate_answer(
                    query,
                    chunks,
                    questionnaire_answers=prompt_context if prompt_context else None,
                    model=model_choice,
                )
                status.success("Response generated.")
            except RAGProviderError as exc:
                status.empty()
                st.error(str(exc))
                st.stop()

            # Save to history
            st.session_state.history.insert(0, {
                "query":   query,
                "answer":  answer,
                "chunks":  chunks,
                "context": dict(answers),
            })
            st.session_state.history = st.session_state.history[:MAX_HISTORY_ITEMS]
            _save_history(conversation_id, st.session_state.history)

            # Log to Google Sheets
            _log_err = log_query(query, answer, chunks, questionnaire_answers=answers, model=model_choice)
            if _log_err:
                st.caption(f"⚠️ Logging error (temporary debug): {_log_err}")

            st.markdown("### Response")
            st.caption(
                "⚠️ The following response is AI-generated from managed retreat research literature. "
                "It is intended to support — not replace — professional judgement. Verify findings "
                "against primary sources before use in any planning or policy process."
            )
            st.markdown(answer.replace("$", r"\$"))

            # ── Context used ──────────────────────────────────────────────
            if answers:
                with st.expander("Context used"):
                    for qid, val in answers.items():
                        q_text = next((q["text"] for q in questions if q["id"] == qid), qid)
                        st.markdown(f"**{q_text}** {val}")

            # ── Case studies used ─────────────────────────────────────────
            cs_meta = load_case_meta()

            seen_ids: set[str] = set()
            retrieved_cs = []
            for c in chunks:
                cid = c["metadata"].get("case_id", "")
                if cid in cs_meta and cid not in seen_ids:
                    seen_ids.add(cid)
                    retrieved_cs.append(c)

            mentioned_ids = {
                f"CS{n}" for n in re.findall(r'\bCS(\d+)\b', answer)
            }

            if retrieved_cs:
                st.markdown("---")
                st.markdown('<span id="case-studies"></span>', unsafe_allow_html=True)
                st.markdown("### Case Studies Used in This Answer")
                st.caption(
                    "These are the case studies whose extracted content was retrieved "
                    "and sent to the model to generate the response above."
                )
                for chunk in retrieved_cs:
                    cid     = chunk["metadata"]["case_id"]
                    meta    = cs_meta[cid]
                    name    = meta.get("name", "") or meta.get("location", cid)
                    country = meta.get("country", "")
                    section = _section_label(chunk["metadata"].get("section", ""))
                    cited   = "✅ cited in response" if cid in mentioned_ids else "📄 used as context"

                    with st.expander(f"{cid} — {name}, {country}  {cited}"):
                        st.markdown(f"**Section retrieved:** {section}")
                        st.markdown(f"**Source:** {chunk['metadata'].get('source', '')}")
                        _render_source_links(chunk["metadata"].get("source_links"))
                        excerpt = _clean_excerpt(chunk["text"])
                        if len(excerpt) > 40:
                            st.markdown("**Excerpt:**")
                            st.text(excerpt)
                        else:
                            st.caption("This section contains structural metadata only — no content preview available.")

# ── History panel (right column) ──────────────────────────────────────────────
with history_col:
    st.markdown('<span id="previous-responses"></span>', unsafe_allow_html=True)
    st.subheader("Previous Responses")
    st.caption(
        "Saved for this browser conversation. Avoid entering sensitive or confidential information."
    )

    if not st.session_state.history:
        st.caption("Your previous answers will appear here.")
    else:
        if st.button("Clear history", type="secondary"):
            st.session_state.history = []
            _save_history(conversation_id, st.session_state.history)
            st.rerun()

        for i, entry in enumerate(st.session_state.history):
            label = entry["query"][:60] + "..." if len(entry["query"]) > 60 else entry["query"]
            with st.expander(f"Q{len(st.session_state.history) - i}: {label}"):
                st.markdown(f"**Question:** {entry['query']}")
                st.divider()
                st.markdown(entry["answer"])

                if entry["context"]:
                    st.divider()
                    st.caption("Context used:")
                    for qid, val in entry["context"].items():
                        q_text = next((q["text"] for q in questions if q["id"] == qid), qid)
                        st.caption(f"• {q_text}: {val}")
