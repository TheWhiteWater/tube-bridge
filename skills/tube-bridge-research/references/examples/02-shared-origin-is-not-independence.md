# Worked example: shared origin is not independence

**Status:** Synthetic example. Sources and values are invented to demonstrate source lineage.

## Question

> Did component shipments fall by 40% in the last quarter?

## Apparent evidence

Corpus search returns three videos:

- Video A: “Shipments fell 40%, according to the Industry Weekly bulletin.”
- Video B: “Analysts report a 40% collapse,” linking Video A in its description.
- Video C: “The new shipment crisis is worse than expected,” showing a screenshot from the same Industry Weekly bulletin.

A naive summary says: “Three independent videos confirm a 40% fall.”

## Source lineage

```text
Industry Weekly bulletin
├── Video A quotes it directly
├── Video C displays the same bulletin
└── Video B repeats Video A
```

This is one upstream SOURCE-CLAIM, repeated through three publication paths. Video count is three; independent observation count is one.

## Distinguishing retrieval

The analyst searches for the bulletin's stated underlying dataset and finds a manufacturer association table. The table reports:

- units shipped: down 18%;
- shipment value in one regional segment: down 40% after currency conversion;
- quarter definition differs from the videos' wording.

## Updated inventory

- **FACT:** three videos repeat the same bulletin lineage.
- **SOURCE-CLAIM:** total component shipments fell 40%.
- **FACT:** the located table reports an 18% unit decline and a 40% value decline for one segment.
- **INFERENCE:** the videos collapsed a segment/value measure into a total/unit claim.
- **UNKNOWN:** whether a later revision changed the table.

## Correct synthesis

> Three videos repeat one upstream bulletin and therefore do not provide three independent confirmations. The underlying table, if authentic and current, supports an 18% decline in units and a 40% decline in value for one segment, not a 40% decline in total shipments.

## Lesson

Ask for the earliest traceable origin before counting corroboration. Independence can exist at the level of observation, interpretation, or publication; say which one you mean.
