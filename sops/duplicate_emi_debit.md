# SOP: Duplicate EMI debit

**SOP id:** duplicate_emi_debit
**Use when:** the customer says their EMI (monthly loan instalment) was debited, deducted or charged twice, taken two times, or they were double charged.

## Steps
1. Verify identity with loan ID and date of birth (`verify_customer`). Do not share any loan data before this succeeds.
2. Get the payment history (`get_payments`).
3. Check for a duplicate: two or more EMI debits of the same amount on the same date.
4. If a duplicate is confirmed:
   - Raise a refund ticket (`raise_refund_ticket`) for the extra transaction only (keep the first one as the real EMI).
   - Tell the customer the ticket id, the refunded amount, and that the refund takes **5-7 working days**.
5. If no duplicate is found:
   - Do not raise a ticket.
   - Explain what was found (for example: one EMI debit on that date) and ask the customer to share the transaction details or bank statement if they still see two debits.

## Escalate to a human instead if
- The customer says they did not authorise a debit at all (possible fraud).
