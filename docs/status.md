# Progress

## Foundation — in progress

The new private project is being established from e8s. Current requirements and recovered
measurements are recorded. Enclosure options, electronics trade-offs and firmware control are
being developed in parallel. No fresh integrated controller has passed hardware validation.

## Inherited references

PD12V6 and PD12V6Mini remain under `hw/` with their original design notes. PD12V6Mini is a
USB-C PD-to-12.6 V supply, not a complete charger or smart-blind controller. Its prior validation
claims apply only to the recorded reference design and must be checked before reuse.

## Next gates

1. Compare complete packaging alternatives and electrical/radio architectures.
2. Select a provisional architecture with explicit dimensions, interfaces and power/cost budgets.
3. Implement original CAD, integrated circuit design and coordinated control software.
4. Complete source-level checks and document unresolved physical measurements.
5. Build/test two prototypes with the owner's hardware before the eight-unit batch.

[Brief](brief.md) · [Verification plan](verification-plan.md) · [Recovered evidence](research/archive-findings.md)
