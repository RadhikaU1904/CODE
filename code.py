Subject: H&W Weekly Trade Report Validation | Power BI vs Databricks | Week 42 WTD (Nov 20, 2026)

Hi Team,

Attached is the Week 42 (week to date, Nov 14 to Nov 19, 6 of 7 days) validation comparing the H&W Weekly Trade Report in Power BI and Databricks as of Nov 20, 2026, about 9:45 AM CST.

Overall, 99.7% of metrics are aligned between the two reports, with 868 metrics compared:

- 852 Matches
- 13 Style/formatting differences only
- 3 Mismatches

[Paste the chart image here]

The match rate is the same as yesterday (99.7%, 3 mismatches), but the items changed.

Resolved since yesterday:

- Store Wage per Script vs LY now matches. Power BI shows -10.03%, the same as Databricks. Until yesterday Power BI showed -5.15% (the known Power BI issue), so the fix appears to be live.

The 3 mismatches today:

- Rx Delivery Penetration pts vs LY on the Executive Summary card (2.7 vs 2.79). Power BI shows 2.7 for the same metric on its other pages. Today the card value rounds to 2.8, so it is slightly more than a display difference.
- New Rx Accounts vs LY, Week (17.3% vs 17.4%). This is the third day in a row with a 0.1 gap on this metric.
- New Rx Accounts vs LY, MTD (18.4% vs 18.5%). This one is new today.

All three need investigation. The New Rx Accounts gap is small but consistent, so it may be a calculation difference between the two reports and not just rounding.

The Rx Delivery top-of-funnel stages (Order Ready Session and Add to Cart) match again this morning.

The attached Excel file contains the detailed validation results by report tab, along with the summary chart and match percentages by tab.

Thanks,
Radhika