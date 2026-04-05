

# **Product Requirements Document (PRD)**

## **Project Title:** Story Nest

## **Project Type:** Web-Based Story Publishing and Reading Platform

---

## **1. Purpose of the Document**

This Product Requirements Document (PRD) defines the functional, technical, and operational requirements of the **Story Nest** system. It serves as a guideline for design, development, and evaluation of the system.

---

## **2. Product Overview**

**Story Nest** is a web-based platform that allows users to read, write, and manage stories. Authors can publish stories and chapters, readers can explore and interact with content, and administrators can manage and moderate the platform.

---

## **3. Target Users**

* **Readers** – Read stories, comment, rate, and manage reading lists
* **Authors** – Write, publish, and analyze stories
* **Administrators** – Moderate content and manage users

---

## **4. Technology Stack (STRICT RULES)**

### **Frontend (STRICT)**

* HTML5
* CSS3
  ❌ JavaScript frameworks (React, Angular, Vue) are **NOT allowed**

### **Backend (STRICT)**

* Python

  * Flask (allowed)
    ❌ No backend language other than Python

### **Database (STRICT)**

* PostgreSQL
* PL/pgSQL for:

  * Stored procedures
  * Triggers
  * Business rules

❌ MySQL / MongoDB / Firebase are **NOT allowed**

---

## **5. System Architecture**

```
[ HTML + CSS Frontend ]
           ↓
[ Flask Backend API ]
           ↓
[ PostgreSQL Database (PL/pgSQL) ]
```

---

## **6. Functional Requirements**

### **6.1 User Management**

* Users must be able to register and log in.
* Users must choose a role (Reader / Author).
* Authentication must be handled by the Python backend.

---

### **6.2 Story Management (Author)**

* Authors can:

  * Create stories
  * Add chapters
  * Save drafts
  * Publish content
* Each story must belong to a genre and may have tags.

---

### **6.3 Reader Interaction**

* Readers can:

  * Search stories
  * Read chapters
  * Rate stories (1–5 stars)
  * Comment on stories
  * Save stories to their library

---

### **6.4 Admin Management**

* Admins can:

  * View system statistics
  * Moderate reported stories
  * Block users
  * Remove inappropriate content

---

### **6.5 Notifications**

* Authors receive notifications for:

  * New comments
  * Ratings
  * Story milestones

---

## **7. Non-Functional Requirements**

### **7.1 Usability**

* UI must be simple and intuitive.
* No client-side scripting complexity.

### **7.2 Performance**

* Backend must handle multiple concurrent users.
* Database queries must be optimized using indexes.

### **7.3 Security**

* Passwords must be hashed in Python.
* SQL injection must be prevented.
* Role-based access control must be enforced.

### **7.4 Scalability**

* Backend APIs must be modular.
* Database must support increasing data volume.

---

## **8. Input Requirements**

### **Author Inputs**

* Story title
* Genre
* Tags
* Cover image
* Chapter content

### **Reader Inputs**

* Search queries
* Ratings
* Comments
* Reading list actions

### **Admin Inputs**

* Content moderation actions
* User management actions

---

## **9. Output Requirements**

### **System Outputs**

* Search results
* Story reading pages
* Author analytics dashboard
* Reader library
* Admin reports
* Notifications

---

## **10. Database Requirements (PL/pgSQL)**

* Tables must follow **3NF normalization**
* Use **PL/pgSQL** for:

  * Trigger to update view counts
  * Stored procedure for publishing stories
  * Function to calculate average ratings

Example:

```sql
CREATE OR REPLACE FUNCTION update_view_count()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE stories SET view_count = view_count + 1
  WHERE story_id = NEW.story_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## **11. Constraints & Rules**

* Frontend **must not** use JavaScript frameworks.
* Backend **must only** be written in Python.
* Database logic **must use PL/pgSQL**.
* System must follow MVC or layered architecture.
* No third-party CMS allowed.

---

## **12. Assumptions**

* Users have basic internet access.
* System is web-based only (no mobile app).
* Admins are trusted users.

---

## **13. Future Scope**

* Recommendation system
* Mobile app version
* AI-based story suggestions
* Voice-based reading

---

## **14. Conclusion**

Story Nest is designed as a modular, scalable, and secure web-based story platform. By strictly separating frontend, backend, and database responsibilities, the system ensures maintainability, performance, and academic compliance.

