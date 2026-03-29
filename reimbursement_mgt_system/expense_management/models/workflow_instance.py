# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class WorkflowInstance(models.Model):
    _name = 'workflow.instance'
    _description = 'Workflow Instance (Runtime Engine)'
    _order = 'create_date desc'

    expense_id = fields.Many2one(
        'expense.claim', string='Expense Claim',
        required=True, ondelete='cascade'
    )
    workflow_id = fields.Many2one(
        'approval.workflow', string='Workflow',
        required=True
    )
    current_step = fields.Integer(string='Current Step Index', default=0)
    total_steps = fields.Integer(string='Total Steps', compute='_compute_total_steps', store=True)
    status = fields.Selection([
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='in_progress')

    instance_step_ids = fields.One2many(
        'workflow.instance.step', 'instance_id',
        string='Instance Steps'
    )

    # Workflow config (copied for reference)
    rule_type = fields.Selection(related='workflow_id.rule_type', store=True)
    percentage_threshold = fields.Float(related='workflow_id.percentage_threshold')
    specific_approver_id = fields.Many2one(related='workflow_id.specific_approver_id')

    @api.depends('instance_step_ids')
    def _compute_total_steps(self):
        for rec in self:
            rec.total_steps = len(rec.instance_step_ids)

    # -----------------------------------------------------------------------
    # Workflow Lifecycle
    # -----------------------------------------------------------------------

    def start_workflow(self):
        """Initialize the workflow instance: create runtime steps from the workflow config."""
        self.ensure_one()
        workflow = self.workflow_id
        expense = self.expense_id
        employee = expense.employee_id
        steps_to_create = []
        seq = 0

        # Step 0: Manager approval (if is_manager_first and employee has a manager)
        if workflow.is_manager_first and employee.is_manager_approver and employee.expense_manager_id:
            steps_to_create.append({
                'instance_id': self.id,
                'step_id': False,  # No workflow.step record for the auto-manager step
                'sequence': seq,
                'name': _('Manager Approval (%s)') % employee.expense_manager_id.name,
                'approver_ids': [(6, 0, [employee.expense_manager_id.id])],
            })
            seq += 1

        # Regular workflow steps
        for step in workflow.step_ids.sorted('sequence'):
            approver_ids = self._resolve_step_approvers(step, employee)
            steps_to_create.append({
                'instance_id': self.id,
                'step_id': step.id,
                'sequence': seq,
                'name': step.name,
                'approver_ids': [(6, 0, approver_ids)],
            })
            seq += 1

        # Create all instance steps
        for step_vals in steps_to_create:
            self.env['workflow.instance.step'].create(step_vals)

        self.current_step = 0
        _logger.info("Workflow started for expense %s with %d steps", expense.name, len(steps_to_create))

    def _resolve_step_approvers(self, step, employee):
        """Resolve the approver user IDs for a workflow step."""
        if step.approver_type == 'manager':
            if employee.expense_manager_id:
                return [employee.expense_manager_id.id]
            return []

        elif step.approver_type == 'specific_user':
            return step.approver_ids.ids

        elif step.approver_type == 'role_based':
            if step.role_group_id:
                return step.role_group_id.users.ids
            return []

        return []

    # -----------------------------------------------------------------------
    # Core Approval Engine
    # -----------------------------------------------------------------------

    def process_approval(self, user, action):
        """
        Process an approval or rejection action.

        This is the CORE WORKFLOW ENGINE that handles all 4 rule types:
        - sequential: step-by-step, each must approve
        - percentage: threshold % of approvers must approve
        - specific_approver: auto-approve if specific person approves
        - hybrid: percentage threshold OR specific approver
        """
        self.ensure_one()

        if self.status != 'in_progress':
            return

        current_instance_step = self._get_current_instance_step()
        if not current_instance_step:
            _logger.warning("No current step found for workflow instance %s", self.id)
            return

        # Verify this user is authorized to approve at this step
        if user.id not in current_instance_step.approver_ids.ids:
            # For percentage/hybrid, check if user is in ANY step
            if self.rule_type in ('percentage', 'hybrid'):
                all_approvers = self.instance_step_ids.mapped('approver_ids').ids
                if user.id not in all_approvers:
                    return
            else:
                return

        # Log the action
        self.env['approval.log'].create({
            'expense_id': self.expense_id.id,
            'user_id': user.id,
            'action': 'approved' if action == 'approve' else 'rejected',
            'comment': _('%s by %s at step: %s') % (
                'Approved' if action == 'approve' else 'Rejected',
                user.name, current_instance_step.name
            ),
            'step_sequence': current_instance_step.sequence,
        })

        if action == 'reject':
            self._reject_workflow(current_instance_step, user)
            return

        # ---- APPROVAL LOGIC BY RULE TYPE ----

        if self.rule_type == 'sequential':
            self._process_sequential(current_instance_step, user)

        elif self.rule_type == 'percentage':
            self._process_percentage(current_instance_step, user)

        elif self.rule_type == 'specific_approver':
            self._process_specific_approver(current_instance_step, user)

        elif self.rule_type == 'hybrid':
            self._process_hybrid(current_instance_step, user)

    # ---- Sequential: Approve step, move to next ----
    def _process_sequential(self, instance_step, user):
        """Sequential: one approver per step. Step approved → move to next."""
        instance_step.write({
            'status': 'approved',
            'approved_by_ids': [(4, user.id)],
        })

        # Check if there are more steps
        if self._has_more_steps():
            self._advance_to_next_step()
        else:
            self._complete_workflow()

    # ---- Percentage: Check if threshold reached ----
    def _process_percentage(self, instance_step, user):
        """Percentage: accumulate approvals across all approvers. Approve if >= threshold."""
        instance_step.write({
            'approved_by_ids': [(4, user.id)],
        })

        # Count total approvals across ALL steps
        total_approvers = len(self.instance_step_ids.mapped('approver_ids'))
        total_approved = len(self.instance_step_ids.mapped('approved_by_ids'))

        if total_approvers > 0:
            pct = (total_approved / total_approvers) * 100
            if pct >= self.percentage_threshold:
                # Threshold reached — approve all
                for step in self.instance_step_ids:
                    step.status = 'approved'
                self._complete_workflow()
                return

        # Check if current step is fully approved to advance
        step_approvers = len(instance_step.approver_ids)
        step_approved = len(instance_step.approved_by_ids)
        if step_approved >= step_approvers:
            instance_step.status = 'approved'
            if self._has_more_steps():
                self._advance_to_next_step()

    # ---- Specific Approver: Auto-approve if matched ----
    def _process_specific_approver(self, instance_step, user):
        """Specific Approver: if the designated person approves at any step, auto-approve."""
        instance_step.write({
            'approved_by_ids': [(4, user.id)],
        })

        # Check if this user is THE specific approver
        if self.specific_approver_id and user.id == self.specific_approver_id.id:
            # Auto-approve entire workflow
            for step in self.instance_step_ids:
                step.status = 'approved'
            self._complete_workflow()
            return

        # Otherwise, treat like sequential
        instance_step.status = 'approved'
        if self._has_more_steps():
            self._advance_to_next_step()
        else:
            self._complete_workflow()

    # ---- Hybrid: Percentage OR Specific Approver ----
    def _process_hybrid(self, instance_step, user):
        """Hybrid: approve if EITHER percentage threshold met OR specific approver approves."""
        instance_step.write({
            'approved_by_ids': [(4, user.id)],
        })

        # Check 1: Is this the specific approver?
        if self.specific_approver_id and user.id == self.specific_approver_id.id:
            for step in self.instance_step_ids:
                step.status = 'approved'
            self._complete_workflow()
            return

        # Check 2: Has the percentage threshold been met?
        total_approvers = len(self.instance_step_ids.mapped('approver_ids'))
        total_approved = len(self.instance_step_ids.mapped('approved_by_ids'))

        if total_approvers > 0:
            pct = (total_approved / total_approvers) * 100
            if pct >= self.percentage_threshold:
                for step in self.instance_step_ids:
                    step.status = 'approved'
                self._complete_workflow()
                return

        # Neither condition met — advance step if current is complete
        step_approvers = len(instance_step.approver_ids)
        step_approved = len(instance_step.approved_by_ids)
        if step_approved >= step_approvers:
            instance_step.status = 'approved'
            if self._has_more_steps():
                self._advance_to_next_step()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _get_current_instance_step(self):
        """Get the current instance step."""
        return self.instance_step_ids.filtered(
            lambda s: s.sequence == self.current_step and s.status == 'pending'
        )[:1]

    def _has_more_steps(self):
        """Check if there are more steps after the current one."""
        return self.current_step < (self.total_steps - 1)

    def _advance_to_next_step(self):
        """Move to the next step in the workflow."""
        self.current_step += 1
        next_step = self.instance_step_ids.filtered(
            lambda s: s.sequence == self.current_step
        )[:1]
        if next_step:
            next_step.status = 'pending'

        # Update expense's current approver
        self.expense_id.write({
            'current_approver_id': self.get_current_approver_id(),
        })

        _logger.info("Workflow %s advanced to step %d", self.id, self.current_step)

    def _complete_workflow(self):
        """Mark workflow as approved."""
        self.status = 'approved'
        _logger.info("Workflow %s completed — expense %s approved", self.id, self.expense_id.name)

    def _reject_workflow(self, instance_step, user):
        """Mark workflow and step as rejected."""
        instance_step.write({
            'status': 'rejected',
            'rejected_by_id': user.id,
        })
        self.status = 'rejected'
        self.expense_id.write({
            'status': 'rejected',
            'current_approver_id': False,
        })
        self.expense_id.message_post(
            body=_('Expense rejected by %s at step: %s') % (user.name, instance_step.name)
        )
        _logger.info("Workflow %s rejected at step %d by %s", self.id, self.current_step, user.name)

    def get_current_approver_id(self):
        """Get the first approver of the current step."""
        current = self._get_current_instance_step()
        if current and current.approver_ids:
            return current.approver_ids[0].id
        return False
