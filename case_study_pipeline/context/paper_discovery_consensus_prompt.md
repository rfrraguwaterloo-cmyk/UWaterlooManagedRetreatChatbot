# Paper-Discovery Prompt for New Case Studies (Consensus / academic search)

Purpose: a reusable template for finding the source papers for a **new** managed-retreat (MR)
case study before running the pipeline (Prompt A). Use it with the Consensus search tool
(or Google Scholar / Semantic Scholar). It is designed so the retrieved papers cover the
RFR codebook themes, not just MR in general.

How to use:
1. Fill in the CASE PROFILE placeholders.
2. Run the BASE QUERY first, then the THEME QUERIES to fill gaps.
3. Screen results with the INCLUSION / EXCLUSION rules.
4. Log every kept paper in the "Literature Search Log" sheet and drop the PDFs/text into
   `data/raw/CS<NN>/` so the pipeline can ingest them.

---

## CASE PROFILE (fill in)

- **Case ID:** CS<NN>
- **Place name (and alternate spellings):** <village / city / region>
- **Country / region:** <country>, <state/province/district>
- **Primary hazard(s):** <e.g., riverine flooding / coastal erosion / drought–water scarcity / tidal inundation>
- **MR action / stage:** <buyout / community resettlement / managed realignment | pre- / during / post->
- **Known actors or program name (if any):** <NGO, agency, program>

---

## BASE QUERY (run first)

> What does the research literature document about the managed retreat / planned relocation /
> community resettlement of **<place name>**, **<country>**, in response to **<primary hazard>** —
> including the drivers of relocation, who decided, how it was funded, community engagement,
> equity and cultural impacts, and outcomes?

Variants to also try (place names and framing vary a lot in this literature):
- "**<place name>** relocation OR resettlement OR buyout OR 'managed retreat' OR 'planned relocation'"
- "**<place name>** climate displacement OR climate refugees OR out-migration **<hazard>**"
- "**<region/district>** community relocation **<hazard>** adaptation"

---

## THEME QUERIES (run to fill gaps — mapped to the RFR codebook)

1. **Hazard & trigger:** "**<place>** **<hazard>** trend / drivers / why residents relocated"
2. **Institutional & funding:** "**<place>** relocation funding OR compensation OR land acquisition OR legal framework OR government program"
3. **Planning & decision support:** "**<place>** relocation site selection OR land suitability OR hazard mapping OR feasibility study"
4. **Community engagement & governance:** "**<place>** community participation OR consultation OR who decided OR voluntary vs forced relocation"
5. **Socio-cultural & equity:** "**<place>** Indigenous OR cultural heritage OR place attachment OR equity OR livelihoods relocation"
6. **Outcomes / lessons:** "**<place>** relocation outcomes OR success OR failure OR post-resettlement lessons"

(If a theme returns nothing, that is itself a useful finding — it likely becomes a
"Fields with Limited or No Evidence" entry in the Prompt A output.)

---

## INCLUSION / EXCLUSION RULES (screening)

Keep a source if it:
- Describes **this specific case** (the place, its hazard, or its relocation/adaptation), even if MR is not its main topic; AND
- Provides evidence on at least one codebook theme (hazard, institutional, planning, engagement, socio-cultural, outcomes).

Prefer: peer-reviewed studies and primary/grey-literature on the case (NGO reports, government
plans, feasibility/hydrology/land-suitability studies, local theses). A mix of disciplines is
good — the Prompt A step synthesizes across them.

Drop or down-rank: papers that only discuss MR/climate adaptation **in general** with no link to
the case; pure physical-science papers with no human/decision dimension (unless needed for the
hazard section); duplicates and predatory-journal items.

Do **not** target a fixed number of sources. Some cases will have very few — sometimes only one
or two — genuinely case-specific papers, and that is acceptable. Never pad the set with general
MR/climate literature or loosely-related papers just to reach a count: a small set of truly
relevant sources is better than a larger set diluted with false or generic ones. If little exists,
record that scarcity (it informs the "Fields with Limited or No Evidence" section).

---

## OUTPUT FORMAT FOR THE SEARCH (what to record per kept paper)

For each kept paper, record: citation (IEEE), DOI/URL, which codebook theme(s) it covers, and a
one-line note on what case-specific evidence it provides. Example:

> [2] P. Sherchan (2019), *Grassroots Journal of Natural Resources* 2(1-2):1-19,
> doi:10.33002/nr2581.6853.02121 — Themes: planning (MCDA site selection), socio-cultural,
> outcomes — land-suitability analysis comparing Dhye vs Thangchung; "first climate refugees" framing.

---

## NOTE ON USING CONSENSUS SPECIFICALLY

- Query Consensus with a plain research question (the BASE QUERY), not boolean strings — it is
  built for natural-language questions and returns ranked, cited papers.
- Do **not** apply year/study-type filters unless you specifically need them; MR case evidence is
  often older grey literature.
- Consensus is strongest for peer-reviewed work; pair it with a general web/Scholar search for
  NGO reports, government plans, and local theses, which are frequently the richest case sources.
