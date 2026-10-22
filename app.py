import os
from decimal import Decimal, InvalidOperation
from flask import Flask, abort, flash, redirect, render_template, request, url_for
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "local-dev-key-change-me")
TABLES = {
 "CUSTOMER":"Customer_ID","VEHICLE_MODEL":"Model_ID","VEHICLE":"Vehicle_ID",
 "MECHANIC":"Mechanic_ID","SERVICE_TYPE":"Service_Type_ID","APPOINTMENT":"Appointment_ID",
 "SERVICE_RECORD":"Service_ID","SUPPLIER":"Supplier_ID","PART":"Part_ID",
 "SERVICE_PART":None,"INVENTORY":"Inventory_ID","INVOICE":"Invoice_ID",
 "PAYMENT":"Payment_ID","WARRANTY":"Warranty_ID","FEEDBACK":"Feedback_ID"
}
LABELS = {t:t.replace("_"," ").title() for t in TABLES}

def db():
 return mysql.connector.connect(host=os.getenv("MYSQL_HOST","127.0.0.1"),port=int(os.getenv("MYSQL_PORT","3306")),user=os.getenv("MYSQL_USER","vehicle_app"),password=os.getenv("MYSQL_PASSWORD",""),database=os.getenv("MYSQL_DATABASE","vehicle_service"))

def columns(conn, table):
 cur=conn.cursor(dictionary=True); cur.execute("SHOW COLUMNS FROM "+table); data=cur.fetchall(); cur.close(); return data

def get_rows(conn, table, q=""):
 cols=columns(conn,table); names=[c["Field"] for c in cols]; cur=conn.cursor(dictionary=True)
 if q.strip():
  where=" OR ".join("CAST("+n+" AS CHAR) LIKE %s" for n in names)
  cur.execute("SELECT * FROM "+table+" WHERE "+where+" LIMIT 500",tuple(["%"+q.strip()+"%"]*len(names)))
 else: cur.execute("SELECT * FROM "+table+" LIMIT 500")
 rows=cur.fetchall(); cur.close(); return cols,rows

def fields_for(conn, table, record=None):
 cur=conn.cursor()
 cur.execute("SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",(os.getenv("MYSQL_DATABASE","vehicle_service"),table))
 meta=cur.fetchall(); cur.close(); fields=[]
 for name,typ,nullable,default,extra in meta:
  if "auto_increment" in (extra or "").lower(): continue
  options=[]
  if typ.startswith("enum("): options=[v.replace("''","'") for v in typ[5:-1].split("','")]
  fields.append({"name":name,"type":typ.lower(),"required":nullable=="NO" and default is None,"options":options,"value":str(record.get(name) or "") if record else ""})
 return fields

def value_for(raw, field):
 if raw=="": return None
 typ=field["type"]
 if any(x in typ for x in ("int","decimal","float","double")):
  try: return Decimal(raw) if any(x in typ for x in ("decimal","float","double")) else int(raw)
  except (ValueError,InvalidOperation): raise ValueError("Enter a valid number for "+field["name"])
 if "datetime" in typ and "T" in raw: return raw.replace("T"," ")
 return raw

@app.route("/")
def index():
 conn=db()
 try:
  cur=conn.cursor(); counts={}
  for t in TABLES: cur.execute("SELECT COUNT(*) FROM "+t); counts[t]=cur.fetchone()[0]
  cur.close()
 finally: conn.close()
 return render_template("index.html",tables=TABLES,labels=LABELS,counts=counts,total=sum(counts.values()))

@app.route("/tables/<table>")
def table_view(table):
 if table not in TABLES: abort(404)
 conn=db()
 try: cols,rows=get_rows(conn,table,request.args.get("q",""))
 finally: conn.close()
 return render_template("table.html",tables=TABLES,labels=LABELS,table=table,label=LABELS[table],columns=cols,rows=rows,query=request.args.get("q",""))

@app.route("/tables/<table>/new",methods=["GET","POST"])
def create_record(table):
 if table not in TABLES: abort(404)
 conn=db()
 try:
  fields=fields_for(conn,table)
  if request.method=="POST":
   try:
    names=[]; vals=[]
    for f in fields:
     raw=request.form.get(f["name"],"").strip()
     if f["required"] and not raw: raise ValueError(f["name"]+" is required.")
     if raw: names.append(f["name"]); vals.append(value_for(raw,f))
    if not names: raise ValueError("Enter at least one value.")
    cur=conn.cursor(); cur.execute("INSERT INTO "+table+" ("+",".join(names)+") VALUES ("+",".join(["%s"]*len(names))+")",vals); conn.commit(); cur.close()
    flash("Record added successfully.","success"); return redirect(url_for("table_view",table=table))
   except (ValueError,Error) as e: conn.rollback(); flash(str(e),"error")
  return render_template("form.html",tables=TABLES,table=table,label=LABELS[table],fields=fields,heading="Add record")
 finally: conn.close()

@app.route("/tables/<table>/edit",methods=["GET","POST"])
def edit_record(table):
 if table not in TABLES: abort(404)
 pk=TABLES[table]
 if not pk: flash("This table has a composite primary key. Edit it using MySQL Workbench or SQL.","error"); return redirect(url_for("table_view",table=table))
 rid=request.args.get("id",""); conn=db()
 try:
  cur=conn.cursor(dictionary=True); cur.execute("SELECT * FROM "+table+" WHERE "+pk+"=%s",(rid,)); record=cur.fetchone(); cur.close()
  if not record: abort(404)
  fields=fields_for(conn,table,record)
  if request.method=="POST":
   try:
    sets=[]; vals=[]
    for f in fields:
     raw=request.form.get(f["name"],"").strip()
     if f["required"] and not raw: raise ValueError(f["name"]+" is required.")
     sets.append(f["name"]+"=%s"); vals.append(value_for(raw,f))
    vals.append(rid); cur=conn.cursor(); cur.execute("UPDATE "+table+" SET "+",".join(sets)+" WHERE "+pk+"=%s",vals); conn.commit(); cur.close()
    flash("Record updated successfully.","success"); return redirect(url_for("table_view",table=table))
   except (ValueError,Error) as e:
    conn.rollback(); flash(str(e),"error")
    for f in fields: f["value"]=request.form.get(f["name"],"")
  return render_template("form.html",tables=TABLES,table=table,label=LABELS[table],fields=fields,heading="Edit record")
 finally: conn.close()

@app.post("/tables/<table>/delete")
def delete_record(table):
 if table not in TABLES: abort(404)
 pk=TABLES[table]
 if not pk: flash("This table has a composite key. Delete it using Workbench or SQL.","error"); return redirect(url_for("table_view",table=table))
 conn=db()
 try:
  cur=conn.cursor(); cur.execute("DELETE FROM "+table+" WHERE "+pk+"=%s",(request.form.get("id",""),)); conn.commit()
  flash("Record deleted." if cur.rowcount else "No matching record.","success" if cur.rowcount else "error"); cur.close()
 except Error as e: conn.rollback(); flash("Could not delete record; another table may reference it. "+str(e),"error")
 finally: conn.close()
 return redirect(url_for("table_view",table=table))

@app.route("/reports")
def reports():
 conn=db()
 try:
  cur=conn.cursor(dictionary=True)
  cur.execute("SELECT c.Customer_Name,v.Registration_No,vm.Brand,vm.Model_Name,a.Appointment_Date,a.Status,st.Service_Name,st.Price FROM CUSTOMER c JOIN VEHICLE v ON c.Customer_ID=v.Customer_ID JOIN VEHICLE_MODEL vm ON v.Model_ID=vm.Model_ID LEFT JOIN APPOINTMENT a ON v.Vehicle_ID=a.Vehicle_ID LEFT JOIN SERVICE_TYPE st ON a.Service_Type_ID=st.Service_Type_ID ORDER BY a.Appointment_Date DESC")
  appointments=cur.fetchall()
  cur.execute("SELECT Status,COUNT(*) AS Total FROM APPOINTMENT GROUP BY Status ORDER BY Total DESC"); statuses=cur.fetchall()
  cur.execute("SELECT Payment_Status,COUNT(*) AS Total,SUM(Total_Amount) AS Amount FROM INVOICE GROUP BY Payment_Status ORDER BY Amount DESC"); invoices=cur.fetchall()
  cur.close()
 finally: conn.close()
 return render_template("reports.html",tables=TABLES,appointments=appointments,statuses=statuses,invoices=invoices)

@app.errorhandler(Error)
def db_error(exc):
 app.logger.exception("MySQL query failed")
 return render_template("error.html",tables=TABLES,message="MySQL connection/query failed. Check that MySQL Server is running and .env matches your server.",detail=str(exc)),500

if __name__=="__main__": app.run(host="127.0.0.1",port=5000,debug=True)
