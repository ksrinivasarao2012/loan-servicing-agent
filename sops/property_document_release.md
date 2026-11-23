# SOP: Property document release

**SOP id:** property_document_release
**Use when:** the customer asks for their original property documents, papers, title deed, sale deed, or wants documents returned after the loan.

## Policy
- Original property documents are released only after the loan is **fully closed** (outstanding principal is 0).
- Documents are released within 30 days of closure.

## Steps
1. Verify identity with loan ID and date of birth (`verify_customer`).
2. Check the document release status (`get_document_release_status`).
3. If the loan is closed and documents are ready:
   - Tell the customer the branch and the date from which documents can be collected.
   - Collection process: visit the branch in person with an original photo ID and the loan closure letter. If someone else collects, they need an authorisation letter signed by the customer.
4. If the loan is **not** closed:
   - Politely explain that documents can only be released after the loan is fully paid, and share the outstanding principal.
   - Offer to share the foreclosure amount if they want to pay it off now.
