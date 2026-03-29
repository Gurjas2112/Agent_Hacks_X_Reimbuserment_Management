# -*- coding: utf-8 -*-
{
    'name': 'Expense Management - Reimbursement System',
    'version': '19.0.1.1.0',
    'category': 'Accounting/Expenses',
    'summary': 'Configurable expense reimbursement with multi-level approval workflows, OCR receipt scanning, and currency conversion',
    'description': """
        Reimbursement Management System
        ================================
        - Role-based access: Admin, Manager, Employee
        - Multi-currency expense submission with auto-conversion
        - Configurable approval workflows (sequential, percentage, specific approver, hybrid)
        - OCR receipt scanning via DocStrange
        - Expense policy engine with per-category spending limits
        - Email notifications for key workflow events
        - Analytical reports with pivot and graph views
        - Full audit trail with approval history
        - Notification system via Odoo mail/activity
    """,
    'author': 'Agent Hacks',
    'website': 'https://github.com/Gurjas2112/Agent_Hacks_X_Reimbuserment_Management',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'contacts',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        # Security (must load first)
        'security/expense_groups.xml',
        'security/ir.model.access.csv',
        'security/expense_security.xml',

        # Data
        'data/expense_sequence.xml',
        'data/mail_templates.xml',

        # Views
        'views/expense_company_views.xml',
        'views/res_users_views.xml',
        'views/expense_claim_views.xml',
        'views/expense_policy_views.xml',
        'views/approval_workflow_views.xml',
        'views/approval_dashboard_views.xml',
        'views/expense_report_views.xml',
        'views/menu_items.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
}
