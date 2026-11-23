Subject: H&W Weekly Trade Report Validation | Power BI vs Databricks | Week 42 (Nov 23, 2026)

Hi Team,

Attached is the Week 42 (full week, Nov 14 to Nov 20) validation comparing the H&W Weekly Trade Report in Power BI and Databricks as of Nov 23, 2026, about 10:10 AM CST.

Overall, 99.3% of metrics are aligned between the two reports, with 868 metrics compared:

- 849 Matches
- 13 Style/formatting differences only
- 6 Mismatches

[Paste the chart image here]

This is slightly below Friday's 99.7% (3 mismatches), because of three new differences.

The 6 mismatches today:

- Rx Delivery Penetration pts vs LY on the Executive Summary card (2.7 vs 2.85). Power BI shows 2.7 for the same metric on its other pages, so the Power BI card does not agree with its own tables. The gap is larger today.
- New Rx Accounts vs LY, Week (16.7% vs 16.8%). Fourth validation day in a row with a 0.1 gap.
- New Rx Accounts vs LY, MTD (18.1% vs 18.2%). Second day.
- New RxD Patient, MTD Actual (129.8K vs 130.6K). New today.
- New RxD Patient, MTD vs LY (27.7% vs 28.6%). New today.
- Repeat RxD Patient, YTD YoY % (1139.3% vs 1139.4%). New today.

All six need investigation. The New RxD Patient MTD gap (0.8K, almost 1 point) is too large to be rounding. Its Week and YTD values match, so only the MTD number is off.

Still matching:

- Store Wage per Script vs LY (-10.03% in both), so the Power BI fix is holding.
- The Rx Delivery top-of-funnel stages (Order Ready Session and Add to Cart).

The attached Excel file contains the detailed validation results by report tab, along with the summary chart and match percentages by tab.

Thanks,
Radhika