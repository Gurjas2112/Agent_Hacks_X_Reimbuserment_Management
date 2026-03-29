# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    expense_company_id = fields.Many2one(
        'expense.company', string='Expense Company',
        help='The company this user belongs to for expense management.'
    )
    expense_role = fields.Selection([
        ('employee', 'Employee'),
        ('manager', 'Manager'),
        ('admin', 'Admin'),
    ], string='Expense Role', default='employee',
        help='Role determines permissions in the expense management system.')

    expense_manager_id = fields.Many2one(
        'res.users', string='Expense Manager',
        help='The manager who supervises this employee for expense approvals.',
        domain="[('expense_role', 'in', ['manager', 'admin'])]"
    )
    team_member_ids = fields.One2many(
        'res.users', 'expense_manager_id', string='Team Members',
        help='Employees reporting to this manager.'
    )
    is_manager_approver = fields.Boolean(
        string='Manager is First Approver', default=True,
        help='If checked, the employee\'s manager will be the first approver before the workflow steps.'
    )

    @api.onchange('expense_role')
    def _onchange_expense_role(self):
        """Assign appropriate security groups based on role."""
        if not self.expense_role:
            return

        group_map = {
            'employee': self.env.ref('expense_management.group_expense_employee', raise_if_not_found=False),
            'manager': self.env.ref('expense_management.group_expense_manager', raise_if_not_found=False),
            'admin': self.env.ref('expense_management.group_expense_admin', raise_if_not_found=False),
        }

        group = group_map.get(self.expense_role)
        if group:
            # The implied_ids will handle cascading (admin implies manager implies employee)
            self.group_ids = [(4, group.id)]

    def action_set_role_employee(self):
        """Set user role to Employee."""
        self.write({'expense_role': 'employee'})
        group = self.env.ref('expense_management.group_expense_employee', raise_if_not_found=False)
        if group:
            self.write({'group_ids': [(4, group.id)]})

    def action_set_role_manager(self):
        """Set user role to Manager."""
        self.write({'expense_role': 'manager'})
        group = self.env.ref('expense_management.group_expense_manager', raise_if_not_found=False)
        if group:
            self.write({'group_ids': [(4, group.id)]})

    def action_set_role_admin(self):
        """Set user role to Admin."""
        self.write({'expense_role': 'admin'})
        group = self.env.ref('expense_management.group_expense_admin', raise_if_not_found=False)
        if group:
            self.write({'group_ids': [(4, group.id)]})
