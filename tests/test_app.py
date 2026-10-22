import os
import re
import unittest
import uuid
from unittest.mock import patch

import app as project


class FilterHelperTests(unittest.TestCase):
    def test_like_wildcards_are_treated_as_literal_text(self):
        self.assertEqual(project.escape_like("red_%!"), "red!_!%!!")

    def test_valid_numeric_range(self):
        self.assertTrue(project.validate_filter_range("number", "100", "200"))
        self.assertTrue(project.validate_filter_range("number", "100", ""))

    def test_reversed_numeric_range_is_rejected(self):
        with self.assertRaises(ValueError):
            project.validate_filter_range("number", "50000", "10000")

    def test_non_finite_numeric_range_is_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    project.validate_filter_range("number", value, "")

    def test_date_range_validation(self):
        self.assertTrue(project.validate_filter_range("date", "2026-10-01", "2026-10-31"))
        with self.assertRaises(ValueError):
            project.validate_filter_range("date", "2026-10-31", "2026-10-01")
        with self.assertRaises(ValueError):
            project.validate_filter_range("date", "not-a-date", "")


class RouteTests(unittest.TestCase):
    def setUp(self):
        project.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = project.app.test_client()
        self.columns = [
            {"name": "Mileage", "type": "DECIMAL(10,2)", "notnull": False,
             "pk": False, "identity": False, "default": None, "fk": None},
            {"name": "Color", "type": "VARCHAR(50)", "notnull": False,
             "pk": False, "identity": False, "default": None, "fk": None},
            {"name": "Appointment_Date", "type": "DATETIME", "notnull": True,
             "pk": False, "identity": False, "default": None, "fk": None},
        ]

    def fake_connection(self):
        class Connection:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_value, traceback):
                return False
        return Connection()

    def table_patches(self):
        return (
            patch.object(project, "connect_db", side_effect=self.fake_connection),
            patch.object(project, "table_info", return_value=self.columns),
            patch.object(project, "columns_for", return_value=self.columns),
            patch.object(project, "foreign_key_issue_count", return_value=0),
        )

    def test_invalid_numeric_range_does_not_query_records(self):
        p1, p2, p3, p4 = self.table_patches()
        with p1, p2, p3, p4, patch.object(project, "get_rows") as get_rows:
            response = self.client.get("/table/VEHICLE?filter_min_Mileage=50000&filter_max_Mileage=10000")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid range", response.data)
        self.assertIn(b"No matching records", response.data)
        get_rows.assert_not_called()

    def test_partial_text_filter_escapes_sql_wildcards(self):
        p1, p2, p3, p4 = self.table_patches()
        with p1, p2, p3, p4, patch.object(project, "get_rows", return_value=(self.columns, [])) as get_rows:
            response = self.client.get("/table/VEHICLE?filter_Color=red_%25")
        self.assertEqual(response.status_code, 200)
        args = get_rows.call_args.args
        self.assertIn("LIKE %s ESCAPE '!'", args[3][0])
        self.assertEqual(args[4], ["%red!_!%%"])

    def test_global_search_and_multiple_column_filters_are_combined(self):
        p1, p2, p3, p4 = self.table_patches()
        with p1, p2, p3, p4, patch.object(project, "get_rows", return_value=(self.columns, [])) as get_rows:
            response = self.client.get("/table/VEHICLE?q=swift&filter_Color=red&filter_min_Mileage=10000")
        self.assertEqual(response.status_code, 200)
        args = get_rows.call_args.args
        self.assertEqual(args[2], "swift")
        self.assertEqual(len(args[3]), 2)
        self.assertIn("Mileage", args[3][0])
        self.assertIn("LIKE %s ESCAPE '!'", args[3][1])
        self.assertEqual(str(args[4][0]), "10000")
        self.assertEqual(args[4][1], "%red%")

    def test_date_range_is_applied_to_the_database_query(self):
        p1, p2, p3, p4 = self.table_patches()
        with p1, p2, p3, p4, patch.object(project, "get_rows", return_value=(self.columns, [])) as get_rows:
            response = self.client.get("/table/VEHICLE?filter_from_Appointment_Date=2026-10-01&filter_to_Appointment_Date=2026-10-31")
        self.assertEqual(response.status_code, 200)
        args = get_rows.call_args.args
        self.assertEqual(len(args[3]), 2)
        self.assertIn("Appointment_Date", args[3][0])
        self.assertIn("Appointment_Date", args[3][1])
        self.assertEqual(args[4], ["2026-10-01", "2026-10-31 23:59:59"])

    def test_report_selector_loads_without_running_a_query(self):
        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Run Query", response.data)
        self.assertIn(b"Vehicle Service History", response.data)

    def test_post_without_csrf_token_is_rejected_before_database_access(self):
        response = self.client.post("/table/CUSTOMER/add", data={"Customer_Name": "Test"})
        self.assertEqual(response.status_code, 400)

    def test_all_reports_are_select_whitelisted(self):
        self.assertGreaterEqual(len(project.REPORTS), 16)
        for key, definition in project.REPORTS.items():
            with self.subTest(report=key):
                self.assertTrue(definition["sql"].lstrip().upper().startswith("SELECT"))


@unittest.skipUnless(os.getenv("RUN_DB_INTEGRATION") == "1", "Requires the disposable MySQL integration database")
class DatabaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        project.app.config.update(TESTING=True, SECRET_KEY="integration-test-secret")
        self.client = project.app.test_client()

    def csrf_from(self, response):
        html = response.get_data(as_text=True)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        self.assertIsNotNone(match, "Expected a CSRF token on the form")
        return match.group(1)

    def test_every_report_executes_without_sql_error(self):
        for key, definition in project.REPORTS.items():
            with self.subTest(report=key):
                response = self.client.get("/reports", query_string={"report": key})
                self.assertEqual(response.status_code, 200)
                self.assertIn(definition["title"].encode(), response.data)
                self.assertNotIn(b"Query error", response.data)

    def test_health_reports_expected_schema_and_no_orphans(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["table_count"], 15)
        self.assertGreaterEqual(data["view_count"], 1)
        self.assertEqual(data["foreign_key_violations"], 0)

    def test_customer_create_edit_delete_cycle(self):
        suffix = uuid.uuid4().hex
        email = "dbms-test-" + suffix + "@example.test"
        phone = "9" + suffix[:14]
        customer_id = None
        try:
            form = self.client.get("/table/CUSTOMER/add")
            self.assertEqual(form.status_code, 200)
            response = self.client.post("/table/CUSTOMER/add", data={
                "csrf_token": self.csrf_from(form),
                "Customer_Name": "DBMS Test Customer",
                "Phone": phone,
                "Email": email,
                "Address": "Temporary test record",
            })
            self.assertEqual(response.status_code, 302)

            conn = project.db()
            try:
                cur = conn.cursor()
                cur.execute("SELECT Customer_ID FROM CUSTOMER WHERE Email=%s", (email,))
                found = cur.fetchone()
                self.assertIsNotNone(found)
                customer_id = found[0]
                cur.close()
            finally:
                conn.close()

            edit_form = self.client.get("/table/CUSTOMER/edit/" + str(customer_id))
            self.assertEqual(edit_form.status_code, 200)
            response = self.client.post("/table/CUSTOMER/edit/" + str(customer_id), data={
                "csrf_token": self.csrf_from(edit_form),
                "Customer_Name": "DBMS Test Customer Edited",
                "Phone": phone,
                "Email": email,
                "Address": "Updated test record",
            })
            self.assertEqual(response.status_code, 302)

            conn = project.db()
            try:
                cur = conn.cursor()
                cur.execute("SELECT Customer_Name FROM CUSTOMER WHERE Customer_ID=%s", (customer_id,))
                self.assertEqual(cur.fetchone()[0], "DBMS Test Customer Edited")
                cur.close()
            finally:
                conn.close()

            table_page = self.client.get("/table/CUSTOMER")
            response = self.client.post("/table/CUSTOMER/delete/" + str(customer_id), data={
                "csrf_token": self.csrf_from(table_page)
            })
            self.assertEqual(response.status_code, 302)
            customer_id = None
        finally:
            conn = project.db()
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM CUSTOMER WHERE Email=%s", (email,))
                conn.commit()
                cur.close()
            finally:
                conn.close()

    def test_database_rejects_orphan_vehicle_and_negative_mileage(self):
        conn = project.db()
        try:
            cur = conn.cursor()
            with self.assertRaises(project.Error):
                cur.execute(
                    "INSERT INTO VEHICLE (Registration_No,Customer_ID,Model_ID,Manufacture_Year,Mileage) VALUES (%s,%s,%s,%s,%s)",
                    ("TEST-FK-" + uuid.uuid4().hex[:10], 999999, 201, 2022, 1000),
                )
            conn.rollback()
            with self.assertRaises(project.Error):
                cur.execute(
                    "INSERT INTO VEHICLE (Registration_No,Customer_ID,Model_ID,Manufacture_Year,Mileage) VALUES (%s,%s,%s,%s,%s)",
                    ("TEST-CK-" + uuid.uuid4().hex[:10], 101, 201, 2022, -1),
                )
            conn.rollback()
            cur.close()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
