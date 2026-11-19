Subject: H&W Weekly Trade Report Validation | Power BI vs Databricks | Week 42 WTD (Nov 19, 2026)

Hi Team,

Attached is the Week 42 (week to date, Nov 14 to Nov 18, 5 of 7 days) validation comparing the H&W Weekly Trade Report in Power BI and Databricks as of Nov 19, 2026.

Overall, 99.7% of metrics are aligned between the two reports, with 868 metrics compared:

- 852 Matches
- 13 Style/formatting differences only
- 3 Mismatches

[Paste the chart image here]

This is up from yesterday's 98.6% match rate (12 mismatches).

The main reason for the improvement: the Rx Delivery top-of-funnel stages (Order Ready Session and Add to Cart) are now visible in Power BI without the "being validated" banner, and all 8 values match Databricks. These were set aside as mismatches until yesterday. Rx Delivery Placed Orders (Week) also matches today (274.2K in both).

The 3 remaining mismatches:

- Rx Delivery Penetration pts vs LY on the Executive Summary card (2.8 vs 2.81). Power BI shows 2.8 for the same metric on its other pages, so this appears to be a decimal/display difference on the Power BI card.
- New Rx Accounts vs LY, Week (17.2% vs 17.3%). This is the second day with the same 0.1 gap.
- Store Wage per Script vs LY (-10.03% vs -5.15%), the known Power BI issue.

The first two are the items requiring investigation.

One note: Databricks still shows the two top-of-funnel stages greyed and tagged "being validated". Since Power BI now shows them as normal values, we may want to decide whether to keep that tag.

The attached Excel file contains the detailed validation results by report tab, along with the summary chart and match percentages by tab.

Thanks,
Radhika