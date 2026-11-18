Hi Team,

Attached is the Week 42 (week to date, Nov 14 to Nov 17, 4 of 7 days) validation comparing the H&W Weekly Trade Report in Power BI and Databricks as of Nov 18, 2026.

Overall, 98.6% of metrics are aligned between the two reports, with 868 metrics compared:

- 843 Matches
- 13 Style/formatting differences only
- 12 Mismatches

[Paste the chart image here]

The match rate is the same as yesterday (98.6%). Two of yesterday's mismatches are now resolved, and two new small differences appeared.

Of the 12 mismatches:

- 8 are related to the Rx Delivery top-of-funnel stages that are currently under validation and are set aside for now, per Sumanth.
- 1 is the known Power BI issue for Store Wage per Script vs LY (-10.03% vs -5.15%).
- 1 is Rx Delivery Penetration pts vs LY on the Executive Summary card (2.8 vs 2.78). Power BI shows 2.8 for the same metric on its other pages, so this appears to be a decimal/display difference on the Power BI card.
- 1 is new: New Rx Accounts vs LY, Week (17.2% vs 17.3%).
- 1 is new: Rx Delivery Placed Orders, Week (212.5K vs 212.4K).

The last three are the items requiring investigation. Both new ones differ only in the last digit, so they look like rounding or data timing differences.

Resolved since yesterday:

- New RxD Patient, MTD now matches (108.3K in both).
- Vision Merch Sales vs LY for BU O now matches (10749.1% in both). The value itself looks unusual because the actual is only $371, so it may be worth a separate look.

The attached Excel file contains the detailed validation results by report tab, along with the summary chart and match percentages by tab.

Thanks,
Radhika