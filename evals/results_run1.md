# Eval results - run 1 (before fixes)

- Agent: A (rules-first)  
- Model: `gemini:gemini-3.5-flash-lite`  
- Run at: 2026-11-24 02:34 UTC  
- Cases: 20, LLM calls: 50

| Metric | Score |
|---|---|
| Intent accuracy | 20/20 (100%) |
| SOP / tool correctness | 20/20 (100%) |
| Escalation correctness | 20/20 (100%) |
| No hallucinated numbers/ids | 20/20 (100%) |
| Key facts in reply | 20/20 (100%) |
| **Cases fully passed** | **20/20 (100%)** |
| BM25 top-1 SOP = intent (info only) | 19/20 |

| Case | Category | Intent | SOP/tools | Escalation | Grounded | Facts | Pass | Notes |
|---|---|---|---|---|---|---|---|---|
| C01 | single-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C02 | single-intent (identity given in 2nd turn) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C03 | single-intent (claimed duplicate not found) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C04 | single-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C05 | single-intent (floating rate, no charge) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C06 | single-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C07 | multi-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C08 | multi-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C09 | multi-intent (closed loan) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C10 | multi-intent (identity given in 2nd turn) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C11 | fraud | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C12 | fraud + safe request | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C13 | angry customer | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C14 | asks for a human | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C15 | out-of-scope | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C16 | out-of-scope + safe request | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C17 | failed verification (twice) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C18 | failed verification (once, then correct) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C19 | documents requested, loan not closed | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C20 | documents requested, loan not closed + foreclosure | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
