import os
import re
import hmac
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from contextlib import contextmanager
import mysql.connector
import sqlparse
from mysql.connector import Error
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
DB_NAME = os.getenv("MYSQL_DATABASE", "vehicle_service")
BUILTIN_TABLES = ["CUSTOMER","VEHICLE_MODEL","VEHICLE","MECHANIC","SERVICE_TYPE","APPOINTMENT","SERVICE_RECORD","SUPPLIER","PART","SERVICE_PART","INVENTORY","INVOICE","PAYMENT","WARRANTY","FEEDBACK"]
TABLES = BUILTIN_TABLES.copy()
LABELS = {t:t.replace("_"," ").title() for t in TABLES}
PKS = {"CUSTOMER":"Customer_ID","VEHICLE_MODEL":"Model_ID","VEHICLE":"Vehicle_ID","MECHANIC":"Mechanic_ID","SERVICE_TYPE":"Service_Type_ID","APPOINTMENT":"Appointment_ID","SERVICE_RECORD":"Service_ID","SUPPLIER":"Supplier_ID","PART":"Part_ID","SERVICE_PART":None,"INVENTORY":"Inventory_ID","INVOICE":"Invoice_ID","PAYMENT":"Payment_ID","WARRANTY":"Warranty_ID","FEEDBACK":"Feedback_ID"}

def db():
    return mysql.connector.connect(host=os.getenv("MYSQL_HOST","127.0.0.1"), port=int(os.getenv("MYSQL_PORT","3306")), user=os.getenv("MYSQL_USER","root"), password=os.getenv("MYSQL_PASSWORD",""), database=DB_NAME)

@app.before_request
def protect_post_requests():
    global TABLES, LABELS
    if request.method == "POST":
        expected = session.get("_csrf_token")
        submitted = request.form.get("csrf_token", "")
        if not expected or not submitted or not hmac.compare_digest(expected, submitted):
            abort(400)
    if app.testing:
        return
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'",
            (DB_NAME,)
        )
        found = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()
        original_order = [
            "CUSTOMER", "VEHICLE_MODEL", "VEHICLE", "MECHANIC",
            "SERVICE_TYPE", "APPOINTMENT", "SERVICE_RECORD", "SUPPLIER",
            "PART", "SERVICE_PART", "INVENTORY", "INVOICE", "PAYMENT",
            "WARRANTY", "FEEDBACK"
        ]
        TABLES = [name for name in original_order if name in found]
        TABLES.extend(sorted(found.difference(TABLES)))
        LABELS = {name: name.replace("_", " ").title() for name in TABLES}
    except Error:
        app.logger.exception("Could not refresh the database table list.")

@app.context_processor
def inject_csrf_token():
    def csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token
    return {"csrf_token": csrf_token}

def escape_like(value):
    return str(value).replace("!", "!!").replace("%", "!%").replace("_", "!_")

def validate_filter_range(kind, low, high):
    if kind == "number":
        lower = Decimal(low) if low else None
        upper = Decimal(high) if high else None
        if any(value is not None and not value.is_finite() for value in (lower, upper)):
            raise ValueError("Numeric filter values must be finite numbers.")
    elif kind == "date":
        lower = date.fromisoformat(low) if low else None
        upper = date.fromisoformat(high) if high else None
    else:
        return True
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("The lower filter bound cannot exceed the upper bound.")
    return True

@contextmanager
def connect_db():
    conn=db()
    try:
        yield conn
    finally:
        conn.close()

def qi(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(name)):
        raise ValueError("Invalid identifier")
    return "`"+str(name)+"`"

def columns_for(conn, table):
    if table not in TABLES: abort(404)
    cur=conn.cursor(dictionary=True)
    cur.execute("SELECT COLUMN_NAME AS name,COLUMN_TYPE AS type,IS_NULLABLE AS nullable,COLUMN_DEFAULT AS default_value,EXTRA AS extra,COLUMN_KEY AS column_key FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",(DB_NAME,table))
    rows=cur.fetchall(); cur.close()
    return rows

def table_info(conn, table):
    cols=columns_for(conn,table)
    cur=conn.cursor(dictionary=True)
    cur.execute("SELECT COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL",(DB_NAME,table))
    fks={r["COLUMN_NAME"]:(r["REFERENCED_TABLE_NAME"],r["REFERENCED_COLUMN_NAME"]) for r in cur.fetchall()}; cur.close()
    return [{"name":c["name"],"type":c["type"].upper(),"notnull":c["nullable"]=="NO","pk":c["column_key"]=="PRI","identity":"auto_increment" in (c["extra"] or "").lower(),"default":c["default_value"],"fk":fks.get(c["name"])} for c in cols]

def primary_key(cols):
    keys=[c["name"] for c in cols if c.get("pk")]
    return keys[0] if len(keys)==1 else None

def count_rows(conn, table):
    cur=conn.cursor(); cur.execute("SELECT COUNT(*) FROM "+qi(table)); n=cur.fetchone()[0]; cur.close(); return n

def foreign_key_issue_count(conn):
    checks = [
        ("VEHICLE","Customer_ID","CUSTOMER","Customer_ID"),
        ("VEHICLE","Model_ID","VEHICLE_MODEL","Model_ID"),
        ("APPOINTMENT","Vehicle_ID","VEHICLE","Vehicle_ID"),
        ("APPOINTMENT","Mechanic_ID","MECHANIC","Mechanic_ID"),
        ("APPOINTMENT","Service_Type_ID","SERVICE_TYPE","Service_Type_ID"),
        ("SERVICE_RECORD","Appointment_ID","APPOINTMENT","Appointment_ID"),
        ("PART","Supplier_ID","SUPPLIER","Supplier_ID"),
        ("SERVICE_PART","Service_ID","SERVICE_RECORD","Service_ID"),
        ("SERVICE_PART","Part_ID","PART","Part_ID"),
        ("INVENTORY","Part_ID","PART","Part_ID"),
        ("INVOICE","Service_ID","SERVICE_RECORD","Service_ID"),
        ("PAYMENT","Invoice_ID","INVOICE","Invoice_ID"),
        ("WARRANTY","Service_ID","SERVICE_RECORD","Service_ID"),
        ("WARRANTY","Part_ID","PART","Part_ID"),
        ("FEEDBACK","Service_ID","SERVICE_RECORD","Service_ID"),
        ("FEEDBACK","Customer_ID","CUSTOMER","Customer_ID")
    ]
    cur=conn.cursor()
    total=0
    for child, child_col, parent, parent_col in checks:
        cur.execute("SELECT COUNT(*) FROM "+qi(child)+" c LEFT JOIN "+qi(parent)+" p ON c."+qi(child_col)+"=p."+qi(parent_col)+" WHERE c."+qi(child_col)+" IS NOT NULL AND p."+qi(parent_col)+" IS NULL")
        total += cur.fetchone()[0]
    cur.close()
    return total

def get_rows(conn, table, search="", where=None, params=None, limit=250):
    cols=columns_for(conn,table); conditions=list(where or []); values=list(params or [])
    if search:
        searchable=[c for c in cols if any(t in c["type"].upper() for t in ("CHAR","TEXT","ENUM","SET","INT","DECIMAL","FLOAT","DOUBLE","DATE","YEAR","TIME"))]
        if searchable:
            conditions.append("("+" OR ".join("CAST("+qi(c["name"])+" AS CHAR) LIKE %s ESCAPE '!'" for c in searchable)+")")
            values.extend(["%"+escape_like(search)+"%"]*len(searchable))
    sql="SELECT * FROM "+qi(table)
    if conditions: sql+=" WHERE "+" AND ".join(conditions)
    sql+=" LIMIT "+str(int(limit))
    cur=conn.cursor(dictionary=True); cur.execute(sql,tuple(values)); rows=cur.fetchall(); cur.close()
    return cols,rows

def form_fields(conn, table):
    cols=table_info(conn,table); cur=conn.cursor(dictionary=True)
    for col in cols:
        col["options"]=[]
        if col["fk"]:
            ref_table,ref_col=col["fk"]; refcols=columns_for(conn,ref_table)
            label_col=next((x["name"] for x in refcols if x["name"].lower().endswith("name")),ref_col)
            cur.execute("SELECT "+qi(ref_col)+" AS value,"+qi(label_col)+" AS label FROM "+qi(ref_table)+" ORDER BY 2 LIMIT 500")
            col["options"]=cur.fetchall()
    cur.close()
    return cols

CUSTOM_REQUIRED = {
    ("MECHANIC", "specialization"),
    ("INVOICE", "total_amount"),
    ("INVOICE", "payment_status"),
    ("PAYMENT", "payment_mode"),
    ("WARRANTY", "part_id"),
    ("FEEDBACK", "rating"),
    ("VEHICLE", "manufacture_year"),
}

def field_required(table, col):
    return (table.upper(), col["name"].lower()) in CUSTOM_REQUIRED or (
        col["notnull"] and col["default"] is None and (not col["pk"] or not col["identity"])
    )

def convert_value(raw,col):
    if raw=="": return None
    typ=col["type"].upper(); name=col["name"].lower()
    if "DATETIME" in typ or "TIMESTAMP" in typ:
        return raw.replace("T"," ")+(":00" if "T" in raw and len(raw)==16 else "")
    if typ=="DATE" or name.endswith("_date") or name=="last_updated": return raw[:10]
    if any(t in typ for t in ("INT","DECIMAL","FLOAT","DOUBLE","NUMERIC","YEAR")):
        try: return Decimal(raw) if any(t in typ for t in ("DECIMAL","FLOAT","DOUBLE","NUMERIC")) else int(raw)
        except (ValueError,InvalidOperation): raise ValueError("Enter a valid number for "+col["name"]+".")
    return raw

@app.template_filter("date_input")
def date_input(value):
    if value is None: return ""
    if isinstance(value,(date,datetime)): return value.strftime("%Y-%m-%d")
    return str(value)[:10]

@app.template_filter("datetime_input")
def datetime_input(value):
    if value is None: return ""
    if isinstance(value,(date,datetime)): return value.strftime("%Y-%m-%dT%H:%M")
    return str(value).replace(" ","T")[:16]

@app.template_filter("date_only")
def date_only(value):
    """Display date/datetime values as dates only in every table."""
    if value is None: return value
    if isinstance(value, (date, datetime)): return value.strftime("%Y-%m-%d")
    value = str(value).strip()
    # Handle MySQL datetime strings with or without seconds/timezone suffix.
    if len(value) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[ T])", value):
        return value[:10]
    return value

@app.context_processor
def inject_navigation():
    return {"nav_tables":TABLES,"labels":LABELS,"nav_views":VIEWS,"view_labels":VIEW_LABELS,"db_backend":"MySQL"}

@app.route("/create-table",methods=["GET","POST"])
def create_table():
    foreign_key_options = []
    with connect_db() as option_conn:
        for option_table in TABLES:
            option_columns = table_info(option_conn, option_table)
            option_pk = primary_key(option_columns)
            if option_pk:
                option_col = next((col for col in option_columns if col["name"] == option_pk), None)
                if option_col:
                    foreign_key_options.append({
                        "table": option_table,
                        "column": option_pk,
                        "type": option_col["type"].upper().split("(")[0].strip()
                    })
    if request.method == "GET":
        return render_template("create_table.html", foreign_key_options=foreign_key_options)

    raw_table = request.form.get("table_name", "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", raw_table):
        flash("Use a table name starting with a letter and containing only letters, numbers, and underscores (maximum 64 characters).", "error")
        return render_template("create_table.html", foreign_key_options=foreign_key_options)

    column_names = request.form.getlist("column_name[]")
    column_types = request.form.getlist("column_type[]")
    pk_indexes = set(request.form.getlist("column_pk[]"))
    required_indexes = set(request.form.getlist("column_required[]"))
    auto_indexes = set(request.form.getlist("column_auto[]"))
    fk_tables = request.form.getlist("column_fk_table[]")
    fk_columns = request.form.getlist("column_fk_column[]")
    fk_actions = request.form.getlist("column_fk_action[]")
    allowed_types = {"INT": "INT", "VARCHAR(255)": "VARCHAR(255)", "TEXT": "TEXT", "DECIMAL(10,2)": "DECIMAL(10,2)", "DATE": "DATE", "DATETIME": "DATETIME", "BOOLEAN": "BOOLEAN"}

    if raw_table in TABLES:
        flash("A table with that name already exists.", "error")
        return render_template("create_table.html", foreign_key_options=foreign_key_options)
    if len(column_names) < 1 or len(column_names) > 20 or len(column_names) != len(column_types) or len(fk_tables) != len(column_names) or len(fk_columns) != len(column_names) or len(fk_actions) != len(column_names):
        flash("Add between 1 and 20 columns.", "error")
        return render_template("create_table.html", foreign_key_options=foreign_key_options)
    valid_indexes = {str(index) for index in range(len(column_names))}
    if not pk_indexes.issubset(valid_indexes) or not required_indexes.issubset(valid_indexes) or not auto_indexes.issubset(valid_indexes) or len(pk_indexes) != 1:
        flash("Choose exactly one valid primary-key column.", "error")
        return render_template("create_table.html", foreign_key_options=foreign_key_options)

    fk_by_index = []
    option_lookup = {(item["table"], item["column"]): item for item in foreign_key_options}
    for index, (fk_table, fk_column, fk_action) in enumerate(zip(fk_tables, fk_columns, fk_actions)):
        if fk_action not in {"RESTRICT", "CASCADE", "SET NULL"}:
            flash("Choose a valid foreign-key delete rule.", "error")
            return render_template("create_table.html", foreign_key_options=foreign_key_options)
        if bool(fk_table) != bool(fk_column):
            flash("Choose both a referenced table and column for each foreign key.", "error")
            return render_template("create_table.html", foreign_key_options=foreign_key_options)
        if fk_table:
            target = option_lookup.get((fk_table, fk_column))
            if not target or fk_table not in TABLES:
                flash("Choose an existing table and its primary-key column for the foreign key.", "error")
                return render_template("create_table.html", foreign_key_options=foreign_key_options)
            if column_types[index] not in allowed_types:
                flash("Choose a supported data type for every column.", "error")
                return render_template("create_table.html", foreign_key_options=foreign_key_options)
            source_family = allowed_types[column_types[index]].split("(")[0].upper()
            target_family = target["type"].split("(")[0].upper()
            if source_family != target_family:
                flash("The foreign-key column must use a compatible data type with the referenced primary key.", "error")
                return render_template("create_table.html", foreign_key_options=foreign_key_options)
            if fk_action == "SET NULL" and str(index) in required_indexes:
                flash("SET NULL requires the foreign-key column to allow NULL values.", "error")
                return render_template("create_table.html", foreign_key_options=foreign_key_options)
            fk_by_index.append((index, fk_table, fk_column, fk_action))
    clean_columns = []
    seen_names = set()
    for index, (raw_name, raw_type) in enumerate(zip(column_names, column_types)):
        name = raw_name.strip()
        normalized = name.lower()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name) or normalized in seen_names:
            flash("Column names must be unique and contain only letters, numbers, and underscores.", "error")
            return render_template("create_table.html", foreign_key_options=foreign_key_options)
        if raw_type not in allowed_types:
            flash("Choose a supported data type for every column.", "error")
            return render_template("create_table.html", foreign_key_options=foreign_key_options)
        is_pk = str(index) in pk_indexes
        is_required = str(index) in required_indexes or is_pk
        is_auto = str(index) in auto_indexes
        if is_auto and (raw_type != "INT" or not is_pk):
            flash("AUTO_INCREMENT can only be used on an INT primary-key column.", "error")
            return render_template("create_table.html", foreign_key_options=foreign_key_options)
        definition = qi(name) + " " + allowed_types[raw_type]
        if is_required:
            definition += " NOT NULL"
        if is_auto:
            definition += " AUTO_INCREMENT"
        if is_pk:
            definition += " PRIMARY KEY"
        clean_columns.append(definition)
        seen_names.add(normalized)

    if len(pk_indexes) != 1:
        flash("Choose exactly one primary-key column.", "error")
        return render_template("create_table.html", foreign_key_options=foreign_key_options)

    for index, fk_table, fk_column, fk_action in fk_by_index:
        clean_columns.append(
            "FOREIGN KEY (" + qi(column_names[index].strip()) + ") REFERENCES "
            + qi(fk_table) + "(" + qi(fk_column) + ") ON DELETE " + fk_action
        )

    statement = "CREATE TABLE " + qi(raw_table) + " (\n    " + ",\n    ".join(clean_columns) + "\n);"
    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute(statement)
            conn.commit()
            cur.close()
    except (Error, ValueError) as exc:
        app.logger.warning("Could not create table %s: %s", raw_table, exc)
        flash("MySQL could not create this table. Check its name and column definitions.", "error")
        return render_template("create_table.html", foreign_key_options=foreign_key_options)

    schema_saved = False
    schema_path = os.path.join(app.root_path, "schema.sql")
    try:
        with open(schema_path, "a", encoding="utf-8") as schema_file:
            schema_file.write("\n\n-- Table created from the website: " + raw_table + "\n")
            schema_file.write(statement + "\n")
        schema_saved = True
    except OSError:
        app.logger.exception("Table %s was created, but schema.sql could not be updated.", raw_table)

    if schema_saved:
        flash("Table " + raw_table + " created successfully and appended to schema.sql.", "success")
    else:
        flash("Table " + raw_table + " was created, but schema.sql could not be updated. Check file permissions.", "error")
    return redirect(url_for("tables_page"))


@app.route("/")
def index():
    with connect_db() as conn:
        counts={t:count_rows(conn,t) for t in TABLES}
        cur=conn.cursor()
        cur.execute("SELECT COUNT(*) FROM APPOINTMENT WHERE Status='Completed'"); completed=cur.fetchone()[0]
        cur.close()
    return render_template("index.html",counts=counts,customer_count=counts["CUSTOMER"],vehicle_count=counts["VEHICLE"],appointment_count=counts["APPOINTMENT"],completed=completed)

@app.route("/edit-table/<table>", methods=["GET", "POST"])
def edit_table(table):
    if table not in TABLES:
        abort(404)

    allowed_types = {
        "INT": "INT",
        "BIGINT": "BIGINT",
        "VARCHAR(255)": "VARCHAR(255)",
        "TEXT": "TEXT",
        "DECIMAL(10,2)": "DECIMAL(10,2)",
        "DATE": "DATE",
        "DATETIME": "DATETIME",
        "BOOLEAN": "BOOLEAN"
    }

    with connect_db() as conn:
        columns = table_info(conn, table)
        foreign_key_options = []
        for option_table in TABLES:
            option_columns = table_info(conn, option_table)
            option_pk = primary_key(option_columns)
            option_col = next((col for col in option_columns if col["name"] == option_pk), None) if option_pk else None
            if option_col:
                foreign_key_options.append({"table": option_table, "column": option_pk, "type": option_col["type"].upper().split("(")[0].strip()})
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, "
            "CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL",
            (DB_NAME, table)
        )
        fk_rows = cur.fetchall()
        fk_columns = {row["COLUMN_NAME"] for row in fk_rows}
        fk_rules = [{
            "column": row["COLUMN_NAME"],
            "table": row["REFERENCED_TABLE_NAME"],
            "referenced_column": row["REFERENCED_COLUMN_NAME"],
            "constraint": row["CONSTRAINT_NAME"]
        } for row in fk_rows]
        cur.close()

        if request.method == "GET":
            return render_template(
                "edit_table.html", table=table, label=LABELS[table],
                columns=columns, fk_columns=fk_columns, fk_rules=fk_rules,
                allowed_types=list(allowed_types), foreign_key_options=foreign_key_options
            )

        action = request.form.get("action", "")
        statements = []
        if action == "add":
            name = request.form.get("column_name", "").strip()
            raw_type = request.form.get("column_type", "")
            nullable = request.form.get("nullable") == "yes"
            fk_table = request.form.get("fk_table", "").strip()
            fk_column = request.form.get("fk_column", "").strip()
            fk_action = request.form.get("fk_action", "RESTRICT")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
                flash("Use a valid column name.", "error")
                return redirect(url_for("edit_table", table=table))
            if name.lower() in {col["name"].lower() for col in columns}:
                flash("That column already exists.", "error")
                return redirect(url_for("edit_table", table=table))
            if raw_type not in allowed_types or fk_action not in {"RESTRICT", "CASCADE", "SET NULL"}:
                flash("Choose a valid data type and foreign-key rule.", "error")
                return redirect(url_for("edit_table", table=table))
            definition = qi(name) + " " + allowed_types[raw_type]
            if not nullable:
                definition += " NOT NULL"
            if fk_table or fk_column:
                if not fk_table or not fk_column:
                    flash("Choose both a referenced table and key.", "error")
                    return redirect(url_for("edit_table", table=table))
                if fk_table not in TABLES:
                    flash("Referenced table does not exist.", "error")
                    return redirect(url_for("edit_table", table=table))
                target_columns = table_info(conn, fk_table)
                target = next((col for col in target_columns if col["name"] == fk_column and col["pk"]), None)
                if not target:
                    flash("Foreign keys must reference an existing primary key.", "error")
                    return redirect(url_for("edit_table", table=table))
                source_family = allowed_types[raw_type].split("(")[0].upper()
                target_family = target["type"].split("(")[0].upper()
                if source_family != target_family:
                    flash("Foreign-key data type must match the referenced primary key type.", "error")
                    return redirect(url_for("edit_table", table=table))
                if fk_action == "SET NULL" and not nullable:
                    flash("SET NULL requires this column to allow NULL values.", "error")
                    return redirect(url_for("edit_table", table=table))
                constraint = "fk_" + table.lower() + "_" + name.lower()
                statements.append(
                    "ALTER TABLE " + qi(table) + " ADD COLUMN " + definition +
                    ", ADD CONSTRAINT " + qi(constraint) + " FOREIGN KEY (" + qi(name) +
                    ") REFERENCES " + qi(fk_table) + "(" + qi(fk_column) +
                    ") ON DELETE " + fk_action
                )
            else:
                statements.append("ALTER TABLE " + qi(table) + " ADD COLUMN " + definition)
        elif action == "modify":
            name = request.form.get("existing_column", "")
            raw_type = request.form.get("new_type", "")
            nullable = request.form.get("new_nullable") == "yes"
            current = next((col for col in columns if col["name"] == name), None)
            if not current or raw_type not in allowed_types:
                flash("Choose an existing column and valid data type.", "error")
                return redirect(url_for("edit_table", table=table))
            if current["name"] in fk_columns or current["pk"]:
                flash("Primary-key and foreign-key columns cannot be modified here. Remove or redesign their constraints first.", "error")
                return redirect(url_for("edit_table", table=table))
            definition = qi(name) + " " + allowed_types[raw_type] + (" NULL" if nullable else " NOT NULL")
            if current["default"] is not None:
                default_value = str(current["default"])
                if default_value.upper() in {"CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME"} or re.fullmatch(r"-?\d+(?:\.\d+)?", default_value):
                    definition += " DEFAULT " + default_value
                else:
                    definition += " DEFAULT '" + default_value.replace("\\", "\\\\").replace("'", "''") + "'"
            statements.append("ALTER TABLE " + qi(table) + " MODIFY COLUMN " + definition)
        elif action == "rule":
            name = request.form.get("fk_rule_column", "")
            fk_action = request.form.get("fk_rule_action", "")
            fk_rule = next((item for item in fk_rules if item["column"] == name), None)
            current = next((col for col in columns if col["name"] == name), None)
            if not fk_rule or not current or fk_action not in {"RESTRICT", "CASCADE", "SET NULL"}:
                flash("Choose a valid existing foreign key and delete rule.", "error")
                return redirect(url_for("edit_table", table=table))
            if fk_action == "SET NULL" and current["notnull"]:
                flash("SET NULL requires the foreign-key column to allow NULL values.", "error")
                return redirect(url_for("edit_table", table=table))
            constraint = qi(fk_rule["constraint"])
            statements.append(
                "ALTER TABLE " + qi(table) + " DROP FOREIGN KEY " + constraint +
                ", ADD CONSTRAINT " + constraint + " FOREIGN KEY (" + qi(name) +
                ") REFERENCES " + qi(fk_rule["table"]) + "(" + qi(fk_rule["referenced_column"]) +
                ") ON DELETE " + fk_action
            )
        elif action == "drop":
            name = request.form.get("drop_column", "")
            current = next((col for col in columns if col["name"] == name), None)
            if not current:
                flash("Choose an existing column.", "error")
                return redirect(url_for("edit_table", table=table))
            if current["pk"] or current["name"] in fk_columns:
                flash("Primary-key and foreign-key columns are protected from removal in this form.", "error")
                return redirect(url_for("edit_table", table=table))
            cur = conn.cursor()
            cur.execute(
                "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME=%s AND REFERENCED_COLUMN_NAME=%s",
                (DB_NAME, table, name)
            )
            referenced = cur.fetchall()
            cur.close()
            if referenced:
                flash("This column is referenced by another table and cannot be removed.", "error")
                return redirect(url_for("edit_table", table=table))
            statements.append("ALTER TABLE " + qi(table) + " DROP COLUMN " + qi(name))
        else:
            flash("Choose a valid table-edit action.", "error")
            return redirect(url_for("edit_table", table=table))

        try:
            cur = conn.cursor()
            for statement in statements:
                cur.execute(statement)
            conn.commit()
            cur.close()
        except (Error, ValueError) as exc:
            conn.rollback()
            app.logger.warning("Could not alter table %s: %s", table, exc)
            flash("MySQL rejected the table change: " + str(exc.msg if hasattr(exc, "msg") else exc)[:180], "error")
            return redirect(url_for("edit_table", table=table))

    schema_path = os.path.join(app.root_path, "schema.sql")
    try:
        with open(schema_path, "a", encoding="utf-8") as schema_file:
            schema_file.write("\n\n-- Table structure change made from the website: " + table + "\n")
            schema_file.write(";\n".join(statements) + ";\n")
        flash("Table structure updated in MySQL and change recorded in schema.sql.", "success")
    except OSError:
        app.logger.exception("Table %s altered, but schema.sql could not be updated.", table)
        flash("Table structure changed in MySQL, but schema.sql could not be updated.", "error")
    return redirect(url_for("table_page", table=table))


@app.route("/delete-table/<table>", methods=["POST"])
def delete_table(table):
    if table not in TABLES or table in BUILTIN_TABLES:
        flash("Only custom tables created in this database can be deleted here. Built-in project tables are protected.", "error")
        return redirect(url_for("tables_page"))

    try:
        with connect_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                "WHERE REFERENCED_TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME=%s",
                (DB_NAME, table)
            )
            references = cur.fetchall()
            if references:
                cur.close()
                flash("Cannot delete " + table + " because another table references it. Remove those foreign keys or dependent tables first.", "error")
                return redirect(url_for("tables_page"))
            cur.execute("DROP TABLE " + qi(table))
            conn.commit()
            cur.close()
    except Error:
        app.logger.exception("Could not delete custom table %s", table)
        flash("The table could not be deleted. Check its foreign-key dependencies and database permissions.", "error")
        return redirect(url_for("tables_page"))

    schema_path = os.path.join(app.root_path, "schema.sql")
    try:
        with open(schema_path, "r", encoding="utf-8") as schema_file:
            schema_text = schema_file.read()
        marker = re.compile(
            r"\n\n-- Table created from the website: " + re.escape(table) +
            r"\n.*?;[ \t]*(?=\n|$)",
            re.IGNORECASE | re.DOTALL
        )
        schema_text = marker.sub("", schema_text, count=1)
        with open(schema_path, "w", encoding="utf-8") as schema_file:
            schema_file.write(schema_text)
    except OSError:
        app.logger.exception("Table %s deleted from MySQL, but schema.sql could not be updated.", table)
        flash("Table " + table + " was deleted from MySQL, but schema.sql could not be updated.", "error")
        return redirect(url_for("tables_page"))

    flash("Custom table " + table + " deleted from MySQL and removed from schema.sql.", "success")
    return redirect(url_for("tables_page"))



@app.route("/tables")
def tables_page():
    with connect_db() as conn:
        items=[]
        for t in TABLES:
            cols=table_info(conn,t); items.append({"name":t,"columns":len(cols),"rows":count_rows(conn,t),"pk":primary_key(cols)})
    return render_template("tables.html",items=items)

@app.route("/table/<table>")
def table_page(table):
    if table not in TABLES: abort(404)
    search=request.args.get("q","").strip(); where=[]; params=[]; filters=[]; invalid_filters=False
    with connect_db() as conn:
        cols=table_info(conn,table)
        for col in cols:
            name=col["name"]; typ=col["type"].upper()
            if any(t in typ for t in ("DATE","TIME")):
                kind="date"; low=request.args.get("filter_from_"+name,"").strip(); high=request.args.get("filter_to_"+name,"").strip()
            elif any(t in typ for t in ("INT","YEAR","DECIMAL","FLOAT","DOUBLE","NUMERIC")):
                kind="number"; low=request.args.get("filter_min_"+name,"").strip(); high=request.args.get("filter_max_"+name,"").strip()
            else:
                kind="text"; low=request.args.get("filter_"+name,"").strip(); high=""
            filters.append({"name":name,"kind":kind,"lower":low,"upper":high})
            if kind in ("date","number") and (low or high):
                try:
                    validate_filter_range(kind, low, high)
                except (ValueError, InvalidOperation):
                    flash("Invalid range for "+name+": enter valid values and ensure the minimum/from does not exceed the maximum/to.","error")
                    invalid_filters=True
                    continue
            if kind=="date":
                if low: where.append("CAST("+qi(name)+" AS CHAR)>=%s"); params.append(low)
                if high: where.append("CAST("+qi(name)+" AS CHAR)<=%s"); params.append(high+(" 23:59:59" if "DATETIME" in typ and len(high)==10 else ""))
            elif kind=="number":
                try:
                    low_number=Decimal(low) if low else None
                    high_number=Decimal(high) if high else None
                except (ValueError, InvalidOperation):
                    flash("Invalid numeric range for "+name+". Correct the value before applying filters.","error")
                    invalid_filters=True
                    continue
                if low_number is not None:
                    where.append(qi(name)+">=%s"); params.append(low_number)
                if high_number is not None:
                    where.append(qi(name)+"<=%s"); params.append(high_number)
            elif low: where.append("CAST("+qi(name)+" AS CHAR) LIKE %s ESCAPE '!'"); params.append("%"+escape_like(low)+"%")
        if invalid_filters:
            cols=columns_for(conn,table); rows=[]
        else:
            cols,rows=get_rows(conn,table,search,where,params,250)
        pk=primary_key(table_info(conn,table))
        fk_errors=foreign_key_issue_count(conn)
    return render_template("table.html",table=table,label=LABELS[table],columns=[c["name"] for c in cols],rows=rows,pk=pk,search=search,filter_fields=filters,has_column_filters=any(f["lower"] or f["upper"] for f in filters),total=len(rows),fk_error_count=fk_errors,is_custom_table=table not in BUILTIN_TABLES)

def render_record_form(table,mode,record=None):
    with connect_db() as conn: cols=form_fields(conn,table)
    return render_template("form.html",table=table,label=LABELS[table],mode=mode,columns=cols,record=record or {})

@app.route("/table/<table>/add",methods=["GET","POST"])
def add_record(table):
    if table not in TABLES: abort(404)
    if request.method=="GET": return render_record_form(table,"add")
    with connect_db() as conn:
        cols=table_info(conn,table); data={}
        for col in cols:
            name=col["name"]; raw=request.form.get(name,"").strip()
            if col["identity"] and not raw: continue
            if not raw and col["default"] is not None and not field_required(table,col): continue
            if not raw and not field_required(table,col): data[name]=None
            elif not raw:
                flash(name.replace("_"," ").title()+" is required.","error"); return render_record_form(table,"add",request.form)
            else:
                try:
                    value=convert_value(raw,col)
                    if table=="VEHICLE" and name.lower()=="manufacture_year" and int(value)<=2000:
                        raise ValueError("Manufacture year must be later than 2000.")
                    if table=="FEEDBACK" and name.lower()=="rating" and int(value) not in (1,2,3,4,5):
                        raise ValueError("Rating must be 1, 2, 3, 4, or 5.")
                    data[name]=value
                except (ValueError,InvalidOperation) as exc:
                    flash(str(exc),"error"); return render_record_form(table,"add",request.form)
        if not data:
            flash("Please enter values for the record.","error"); return render_record_form(table,"add")
        try:
            names=list(data); sql="INSERT INTO "+qi(table)+" ("+",".join(qi(n) for n in names)+") VALUES ("+",".join(["%s"]*len(names))+")"
            cur=conn.cursor(); cur.execute(sql,[data[n] for n in names]); conn.commit(); cur.close()
            flash("Record added to "+LABELS[table]+".","success"); return redirect(url_for("table_page",table=table))
        except (Error,ValueError) as exc:
            conn.rollback()
            app.logger.warning("Could not add record to %s: %s", table, exc)
            flash("Could not add record: " + str(exc.msg if hasattr(exc, "msg") else exc)[:220], "error")
            return render_record_form(table,"add",data)

@app.route("/table/<table>/edit/<path:key>",methods=["GET","POST"])
def edit_record(table,key):
    if table not in TABLES: abort(404)
    with connect_db() as conn:
        pk=primary_key(table_info(conn,table))
        if not pk:
            flash("This table has a composite primary key or no single-column primary key. Edit it in SQL.","error"); return redirect(url_for("table_page",table=table))
        cur=conn.cursor(dictionary=True); cur.execute("SELECT * FROM "+qi(table)+" WHERE "+qi(pk)+"=%s",(key,)); record=cur.fetchone(); cur.close()
        if not record: abort(404)
        if request.method=="GET": return render_record_form(table,"edit",record)
        data={}
        for col in table_info(conn,table):
            name=col["name"]
            if name==pk: continue
            raw=request.form.get(name,"").strip()
            if not raw and col["default"] is not None and not field_required(table,col): continue
            if not raw and not field_required(table,col): data[name]=None
            elif not raw:
                flash(name.replace("_"," ").title()+" is required.","error"); return render_record_form(table,"edit",{**record,**request.form})
            else:
                try:
                    value=convert_value(raw,col)
                    if table=="VEHICLE" and name.lower()=="manufacture_year" and int(value)<=2000:
                        raise ValueError("Manufacture year must be later than 2000.")
                    if table=="FEEDBACK" and name.lower()=="rating" and int(value) not in (1,2,3,4,5):
                        raise ValueError("Rating must be 1, 2, 3, 4, or 5.")
                    data[name]=value
                except (ValueError,InvalidOperation) as exc:
                    flash(str(exc),"error"); return render_record_form(table,"edit",{**record,**request.form})
        try:
            if data:
                sql="UPDATE "+qi(table)+" SET "+",".join(qi(n)+"=%s" for n in data)+" WHERE "+qi(pk)+"=%s"
                cur=conn.cursor(); cur.execute(sql,list(data.values())+[key]); conn.commit(); cur.close()
            flash("Record updated in "+LABELS[table]+".","success"); return redirect(url_for("table_page",table=table))
        except (Error,ValueError) as exc:
            conn.rollback()
            app.logger.warning("Could not update record in %s: %s", table, exc)
            flash("Could not update record. Check the entered values and database constraints.","error")
            return render_record_form(table,"edit",{**record,**data})

@app.route("/table/<table>/delete/<path:key>",methods=["POST"])
def delete_record(table,key):
    if table not in TABLES: abort(404)
    with connect_db() as conn:
        pk=primary_key(table_info(conn,table))
        if not pk:
            flash("Delete is disabled for tables without a single-column primary key.","error"); return redirect(url_for("table_page",table=table))
        try:
            cur=conn.cursor(); cur.execute("DELETE FROM "+qi(table)+" WHERE "+qi(pk)+"=%s",(key,)); conn.commit()
            flash("Record deleted." if cur.rowcount else "No matching record.","success" if cur.rowcount else "error"); cur.close()
        except Error as exc:
            conn.rollback()
            app.logger.warning("Could not delete record from %s: %s", table, exc)
            if getattr(exc, "errno", None) == 1451:
                flash("Cannot delete this record because another table references it. This foreign key uses RESTRICT/NO ACTION; delete or reassign dependent records first.", "error")
            else:
                flash("Could not delete record: " + str(exc.msg if hasattr(exc, "msg") else exc)[:180], "error")
    return redirect(url_for("table_page",table=table))

REPORTS = {
    "vehicle_service_history": {
        "title": "Vehicle Service History",
        "description": "Service dates, vehicle, mechanic, service type and cost.",
        "sql": """SELECT v.Registration_No, vm.Brand, vm.Model_Name, sr.Service_Date, sr.Completion_Date, m.Mechanic_Name, st.Service_Name, sr.Cost
FROM SERVICE_RECORD sr
JOIN APPOINTMENT a ON sr.Appointment_ID=a.Appointment_ID
JOIN VEHICLE v ON a.Vehicle_ID=v.Vehicle_ID
JOIN VEHICLE_MODEL vm ON v.Model_ID=vm.Model_ID
JOIN MECHANIC m ON a.Mechanic_ID=m.Mechanic_ID
JOIN SERVICE_TYPE st ON a.Service_Type_ID=st.Service_Type_ID
ORDER BY sr.Service_Date DESC, v.Registration_No"""
    },
    "upcoming_appointments": {
        "title": "Upcoming Appointments",
        "description": "Future booked or in-progress appointments with customer and vehicle details.",
        "sql": """SELECT a.Appointment_ID, a.Appointment_Date, a.Status, c.Customer_Name, v.Registration_No, vm.Brand, vm.Model_Name, m.Mechanic_Name, st.Service_Name
FROM APPOINTMENT a
JOIN VEHICLE v ON a.Vehicle_ID=v.Vehicle_ID
JOIN CUSTOMER c ON v.Customer_ID=c.Customer_ID
JOIN VEHICLE_MODEL vm ON v.Model_ID=vm.Model_ID
JOIN MECHANIC m ON a.Mechanic_ID=m.Mechanic_ID
JOIN SERVICE_TYPE st ON a.Service_Type_ID=st.Service_Type_ID
WHERE a.Appointment_Date >= NOW() AND a.Status IN ('Booked','In Progress')
ORDER BY a.Appointment_Date"""
    },
    "unpaid_invoices": {
        "title": "Unpaid Invoices",
        "description": "Invoices not fully paid, including the remaining balance after recorded payments.",
        "sql": """SELECT i.Invoice_ID, i.Invoice_Date, c.Customer_Name, v.Registration_No, i.Payment_Status, i.Total_Amount,
GREATEST(i.Total_Amount-COALESCE(p.Amount_Paid,0),0) AS Amount_Due
FROM INVOICE i
JOIN SERVICE_RECORD sr ON i.Service_ID=sr.Service_ID
JOIN APPOINTMENT a ON sr.Appointment_ID=a.Appointment_ID
JOIN VEHICLE v ON a.Vehicle_ID=v.Vehicle_ID
JOIN CUSTOMER c ON v.Customer_ID=c.Customer_ID
LEFT JOIN (SELECT Invoice_ID, SUM(Amount) AS Amount_Paid FROM PAYMENT GROUP BY Invoice_ID) p ON p.Invoice_ID=i.Invoice_ID
WHERE i.Payment_Status <> 'Paid' OR GREATEST(i.Total_Amount-COALESCE(p.Amount_Paid,0),0) > 0
ORDER BY i.Invoice_Date DESC"""
    },
    "mechanic_workload": {
        "title": "Mechanic Workload",
        "description": "Assigned appointments, completed jobs and open jobs for each mechanic.",
        "sql": """SELECT m.Mechanic_ID, m.Mechanic_Name,
COUNT(a.Appointment_ID) AS Assigned_Appointments,
SUM(CASE WHEN a.Status='Completed' THEN 1 ELSE 0 END) AS Completed_Jobs,
SUM(CASE WHEN a.Status IN ('Booked','In Progress') THEN 1 ELSE 0 END) AS Open_Jobs
FROM MECHANIC m
LEFT JOIN APPOINTMENT a ON a.Mechanic_ID=m.Mechanic_ID AND a.Status <> 'Cancelled'
GROUP BY m.Mechanic_ID,m.Mechanic_Name
ORDER BY Assigned_Appointments DESC,m.Mechanic_Name"""
    },
    "most_serviced_vehicles": {
        "title": "Most-Serviced Vehicles",
        "description": "Vehicles ranked by their number of service records.",
        "sql": """SELECT v.Registration_No, vm.Brand, vm.Model_Name, COUNT(sr.Service_ID) AS Service_Count
FROM VEHICLE v
JOIN VEHICLE_MODEL vm ON v.Model_ID=vm.Model_ID
LEFT JOIN APPOINTMENT a ON v.Vehicle_ID=a.Vehicle_ID
LEFT JOIN SERVICE_RECORD sr ON a.Appointment_ID=sr.Appointment_ID
GROUP BY v.Vehicle_ID,v.Registration_No,vm.Brand,vm.Model_Name
ORDER BY Service_Count DESC,v.Registration_No"""
    },
    "monthly_revenue": {
        "title": "Monthly Revenue",
        "description": "Monthly invoiced totals and payments recorded against invoices.",
        "sql": """SELECT DATE_FORMAT(i.Invoice_Date,'%Y-%m') AS Revenue_Month,
SUM(i.Total_Amount) AS Total_Invoiced,
SUM(COALESCE(p.Amount_Paid,0)) AS Total_Paid
FROM INVOICE i
LEFT JOIN (SELECT Invoice_ID,SUM(Amount) AS Amount_Paid FROM PAYMENT GROUP BY Invoice_ID) p ON p.Invoice_ID=i.Invoice_ID
GROUP BY DATE_FORMAT(i.Invoice_Date,'%Y-%m')
ORDER BY Revenue_Month DESC"""
    },
    "low_stock_parts": {
        "title": "Low-Stock Parts",
        "description": "Inventory at or below reorder level, with supplier details.",
        "sql": """SELECT p.Part_ID,p.Part_Name,p.Category,i.Quantity_In_Stock,i.Reorder_Level,s.Supplier_Name
FROM INVENTORY i
JOIN PART p ON i.Part_ID=p.Part_ID
JOIN SUPPLIER s ON p.Supplier_ID=s.Supplier_ID
WHERE i.Quantity_In_Stock <= i.Reorder_Level
ORDER BY i.Quantity_In_Stock ASC,p.Part_Name"""
    },
    "customer_service_summary": {
        "title": "Customer Service Summary",
        "description": "Vehicles owned, appointments attended and total invoiced spending per customer.",
        "sql": """SELECT c.Customer_ID,c.Customer_Name,
COALESCE(v.Vehicle_Count,0) AS Vehicles_Owned,
COALESCE(a.Visit_Count,0) AS Total_Visits,
COALESCE(i.Total_Spending,0) AS Total_Spending
FROM CUSTOMER c
LEFT JOIN (SELECT Customer_ID,COUNT(*) AS Vehicle_Count FROM VEHICLE GROUP BY Customer_ID) v ON v.Customer_ID=c.Customer_ID
LEFT JOIN (SELECT v.Customer_ID,COUNT(a.Appointment_ID) AS Visit_Count FROM VEHICLE v LEFT JOIN APPOINTMENT a ON a.Vehicle_ID=v.Vehicle_ID GROUP BY v.Customer_ID) a ON a.Customer_ID=c.Customer_ID
LEFT JOIN (SELECT v.Customer_ID,SUM(i.Total_Amount) AS Total_Spending FROM VEHICLE v JOIN APPOINTMENT a ON a.Vehicle_ID=v.Vehicle_ID JOIN SERVICE_RECORD sr ON sr.Appointment_ID=a.Appointment_ID JOIN INVOICE i ON i.Service_ID=sr.Service_ID GROUP BY v.Customer_ID) i ON i.Customer_ID=c.Customer_ID
ORDER BY Total_Spending DESC,c.Customer_Name"""
    },
    "warranty_expiry": {
        "title": "Warranty Expiry",
        "description": "Expired warranties and warranties ending within the next 30 days.",
        "sql": """SELECT w.Warranty_ID,p.Part_Name,w.Start_Date,w.End_Date,
CASE WHEN w.End_Date < CURDATE() THEN 'Expired' ELSE 'Expires within 30 days' END AS Expiry_Status,w.Details
FROM WARRANTY w
LEFT JOIN PART p ON w.Part_ID=p.Part_ID
WHERE w.End_Date <= DATE_ADD(CURDATE(),INTERVAL 30 DAY)
ORDER BY w.End_Date"""
    },
    "supplier_inventory": {
        "title": "Supplier Inventory",
        "description": "Supplier, part, current quantity, reorder level and unit price.",
        "sql": """SELECT s.Supplier_Name,p.Part_ID,p.Part_Name,p.Category,i.Quantity_In_Stock,i.Reorder_Level,p.Unit_Price
FROM SUPPLIER s
JOIN PART p ON p.Supplier_ID=s.Supplier_ID
LEFT JOIN INVENTORY i ON i.Part_ID=p.Part_ID
ORDER BY s.Supplier_Name,p.Part_Name"""
    },
    "appointment_details": {
        "title": "Appointment Details (JOIN)",
        "description": "Joins appointments, customers, vehicles, service types and mechanics.",
        "sql": """SELECT a.Appointment_ID,a.Appointment_Date,a.Status,c.Customer_Name,v.Registration_No,st.Service_Name,m.Mechanic_Name
FROM APPOINTMENT a JOIN VEHICLE v ON a.Vehicle_ID=v.Vehicle_ID
JOIN CUSTOMER c ON v.Customer_ID=c.Customer_ID
JOIN SERVICE_TYPE st ON a.Service_Type_ID=st.Service_Type_ID
JOIN MECHANIC m ON a.Mechanic_ID=m.Mechanic_ID
ORDER BY a.Appointment_Date DESC"""
    },
    "appointments_by_status": {
        "title": "Completed Appointments (WHERE + ORDER BY)",
        "description": "Demonstrates filtering and sorting.",
        "sql": """SELECT Appointment_ID,Appointment_Date,Vehicle_ID,Status FROM APPOINTMENT WHERE Status='Completed' ORDER BY Appointment_Date DESC"""
    },
    "repeat_customers": {
        "title": "Customers with More Than One Appointment (GROUP BY + HAVING)",
        "description": "Demonstrates grouped results and HAVING.",
        "sql": """SELECT c.Customer_ID,c.Customer_Name,COUNT(a.Appointment_ID) AS Appointment_Count
FROM CUSTOMER c JOIN VEHICLE v ON c.Customer_ID=v.Customer_ID
JOIN APPOINTMENT a ON v.Vehicle_ID=a.Vehicle_ID
GROUP BY c.Customer_ID,c.Customer_Name
HAVING COUNT(a.Appointment_ID)>1 ORDER BY Appointment_Count DESC"""
    },
    "service_aggregates": {
        "title": "Service Record Aggregates (COUNT / SUM / AVG / MAX / MIN)",
        "description": "Demonstrates aggregate functions.",
        "sql": """SELECT COUNT(*) AS Service_Count,COALESCE(SUM(Cost),0) AS Total_Cost,COALESCE(AVG(Cost),0) AS Average_Cost,COALESCE(MAX(Cost),0) AS Highest_Cost,COALESCE(MIN(Cost),0) AS Lowest_Cost FROM SERVICE_RECORD"""
    },
    "above_average_mileage": {
        "title": "Vehicles with Above-Average Mileage (Subquery)",
        "description": "Demonstrates a subquery.",
        "sql": """SELECT Vehicle_ID,Registration_No,Mileage FROM VEHICLE WHERE Mileage>(SELECT AVG(Mileage) FROM VEHICLE) ORDER BY Mileage DESC"""
    },
    "customer_vehicle_appointment": {
        "title": "Customer-Vehicle-Appointment View",
        "description": "Demonstrates the existing database view.",
        "sql": """SELECT * FROM CustomerVehicleAppointment"""
    }
}

@app.route("/reports", methods=["GET"])
def reports():
    selected_key = request.args.get("report", "").strip()
    report_result = None
    if selected_key:
        definition = REPORTS.get(selected_key)
        if definition is None:
            flash("Choose a report from the list before running a query.", "error")
            selected_key = ""
        else:
            try:
                with connect_db() as conn:
                    cur = conn.cursor(dictionary=True)
                    cur.execute(definition["sql"])
                    rows = cur.fetchall()
                    columns = [item[0] for item in cur.description] if cur.description else []
                    cur.close()
                report_result = {
                    "key": selected_key,
                    "title": definition["title"],
                    "description": definition["description"],
                    "sql": definition["sql"],
                    "display_sql": sqlparse.format(definition["sql"], reindent=True, keyword_case="upper", indent_width=4, wrap_after=88),
                    "rows": rows,
                    "columns": columns,
                    "error": None,
                }
            except Error:
                app.logger.exception("SQL report failed: %s", selected_key)
                report_result = {
                    "key": selected_key,
                    "title": definition["title"],
                    "description": definition["description"],
                    "sql": definition["sql"],
                    "display_sql": sqlparse.format(definition["sql"], reindent=True, keyword_case="upper", indent_width=4, wrap_after=88),
                    "rows": [],
                    "columns": [],
                    "error": "This report could not be run. Check the database schema and connection, then try again.",
                }
    options = [{"key": key, "title": value["title"], "description": value["description"]} for key, value in REPORTS.items()]
    return render_template("reports.html", report_options=options, selected_report=selected_key, report_result=report_result)

@app.route("/health")
def health():
    with connect_db() as conn:
        cur=conn.cursor()
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'",(DB_NAME,)); tables=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA=%s",(DB_NAME,)); views=cur.fetchone()[0]
        cur.close()
        fk_violations=foreign_key_issue_count(conn)
    return {"database":DB_NAME,"backend":"mysql","table_count":tables,"view_count":views,"expected_tables":len(TABLES),"foreign_key_violations":fk_violations}

@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html",title="Request rejected",message="This request could not be verified. Reload the page and try again."),400

@app.errorhandler(404)
def not_found(error):
    return render_template("error.html",title="Not found",message="That table or record was not found."),404

@app.errorhandler(Error)
def db_error(exc):
    app.logger.exception("MySQL query failed")
    return render_template("error.html",title="Database error",message="Check that MySQL Server is running and .env matches your database."),500

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")),debug=os.getenv("FLASK_DEBUG","0")=="1")
