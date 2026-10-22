# Vehicle Service & Maintenance Management System — MySQL Edition

This is the MySQL Workbench / MySQL Server port of the original Flask DBMS project in [SourishHere/DBMS](https://github.com/SourishHere/DBMS/tree/main/vehicle_service_review3).

## Restored original features and data
- The same 15 original tables and the `CustomerVehicleAppointment` view.
- Original sample rows, identifiers and relationships copied from the original SQLite demo schema.
- Dashboard with live customer, vehicle, appointment and completed-appointment counts, recent appointments and table counts.
- Dynamic table browsing, row counts, primary-key information and search across columns.
- Combined per-column text filters, numeric ranges and date ranges.
- Add, view, edit and delete operations with MySQL constraint-error feedback.
- Related-record dropdowns for foreign keys, dropdowns for status/payment/fuel/vehicle types, date/time fields and required-field checks.
- SQL Query Selector with operational reports (service history, upcoming appointments, unpaid invoices, mechanic workload, most-serviced vehicles, monthly revenue, low-stock parts, customer summary, warranty expiry and supplier inventory) plus six SQL-learning reports.
- `/health` endpoint to inspect the selected database and count tables/views.
- CSRF protection for record-creation, record-editing and record-deletion forms; generic database error messages.
- Automated unit tests for filter validation, literal text filtering, combined search, invalid ranges, report selection and CSRF. See `TESTING_CHECKLIST.md` for the manual database/CRUD/demo checks.

## Requirements
- Python 3.10+
- MySQL Server and MySQL Workbench

## Setup
1. Open `schema.sql` in MySQL Workbench and execute it **only if `vehicle_service` is fresh/empty**. It creates the database, 15 tables, the view and original demo data. It does not drop tables.
2. In Terminal, enter the project folder and run:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Edit `.env` with your own working MySQL credentials. Set `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=3306`, `MYSQL_USER` and `MYSQL_PASSWORD` to the account you tested in Workbench, and `MYSQL_DATABASE=vehicle_service`. Keep `.env` private; do not commit it.
4. Start the website:

   ```bash
   python app.py
   ```

5. Open http://127.0.0.1:5000.
6. Run unit checks with `python -m unittest discover -s tests -v`. With MySQL running and the original demo sample data present, run `RUN_DB_INTEGRATION=1 python -m unittest discover -s tests -v` to also verify the report SQL, live filters, CRUD, and constraints. Integration tests create and clean up one temporary CUSTOMER row; they do not reset the database.

## Important
- The website connects to MySQL Server. MySQL Workbench is the client used to inspect that same database.
- The database name used by this repository is `vehicle_service`. If you previously created a separate empty `vehicle_service_db`, it is not the database selected by this project's schema.
- `SERVICE_PART` has a composite primary key, so generic row-level edit/delete is disabled for safety. Change those rows in Workbench SQL.
- Do not run `schema.sql` again after adding your own records. Existing tables will cause creation errors; the script deliberately contains no destructive `DROP` statements.
- The project files are ported for feature and demo-data parity, but the website still needs to be run against your local MySQL instance to verify runtime behavior.
