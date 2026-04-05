# **dev-notes.md**

### *Implementation Guardrails & Missing Decisions*

> This document exists to remove ambiguity during implementation.
> If there is any conflict between documents, follow this order:
>
> **dev-notes.md → design.md → prd.md**

---

## **1. Backend Framework Decision**

* **Backend Framework:** Flask (Python)
* **Reason:** Lightweight, minimal abstraction, ideal for academic and MVP projects
* **Pattern:** Server-rendered HTML using Jinja templates

❌ Do not use:

* Django ORM
* FastAPI async features
* Any JavaScript-based backend logic

---

## **2. Application Folder Structure (MANDATORY)**

```
story_nest/
│
├── app.py                 # Application entry point
├── config.py              # Database & app config
│
├── templates/             # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── home.html
│   ├── story.html
│   ├── author_dashboard.html
│   └── admin_dashboard.html
│
├── static/
│   └── style.css
│
├── db/
│   ├── schema.sql         # Tables
│   ├── functions.sql     # PL/pgSQL functions
│   └── triggers.sql      # Triggers
│
└── README.md
```

---

## **3. Routing Conventions**

All routes must be **simple, REST-like, and form-driven**.

### **Authentication**

```
GET  /login
POST /login
GET  /register
POST /register
GET  /logout
```

### **Stories**

```
GET  /               → Home (story list)
GET  /story/<id>     → Read story
GET  /author/create  → Create story form
POST /author/create  → Save draft
POST /author/publish → Publish story
```

### **Reader Actions**

```
POST /story/<id>/rate
POST /story/<id>/comment
POST /story/<id>/save
```

### **Admin**

```
GET  /admin/dashboard
POST /admin/block-user
POST /admin/remove-story
```

❌ No dynamic JavaScript routing
❌ No client-side API calls

---

## **4. Authentication & Session Handling**

* Use **Flask sessions**
* Session data:

  * `user_id`
  * `role` (reader / author / admin)

### **Password Rules**

* Hash passwords using `werkzeug.security`
* Never store plain-text passwords

---

## **5. Role-Based Access Control (RBAC)**

| Role   | Permissions                     |
| ------ | ------------------------------- |
| Reader | Read, comment, rate, save       |
| Author | Reader + create/publish stories |
| Admin  | Full access                     |

RBAC must be enforced:

* At **route level**
* Not in frontend templates

---

## **6. Database Access Rules**

* Use **psycopg2**
* Always use **parameterized queries**
* No raw string SQL concatenation

❌ No ORM (SQLAlchemy)
❌ No NoSQL DB

---

## **7. PL/pgSQL Responsibility Split**

### **Handled in Database**

* View count increment
* Average rating calculation
* Publish story logic
* Notification creation

### **Handled in Python**

* Input validation
* Authorization
* Page rendering
* Error handling

---

## **8. HTML & CSS Rules**

* All pages extend `base.html`
* Navigation rendered server-side
* Forms must use POST where applicable
* CSS kept in **single file**

❌ No JavaScript frameworks
❌ No inline CSS for layouts

---

## **9. Error Handling Strategy**

* Backend returns:

  * Friendly error pages
  * Flash messages for user actions
* Database errors logged server-side
* No raw stack traces shown to users

---

## **10. Development Scope Limits**

This project is **NOT** expected to include:

* Real-time notifications
* WebSockets
* Payment systems
* OAuth / social login
* AI features

---

## **11. “Good Enough” Definition (IMPORTANT)**

The system is considered complete when:

* All PRD features work via HTML forms
* Roles behave correctly
* Stories can be published and read
* Admin moderation functions correctly
* Database uses at least:

  * 1 trigger
  * 1 stored procedure
  * 1 PL/pgSQL function

No polishing beyond this is required.

---

## **12. Agent Instruction (Kiro / Copilot / AI Tools)**

> Generate **simple, readable code**.
> Prefer clarity over abstraction.
> Do not introduce technologies not explicitly listed.
> Do not optimize prematurely.
> This is an academic + MVP system.