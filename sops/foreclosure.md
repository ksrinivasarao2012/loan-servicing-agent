# SOP: Foreclosure (early full closure) amount

**SOP id:** foreclosure
**Use when:** the customer wants to close the loan early, pay off the full loan, prepay everything, or asks for the foreclosure, payoff or closure amount.

## Policy
- Foreclosure amount = outstanding principal + foreclosure charge.
- Foreclosure charge: **2% of outstanding principal for fixed-rate loans; 0% for floating-rate loans.**
- The quoted amount is valid for today only. Interest for the days until payment may be added.

## Steps
1. Verify identity with loan ID and date of birth (`verify_customer`).
2. Get the foreclosure amount (`get_foreclosure_amount`).
3. Tell the customer: the outstanding principal, the foreclosure charge (and why: fixed or floating rate), and the total amount.
4. Next steps: the customer pays the total by bank transfer to their loan account, then receives a closure letter, and can then request property document release.
5. If the loan is not active (already closed), tell the customer there is nothing to foreclose.
