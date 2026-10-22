USE vehicle_service;

-- Add-on demo data for the SQL Query reports.
-- Safe to re-run: every added row uses a fixed primary key with INSERT IGNORE.
-- Run this against the existing demo database; do NOT rerun schema.sql.

INSERT IGNORE INTO APPOINTMENT
(Appointment_ID, Vehicle_ID, Mechanic_ID, Service_Type_ID, Appointment_Date, Status, Notes) VALUES
(721,601,301,401,'2026-10-23 09:00:00','Booked','Upcoming demo appointment'),
(722,602,302,402,'2026-10-24 10:00:00','Booked','Upcoming demo appointment'),
(723,603,303,403,'2026-10-25 11:00:00','In Progress','Upcoming demo appointment'),
(724,604,304,404,'2026-10-26 09:30:00','Booked','Upcoming demo appointment'),
(725,605,305,405,'2026-10-27 13:00:00','Booked','Upcoming demo appointment'),
(726,606,306,406,'2026-10-28 14:00:00','Booked','Upcoming demo appointment'),
(727,607,307,407,'2026-10-29 10:30:00','Booked','Upcoming demo appointment'),
(728,608,308,408,'2026-10-30 15:00:00','Booked','Upcoming demo appointment');

-- Additional completed work, spread across months so history and revenue reports
-- show a useful range of results. These appointments are separate from the upcoming set.
INSERT IGNORE INTO APPOINTMENT
(Appointment_ID, Vehicle_ID, Mechanic_ID, Service_Type_ID, Appointment_Date, Status, Notes) VALUES
(729,601,301,402,'2026-03-15 09:00:00','Completed','Historical demo service'),
(730,602,302,403,'2026-04-15 10:00:00','Completed','Historical demo service'),
(731,603,303,404,'2026-05-15 11:00:00','Completed','Historical demo service'),
(732,604,304,405,'2026-06-15 09:30:00','Completed','Historical demo service'),
(733,605,305,406,'2026-07-15 13:00:00','Completed','Historical demo service'),
(734,606,306,407,'2026-08-15 14:00:00','Completed','Historical demo service'),
(735,607,307,408,'2026-09-15 10:30:00','Completed','Historical demo service'),
(736,608,308,409,'2026-10-18 15:00:00','Completed','Historical demo service');

INSERT IGNORE INTO SERVICE_RECORD
(Service_ID, Appointment_ID, Service_Date, Completion_Date, Cost, Description) VALUES
(811,729,'2026-03-15','2026-03-15',2200,'General service completed'),
(812,730,'2026-04-15','2026-04-15',2600,'Brake repair completed'),
(813,731,'2026-05-15','2026-05-15',7200,'Engine repair completed'),
(814,732,'2026-06-15','2026-06-15',4300,'Battery replacement completed'),
(815,733,'2026-07-15','2026-07-15',1900,'AC service completed'),
(816,734,'2026-08-15','2026-08-15',1100,'Wheel alignment completed'),
(817,735,'2026-09-15','2026-09-15',4800,'Tyre replacement completed'),
(818,736,'2026-10-18','2026-10-18',5700,'Transmission service completed');

INSERT IGNORE INTO INVOICE
(Invoice_ID, Service_ID, Invoice_Date, Tax_Amount, Total_Amount, Payment_Status) VALUES
(1111,811,'2026-03-15',396,2596,'Pending'),
(1112,812,'2026-04-15',468,3068,'Pending'),
(1113,813,'2026-05-15',1296,8496,'Pending'),
(1114,814,'2026-06-15',774,5074,'Pending'),
(1115,815,'2026-07-15',342,2242,'Pending'),
(1116,816,'2026-08-15',198,1298,'Pending'),
(1117,817,'2026-09-15',864,5664,'Pending'),
(1118,818,'2026-10-18',1026,6726,'Pending');

INSERT IGNORE INTO PART (Part_ID, Part_Name, Category, Supplier_ID, Unit_Price) VALUES
(911,'Brake Fluid','Fluids',501,450),
(912,'Cabin Air Filter','Filter',502,750),
(913,'Coolant','Fluids',503,650),
(914,'Clutch Plate','Transmission',504,2800),
(915,'Alternator Belt','Engine',505,900),
(916,'Wiper Blade Set','Accessories',506,550),
(917,'Fuel Filter','Filter',507,800),
(918,'Radiator Hose','Cooling',508,700);

INSERT IGNORE INTO INVENTORY
(Inventory_ID, Part_ID, Quantity_In_Stock, Reorder_Level, Last_Updated) VALUES
(1011,911,2,10,'2026-10-20'),
(1012,912,3,8,'2026-10-20'),
(1013,913,0,6,'2026-10-20'),
(1014,914,1,5,'2026-10-20'),
(1015,915,4,12,'2026-10-20'),
(1016,916,2,9,'2026-10-20'),
(1017,917,5,10,'2026-10-20'),
(1018,918,1,7,'2026-10-20');

INSERT IGNORE INTO WARRANTY
(Warranty_ID, Service_ID, Part_ID, Start_Date, End_Date, Details) VALUES
(1311,811,911,'2026-03-15','2026-10-25','Brake fluid service warranty'),
(1312,812,912,'2026-04-15','2026-10-27','Cabin filter warranty'),
(1313,813,913,'2026-05-15','2026-10-29','Coolant replacement warranty'),
(1314,814,914,'2026-06-15','2026-10-31','Clutch repair warranty'),
(1315,815,915,'2026-07-15','2026-11-02','Belt replacement warranty'),
(1316,816,916,'2026-08-15','2026-11-04','Wiper set warranty'),
(1317,817,917,'2026-09-15','2026-11-06','Fuel filter warranty'),
(1318,818,918,'2026-10-18','2026-11-08','Radiator hose warranty');
