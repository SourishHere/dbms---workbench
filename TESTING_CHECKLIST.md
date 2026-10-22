# DBMS Review 3 — verification checklist

This checklist is for the existing MySQL database. It does not reset, seed, or delete data. Run automated tests first, then use the website to complete the manual checks.

## Automated checks

From the Codespaces terminal, run:

    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -v

With MySQL running and the original demo sample data present, run the full live-database suite as well:

    RUN_DB_INTEGRATION=1 python -m unittest discover -s tests -v

The live integration suite executes every report, checks seeded-data text/numeric/date/combined filters, tests a create-edit-delete cycle, checks foreign-key and CHECK constraints, and checks /health. It creates and cleans up one temporary CUSTOMER record and does not reset the database.

## Table filter tests

Use VEHICLE unless otherwise noted.

1. Open the VEHICLE table and note a known registration number.
2. Filter Color with a partial value such as Wh; every visible match should contain that text in Color.
3. Apply two column filters together, e.g. Color Wh and Mileage minimum 10000; every result must satisfy both.
4. Use global search while a column filter is active; verify both remain in the URL/form and both constrain the results.
5. Filter Manufacture_Year or a date column with a lower and upper bound; values outside the range must not appear.
6. Set Mileage minimum 50000 and maximum 10000; the page must show an error and zero rows, never broaden the query.
7. Try an invalid numeric URL value such as filter_min_Mileage=NaN; it must show an error and zero rows.
8. Use Clear filters; all filters and global search should be removed.
9. For text fields, search for percent, underscore, or exclamation mark; these characters should be treated literally, not as SQL LIKE wildcards.

## CRUD and validation tests

Use disposable test records only; do not modify seeded records needed for the demo.

- CUSTOMER: add a uniquely named test customer, view it, edit a harmless field, then delete it.
- VEHICLE: attempt to add a vehicle with a nonexistent Customer_ID or Model_ID; the database must reject it.
- CUSTOMER: try a duplicate non-null Email; the database should reject it.
- VEHICLE: test negative Mileage and a manufacture year at or below 2000; invalid values should be rejected.
- FEEDBACK: test rating 0 and 6; both should be rejected.
- APPOINTMENT: verify Status is selected from the four available options, not free text.
- INVOICE: verify Payment_Status uses the available dropdown values.
- SERVICE_PART: confirm generic Edit/Delete remains disabled for its composite primary key.
- Try deleting a parent record referenced by a child record; the foreign-key constraint should prevent orphaning.

## SQL Query Selector tests

Run each report and check result headings and values against the existing database:

- Vehicle Service History
- Upcoming Appointments
- Unpaid Invoices
- Mechanic Workload
- Most-Serviced Vehicles
- Monthly Revenue
- Low-Stock Parts
- Customer Service Summary
- Warranty Expiry
- Supplier Inventory
- The six SQL-learning reports

Empty results are acceptable for Upcoming Appointments, Unpaid Invoices, and Low-Stock Parts if current data has no matching rows. The page should explain that no records matched rather than showing an error.

## Database integrity and error handling

1. Open /health; expect 15 base tables, at least one view, and zero foreign-key violations.
2. Confirm the schema has its primary keys, foreign keys, UNIQUE constraints, CHECK constraints, and ENUM columns.
3. Submit a form with a required field empty and confirm it is rejected.
4. Submit a POST without a CSRF token; the automated test covers this and it should be rejected.
5. Stop MySQL briefly only if safe to do so; confirm the website shows a generic connection message, not credentials or a stack trace, then restart MySQL.
6. Confirm FLASK_DEBUG is not set to 1 for the demo run.

## End-to-end demo

Dashboard → All Tables → search/filter VEHICLE → add a disposable record → edit it → run a SQL report → delete the disposable record → /health.

Record the actual outcomes and any failures before claiming the project is fully verified.
