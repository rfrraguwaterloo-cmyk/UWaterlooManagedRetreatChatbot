"""
Prompt templates for the managed-retreat case study pipeline.

Source: "Case Study Processing with PDFs" (RFR project doc), prompts (A) and (B).

Pipeline:
  1. PROMPT_A  -> Claude generates the Ver 1 narrative case-study questionnaire PDF
                  from the questionnaire, codebook, and source documents.
  2. PROMPT_B  -> ChatGPT audits Ver 1 ("Check 1"), producing a scored report.
  3. PROMPT_REVISION -> Claude revises Ver 1 into Ver 2 using the Check 1 report.
  4. PROMPT_B (fresh call, no prior conversation/messages = "no memory")
              -> ChatGPT audits Ver 2 ("Check 2"), producing a scored report
                 to measure improvement over Check 1.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# (A) Prompt for Making the Questionnaire PDF — used with Claude (Ver 1)
# ---------------------------------------------------------------------------

PROMPT_A_TEMPLATE = """You are assisting with a systematic review of managed retreat (MR) case studies.

I will provide:
1. A questionnaire containing the coding questions.
2. A codebook defining categories and coding rules.
3. RFR cross-cutting themes guidance and note-taking guidelines.
4. A set of academic papers, reports, government documents, and other sources \
associated with a single managed retreat case study (Case ID: {case_id}).

Task: Synthesize information across the provided sources only.
Output: Produce a single narrative case-study questionnaire document.

Important principles:
- Treat the questionnaire as the primary coding framework.
- Use the codebook definitions whenever assigning categories.
- Extract information from all sources jointly rather than coding papers individually.
- Do not force answers. If evidence is insufficient, explicitly state "N/A" or \
"No evidence found in reviewed sources."
- Distinguish between:
  - evidence directly related to the managed retreat decision process; and
  - evidence related to broader recovery, adaptation, redevelopment, or hazard \
mitigation activities.
- Avoid overstating conclusions.
- When multiple papers provide complementary information, integrate them into a \
single answer.
- When papers disagree, explain the disagreement.
- Preserve important nuances and uncertainties.
- When discussing evidence, prioritize information directly describing what \
happened in the case over literature-review statements about managed retreat in \
general.

Structure the output document as follows:
1. Begin with the **Case Study Overview** section (as defined in the questionnaire). \
Write this as a plain-language briefing note — not in question-and-answer format — \
covering: case name and location, hazard(s), type of retreat, scale, key actors, \
timeline, key outcomes, and a 2–3 paragraph narrative summary suitable for a \
non-technical reader such as a municipal planner or community leader.
2. Then answer each coding question in the order it appears in the questionnaire.

For every coding question:
1. Repeat the full question as a heading.
2. Provide a direct answer first.
3. Follow with a narrative explanation synthesizing evidence from all sources.
4. Explain why specific coding categories were selected.
5. Note alternative interpretations when appropriate.
6. Clearly identify any uncertainty or missing information.

For categorical questions:
- Explicitly state which category or categories apply.
- Explain why categories were selected.
- Explain why other categories were not selected when relevant.

For example:
Question: "What was the geographic scale of the MR project?"
Answer: "Neighbourhood and Individual Homes."
Narrative: "The acquisition program operated at the parcel scale through voluntary \
buyouts of individual properties. However, the acquisitions were concentrated \
within several flood-affected neighbourhoods and were incorporated into \
neighbourhood-scale redevelopment planning. Therefore, both 'Individual Homes' and \
'Neighbourhood' are supported."

At the end of the document, create a section titled:
"Additional Notes and Lessons Learned"
This section should include important findings that do not fit neatly into any \
questionnaire category, such as: institutional innovations, governance lessons, \
planning insights, funding observations, equity implications, unexpected outcomes, \
methodological observations, contradictions or tensions within the case, and \
broader lessons for managed retreat practice.

Also create a final section titled:
"Fields with Limited or No Evidence"
List questionnaire topics for which the reviewed sources provide little or no \
information.

The final product should be read as a high-quality case-study memo suitable for use \
in a systematic review database or qualitative comparative analysis of managed \
retreat cases.

=== QUESTIONNAIRE (coding questions) ===
{ai_questionnaire}

=== CODEBOOK ===
{codebook}

=== CROSS-CUTTING THEMES GUIDE ===
{cross_cutting_guide}

=== NOTE-TAKING GUIDELINES ===
{note_taking_guidelines}

=== SOURCE DOCUMENTS (Case ID: {case_id}) ===
{source_documents}
"""


# ---------------------------------------------------------------------------
# (B) Document evaluation prompt — used with ChatGPT (Check 1 and Check 2)
# ---------------------------------------------------------------------------

PROMPT_B_TEMPLATE = """You are an independent auditor for the Retreating From Risk \
(RFR) managed retreat case study project.

I will provide:
1. A case study document produced by another LLM (Case ID: {case_id}, {version_label}).
2. The original source documents.
3. The RFR codebook and/or note-taking guidelines.

Your task is to check whether the case study document is accurate, source-grounded, \
properly cited, and correctly coded.

Do not assume the document is correct. Verify its claims against the sources.

Do not penalize the document for not being exhaustive. The goal is not to check \
whether every possible detail was included. Only flag missing information if its \
absence makes an included claim misleading, incorrect, or miscoded.

Check for:
1. Unsupported or hallucinated factual claims.
2. Claims that misrepresent or exaggerate the sources.
3. Citations that do not support the sentence they are attached to.
4. Missing citations for factual claims.
5. Incorrect or weak RFR code/category assignments.
6. Confusion between managed retreat and broader recovery, adaptation, \
redevelopment, hazard mitigation, or disaster response.
7. Overstated conclusions where the evidence is limited or indirect.
8. Internal contradictions in numbers, dates, actors, funding, voluntariness, \
scale, hazards, compensation, engagement, or outcomes.
9. Formatting or citation-style problems based on RFR guidelines.

For each issue, provide: the exact claim, citation, or code from the document; why \
it is inaccurate, unsupported, overstated, or miscoded; what the source documents \
actually support; the corrected wording or coding; and a severity rating (High, \
Medium, or Low).

Use this output structure:
1. Overall assessment
2. Major issues requiring correction
3. Minor issues and wording improvements
4. Coding corrections table
5. Citation corrections table
6. Final recommended grade from 0-100

Use this grading guide:
90-100: Very strong. Minor corrections only. Claims are well-supported and coding \
is reliable.
80-89: Good. Mostly reliable, but several corrections needed.
70-79: Usable with moderate revision. Some unsupported claims, citation issues, or \
coding problems.
60-69: Weak. Significant source-grounding problems. Needs substantial revision.
Below 60: Not reliable. Many claims or codes are unsupported, incorrect, or poorly \
cited.

The grade should be based on factual accuracy, citation accuracy, codebook \
alignment, uncertainty handling, internal consistency, and overall reliability. Do \
not lower the grade simply because the document is not exhaustive.

End your response with a line in the exact format:
FINAL GRADE: <number>/100

=== CASE STUDY DOCUMENT TO AUDIT ({version_label}) ===
{case_study_document}

=== RFR CODEBOOK ===
{codebook}

=== NOTE-TAKING GUIDELINES ===
{note_taking_guidelines}

=== ORIGINAL SOURCE DOCUMENTS (Case ID: {case_id}) ===
{source_documents}
"""


# ---------------------------------------------------------------------------
# Revision prompt — used with Claude to produce Ver 2 from the Check 1 report
#
# Design intent: structurally identical to PROMPT_A (fresh generation from
# sources) so Claude re-reads the documents rather than patching Ver 1.
# Check 1 is provided as a mandatory pre-flight checklist, not as a base
# to edit from. Ver 1 is included only as a reference for what to avoid.
# ---------------------------------------------------------------------------

PROMPT_REVISION_TEMPLATE = """You are assisting with a systematic review of managed retreat (MR) case studies.

I will provide:
1. A questionnaire containing the coding questions.
2. A codebook defining categories and coding rules.
3. RFR cross-cutting themes guidance and note-taking guidelines.
4. A set of academic papers, reports, government documents, and other sources \
associated with a single managed retreat case study (Case ID: {case_id}).
5. A previous attempt at this document (Version 1) and an independent audit \
report (Check 1) identifying its errors.

Task: Produce Version 2 — a complete, freshly written case-study questionnaire \
document generated directly from the source documents. Do not edit or patch \
Version 1. Instead, treat the source documents as your only input for facts and \
coding, and treat the Check 1 audit as a pre-flight checklist of known errors \
to avoid.

Before you begin writing, work through the Check 1 audit report and for each \
flagged issue confirm in the source documents what the correct fact, code, or \
wording is. Only then start generating Version 2 from scratch.

Important principles:
- Treat the questionnaire as the primary coding framework.
- Use the codebook definitions whenever assigning categories.
- Extract information from all sources jointly rather than coding papers individually.
- Do not force answers. If evidence is insufficient, explicitly state "N/A" or \
"No evidence found in reviewed sources."
- Distinguish between:
  - evidence directly related to the managed retreat decision process; and
  - evidence related to broader recovery, adaptation, redevelopment, or hazard \
mitigation activities.
- Avoid overstating conclusions.
- When multiple papers provide complementary information, integrate them into a \
single answer.
- When papers disagree, explain the disagreement.
- Preserve important nuances and uncertainties.
- When discussing evidence, prioritize information directly describing what \
happened in the case over literature-review statements about managed retreat in \
general.
- Every factual claim must be traceable to a specific source. Do not include any \
claim that cannot be directly supported by the source documents provided. If you \
cannot find support for a claim from Version 1, omit it or flag it as \
unverifiable.

Mandatory checks before writing (apply every item from the Check 1 audit):
1. Resolve every "Major issue requiring correction" — these are non-negotiable.
2. Apply every "Coding correction" using the codebook definitions.
3. Apply every "Citation correction."
4. Apply "Minor issues and wording improvements" wherever they increase accuracy \
or clarity.
5. Where Version 1 overstated conclusions or treated indirect evidence as direct \
evidence, rewrite those passages with appropriate hedging.
6. Do not introduce any new claim that is not directly supported by the source \
documents below.

Discretion:
- You may push back on a specific auditor finding only if you can cite the exact \
passage in the source documents that supports your original wording. Note any \
such disagreement briefly in the "Additional Notes and Lessons Learned" section.

Structure the output document as follows:
1. Begin with the **Case Study Overview** section (as defined in the questionnaire). \
Write this as a plain-language briefing note — not in question-and-answer format — \
covering: case name and location, hazard(s), type of retreat, scale, key actors, \
timeline, key outcomes, and a 2–3 paragraph narrative summary suitable for a \
non-technical reader such as a municipal planner or community leader.
2. Then answer each coding question in the order it appears in the questionnaire.

For every coding question:
1. Repeat the full question as a heading.
2. Provide a direct answer first.
3. Follow with a narrative explanation synthesizing evidence from all sources.
4. Explain why specific coding categories were selected.
5. Note alternative interpretations when appropriate.
6. Clearly identify any uncertainty or missing information.

For categorical questions:
- Explicitly state which category or categories apply.
- Explain why categories were selected.
- Explain why other categories were not selected when relevant.

At the end of the document, create a section titled:
"Additional Notes and Lessons Learned"
This section should include important findings that do not fit neatly into any \
questionnaire category, such as: institutional innovations, governance lessons, \
planning insights, funding observations, equity implications, unexpected outcomes, \
methodological observations, contradictions or tensions within the case, and \
broader lessons for managed retreat practice.

Also create a final section titled:
"Fields with Limited or No Evidence"
List questionnaire topics for which the reviewed sources provide little or no \
information.

The final product should be read as a high-quality case-study memo suitable for \
use in a systematic review database or qualitative comparative analysis of managed \
retreat cases.

=== CHECK 1 AUDIT REPORT (errors to resolve before writing) ===
{check_1_report}

=== VERSION 1 (reference only — do not edit this; generate Version 2 fresh from sources) ===
{version_1_document}

=== QUESTIONNAIRE (coding questions) ===
{ai_questionnaire}

=== CODEBOOK ===
{codebook}

=== CROSS-CUTTING THEMES GUIDE ===
{cross_cutting_guide}

=== NOTE-TAKING GUIDELINES ===
{note_taking_guidelines}

=== SOURCE DOCUMENTS (Case ID: {case_id}) ===
{source_documents}
"""


def build_prompt_a(
    case_id: str,
    ai_questionnaire: str,
    codebook: str,
    cross_cutting_guide: str,
    note_taking_guidelines: str,
    source_documents: str,
) -> str:
    return PROMPT_A_TEMPLATE.format(
        case_id=case_id,
        ai_questionnaire=ai_questionnaire,
        codebook=codebook,
        cross_cutting_guide=cross_cutting_guide,
        note_taking_guidelines=note_taking_guidelines,
        source_documents=source_documents,
    )


def build_prompt_b(
    case_id: str,
    version_label: str,
    case_study_document: str,
    codebook: str,
    note_taking_guidelines: str,
    source_documents: str,
) -> str:
    return PROMPT_B_TEMPLATE.format(
        case_id=case_id,
        version_label=version_label,
        case_study_document=case_study_document,
        codebook=codebook,
        note_taking_guidelines=note_taking_guidelines,
        source_documents=source_documents,
    )


def build_prompt_revision(
    case_id: str,
    version_1_document: str,
    check_1_report: str,
    ai_questionnaire: str,
    codebook: str,
    cross_cutting_guide: str,
    note_taking_guidelines: str,
    source_documents: str,
) -> str:
    return PROMPT_REVISION_TEMPLATE.format(
        case_id=case_id,
        version_1_document=version_1_document,
        check_1_report=check_1_report,
        ai_questionnaire=ai_questionnaire,
        codebook=codebook,
        cross_cutting_guide=cross_cutting_guide,
        note_taking_guidelines=note_taking_guidelines,
        source_documents=source_documents,
    )
