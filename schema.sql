CREATE DATABASE IF NOT EXISTS vehicle_service CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE vehicle_service;
-- Fresh demo schema: run this on a new/empty vehicle_service database.
-- Do not rerun the script after tables contain data; it intentionally avoids dropping existing tables.

CREATE TABLE CUSTOMER(Customer_ID INT AUTO_INCREMENT PRIMARY KEY,Customer_Name VARCHAR(100) NOT NULL,Phone VARCHAR(20) NOT NULL,Email VARCHAR(255) UNIQUE,Address VARCHAR(250));
CREATE TABLE VEHICLE_MODEL(Model_ID INT AUTO_INCREMENT PRIMARY KEY,Brand VARCHAR(100) NOT NULL,Model_Name VARCHAR(100) NOT NULL,Fuel_Type ENUM('Petrol','Diesel','Electric','Hybrid','CNG') NOT NULL DEFAULT 'Petrol',Vehicle_Type ENUM('Car','Bike','SUV','Truck','Van','Hatchback','Sedan','MUV') NOT NULL DEFAULT 'Car',UNIQUE(Brand,Model_Name));
CREATE TABLE VEHICLE(Vehicle_ID INT AUTO_INCREMENT PRIMARY KEY,Registration_No VARCHAR(30) NOT NULL UNIQUE,Customer_ID INT NOT NULL,Model_ID INT NOT NULL,Manufacture_Year YEAR,Color VARCHAR(50),Mileage DECIMAL(10,2) NULL DEFAULT NULL CHECK(Mileage IS NULL OR Mileage>=0),FOREIGN KEY(Customer_ID) REFERENCES CUSTOMER(Customer_ID),FOREIGN KEY(Model_ID) REFERENCES VEHICLE_MODEL(Model_ID));
CREATE TABLE MECHANIC(Mechanic_ID INT AUTO_INCREMENT PRIMARY KEY,Mechanic_Name VARCHAR(100) NOT NULL,Phone VARCHAR(20) NOT NULL UNIQUE,Specialization VARCHAR(100),Experience_Years INT CHECK(Experience_Years>=0));
CREATE TABLE SERVICE_TYPE(Service_Type_ID INT AUTO_INCREMENT PRIMARY KEY,Service_Name VARCHAR(100) NOT NULL UNIQUE,Description VARCHAR(500),Price DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK(Price>=0));
CREATE TABLE APPOINTMENT(Appointment_ID INT AUTO_INCREMENT PRIMARY KEY,Vehicle_ID INT NOT NULL,Mechanic_ID INT NOT NULL,Service_Type_ID INT NOT NULL,Appointment_Date DATETIME NOT NULL,Status ENUM('Booked','In Progress','Completed','Cancelled') NOT NULL DEFAULT 'Booked',Notes VARCHAR(500),FOREIGN KEY(Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID),FOREIGN KEY(Mechanic_ID) REFERENCES MECHANIC(Mechanic_ID),FOREIGN KEY(Service_Type_ID) REFERENCES SERVICE_TYPE(Service_Type_ID));
CREATE TABLE SERVICE_RECORD(Service_ID INT AUTO_INCREMENT PRIMARY KEY,Appointment_ID INT NOT NULL UNIQUE,Service_Date DATE NOT NULL,Completion_Date DATE,Cost DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK(Cost>=0),Description VARCHAR(500),FOREIGN KEY(Appointment_ID) REFERENCES APPOINTMENT(Appointment_ID));
CREATE TABLE SUPPLIER(Supplier_ID INT AUTO_INCREMENT PRIMARY KEY,Supplier_Name VARCHAR(150) NOT NULL,Phone VARCHAR(20),Email VARCHAR(255) UNIQUE,Address VARCHAR(250));
CREATE TABLE PART(Part_ID INT AUTO_INCREMENT PRIMARY KEY,Part_Name VARCHAR(150) NOT NULL,Category VARCHAR(100),Supplier_ID INT NOT NULL,Unit_Price DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK(Unit_Price>=0),FOREIGN KEY(Supplier_ID) REFERENCES SUPPLIER(Supplier_ID));
CREATE TABLE SERVICE_PART(Service_ID INT NOT NULL,Part_ID INT NOT NULL,Quantity INT NOT NULL DEFAULT 1 CHECK(Quantity>0),Unit_Cost DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK(Unit_Cost>=0),PRIMARY KEY(Service_ID,Part_ID),FOREIGN KEY(Service_ID) REFERENCES SERVICE_RECORD(Service_ID),FOREIGN KEY(Part_ID) REFERENCES PART(Part_ID));
CREATE TABLE INVENTORY(Inventory_ID INT AUTO_INCREMENT PRIMARY KEY,Part_ID INT NOT NULL UNIQUE,Quantity_In_Stock INT NOT NULL DEFAULT 0 CHECK(Quantity_In_Stock>=0),Reorder_Level INT NOT NULL DEFAULT 0 CHECK(Reorder_Level>=0),Last_Updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,FOREIGN KEY(Part_ID) REFERENCES PART(Part_ID));
CREATE TABLE INVOICE(Invoice_ID INT AUTO_INCREMENT PRIMARY KEY,Service_ID INT NOT NULL UNIQUE,Invoice_Date DATE NOT NULL DEFAULT (CURRENT_DATE),Tax_Amount DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK(Tax_Amount>=0),Total_Amount DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK(Total_Amount>=0),Payment_Status ENUM('Pending','Paid','Partially Paid') NOT NULL DEFAULT 'Pending',FOREIGN KEY(Service_ID) REFERENCES SERVICE_RECORD(Service_ID));
CREATE TABLE PAYMENT(Payment_ID INT AUTO_INCREMENT PRIMARY KEY,Invoice_ID INT NOT NULL,Payment_Date DATE NOT NULL DEFAULT (CURRENT_DATE),Amount DECIMAL(10,2) NOT NULL CHECK(Amount>=0),Payment_Mode ENUM('Cash','Card','UPI','Bank Transfer','Net Banking') NOT NULL,FOREIGN KEY(Invoice_ID) REFERENCES INVOICE(Invoice_ID));
CREATE TABLE WARRANTY(Warranty_ID INT AUTO_INCREMENT PRIMARY KEY,Service_ID INT,Part_ID INT,Start_Date DATE NOT NULL,End_Date DATE NOT NULL,Details VARCHAR(500),CHECK(End_Date>=Start_Date),FOREIGN KEY(Service_ID) REFERENCES SERVICE_RECORD(Service_ID),FOREIGN KEY(Part_ID) REFERENCES PART(Part_ID));
CREATE TABLE FEEDBACK(Feedback_ID INT AUTO_INCREMENT PRIMARY KEY,Service_ID INT NOT NULL,Customer_ID INT NOT NULL,Rating TINYINT NOT NULL CHECK(Rating BETWEEN 1 AND 5),Comments VARCHAR(1000),Feedback_Date DATE NOT NULL DEFAULT (CURRENT_DATE),FOREIGN KEY(Service_ID) REFERENCES SERVICE_RECORD(Service_ID),FOREIGN KEY(Customer_ID) REFERENCES CUSTOMER(Customer_ID));

-- Seed records copied from the original SQLite DBMS demo database.

-- Original demo records copied from the SQLite DBMS project.
INSERT INTO CUSTOMER (Customer_ID, Customer_Name, Phone, Email, Address) VALUES
(101, 'Arun Kumar', '9876500001', 'arun@gmail.com', 'Vellore'),
(102, 'Priya Sharma', '9876500002', 'priya@gmail.com', 'Chennai'),
(103, 'Rahul Verma', '9876500003', 'rahul@gmail.com', 'Bengaluru'),
(104, 'Sneha Reddy', '9876500004', 'sneha@gmail.com', 'Hyderabad'),
(105, 'Karthik Raj', '9876500005', 'karthik@gmail.com', 'Coimbatore'),
(106, 'Divya Nair', '9876500006', 'divya@gmail.com', 'Kochi'),
(107, 'Vikram Singh', '9876500007', 'vikram@gmail.com', 'Delhi'),
(108, 'Ananya Das', '9876500008', 'ananya@gmail.com', 'Kolkata'),
(109, 'Rohan Mehta', '9876500009', 'rohan@gmail.com', 'Mumbai'),
(110, 'Meera Iyer', '9876500010', 'meera@gmail.com', 'Madurai');

INSERT INTO VEHICLE_MODEL (Model_ID, Brand, Model_Name, Fuel_Type, Vehicle_Type) VALUES
(201, 'Maruti Suzuki', 'Swift', 'Petrol', 'Hatchback'),
(202, 'Hyundai', 'Creta', 'Diesel', 'SUV'),
(203, 'Tata', 'Nexon', 'Petrol', 'SUV'),
(204, 'Honda', 'City', 'Petrol', 'Sedan'),
(205, 'Toyota', 'Innova', 'Diesel', 'MUV'),
(206, 'Mahindra', 'Thar', 'Diesel', 'SUV'),
(207, 'Kia', 'Seltos', 'Petrol', 'SUV'),
(208, 'Volkswagen', 'Polo', 'Petrol', 'Hatchback'),
(209, 'Renault', 'Kwid', 'Petrol', 'Hatchback'),
(210, 'Hyundai', 'i20', 'Petrol', 'Hatchback');

INSERT INTO SERVICE_TYPE (Service_Type_ID, Service_Name, Description, Price) VALUES
(401, 'Oil Change', 'Engine oil replacement', 1500),
(402, 'General Service', 'Complete vehicle inspection', 3000),
(403, 'Brake Repair', 'Brake inspection and repair', 2500),
(404, 'Engine Repair', 'Engine diagnosis and repair', 8000),
(405, 'Battery Replacement', 'Battery check and replacement', 4500),
(406, 'AC Service', 'Air conditioning maintenance', 2000),
(407, 'Wheel Alignment', 'Wheel alignment and balancing', 1200),
(408, 'Tyre Replacement', 'Replacement of worn tyres', 5000),
(409, 'Transmission Service', 'Transmission inspection', 6000),
(410, 'Electrical Repair', 'Electrical system diagnosis', 1800);

INSERT INTO MECHANIC (Mechanic_ID, Mechanic_Name, Phone, Specialization, Experience_Years) VALUES
(301, 'Ramesh', '9000000001', 'Engine Repair', 8),
(302, 'Suresh', '9000000002', 'Electrical', 6),
(303, 'Manoj', '9000000003', 'Brake System', 5),
(304, 'Ajay', '9000000004', 'Transmission', 7),
(305, 'Kiran', '9000000005', 'General Service', 4),
(306, 'Prakash', '9000000006', 'Engine Repair', 10),
(307, 'Deepak', '9000000007', 'Electrical', 3),
(308, 'Naveen', '9000000008', 'AC Repair', 6),
(309, 'Surya', '9000000009', 'Wheel Alignment', 5),
(310, 'Ganesh', '9000000010', 'General Service', 9);

INSERT INTO SUPPLIER (Supplier_ID, Supplier_Name, Phone, Email, Address) VALUES
(501, 'Auto Parts India', '8000000001', 'sales@autoparts.com', 'Chennai'),
(502, 'Speed Motors Supply', '8000000002', 'sales@speedmotors.com', 'Bengaluru'),
(503, 'Prime Spares', '8000000003', 'info@primespares.com', 'Mumbai'),
(504, 'Reliable Auto Supply', '8000000004', 'contact@reliableauto.com', 'Delhi'),
(505, 'Metro Parts', '8000000005', 'sales@metroparts.com', 'Hyderabad'),
(506, 'Classic Spares', '8000000006', 'info@classicspares.com', 'Kochi'),
(507, 'National Auto Parts', '8000000007', 'sales@nationalauto.com', 'Pune'),
(508, 'Elite Components', '8000000008', 'contact@elitecomponents.com', 'Coimbatore'),
(509, 'Universal Spares', '8000000009', 'sales@universalspares.com', 'Kolkata'),
(510, 'RoadStar Supplies', '8000000010', 'info@roadstar.com', 'Vellore');

INSERT INTO VEHICLE (Vehicle_ID, Registration_No, Customer_ID, Model_ID, Manufacture_Year, Color, Mileage) VALUES
(601, 'TN23AB1001', 101, 201, 2022, 'White', 18000),
(602, 'TN09CD2002', 102, 202, 2021, 'Black', 25000),
(603, 'KA05EF3003', 103, 203, 2023, 'Blue', 12000),
(604, 'TS08GH4004', 104, 204, 2020, 'Silver', 35000),
(605, 'KL07IJ5005', 105, 205, 2022, 'White', 22000),
(606, 'DL01KL6006', 106, 206, 2021, 'Red', 28000),
(607, 'MH02MN7007', 107, 207, 2023, 'Grey', 15000),
(608, 'WB06OP8008', 108, 208, 2019, 'White', 42000),
(609, 'TN58QR9009', 109, 209, 2022, 'Blue', 16000),
(610, 'TN59ST1010', 110, 210, 2024, 'Black', 8000);

INSERT INTO APPOINTMENT (Appointment_ID, Vehicle_ID, Mechanic_ID, Service_Type_ID, Appointment_Date, Status) VALUES
(701, 601, 301, 401, '2026-10-01', 'Completed'),
(702, 602, 302, 402, '2026-10-02', 'Completed'),
(703, 603, 303, 403, '2026-10-03', 'Completed'),
(704, 604, 304, 404, '2026-10-04', 'Completed'),
(705, 605, 305, 405, '2026-10-05', 'Completed'),
(706, 606, 306, 406, '2026-10-06', 'Completed'),
(707, 607, 307, 407, '2026-10-07', 'Completed'),
(708, 608, 308, 408, '2026-10-08', 'Completed'),
(709, 609, 309, 409, '2026-10-09', 'Completed'),
(710, 610, 310, 410, '2026-10-10', 'Completed'),
(711, 601, 301, 402, '2026-10-11', 'Completed'),
(712, 602, 302, 403, '2026-10-12', 'Completed'),
(713, 603, 303, 404, '2026-10-13', 'Completed'),
(714, 604, 304, 405, '2026-10-14', 'Completed'),
(715, 605, 305, 406, '2026-10-15', 'Completed'),
(716, 601, 302, 403, '2026-10-16', 'Completed'),
(717, 602, 303, 404, '2026-10-16', 'Completed'),
(718, 603, 304, 405, '2026-10-16', 'Completed'),
(719, 604, 305, 406, '2026-10-16', 'Completed'),
(720, 605, 306, 407, '2026-10-16', 'Completed');

INSERT INTO PART (Part_ID, Part_Name, Category, Unit_Price, Supplier_ID) VALUES
(901, 'Engine Oil', 'Lubricant', 900, 501),
(902, 'Oil Filter', 'Filter', 350, 502),
(903, 'Brake Pad', 'Brake', 1200, 503),
(904, 'Spark Plug', 'Ignition', 450, 504),
(905, 'Car Battery', 'Electrical', 4000, 505),
(906, 'AC Filter', 'Filter', 600, 506),
(907, 'Air Filter', 'Filter', 500, 507),
(908, 'Car Tyre', 'Tyre', 3500, 508),
(909, 'Gear Oil', 'Lubricant', 1100, 509),
(910, 'Headlight Bulb', 'Electrical', 300, 510);

INSERT INTO SERVICE_RECORD (Service_ID, Appointment_ID, Service_Date, Completion_Date, Cost, Description) VALUES
(801, 701, '2026-10-01', '2026-10-01', 1200, 'Oil change completed'),
(802, 702, '2026-10-02', '2026-10-02', 2500, 'General service completed'),
(803, 703, '2026-10-03', '2026-10-03', 2000, 'Brake pads inspected'),
(804, 704, '2026-10-04', '2026-10-05', 7000, 'Engine repair completed'),
(805, 705, '2026-10-05', '2026-10-05', 1500, 'Battery replaced'),
(806, 706, '2026-10-06', '2026-10-06', 1800, 'AC service completed'),
(807, 707, '2026-10-07', '2026-10-07', 1000, 'Wheel alignment completed'),
(808, 708, '2026-10-08', '2026-10-08', 4000, 'Tyres replaced'),
(809, 709, '2026-10-09', '2026-10-10', 5000, 'Transmission serviced'),
(810, 710, '2026-10-10', '2026-10-10', 1600, 'Electrical repair completed');

INSERT INTO SERVICE_PART (Service_ID, Part_ID, Quantity, Unit_Cost) VALUES
(801, 901, 1, 900),
(801, 902, 1, 350),
(802, 907, 1, 500),
(803, 903, 2, 2400),
(804, 904, 4, 1800),
(805, 905, 1, 4000),
(806, 906, 1, 600),
(807, 907, 1, 500),
(808, 908, 4, 14000),
(809, 909, 2, 2200),
(810, 910, 2, 600);

INSERT INTO INVENTORY (Inventory_ID, Part_ID, Quantity_In_Stock, Reorder_Level, Last_Updated) VALUES
(1001, 901, 50, 10, '2026-10-01'),
(1002, 902, 40, 8, '2026-10-01'),
(1003, 903, 25, 5, '2026-10-02'),
(1004, 904, 60, 12, '2026-10-02'),
(1005, 905, 15, 3, '2026-10-03'),
(1006, 906, 35, 7, '2026-10-03'),
(1007, 907, 45, 10, '2026-10-04'),
(1008, 908, 20, 4, '2026-10-04'),
(1009, 909, 30, 6, '2026-10-05'),
(1010, 910, 70, 15, '2026-10-05');

INSERT INTO INVOICE (Invoice_ID, Service_ID, Invoice_Date, Tax_Amount, Total_Amount, Payment_Status) VALUES
(1101, 801, '2026-10-01', 387, 2837, 'Paid'),
(1102, 802, '2026-10-02', 540, 3540, 'Paid'),
(1103, 803, '2026-10-03', 792, 5192, 'Paid'),
(1104, 804, '2026-10-05', 1584, 10384, 'Paid'),
(1105, 805, '2026-10-05', 810, 5310, 'Paid'),
(1106, 806, '2026-10-06', 432, 2832, 'Paid'),
(1107, 807, '2026-10-07', 216, 1416, 'Paid'),
(1108, 808, '2026-10-08', 3240, 21240, 'Paid'),
(1109, 809, '2026-10-10', 1296, 8496, 'Paid'),
(1110, 810, '2026-10-10', 352, 2352, 'Paid');

INSERT INTO PAYMENT (Payment_ID, Invoice_ID, Payment_Date, Amount, Payment_Mode) VALUES
(1201, 1101, '2026-10-01', 2837, 'UPI'),
(1202, 1102, '2026-10-02', 3540, 'Card'),
(1203, 1103, '2026-10-03', 5192, 'Cash'),
(1204, 1104, '2026-10-05', 10384, 'UPI'),
(1205, 1105, '2026-10-05', 5310, 'Card'),
(1206, 1106, '2026-10-06', 2832, 'Net Banking'),
(1207, 1107, '2026-10-07', 1416, 'Cash'),
(1208, 1108, '2026-10-08', 21240, 'UPI'),
(1209, 1109, '2026-10-10', 8496, 'Card'),
(1210, 1110, '2026-10-10', 2352, 'UPI');

INSERT INTO WARRANTY (Warranty_ID, Service_ID, Part_ID, Start_Date, End_Date, Details) VALUES
(1301, 801, 901, '2026-10-01', '2027-10-01', 'Engine oil replacement warranty'),
(1302, 802, 907, '2026-10-02', '2027-04-02', 'Air filter warranty'),
(1303, 803, 903, '2026-10-03', '2027-10-03', 'Brake pad warranty'),
(1304, 804, 904, '2026-10-05', '2027-10-05', 'Spark plug warranty'),
(1305, 805, 905, '2026-10-05', '2027-10-05', 'Battery replacement warranty'),
(1306, 806, 906, '2026-10-06', '2027-04-06', 'AC filter warranty'),
(1307, 807, 907, '2026-10-07', '2027-10-07', 'Air filter warranty'),
(1308, 808, 908, '2026-10-08', '2027-10-08', 'Tyre replacement warranty'),
(1309, 809, 909, '2026-10-10', '2027-10-10', 'Gear oil warranty'),
(1310, 810, 910, '2026-10-10', '2027-10-10', 'Headlight bulb warranty');

INSERT INTO FEEDBACK (Feedback_ID, Service_ID, Customer_ID, Rating, Comments, Feedback_Date) VALUES
(1401, 801, 101, 5, 'Excellent service', '2026-10-01'),
(1402, 802, 102, 4, 'Good service', '2026-10-02'),
(1403, 803, 103, 5, 'Very professional', '2026-10-03'),
(1404, 804, 104, 4, 'Repair completed well', '2026-10-05'),
(1405, 805, 105, 5, 'Quick battery replacement', '2026-10-05'),
(1406, 806, 106, 4, 'AC working properly', '2026-10-06'),
(1407, 807, 107, 5, 'Good alignment service', '2026-10-07'),
(1408, 808, 108, 4, 'Tyres replaced properly', '2026-10-08'),
(1409, 809, 109, 5, 'Transmission works well', '2026-10-10'),
(1410, 810, 110, 4, 'Electrical issue fixed', '2026-10-10');

CREATE OR REPLACE VIEW CustomerVehicleAppointment AS SELECT c.Customer_ID,c.Customer_Name,c.Phone,c.Email,v.Vehicle_ID,v.Registration_No,vm.Brand,vm.Model_Name,a.Appointment_ID,a.Appointment_Date,a.Status FROM CUSTOMER c JOIN VEHICLE v ON c.Customer_ID=v.Customer_ID JOIN VEHICLE_MODEL vm ON v.Model_ID=vm.Model_ID LEFT JOIN APPOINTMENT a ON v.Vehicle_ID=a.Vehicle_ID;
