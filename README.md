# Vehicle Service Management — MySQL Edition

A separate Flask website backed by MySQL Server. This repository contains the MySQL Workbench version of the Vehicle Service & Maintenance Management System.

## Setup
1. Install MySQL Server and MySQL Workbench. Workbench alone is only a client; MySQL Server must be running.
2. Open `schema.sql` in Workbench and execute it to create the `vehicle_service` database and sample records.
3. Copy `.env.example` to `.env` and set your MySQL username/password. Do not commit `.env`.
4. In this repository folder run:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

5. Open http://127.0.0.1:5000.

## Edit data manually
In Workbench, connect to the same local MySQL Server, expand Schemas > `vehicle_service` > Tables, right-click a table and choose Select Rows - Limit 1000. Edit cells and apply changes. The website reads from that same database.

This website does not read the old SQLite `.db` file. Do not expose MySQL publicly. See `.env.example` for configuration.