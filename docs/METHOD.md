# Method

**Haircut taint.** Every address holds a mix of fund origins. A transfer carries the sender's current mix proportionally,
so 100 received from a mixer and 300 of unexplained origin give a 25% mixer share. The exposure score is
`100 x sum(share_category x weight_category)` over everything the address *received*.

**Untracked funds.** Whatever the data does not explain is "untracked" and has weight 0. Exposure is therefore a
lower bound on what a full-history analysis would show.

**Labeled addresses.** A labeled risky address is treated as the origin of its own outgoing funds. An address with a
reset category (exchange) emits untracked funds, because customer funds are pooled.

**Risk level.** High: score >= 50. Medium: score >= 10, any typology flag, or within 2 hops of a risky address.
Labeled addresses are classified by their category weight. Thresholds are configurable and illustrative.

**Peeling chain.** Consecutive transactions where the main output (>= 80% of the amount) goes to an address that then
sends the next peeling transaction. Default minimum: 4 transactions.

**Alternatives.** Poison (all-or-nothing) and FIFO taint models give different numbers; the haircut model was chosen
because it is order-independent within a transaction and easy to explain.
