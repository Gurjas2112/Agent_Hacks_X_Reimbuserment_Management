# -*- coding: utf-8 -*-
"""
Tests for Approval Workflow Engine
====================================
Tests all 4 rule types: sequential, percentage, specific_approver, hybrid.
"""

from odoo.tests.common import TransactionCase


class TestApprovalFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['expense.company'].create({
            'name': 'Flow Test Corp',
            'country': 'India',
            'currency_code': 'INR',
        })

        cls.admin = cls.env['res.users'].create({
            'name': 'Flow Admin',
            'login': 'flow_admin@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'admin',
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_admin').id)],
        })

        cls.manager = cls.env['res.users'].create({
            'name': 'Flow Manager',
            'login': 'flow_manager@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'manager',
            'expense_manager_id': cls.admin.id,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_manager').id)],
        })

        cls.finance = cls.env['res.users'].create({
            'name': 'Flow Finance',
            'login': 'flow_finance@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'manager',
            'expense_manager_id': cls.admin.id,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_manager').id)],
        })

        cls.employee = cls.env['res.users'].create({
            'name': 'Flow Employee',
            'login': 'flow_employee@test.com',
            'expense_company_id': cls.company.id,
            'expense_role': 'employee',
            'expense_manager_id': cls.manager.id,
            'is_manager_approver': True,
            'group_ids': [(4, cls.env.ref('expense_management.group_expense_employee').id)],
        })

    def _create_expense(self):
        """Helper to create a test expense."""
        return self.env['expense.claim'].with_user(self.employee).create({
            'amount_original': 1000.00,
            'currency_original': 'INR',
            'category': 'meals',
            'expense_date': '2026-03-15',
        })

    # -----------------------------------------------------------------
    # Test 1: Sequential Flow
    # -----------------------------------------------------------------

    def test_sequential_3_step_approval(self):
        """Test sequential approval: Manager → Finance → Admin."""
        # Create workflow
        workflow = self.env['approval.workflow'].create({
            'name': 'Sequential Test',
            'company_id': self.company.id,
            'rule_type': 'sequential',
            'is_manager_first': True,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Finance', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.finance.id])],
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 20,
            'name': 'Admin', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        # Step 0: Manager approval
        self.assertEqual(expense.status, 'pending')
        self.assertEqual(expense.current_approver_id, self.manager)
        expense.with_user(self.manager).action_approve()

        # Step 1: Finance approval
        self.assertEqual(expense.status, 'pending')
        self.assertEqual(expense.current_approver_id, self.finance)
        expense.with_user(self.finance).action_approve()

        # Step 2: Admin approval → DONE
        self.assertEqual(expense.status, 'pending')
        self.assertEqual(expense.current_approver_id, self.admin)
        expense.with_user(self.admin).action_approve()

        self.assertEqual(expense.status, 'approved')

    def test_sequential_rejection_stops_flow(self):
        """Test that rejection at any step stops the workflow."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Sequential Reject Test',
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

        # Manager approves
        expense.with_user(self.manager).action_approve()

        # Admin rejects
        expense.with_user(self.admin).action_reject()

        self.assertEqual(expense.status, 'rejected')
        self.assertFalse(expense.current_approver_id)

    # -----------------------------------------------------------------
    # Test 2: Percentage Flow
    # -----------------------------------------------------------------

    def test_percentage_threshold_approval(self):
        """Test percentage rule: 60% threshold with 3 approvers (2 needed)."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Percentage Test',
            'company_id': self.company.id,
            'rule_type': 'percentage',
            'percentage_threshold': 60.0,
            'is_manager_first': False,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Committee', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.manager.id, self.finance.id, self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        # Approver 1 approves (33% — not enough)
        instance = expense.workflow_instance_id
        instance.process_approval(self.manager, 'approve')
        self.assertEqual(instance.status, 'in_progress')

        # Approver 2 approves (66% >= 60% — approved!)
        instance.process_approval(self.finance, 'approve')
        self.assertEqual(instance.status, 'approved')
        self.assertEqual(expense.status, 'approved')

    # -----------------------------------------------------------------
    # Test 3: Specific Approver Flow
    # -----------------------------------------------------------------

    def test_specific_approver_auto_approve(self):
        """Test that the specific approver (CFO) can auto-approve at any step."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Specific Approver Test',
            'company_id': self.company.id,
            'rule_type': 'specific_approver',
            'specific_approver_id': self.admin.id,
            'is_manager_first': True,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Finance', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.finance.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        # Manager approves (Step 0)
        expense.with_user(self.manager).action_approve()

        # Admin approves at Finance step → auto-approve entire workflow
        instance = expense.workflow_instance_id
        instance.process_approval(self.admin, 'approve')

        self.assertEqual(instance.status, 'approved')

    # -----------------------------------------------------------------
    # Test 4: Hybrid Flow
    # -----------------------------------------------------------------

    def test_hybrid_specific_approver_path(self):
        """Test hybrid: specific approver approves → auto-approve."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Hybrid Test',
            'company_id': self.company.id,
            'rule_type': 'hybrid',
            'percentage_threshold': 80.0,
            'specific_approver_id': self.admin.id,
            'is_manager_first': False,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Committee', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.manager.id, self.finance.id, self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        # Admin (specific approver) approves → auto-approve
        instance = expense.workflow_instance_id
        instance.process_approval(self.admin, 'approve')

        self.assertEqual(instance.status, 'approved')

    def test_hybrid_percentage_path(self):
        """Test hybrid: percentage threshold met → approve."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Hybrid Pct Test',
            'company_id': self.company.id,
            'rule_type': 'hybrid',
            'percentage_threshold': 60.0,
            'specific_approver_id': self.admin.id,
            'is_manager_first': False,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Committee', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.manager.id, self.finance.id, self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        instance = expense.workflow_instance_id

        # Manager approves (33%)
        instance.process_approval(self.manager, 'approve')
        self.assertEqual(instance.status, 'in_progress')

        # Finance approves (66% >= 60%)
        instance.process_approval(self.finance, 'approve')
        self.assertEqual(instance.status, 'approved')

    # -----------------------------------------------------------------
    # Test 5: No Manager First
    # -----------------------------------------------------------------

    def test_skip_manager_when_disabled(self):
        """Test that manager step is skipped when is_manager_first is False."""
        workflow = self.env['approval.workflow'].create({
            'name': 'No Manager Test',
            'company_id': self.company.id,
            'rule_type': 'sequential',
            'is_manager_first': False,
        })
        self.env['workflow.step'].create({
            'workflow_id': workflow.id, 'sequence': 10,
            'name': 'Admin Only', 'approver_type': 'specific_user',
            'approver_ids': [(6, 0, [self.admin.id])],
        })

        expense = self._create_expense()
        expense.action_submit()

        # Should go directly to Admin (no manager step)
        self.assertEqual(expense.current_approver_id, self.admin)

        expense.with_user(self.admin).action_approve()
        self.assertEqual(expense.status, 'approved')

    def test_reset_rejected_to_draft(self):
        """Test that a rejected expense can be reset to draft."""
        workflow = self.env['approval.workflow'].create({
            'name': 'Reset Test',
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
        expense.with_user(self.manager).action_reject()

        self.assertEqual(expense.status, 'rejected')

        expense.action_reset_to_draft()
        self.assertEqual(expense.status, 'draft')
        self.assertFalse(expense.workflow_instance_id)
