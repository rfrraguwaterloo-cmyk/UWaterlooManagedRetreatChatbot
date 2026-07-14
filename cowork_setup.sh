#!/usr/bin/env bash
# One-step setup for working with case_study_pipeline inside a Cowork sandbox session.
#
# WHY THIS EXISTS: the Cowork sandbox is ephemeral — installed packages do NOT
# persist between sessions, so they must be reinstalled once per session. This
# script makes that a single ~60-90s command instead of trial-and-error.
#
# It installs ONLY the minimal deps the pipeline imports (see requirements-cowork.txt),
# not the heavy RAG stack (torch/chromadb) in requirements.txt.
#
# Usage (inside Cowork, from the repo root):  bash cowork_setup.sh
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing minimal pipeline dependencies (~60-90s)..."
pip install -q --break-system-packages -r "$HERE/requirements-cowork.txt"

echo
echo "Done."
echo
echo "IMPORTANT — sandbox limitations (do not waste time re-diagnosing these):"
echo "  1. The sandbox egress proxy BLOCKS api.anthropic.com (returns proxy 401) and"
echo "     api.openai.com (unreachable). The live 4-step API run CANNOT complete in"
echo "     Cowork — run it on your Mac instead:"
echo "       python -m case_study_pipeline.run_case_study --case-folder data/raw/CSxx --case-id CSxx --max-tokens 32000 --force"
echo "  2. If you DO attempt any outbound HTTPS from Python here, the proxy uses a"
echo "     self-signed cert, so prefix commands with the system CA bundle:"
echo "       export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt"
echo "       export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt"
echo "  3. Offline tasks that DO work in Cowork: PDF rendering (pdf_utils.text_to_pdf),"
echo "     source-text extraction (pdfplumber), and manual Ver1/Ver2 drafting."
