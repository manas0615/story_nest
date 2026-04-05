# **System Design Document (design.md)**

## **Project Title:** Story Nest

**Project Type:** Web-Based Story Publishing and Reading Platform

---

## **1. Introduction**

This document describes the **system design and architecture** of **Story Nest**, a web-based platform that enables users to read, write, and manage stories. The design strictly follows the constraints defined in the PRD, ensuring academic compliance and modularity.

---

## **2. Design Goals**

The primary goals of the system design are:

* Clear separation of concerns (Frontend, Backend, Database)
* Maintainability and scalability
* Secure handling of user data
* Compliance with strict technology constraints
* Simple and intuitive user experience

---

## **3. System Architecture Overview**

Story Nest follows a **Layered / MVC Architecture**.

```
+---------------------------+
|      Presentation Layer   |
|     (HTML + CSS)          |
+-------------↓-------------+
|     Application Layer     |
|     (Flask Backend)      |
+-------------↓-------------+
|        Data Layer         |
|  PostgreSQL + PL/pgSQL    |
+---------------------------+
```

---

## **4. Component-Level Design**

### **4.1 Presentation Layer (Frontend)**

**Technologies Used**

* HTML5
* CSS3

**Responsibilities**

* Display web pages (login, story list, reading view, dashboards)
* Collect user inputs via forms
* Send HTTP requests to backend
* Display backend responses

**Key Pages**

* Login / Registration Page
* Home Page (Story Listing)
* Story Reading Page
* Author Dashboard
* Admin Dashboard

⚠️ No JavaScript frameworks are used.

---

### **4.2 Application Layer (Backend)**

**Technology Used**

* Python (Flask)

**Responsibilities**

* Handle HTTP requests
* Authenticate users
* Enforce role-based access control
* Execute business logic
* Communicate with PostgreSQL database

**Backend Modules**

* Authentication Module
* User Management Module
* Story & Chapter Management Module
* Reader Interaction Module
* Admin Management Module
* Notification Module

---

### **4.3 Data Layer (Database)**

**Technology Used**

* PostgreSQL
* PL/pgSQL

**Responsibilities**

* Store persistent data
* Enforce data integrity
* Execute stored procedures and triggers
* Handle business rules

---

## **5. Database Design**

### **5.1 Major Tables**

* `users`
* `roles`
* `stories`
* `chapters`
* `genres`
* `tags`
* `story_tags`
* `ratings`
* `comments`
* `reading_list`
* `notifications`
* `reports`

All tables follow **Third Normal Form (3NF)**.

---

### **5.2 Stored Procedures & Functions**

**Examples**

* Publish story procedure
* Calculate average rating function
* Increment view count trigger
* Notification generation procedure

**Example Function**

```sql
CREATE OR REPLACE FUNCTION calculate_average_rating(story_id INT)
RETURNS NUMERIC AS $$
DECLARE avg_rating NUMERIC;
BEGIN
  SELECT AVG(rating) INTO avg_rating
  FROM ratings
  WHERE ratings.story_id = story_id;

  RETURN avg_rating;
END;
$$ LANGUAGE plpgsql;
```

---

## **6. Use Case Design**

### **6.1 User Registration & Login**

* User submits credentials
* Backend validates and hashes password
* User role is assigned
* Session is created

### **6.2 Story Publishing**

* Author creates story draft
* Adds chapters
* Calls publish procedure
* Story becomes visible to readers

### **6.3 Reading & Interaction**

* Reader views story
* Trigger increments view count
* Reader can rate and comment
* Notification sent to author

### **6.4 Admin Moderation**

* Admin views reports
* Takes action (remove story / block user)
* System logs the action

---

## **7. Security Design**

* Password hashing using Python libraries
* SQL injection prevention using parameterized queries
* Role-based access control (RBAC)
* Admin-only protected routes
* Secure database transactions

---

## **8. Performance Design**

* Indexed columns for frequently searched fields
* Optimized SQL queries
* Backend connection pooling
* Minimal frontend overhead

---

## **9. Scalability Design**

* Modular backend services
* Database supports data growth
* Clear separation of responsibilities
* Easy integration of future modules

---

## **10. Error Handling & Logging**

* Backend handles invalid inputs gracefully
* Database constraints prevent inconsistent data
* Logs maintained for admin review
* User-friendly error messages displayed

---

## **11. Assumptions**

* Users access system via web browsers
* Admins are trusted users
* Internet connectivity is available

---

## **12. Limitations**

* No client-side scripting frameworks
* No mobile application
* No real-time updates

---

## **13. Future Enhancements**

* Recommendation engine
* Mobile application
* AI-based story analysis
* Voice narration support

---

## **14. Conclusion**

The design of **Story Nest** ensures a clean separation of frontend, backend, and database layers. By enforcing strict technology constraints and leveraging PL/pgSQL for database logic, the system remains scalable, secure, and academically compliant.