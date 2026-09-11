# dbt Failure Scenarios

`difficulty_level` is a numeric scenario-complexity indicator. The existing `level` field remains unchanged for compatibility.

- **1 - Simple:** isolated, easy-to-localize failures.
- **2 - Intermediate:** failures requiring upstream/downstream propagation or multiple related checks.
- **3 - Advanced:** multi-step transformation, integration, or data-flow reasoning.
- **4 - Adversarial:** misleading, subtle, or deliberately deceptive failure signals.

## Scenario matrix

| Difficulty | Scenarios | Notes |
| --- | --- | --- |
| 1 | SC003-SC007, SC009 | Simple scenarios |
| 2 | SC008, SC011-SC017 | SC008 is the exception within SC003-SC010 |
| 3 | SC010, SC018-SC030 | SC010 is the exception within SC003-SC010 |
| 4 | SC031-SC036 | Adversarial scenarios |

SC001 and SC002 are legacy-compatible and are intentionally outside the new numeric difficulty assignment.
