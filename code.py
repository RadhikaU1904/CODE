Hi Team,

Attached is the Week 42 (week to date, Nov 14 to Nov 16, 3 of 7 days) validation comparing the H&W Weekly Trade Report in Power BI and Databricks as of Nov 17, 2026.

Overall, 98.6% of metrics are aligned between the two reports, with 868 metrics compared:

- 843 Matches
- 13 Style/formatting differences only
- 12 Mismatches

[Paste the chart image here]

This is slightly below yesterday's 98.8% match rate (Week 41), because of two new small differences.

Of the 12 mismatches:

- 8 are related to the Rx Delivery top-of-funnel stages that are currently under validation and are set aside for now, per Sumanth.
- 1 is the known Power BI issue for Store Wage per Script vs LY (-10.03% vs -5.15%).
- 1 is Rx Delivery Penetration pts vs LY on the Executive Summary card (2.9 vs 2.82). Power BI shows 2.9 for the same metric on its Sales & Volume page, so this appears to be a rounding/display difference on the Power BI card.
- 1 is new: New RxD Patient, MTD (101.2K vs 101.3K), which looks like a rounding or timing difference.
- 1 is new: Vision Merch Sales vs LY for BU O (NA vs 0.0%), where the actual is only $529 in both reports.

The last three are the items requiring investigation.

The attached Excel file contains the detailed validation results by report tab, along with the summary chart and match percentages by tab.

Thanks,
Radhika