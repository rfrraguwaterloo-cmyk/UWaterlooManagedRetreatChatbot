# Session handoff note: CS11 Version 1 (Terrebonne Parish, Louisiana)

> **What is this file?** A one-time "continue this work" note written for a
> specific case study (CS11 - Terrebonne Parish). It's kept here as a record
> of how that case study's Version 1 document was produced. It is not part of
> the reusable pipeline -- the scripts in `case_study_pipeline/` (e.g.
> `run_case_study.py`, `run_check1.py`, `run_check2.py`) work for any case
> study ID, not just CS11.

Paste this into a new chat in the "Managed Retreat LLM Chat for Underserved Communities
in Risk of Flooding" project to continue this work.

---

Continue the RFR managed retreat case study pipeline work in /Users/AnnaZhou/rfr-rag.

Background: case_study_pipeline/ already has a working script (run_case_study.py) that
normally calls the Anthropic + OpenAI APIs to generate a case-study questionnaire (Ver1),
have ChatGPT audit it (Check1), revise to Ver2, then re-audit (Check2). In this Cowork
sandbox, api.anthropic.com and api.openai.com are NOT reachable, so for the Claude steps
I'll generate the content directly myself (no API call) instead.

NEW CASE STUDY: CS11 - Terrebonne Parish, Louisiana, US
A Drive folder "RFR - CS11 - Terrebonne Parish, Louisiana, US" already exists at:
https://drive.google.com/drive/folders/15fUllNmyoJBuwlJAEQI8fSgfICrWxoGC
It contains 6 source PDFs (use the connected Google Drive tools' read_file_content on
each fileId to get extracted text - works even for large files):

- 12mMQA4egXVxnGwJDacye0XfED5ebVY8V - "LA SAFE Terrebonne - Final CRS Report.pdf" (314KB)
- 1VSyV1TgM9ywzCBJuZgC6TSbMDRjNyAhU - "LA SAFE Terrebonne - Adaptation Strategy, 2019.pdf" (46.7MB)
- 12JiPXuv-ADGTDWrlt8IDGcg7Fvuqkyrn - "LA SAFE Terrebonne - Summary.pdf" (2.02MB)
- 1IXcYEGsKReM-8oHChoMc6mNERaZFPfMR - "Getting By and Getting Out: How Residents of
  Louisiana's Frontline Communities Are Adapting to Environmental Change.pdf" (1.63MB)
- 1C69nIQ2aOyWTOcQazFztyTPigLxSZ-9Q - "Managing retreat? An empirical reflection on
  adopting relocation initiatives as adaptation policy in Louisiana.pdf" (1.23MB)
- 1V9tfa4oROiHfJeCnso229UewBGn8EfJX - "burley-et-al-2004-losing-ground-in-southern-
  louisiana.pdf" (725KB)

TASK (steps 1-3 of the pipeline, done manually):
1. For each of the 6 files above, call read_file_content(fileId) and save the extracted
   text as a .txt file in data/raw/CS11/ (create the folder). These count as valid
   source documents for case_study_pipeline (it accepts .pdf/.txt/.md).
2. Read case_study_pipeline/prompts.py (PROMPT_A_TEMPLATE / build_prompt_a) and the
   context docs in case_study_pipeline/context/ (ai_questionnaire.md, codebook.md,
   cross_cutting_guide.md, note_taking_guidelines.md).
3. Acting AS the LLM that Prompt A would be sent to, write the Version 1 narrative
   case-study questionnaire document for CS11 (case_id="CS11"), following Prompt A's
   structure exactly (repeat each question as a heading, give direct answer + narrative,
   end with "Additional Notes and Lessons Learned" and "Fields with Limited or No
   Evidence" sections), grounded only in the 6 source documents.
4. Save the result as data/raw/CS11/pipeline_output/CS11_Ver1.md, and render it to PDF
   using case_study_pipeline.pdf_utils.text_to_pdf (title:
   "CS11 - Case Study Questionnaire (Version 1)").
5. Report back a summary (sections covered, anything in "Fields with Limited or No
   Evidence").

After this: I'll run Check 1 manually in ChatGPT (Prompt B from prompts.py) using
CS11_Ver1.md, then bring the report back so Version 2 can be generated the same way.

For Check 1 / Check 2, the standalone scripts now handle this for any case ID:

    python -m case_study_pipeline.run_check1 --case-id CS11
    python -m case_study_pipeline.run_check2 --case-id CS11
