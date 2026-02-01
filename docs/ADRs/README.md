# Architecture Decision Records (ADRs)

This directory contains architectural decisions for the Coinbase Spot Trading Engine project.

## What is an ADR?

An Architecture Decision Record is a brief document describing a significant architectural decision,
the context motivating it, and the consequences (positive and negative) of the choice.

Format (template in each file):

- **Title**: Short noun phrase
- **Status**: Proposed | Accepted | Deprecated | Superseded
- **Context**: The issue or problem motivating this decision
- **Decision**: What we decided to do
- **Consequences**: Positive and negative outcomes
- **Alternatives Considered**: Other options and why we rejected them

## Index

- [ADR-001: Limit Orders Only](./ADR-001-limit-orders-only.md)
- [ADR-002: Ratchet-Only Trailing Stops](./ADR-002-ratchet-only-stops.md)
- [ADR-003: SQLite for Persistence](./ADR-003-sqlite-persistence.md)
- [ADR-004: Sync + Async Dual Implementation](./ADR-004-sync-async-dual.md)
- [ADR-005: Decimal for Price Precision](./ADR-005-decimal-precision.md)
- [ADR-006: Configuration-Driven Strategy](./ADR-006-config-driven-strategy.md)

---

For proposals, use the template below and submit as a PR discussion.

## ADR Template

```markdown
# ADR-NNN: Title

**Status**: Proposed

## Context

[Describe the issue or problem that motivates this decision]

## Decision

[Describe what we decided to do]

## Consequences

### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Drawback 1]
- [Drawback 2]

## Alternatives Considered

1. **Alternative A**
   - Reason for rejection: [...]

2. **Alternative B**
   - Reason for rejection: [...]

## Follow-up

- [ ] Document in README
- [ ] Add tests
- [ ] Update CI/CD if needed
```
