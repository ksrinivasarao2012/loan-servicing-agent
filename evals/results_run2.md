# Eval results - run 2 (network errors from C15 on)

- Agent: A (rules-first)  
- Model: `gemini:gemini-3.5-flash-lite`  
- Run at: 2026-11-24 02:49 UTC  
- Cases: 20, LLM calls: 56 (retries after rate limits included)

| Metric | Score |
|---|---|
| Intent accuracy | 15/20 (75%) |
| SOP / tool correctness | 15/20 (75%) |
| Escalation correctness | 17/20 (85%) |
| No hallucinated numbers/ids | 20/20 (100%) |
| Key facts in reply | 16/20 (80%) |
| No internal codes in reply | 20/20 (100%) |
| **Cases fully passed** | **15/20 (75%)** |
| BM25 top-1 SOP = intent (info only) | 15/15 |

| Case | Category | Intent | SOP/tools | Escalation | Grounded | Facts | Clean | Pass | Notes |
|---|---|---|---|---|---|---|---|---|---|
| C01 | single-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C02 | single-intent (identity given in 2nd turn) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C03 | single-intent (claimed duplicate not found) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C04 | single-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C05 | single-intent (floating rate, no charge) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C06 | single-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C07 | multi-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C08 | multi-intent | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C09 | multi-intent (closed loan) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C10 | multi-intent (identity given in 2nd turn) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C11 | fraud | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C12 | fraud + safe request | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C13 | angry customer | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C14 | asks for a human | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C15 | out-of-scope | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| C16 | out-of-scope + safe request | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | intents got ['out_of_scope']; sops got []; missing tools ['get_foreclosure_amount']; reply missing ['1224000'] |
| C17 | failed verification (twice) | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | intents got ['out_of_scope']; missing tools ['create_handoff'] |
| C18 | failed verification (once, then correct) | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | intents got ['out_of_scope']; sops got []; missing tools ['get_document_release_status']; forbidden tools ['create_handoff']; handoff not expected; reply missing ['Madhapur'] |
| C19 | documents requested, loan not closed | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | intents got ['out_of_scope']; sops got []; missing tools ['get_document_release_status']; forbidden tools ['create_handoff']; handoff not expected; reply missing ['800000'] |
| C20 | documents requested, loan not closed + foreclosure | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | intents got ['out_of_scope']; sops got []; missing tools ['get_document_release_status', 'get_foreclosure_amount']; forbidden tools ['create_handoff']; handoff not expected; reply missing ['800000'] |
