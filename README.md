# Vehicle Service & Maintenance Management System — MySQL Edition

This is the MySQL Workbench / MySQL Server port of the original Flask DBMS project in [SourishHere/DBMS](https://github.com/SourishHere/DBMS/tree/main/vehicle_service_review3).

## Feature parity
- Dashboard with live customer, vehicle, appointment and completion counts, recent appointments and table counts.
- All 15 original tables and the `CustomerVehicleAppointment` view.
- Original demo records and IDs copied from the original SQLite demo schema.
- Dynamic table browsing and record counts.
- Search across columns and combined per-column text, numeric range and date range filters.
- Add, view, edit and delete operations with MySQL constraint handling.
- Related foreign-key dropdowns, enum dropdowns, date/time inputs and basic input validation.
- Six SQL reports: joins, WHERE/ORDER BY, GROUP BY/HAVING, aggregates, subquery and view.
- `/health` endpoint for database and schema counts.

## Requirements
- Python 3.10+
- MySQL Server and MySQL Workbench
- MySQL database created by the included `schema.sql`

## Setup
1. Open `schema.sql` in MySQL Workbench and execute it **only if this is a fresh/empty `vehicle_service` database**. It creates `vehicle_service`, its 15 tables, the view and the original demo data. It does not drop existing tables.
2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set the MySQL credentials:

   ```bash
   cp .env.example .env
   ```

   Set `MYSQL_HOST=127.0.0.1`, `MYSQL_PORT=3306`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE=vehicle_service`. Do not commit `.env`.

4. Run the website:

   ```bash
   python app.py
   ```

5. Open http://127.0.0.1:5000.

## Important
- The website reads and writes to MySQL Server; Workbench is the SQL client used to inspect the same database.
- `SERVICE_PART` has a composite primary key, so generic row-level edit/delete is disabled for that table; use Workbench SQL for changes to it.
- Do not re-run `schema.sql` after adding records. The schema intentionally avoids destructive `DROP` statements, but existing table names will cause creation errors.
- The code has been ported to preserve the original features and sample data. Test it against your local MySQL instance before relying on it for a live demo.
