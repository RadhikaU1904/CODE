I want to automate the daily validation of our Databricks Health & Wellness Weekly Trade Report against the Power BI report.

I’m attaching today’s refreshed Power BI PDF, Databricks PDF, and the existing Excel validation tracker. Use the Excel as the master template for metric names, report sections, column structure, and formatting.

First, check whether both PDFs use the same fiscal week, filters, and data-through date. Flag any differences or information you cannot verify.

Then compare every metric listed in the Excel against the corresponding values in both PDFs. Generate a new dated Excel containing:
- Metric name and report tab/section.
- Databricks value and Power BI value.
- Matching status: Yes, No, or Needs Review.
- Fix needed: Yes, No, or Needs Review. Do not assume every mismatch requires a Databricks fix.
- Comments explaining differences, missing values, rounding, or possible refresh timing issues.
- Source PDF page references for traceability.
Handle currencies, millions/thousands, percentages, negative values, and rounding consistently. Clearly document the comparison rules and any tolerances. Do not invent values or count unreadable, missing, or unverified metrics as matches.

Add a summary sheet with total metrics, matches, mismatches, and items needing review, both overall and by report tab. Calculate match percentage as matches divided by successfully compared metrics, and separately show comparison coverage.

Include an overall match chart and a match-percentage chart by report tab. Add a daily trend chart only if historical validation files are provided.

Preserve the original files and create a separate output named HW_Trade_Report_Validation_YYYY-MM-DD.xlsx. Also draft a short daily team email summarizing the results and remaining differences.

After completing this comparison, propose a reusable Python workflow that can run in Databricks after a successful refresh, read future PDF pairs, and generate the same dated Excel and charts. Identify any extraction limitations and steps that still require manual review.