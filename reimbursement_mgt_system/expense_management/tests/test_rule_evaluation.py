# -*- coding: utf-8 -*-
"""
Tests for Rule Evaluation Edge Cases
======================================
Tests edge cases in workflow rule evaluation.
"""

from odoo.tests.common import TransactionCase


class TestRuleEvaluation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['expense.company'].create({
            'name': 'Rule Test Corp',
            'country': 'India',
            'currency_code': 'INR',
        })

        cls.admin = cls.env['res.users'].create({
            'name': 'Rule Admin',
            'login': 'rule_admin@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'admin',
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_admin').id)],
        })

        cls.manager1 = cls.env['res.users'].create({
            'name': 'Rule Manager 1',
            'login': 'rule_mgr1@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'manager',
            'expense_manager_id': cls.admin.id,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_manager').id)],
        })

        cls.manager2 = cls.env['res.users'].create({
            'name': 'Rule Manager 2',
            'login': 'rule_mgr2@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'manager',
            'expense_manager_id': cls.admin.id,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_manager').id)],
        })

        cls.employee = cls.env['res.users'].create({
            'name': 'Rule Employee',
            'login': 'rule_emp@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'employee',
            'expense_manager_id': cls.manager1.id,
            'is_manager_approver': True,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_employee').id)],
        })

    def _create_expense(self):
        return self.env['expense.claim'].with_user(self.employee).create({
            'amount_original': 500.00,
            'currency_original': 'INR',
            'category': 'meals',
            'expense_date': '2026-03-15',
        })

    def test_single_approver_sequential(self):
        """Test sequential with only 1 step (no manager)."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Single Step',
            'company_id': self.company.id,
            'rule_type': 'sequential',
            'is_manager_first': False,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Single', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()
        expense.with_user(self.admin).action_approve()
        self.assertEqual(expense.status, 'approved')

    def test_percentage_100_threshold(self):
        """Test percentage with 100% threshold (all must approve)."""
        workflow = self.env['approval.workflow'].create({
            'name': '100% Threshold',
            'company_id': self.company.id,
            'rule_type': 'percentage',
            'percentage_threshold': 100.0,
            'is_manager_first': False,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'All must approve', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.manager1.id, self.manager2.id, self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()
        instance = expense.workflow_instance_id

        # 1 of 3 approves (33%)
        instance.process_approval(self.manager1, 'approve')
        self.assertEqual(instance.status, 'in_progress')

        # 2 of 3 approve (66%)
        instance.process_approval(self.manager2, 'approve')
        self.assertEqual(instance.status, 'in_progress')

        # 3 of 3 approve (100%)
        instance.process_approval(self.admin, 'approve')
        self.assertEqual(instance.status, 'approved')

    def test_rejection_at_first_step(self):
        """Test rejection at the very first step."""
        workflow = self.env['approval.workflow'].create({
            'name': 'First Step Reject',
            'company_id': self.company.id,
            'rule_type': 'sequential',
            'is_manager_first': True,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Admin', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        # Manager rejects at Step 0
        expense.with_user(self.manager1).action_reject()
        self.assertEqual(expense.status, 'rejected')

    def test_workflow_instance_step_counts(self):
        """Test that instance step counts are computed correctly."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Count Test',
            'company_id': self.company.id,
            'rule_type': 'sequential',
            'is_manager_first': True,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Step A', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.manager2.id])],
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 20,
            'name': 'Step B', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        instance = expense.workflow_instance_id
        # Manager step (0) + Step A (1) + Step B (2) = 3 total
        self.assertEqual(instance.total_steps, 3)

    def test_approval_log_created_for_each_action(self):
        """Test that each approval/rejection creates a log entry."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Log Test',
            'company_id': self.company.id,
            'rule_type': 'sequential',
            'is_manager_first': True,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Admin', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        # Should have 1 log: submitted
        logs = self.env['approval.log'].search([('expense_id', '=', expense.id)])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, 'submitted')

        # Manager approves → 2 logs
        expense.with_user(self.manager1).action_approve()
        logs = self.env['approval.log'].search([('expense_id', '=', expense.id)])
        self.assertEqual(len(logs), 2)

        # Admin approves → 3 logs
        expense.with_user(self.admin).action_approve()
        logs = self.env['approval.log'].search([('expense_id', '=', expense.id)])
        self.assertEqual(len(logs), 3)

    def test_employee_no_manager_workflow_without_manager_step(self):
        """Test workflow for employee without a manager (is_manager_first=False)."""
        employee_no_mgr = self.env['res.users'].create({
            'name': 'No Manager Employee',
            'login': 'no_mgr@test.com',
            'expense_company_id': self.company.id,
            'expense_role': 'employee',
            'is_manager_approver': False,
            'group_ids': [(4, self.env.ref('expense_management.group_expense_employee').id)],
        })

        workflow = self.env['approval.workflow'].create({
            'name': 'No Manager Workflow',
            'company_id': self.company.id,
            'rule_type': 'sequential',
            'is_manager_first': False,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Admin Direct', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.admin.id])],
        })

        expense = self.env['expense.claim'].with_user(employee_no_mgr).create({
            'amount_original': 200.00,
            'currency_original': 'INR',
            'category': 'miscellaneous',
            'expense_date': '2026-03-15',
        })

        expense.action_submit()
        self.assertEqual(expense.current_approver_id, self.admin)

        expense.with_user(self.admin).action_approve()
        self.assertEqual(expense.status, 'approved')
