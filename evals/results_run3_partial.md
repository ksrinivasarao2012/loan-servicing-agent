# Eval results - run 3 (re-run of C15-C20 only, after the network-retry fix)

- Agent: A (rules-first)  
- Model: `gemini:gemini-3.5-flash-lite`  
- Run at: 2026-11-24 08:14 UTC  
- Cases: 6, LLM calls: 14 (retries after rate limits included)

| Metric | Score |
|---|---|
| Intent accuracy | 6/6 (100%) |
| SOP / tool correctness | 6/6 (100%) |
| Escalation correctness | 6/6 (100%) |
| No hallucinated numbers/ids | 6/6 (100%) |
| Key facts in reply | 6/6 (100%) |
| No internal codes in reply | 6/6 (100%) |
| **Cases fully passed** | **6/6 (100%)** |
| BM25 top-1 SOP = intent (info only) | 4/5 |
| Cases hit by LLM/API errors (info) | 0 |

| Case | Category | Intent | SOP/tools | Escalation | Grounded | Facts | Clean | Pass | Notes |
|---|---|---|---|---|---|---|---|---|---|
| C15 | out-of-scope | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C16 | out-of-scope + safe request | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C17 | failed verification (twice) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C18 | failed verification (once, then correct) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C19 | documents requested, loan not closed | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C20 | documents requested, loan not closed + foreclosure | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
