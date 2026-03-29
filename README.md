# 🏢 Reimbursement Management System — Odoo 19

> **[Odoo × VIT Pune Hackathon 2026](https://hackathon.odoo.com/event/odoo-x-vit-pune-hackathon-26-18/register) — Round 1**
> A production-ready, configurable expense reimbursement module for Odoo 19 with rule-based multi-level approval workflows, **DocStrange OCR receipt scanning**, and real-time multi-currency conversion.

---

## 📋 Table of Contents

- [Problem Statement](#-problem-statement)
- [Solution Overview](#-solution-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Module Structure](#-module-structure)
- [Core Models](#-core-models)
- [Workflow Engine](#-workflow-engine)
- [OCR Pipeline](#-ocr-pipeline-docstrange)
- [Currency Conversion](#-currency-conversion)
- [Security & Roles](#-security--roles)
- [API Endpoints](#-api-endpoints)
- [Testing](#-testing)
- [Team](#-team)

---

## 🎯 Problem Statement

Companies struggle with **manual expense reimbursement processes** that are time-consuming, error-prone, and lack transparency. There is no simple way to:

- Define approval flows based on thresholds
- Manage multi-level approvals
- Support flexible approval rules (percentage, specific approver, hybrid)
- Auto-read receipts to reduce manual data entry

---

## 💡 Solution Overview

We built a **complete Odoo 19 module** (`expense_management`) that solves all of these problems with:

| Capability | Implementation |
|---|---|
| **Configurable Approval Workflows** | 4 rule types: Sequential, Percentage, Specific Approver, Hybrid |
| **OCR Receipt Scanning** | DocStrange Docker container with Tesseract OCR + regex parsing |
| **Multi-Currency Support** | Real-time conversion via ExchangeRate API v6 |
| **Role-Based Access** | Admin → Manager → Employee with Odoo security groups & record rules |
| **Expense Policy Engine** | Per-category spending limits with automatic violation flagging |
| **Audit Trail** | Complete approval history with timestamps and comments |
| **Email Notifications** | Automatic notifications at every workflow step via Odoo mail system |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                         │
│                                                                 │
│  ┌───────────┐    ┌──────────────────┐    ┌──────────────────┐ │
│  │PostgreSQL │◄──►│   Odoo 19        │◄──►│  DocStrange      │ │
│  │   16      │    │                  │    │  OCR Service     │ │
│  │           │    │ expense_management│    │                  │ │
│  │  :5433    │    │  module           │    │  Flask API       │ │
│  │           │    │                  │    │  :5000           │ │
│  └───────────┘    │  :8080           │    │                  │ │
│                   │                  │    │  Tesseract OCR   │ │
│                   │  Currency API ◄──┼───►│  Cloud Mode      │ │
│                   │  (ExchangeRate)  │    │                  │ │
│                   └──────────────────┘    └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Data Flow — Receipt OCR:**
```
Receipt Image → Odoo Controller → DocStrange API (/api/extract)
     → Raw Text → Regex Pipeline → Structured JSON → Auto-fill Expense
```

**Data Flow — Expense Approval:**
```
Employee Submits → Currency Conversion → Policy Check → Workflow Engine
     → Step 1 Approver → Step 2 Approver → ... → Approved/Rejected
```

---

## ✨ Features

### 1. Authentication & User Management
- **Auto-company creation**: On first login, a new Company is created with the selected country's currency auto-set
- **Admin can**: Create Employees & Managers, assign/change roles, define manager relationships
- **Role hierarchy**: Admin → Manager → Employee (Odoo security groups with `implied_ids`)

### 2. Expense Submission (Employee Role)
- Submit expense claims with: Amount, Currency, Category, Description, Date, Receipt
- **Multi-currency**: Expense can be in any currency — auto-converted to company currency
- View expense history filtered by status (Approved, Rejected, Pending, Draft)
- **OCR Scan Button**: Upload a receipt and auto-fill all fields with one click

### 3. Configurable Approval Workflow (Manager/Admin Role)

| Rule Type | Description |
|---|---|
| **Sequential** | Step-by-step: each approver must approve in order |
| **Percentage** | Approve when X% of all approvers have approved (e.g., 60%) |
| **Specific Approver** | Auto-approve if a designated person (e.g., CFO) approves at any step |
| **Hybrid** | Combine both: approve if EITHER percentage threshold OR specific approver approves |

- **Manager-first option**: If enabled, the employee's direct manager is automatically Step 1
- **Multi-step**: Admin defines the sequence (e.g., Step 1 → Manager, Step 2 → Finance, Step 3 → Director)
- **Dynamic routing**: Expense moves to next approver only after current one acts
- Managers can view pending expenses, approve/reject with comments

### 4. OCR Receipt Scanning (DocStrange)
- Employees upload a receipt (image or PDF)
- **DocStrange Docker container** extracts text via cloud OCR
- **Regex parsing pipeline** extracts structured data:
  - Vendor name, address, GST number
  - Date, time, invoice number
  - Amounts (subtotal, tax, total, currency)
  - Line items (name, quantity, unit price, total)
  - Payment method, last 4 card digits
  - Category (auto-guessed from keywords)
  - Confidence score (0-100%)
- All fields auto-fill in the expense form

### 5. Multi-Currency Conversion
- Powered by **ExchangeRate API v6** (API key included)
- Automatic conversion on expense submission
- Stores both original and converted amounts + exchange rate
- Currency auto-set from country selection via `country_currency.json` (restcountries.com data)

### 6. Expense Policy Engine
- Admin configures per-category spending limits
- Auto-flags violations on submission (but doesn't block)
- Configurable receipt requirements per category/threshold

### 7. Audit Trail & Notifications
- Complete approval log: who approved/rejected, timestamp, comments, step number
- Odoo mail activities for approvers
- Email templates for submission, approval, and rejection

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| ERP Framework | Odoo 19 Community Edition |
| Database | PostgreSQL 16 |
| OCR Engine | DocStrange (NanoNets) + Tesseract OCR |
| Currency API | ExchangeRate API v6 |
| Country Data | restcountries.com (pre-loaded JSON) |
| Containerization | Docker + Docker Compose |
| Language | Python 3.11, XML (Odoo views) |

---

## 🚀 Quick Start

### Prerequisites
- **Docker Desktop** installed and running
- **Git** installed

### 1. Clone the Repository
```bash
git clone https://github.com/Gurjas2112/Agent_Hacks_X_Reimbuserment_Management.git
cd Agent_Hacks_X_Reimbuserment_Management
```

### 2. Start the Stack
```bash
docker compose up -d --build
```

This builds and starts 3 containers:
| Service | Container | URL |
|---|---|---|
| PostgreSQL 16 | `expense_db` | `localhost:5433` |
| Odoo 19 | `expense_odoo` | [http://localhost:8080](http://localhost:8080) |
| DocStrange OCR | `docstrange_ocr` | [http://localhost:5000](http://localhost:5000) |

### 3. Access Odoo
1. Open [http://localhost:8080](http://localhost:8080)
2. Create a new database (or use the auto-initialized one)
3. Install the **"Expense Management - Reimbursement System"** module
4. Start managing expenses!

### 4. Test OCR
```bash
# Check DocStrange health
curl http://localhost:5000/api/health

# Upload a receipt for OCR
curl -X POST http://localhost:8080/upload_receipt \
  -F "file=@sample_doc_upload/restaurant_receipt.png" \
  -H "Cookie: session_id=YOUR_SESSION_ID"
```

### Stop the Stack
```bash
docker compose down
```

### Reset Everything (including data)
```bash
docker compose down -v
```

---

## 📁 Module Structure

```
reimbursement_mgt_system/expense_management/
├── __manifest__.py              # Module metadata & dependencies
├── __init__.py                  # Package init
│
├── models/                      # Odoo ORM models
│   ├── expense_claim.py         # Core expense claim model
│   ├── expense_claim_line.py    # Expense line items
│   ├── expense_company.py       # Company with country/currency
│   ├── approval_workflow.py     # Workflow configuration
│   ├── workflow_step.py         # Workflow step definitions
│   ├── workflow_instance.py     # Runtime workflow engine
│   ├── workflow_instance_step.py# Runtime step tracking
│   ├── approval_log.py          # Audit trail
│   ├── expense_policy.py        # Spending limits/policies
│   └── res_users.py             # User role extensions
│
├── views/                       # XML view definitions
│   ├── expense_claim_views.xml  # Form, tree, kanban, search views
│   ├── approval_workflow_views.xml # Workflow config UI
│   ├── approval_dashboard_views.xml # Manager approval dashboard
│   ├── expense_company_views.xml # Company setup
│   ├── expense_policy_views.xml # Policy configuration
│   ├── expense_report_views.xml # Reporting/analytics views
│   ├── res_users_views.xml      # User management extensions
│   └── menu_items.xml           # Navigation menus
│
├── security/                    # Access control
│   ├── expense_groups.xml       # Security groups (Admin/Manager/Employee)
│   ├── expense_security.xml     # Record rules
│   └── ir.model.access.csv     # Model-level CRUD access
│
├── controllers/                 # HTTP controllers
│   └── receipt_controller.py    # /upload_receipt endpoint
│
├── services/                    # Business logic services
│   ├── ocr_parser.py            # DocStrange API + regex parsing pipeline
│   └── currency_service.py      # ExchangeRate API integration
│
├── data/                        # Data files
│   ├── country_currency.json    # 250+ countries with currencies
│   ├── expense_sequence.xml     # Auto-numbering (EXP/0001)
│   ├── mail_templates.xml       # Email notification templates
│   └── demo_data.xml            # Demo data for testing
│
├── tests/                       # Unit tests
│   ├── test_expense_submission.py
│   ├── test_approval_flow.py
│   └── test_rule_evaluation.py
│
└── static/                      # Static assets
```

---

## 📊 Core Models

### `expense.claim`
The central model for expense submissions.

| Field | Type | Description |
|---|---|---|
| `employee_id` | Many2one → res.users | Submitting employee |
| `amount_original` | Float | Amount in expense currency |
| `currency_original` | Char | Expense currency (e.g., USD) |
| `amount_converted` | Float | Amount in company currency |
| `company_currency` | Char | Company's default currency |
| `exchange_rate` | Float | Applied exchange rate |
| `category` | Selection | travel, meals, accommodation, etc. |
| `description` | Text | Expense description |
| `receipt` | Binary | Uploaded receipt image |
| `status` | Selection | draft → pending → approved/rejected |
| `current_approver_id` | Many2one → res.users | Currently assigned approver |
| `workflow_instance_id` | Many2one → workflow.instance | Linked runtime workflow |
| `ocr_*` | Various | OCR-extracted fields (vendor, amounts, etc.) |
| `ocr_confidence_score` | Float | OCR extraction confidence (0-100%) |

### `approval.workflow`
Configurable workflow templates.

| Field | Type | Description |
|---|---|---|
| `name` | Char | Workflow name |
| `rule_type` | Selection | sequential / percentage / specific_approver / hybrid |
| `percentage_threshold` | Float | Required approval % (for percentage/hybrid) |
| `specific_approver_id` | Many2one | CFO/override approver (for specific/hybrid) |
| `is_manager_first` | Boolean | Auto-add manager as Step 1 |
| `step_ids` | One2many | Ordered approval steps |

### `workflow.instance`
Runtime engine that tracks approval progress per expense.

### `workflow.step`
Individual step configuration (approver type, sequence, assigned users).

---

## ⚙️ Workflow Engine

The workflow engine is **100% database-driven** — no hardcoded logic.

```
Admin configures workflow:
  ┌─────────────────────────────────────────────────────┐
  │ Workflow: "Standard Approval"                       │
  │ Rule Type: Hybrid (60% OR CFO approves)             │
  │ Steps:                                              │
  │   1. Manager (auto if is_manager_first=True)        │
  │   2. Finance Team (role_based)                      │
  │   3. Director (specific_user)                       │
  └─────────────────────────────────────────────────────┘

On expense submission:
  1. workflow.instance created with runtime steps
  2. First approver notified via mail activity
  3. On approval → rule engine evaluates:
     - Sequential: advance to next step
     - Percentage: check if 60% reached → auto-approve all
     - Specific: check if CFO → auto-approve all
     - Hybrid: check EITHER condition
  4. On rejection → workflow stops, expense rejected
```

---

## 🔍 OCR Pipeline (DocStrange)

### Architecture

The OCR system uses a **microservice architecture**:

```
┌─────────────┐     HTTP POST      ┌──────────────────┐
│  Odoo       │ ──────────────────► │  DocStrange      │
│  Module     │   /api/extract      │  Docker Container│
│             │ ◄────────────────── │                  │
│ ocr_parser  │    Raw Text         │  Flask API       │
│   .py       │                     │  Tesseract OCR   │
│             │                     │  Cloud Processing│
│ Regex       │                     └──────────────────┘
│ Pipeline    │
│     ↓       │
│ Structured  │
│ JSON        │
└─────────────┘
```

### OCR JSON Schema

Every receipt is parsed into this structure:

```json
{
  "vendor": {
    "name": "Cafe Mocha",
    "gst_number": "27AABCU9603R1Z1",
    "address": "MG Road, Pune 411001"
  },
  "transaction": {
    "date": "2026-03-15",
    "time": "14:30",
    "invoice_number": "INV-2026-0042"
  },
  "amounts": {
    "subtotal": 450.00,
    "tax": 81.00,
    "total": 531.00,
    "currency": "INR"
  },
  "line_items": [
    {
      "name": "Cappuccino",
      "quantity": 2,
      "unit_price": 180.00,
      "total_price": 360.00
    }
  ],
  "payment": {
    "method": "UPI",
    "last4_digits": ""
  },
  "category": "meals",
  "confidence_score": 85.0
}
```

### Parsing Functions

| Function | Responsibility |
|---|---|
| `extract_vendor_name()` | First meaningful line = vendor name |
| `extract_gst()` | GSTIN pattern (15-char alphanumeric) |
| `extract_date()` | Multiple date formats (DD/MM/YYYY, YYYY-MM-DD, etc.) |
| `extract_amounts()` | Subtotal, tax (CGST/SGST/IGST), total with currency detection |
| `extract_line_items()` | Qty × Item Price patterns |
| `extract_payment_method()` | Keyword matching (Visa, UPI, Cash, etc.) |
| `guess_category()` | Keyword heuristics for 7 expense categories |
| `calculate_confidence()` | Weighted score based on extracted fields |

### DocStrange Docker Container

- **Image**: Custom `python:3.11-slim` with Tesseract OCR
- **Port**: 5000
- **Endpoints**:
  - `POST /api/extract` — Extract text/JSON from uploaded file
  - `GET /api/health` — Health check
  - `GET /api/supported-formats` — List supported file types
- **Volume**: `./docstrange_models:/root/.cache` for model persistence

---

## 💱 Currency Conversion

### API Integration
```
ExchangeRate API v6
URL: https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{BASE}
API Key: d626e2dd0a780145256e5f85
```

### Flow
1. Employee submits expense in USD
2. System fetches live exchange rate (USD → INR)
3. Converts and stores both amounts
4. Manager sees amount in company currency

### Country → Currency Mapping
Pre-loaded from [restcountries.com](https://restcountries.com/v3.1/all?fields=name,currencies) (`country_currency.json` with 250+ countries).

---

## 🔒 Security & Roles

### Security Groups (with hierarchy)

```
group_expense_admin
    └── implies: group_expense_manager
                    └── implies: group_expense_employee
```

### Permissions Matrix

| Permission | Employee | Manager | Admin |
|---|:---:|:---:|:---:|
| Submit expenses | ✅ | ✅ | ✅ |
| View own expenses | ✅ | ✅ | ✅ |
| View team expenses | ❌ | ✅ | ✅ |
| View ALL expenses | ❌ | ❌ | ✅ |
| Approve/Reject | ❌ | ✅ | ✅ |
| Configure workflows | ❌ | ❌ | ✅ |
| Manage users & roles | ❌ | ❌ | ✅ |
| Override approvals | ❌ | ❌ | ✅ |
| Configure policies | ❌ | ❌ | ✅ |

### Record Rules
- **Employees**: See only their own `expense.claim` records
- **Managers**: See expenses from their `team_member_ids`
- **Admins**: See all records (no domain filter)

---

## 🔌 API Endpoints

### Receipt OCR

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/upload_receipt` | User | Upload receipt for OCR processing |
| `GET` | `/upload_receipt/schema` | Public | Get expected JSON schema |
| `GET` | `/upload_receipt/health` | Public | Check DocStrange service health |

### DocStrange (internal)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/extract` | Extract text/JSON from document |
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/supported-formats` | List supported formats |

---

## 🧪 Testing

### Unit Tests

```bash
# Run all expense management tests
docker exec expense_odoo odoo \
  -d testdb \
  --test-enable \
  --stop-after-init \
  -i expense_management
```

| Test File | Coverage |
|---|---|
| `test_expense_submission.py` | Expense creation, submission, currency conversion |
| `test_approval_flow.py` | Sequential, multi-step, manager-first approval |
| `test_rule_evaluation.py` | Percentage, specific approver, hybrid rules |

### Sample Receipts

Pre-loaded in `sample_doc_upload/` with ground truth JSON:

| File | Category |
|---|---|
| `restaurant_receipt.png` | Meals |
| `hotel_invoice.png` | Accommodation |
| `taxi_receipt.png` | Transport |
| `office_supplies_receipt.png` | Office Supplies |

---

## 🏗 Docker Services

| Service | Image | Port | Container |
|---|---|---|---|
| PostgreSQL 16 | `postgres:16` | 5433 | `expense_db` |
| Odoo 19 | Custom (Dockerfile) | 8080, 8072 | `expense_odoo` |
| DocStrange OCR | Custom (docstrange/Dockerfile) | 5000 | `docstrange_ocr` |

### Volumes
- `pgdata` — PostgreSQL data persistence
- `odoo_data` — Odoo filestore persistence
- `./docstrange_models` — ML model cache (bind mount)

---

## 👥 Team

**Team: Agent Hacks** — [Odoo × VIT Pune Hackathon 2026](https://hackathon.odoo.com/event/odoo-x-vit-pune-hackathon-26-18/register)

| Photo | Name | Role | GitHub |
| :---: | --- | --- | --- |
| <img src="team_member_details/team_member_1.jpg" width="100" style="border-radius: 50%;"> | **Gurjas Singh Gandhi** | Team Leader | [Gurjas2112](https://github.com/Gurjas2112) |
| <img src="team_member_details/team_member_2.jpeg" width="100" style="border-radius: 50%;"> | **Joy Kujur** | Developer | [joyboy-pega](https://github.com/joyboy-pega) |
| <img src="team_member_details/team_member_4.jpeg" width="100" style="border-radius: 50%;"> | **Sarvesh Varode** | Developer | [sarveshvarode092704](https://github.com/sarveshvarode092704) |
| <img src="team_member_details/team_member_3.jpeg" width="100" style="border-radius: 50%;"> | **Prathamesh Nibandhe** | Developer | [prathamesh-coding](https://github.com/prathamesh-coding) |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🔗 References

- [Odoo 19 Developer Documentation](https://www.odoo.com/documentation/19.0/developer/reference/)
- [DocStrange (NanoNets)](https://github.com/NanoNets/docstrange)
- [ExchangeRate API](https://www.exchangerate-api.com/)
- [REST Countries API](https://restcountries.com/)
- [Problem Statement Mockup](https://link.excalidraw.com/l/65VNwvy7c4X/4WSLZDTrhkA)
