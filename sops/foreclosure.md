# SOP: Foreclosure (early full closure) amount

**SOP id:** foreclosure
**Use when:** the customer wants to close the loan early, pay off the full loan, prepay everything, or asks for the foreclosure, payoff or closure amount.

## Policy
- Foreclosure amount = outstanding principal + foreclosure charge.
- **Floating-rate loans: no foreclosure charge (0%).** Home loans to individuals on a floating rate cannot carry a foreclosure charge.
- **Fixed-rate loans: 2% of the amount being prepaid** (for full foreclosure, that is the outstanding principal), as stated in the customer's sanction letter and loan agreement.
- The quoted amount is valid for today only. Interest for the days until payment may be added.

_Demo note: the 0% floating-rate rule mirrors RBI's (Pre-payment Charges on Loans) Directions, 2025. The 2% fixed-rate charge is this fake lender's own policy; RBI leaves fixed-rate charges to each lender's disclosed policy._

## Steps
1. Verify identity with loan ID and date of birth (`verify_customer`).
2. Get the foreclosure amount (`get_foreclosure_amount`).
3. Tell the customer: the outstanding principal, the foreclosure charge (and why: fixed or floating rate), and the total amount.
4. Next steps: the customer pays the total by bank transfer to their loan account, then receives a closure letter, and can then request property document release.
5. If the loan is not active (already closed), tell the customer there is nothing to foreclose.
