import os
import re
import hmac
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from contextlib import contextmanager
import mysql.connector
from mysql.connector import Error
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
DB_NAME = os.getenv("MYSQL_DATABASE", "vehicle_service")
TABLES = ["CUSTOMER","VEHICLE_MODEL","VEHICLE","MECHANIC","SERVICE_TYPE","APPOINTMENT","SERVICE_RECORD","SUPPLIER","PART","SERVICE_PART","INVENTORY","INVOICE","PAYMENT","WARRANTY","FEEDBACK"]
LABELS = {t:t.replace("_"," ").title() for t in TABLES}
PKS = {"CUSTOMER":"Customer_ID","VEHICLE_MODEL":"Model_ID","VEHICLE":"Vehicle_ID","MECHANIC":"Mechanic_ID","SERVICE_TYPE":"Service_Type_ID","APPOINTMENT":"Appointment_ID","SERVICE_RECORD":"Service_ID","SUPPLIER":"Supplier_ID","PART":"Part_ID","SERVICE_PART":None,"INVENTORY":"Inventory_ID","INVOICE":"Invoice_ID","PAYMENT":"Payment_ID","WARRANTY":"Warranty_ID","FEEDBACK":"Feedback_ID"}

def db():
    return mysql.connector.connect(host=os.getenv("MYSQL_HOST","127.0.0.1"), port=int(os.getenv("MYSQL_PORT","3306")), user=os.getenv("MYSQL_USER","root"), password=os.getenv("MYSQL_PASSWORD",""), database=DB_NAME)

@app.before_request
def protect_post_requests():
    if request.method == "POST":
        expected = session.get("_csrf_token")
        submitted = request.form.get("csrf_token", "")
        if not expected or not submitted or not hmac.compare_digest(expected, submitted):
            abort(400)

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
        col["notnull"] and col["default"] is None and not col["pk"]
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
    return {"nav_tables":TABLES,"labels":LABELS,"db_backend":"MySQL"}

@app.route("/")
def index():
    with connect_db() as conn:
        counts={t:count_rows(conn,t) for t in TABLES}
        cur=conn.cursor()
        cur.execute("SELECT COUNT(*) FROM APPOINTMENT WHERE Status='Completed'"); completed=cur.fetchone()[0]
        cur.close()
    return render_template("index.html",counts=counts,customer_count=counts["CUSTOMER"],vehicle_count=counts["VEHICLE"],appointment_count=counts["APPOINTMENT"],completed=completed)

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
    return render_template("table.html",table=table,label=LABELS[table],columns=[c["name"] for c in cols],rows=rows,pk=pk,search=search,filter_fields=filters,has_column_filters=any(f["lower"] or f["upper"] for f in filters),total=len(rows),fk_error_count=fk_errors)

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
            conn.rollback(); flash("Could not add record: "+str(exc),"error"); return render_record_form(table,"add",data)

@app.route("/table/<table>/edit/<path:key>",methods=["GET","POST"])
def edit_record(table,key):
    if table not in TABLES: abort(404)
    pk=PKS[table]
    if not pk:
        flash("This table has a composite primary key. Edit it in MySQL Workbench or SQL.","error"); return redirect(url_for("table_page",table=table))
    with connect_db() as conn:
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
            conn.rollback(); flash("Could not update record: "+str(exc),"error"); return render_record_form(table,"edit",{**record,**data})

@app.route("/table/<table>/delete/<path:key>",methods=["POST"])
def delete_record(table,key):
    if table not in TABLES: abort(404)
    pk=PKS[table]
    if not pk:
        flash("Delete is disabled for this composite-key table.","error"); return redirect(url_for("table_page",table=table))
    with connect_db() as conn:
        try:
            cur=conn.cursor(); cur.execute("DELETE FROM "+qi(table)+" WHERE "+qi(pk)+"=%s",(key,)); conn.commit()
            flash("Record deleted." if cur.rowcount else "No matching record.","success" if cur.rowcount else "error"); cur.close()
        except Error as exc:
            conn.rollback(); flash("Could not delete record. It may be referenced by another record. "+str(exc),"error")
    return redirect(url_for("table_page",table=table))

@app.route("/reports")
def reports():
    definitions=[
        ("Appointment details (JOIN)","SELECT a.Appointment_ID,a.Appointment_Date,a.Status,c.Customer_Name,v.Registration_No,st.Service_Name,m.Mechanic_Name FROM APPOINTMENT a JOIN VEHICLE v ON a.Vehicle_ID=v.Vehicle_ID JOIN CUSTOMER c ON v.Customer_ID=c.Customer_ID JOIN SERVICE_TYPE st ON a.Service_Type_ID=st.Service_Type_ID JOIN MECHANIC m ON a.Mechanic_ID=m.Mechanic_ID ORDER BY a.Appointment_Date DESC"),
        ("Appointments by status (WHERE + ORDER BY)","SELECT Appointment_ID,Appointment_Date,Vehicle_ID,Status FROM APPOINTMENT WHERE Status='Completed' ORDER BY Appointment_Date DESC"),
        ("Customers with more than one appointment (GROUP BY + HAVING)","SELECT c.Customer_ID,c.Customer_Name,COUNT(a.Appointment_ID) AS Appointment_Count FROM CUSTOMER c JOIN VEHICLE v ON c.Customer_ID=v.Customer_ID JOIN APPOINTMENT a ON v.Vehicle_ID=a.Vehicle_ID GROUP BY c.Customer_ID,c.Customer_Name HAVING COUNT(a.Appointment_ID)>1 ORDER BY Appointment_Count DESC"),
        ("Service record aggregates (COUNT / SUM / AVG / MAX / MIN)","SELECT COUNT(*) AS Service_Count,COALESCE(SUM(Cost),0) AS Total_Cost,COALESCE(AVG(Cost),0) AS Average_Cost,COALESCE(MAX(Cost),0) AS Highest_Cost,COALESCE(MIN(Cost),0) AS Lowest_Cost FROM SERVICE_RECORD"),
        ("Vehicles with above-average mileage (subquery)","SELECT Vehicle_ID,Registration_No,Mileage FROM VEHICLE WHERE Mileage>(SELECT AVG(Mileage) FROM VEHICLE) ORDER BY Mileage DESC"),
        ("Customer-vehicle-appointment view","SELECT * FROM CustomerVehicleAppointment")
    ]
    results=[]
    with connect_db() as conn:
        for title,sql in definitions:
            try:
                cur=conn.cursor(dictionary=True); cur.execute(sql); rows=cur.fetchall(); cur.close()
                results.append({"title":title,"sql":sql,"rows":rows,"error":None})
            except Error as exc: results.append({"title":title,"sql":sql,"rows":[],"error":str(exc)})
    return render_template("reports.html",reports_data=results)

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
