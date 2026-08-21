# ClaimGuard 🛡️
**Production-Level ESG Consistency Validator**

ClaimGuard is a deterministic, highly-auditable ESG validation engine. It takes sustainability narratives and ground-truth metrics data, extracts the claims, and applies a suite of **15 deterministic mathematical rules** to verify if the claims match the underlying data.

Unlike generic LLM wrappers, **ClaimGuard explicitly prohibits the AI from performing math**. The AI is strictly an extraction layer. All validation is performed by a transparent, auditable Python rules engine.

## 🚀 Features
- **15 Deterministic Rules**: Verifies absolute changes, percentage reductions, YoY direction, scope consistency, total/subtotal arithmetic, percentage bounds, cross-table consistency, and more.
- **Auditable Evidence Chain**: Every decision (PASS/FAIL/UNSUPPORTED) generates a complete evidence chain tracing back to the source data and exact mathematical formula.
- **Enterprise Dashboard**: A premium Streamlit interface to visualize findings, processing times, and export full audit reports.
- **Scalable Architecture**: Support for multi-company, multi-metric, and multi-year data.

## 🛠️ Installation & Setup

1. **Clone the repository and install dependencies:**
   ```bash
   git clone <repository_url>
   cd ClaimGuard
   pip install -r requirements.txt
   ```

2. **Set up Environment Variables:**
   Copy `.env.example` to `.env` and add your Groq API key:
   ```bash
   cp .env.example .env
   ```
   *Note: If no API key is provided, ClaimGuard falls back to a robust offline regex extraction engine.*

3. **Run the Dashboard:**
   ```bash
   streamlit run app.py
   ```

## 🧠 Architecture
- `src/schemas.py`: Rich Pydantic models for Claims, RuleResults, and AuditReports.
- `src/rules/`: The deterministic rules engine (`emissions.py`, `energy.py`, `water.py`, `general.py`).
- `src/extractor.py`: Multi-claim extraction using Groq (Llama 3.3) or regex fallback.
- `src/audit_trail.py`: Persistent storage of evidence chains.
- `app.py`: The enterprise Streamlit dashboard.

## 🧪 Running Tests
ClaimGuard includes a comprehensive test suite covering all 15 rules and pipeline integration.
```bash
python -m pytest tests/ -v
```

## 🐳 Docker Deployment
```bash
docker build -t claimguard .
docker run -p 8501:8501 --env-file .env claimguard
```
