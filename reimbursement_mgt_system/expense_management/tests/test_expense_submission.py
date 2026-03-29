# -*- coding: utf-8 -*-
"""
Tests for Expense Submission
=============================
Validates expense creation, validation, and currency conversion.
"""

from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestExpenseSubmission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test company
        cls.company = cls.env['expense.company'].create({
            'name': 'Test Corp',
            'country': 'India',
            'currency_code': 'INR',
            'currency_symbol': '₹',
        })

        # Create test users
        cls.admin_user = cls.env['res.users'].create({
            'name': 'Test Admin',
            'login': 'test_admin@test.com',
            'email': 'test_admin@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'admin',
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_admin').id)],
        })

        cls.manager_user = cls.env['res.users'].create({
            'name': 'Test Manager',
            'login': 'test_manager@test.com',
            'email': 'test_manager@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'manager',
            'expense_manager_id': cls.admin_user.id,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_manager').id)],
        })

        cls.employee_user = cls.env['res.users'].create({
            'name': 'Test Employee',
            'login': 'test_employee@test.com',
            'email': 'test_employee@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'employee',
            'expense_manager_id': cls.manager_user.id,
            'is_manager_approver': True,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_employee').id)],
        })

        # Create a test workflow
        cls.workflow = cls.env['approval.workflow'].create({
            'name': 'Test Sequential Workflow',
            'company_id': cls.company.id,
            'rule_type': 'sequential',
            'is_manager_first': True,
        })

        cls.env['workflow.step'].create({
            'workflow_id': cls.workflow.id,
            'sequence': 10,
            'name': 'Admin Approval',
            'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [cls.admin_user.id])],
        })

    def test_create_expense(self):
        """Test basic expense creation with auto-generated sequence."""
        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 1500.00,
            'currency_original': 'INR',
            'category': 'meals',
            'description': 'Lunch with client',
            'expense_date': '2026-03-15',
        })

        self.assertTrue(expense.name.startswith('EXP/'))
        self.assertEqual(expense.status, 'draft')
        self.assertEqual(expense.employee_id, self.employee_user)
        self.assertEqual(expense.company_id, self.company)

    def test_expense_validation_zero_amount(self):
        """Test that zero amount expense cannot be submitted."""
        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 0,
            'currency_original': 'INR',
            'category': 'meals',
            'expense_date': '2026-03-15',
        })

        with self.assertRaises(ValidationError):
            expense.action_submit()

    def test_expense_same_currency_no_conversion(self):
        """Test that same currency needs no conversion."""
        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 2000.00,
            'currency_original': 'INR',
            'category': 'transport',
            'expense_date': '2026-03-15',
        })

        expense.action_submit()
        self.assertEqual(expense.amount_converted, 2000.00)
        self.assertEqual(expense.exchange_rate, 1.0)
        self.assertEqual(expense.status, 'pending')

    @patch('odoo.addons.expense_management.services.currency_service.get_exchange_rate')
    @patch('odoo.addons.expense_management.services.currency_service.convert_currency')
    def test_expense_different_currency_conversion(self, mock_convert, mock_rate):
        """Test currency conversion when expense currency differs from company."""
        mock_rate.return_value = 83.5
        mock_convert.return_value = 8350.00

        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 100.00,
            'currency_original': 'USD',
            'category': 'travel',
            'expense_date': '2026-03-15',
        })

        expense.action_submit()
        self.assertEqual(expense.amount_converted, 8350.00)
        self.assertEqual(expense.exchange_rate, 83.5)

    def test_submit_creates_workflow_instance(self):
        """Test that submitting creates a workflow instance."""
        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 500.00,
            'currency_original': 'INR',
            'category': 'office_supplies',
            'expense_date': '2026-03-15',
        })

        expense.action_submit()
        self.assertTrue(expense.workflow_instance_id)
        self.assertEqual(expense.workflow_instance_id.status, 'in_progress')
        self.assertEqual(expense.status, 'pending')

    def test_submit_creates_approval_log(self):
        """Test that submission is logged."""
        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 300.00,
            'currency_original': 'INR',
            'category': 'meals',
            'expense_date': '2026-03-15',
        })

        expense.action_submit()
        logs = self.env['approval.log'].search([('expense_id', '=', expense.id)])
        self.assertTrue(len(logs) >= 1)
        self.assertEqual(logs[0].action, 'submitted')

    def test_only_draft_can_be_submitted(self):
        """Test that only draft expenses can be submitted."""
        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 500.00,
            'currency_original': 'INR',
            'category': 'meals',
            'expense_date': '2026-03-15',
        })

        expense.action_submit()

        with self.assertRaises(UserError):
            expense.action_submit()

    def test_expense_line_total_computed(self):
        """Test that line item total is computed correctly."""
        expense = self.env['expense.claim'].with_user(self.employee_user).create({
            'amount_original': 1000.00,
            'currency_original': 'INR',
            'category': 'meals',
            'expense_date': '2026-03-15',
        })

        line = self.env['expense.claim.line'].create({
            'claim_id': expense.id,
            'name': 'Test Item',
            'quantity': 3,
            'unit_price': 150.00,
        })

        self.assertEqual(line.total_price, 450.00)
