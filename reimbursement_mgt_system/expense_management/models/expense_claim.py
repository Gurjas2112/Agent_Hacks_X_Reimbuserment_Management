# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ExpenseClaim(models.Model):
    _name = 'expense.claim'
    _description = 'Expense Claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference', required=True, readonly=True,
        default=lambda self: _('New'), copy=False
    )
    employee_id = fields.Many2one(
        'res.users', string='Employee', required=True,
        default=lambda self: self.env.user,
        tracking=True, readonly=True,
        states={'draft': [('readonly', False)]}
    )
    company_id = fields.Many2one(
        'expense.company', string='Company',
        related='employee_id.expense_company_id',
        store=True, readonly=True
    )

    # Amount fields
    amount_original = fields.Float(
        string='Original Amount', required=True, digits=(16, 2),
        tracking=True, readonly=True,
        states={'draft': [('readonly', False)]}
    )
    currency_original = fields.Char(
        string='Expense Currency', required=True, default='INR',
        tracking=True, readonly=True,
        states={'draft': [('readonly', False)]},
        help='Currency of the expense (can differ from company currency).'
    )
    amount_converted = fields.Float(
        string='Converted Amount', digits=(16, 2), readonly=True,
        help='Amount in company\'s default currency.'
    )
    company_currency = fields.Char(
        string='Company Currency',
        related='company_id.currency_code',
        store=True, readonly=True
    )
    exchange_rate = fields.Float(
        string='Exchange Rate', digits=(16, 6), readonly=True
    )

    # Details
    category = fields.Selection([
        ('travel', 'Travel'),
        ('meals', 'Meals'),
        ('accommodation', 'Accommodation'),
        ('transport', 'Transport'),
        ('office_supplies', 'Office Supplies'),
        ('training', 'Training'),
        ('medical', 'Medical'),
        ('miscellaneous', 'Miscellaneous'),
    ], string='Category', required=True, tracking=True,
        readonly=True, states={'draft': [('readonly', False)]})

    description = fields.Text(
        string='Description', readonly=True,
        states={'draft': [('readonly', False)]}
    )
    expense_date = fields.Date(
        string='Expense Date', required=True,
        default=fields.Date.context_today,
        tracking=True, readonly=True,
        states={'draft': [('readonly', False)]}
    )

    # Receipt
    receipt = fields.Binary(
        string='Receipt', attachment=True,
        readonly=True, states={'draft': [('readonly', False)]}
    )
    receipt_filename = fields.Char(string='Receipt Filename')

    # Status & Workflow
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True,
        tracking=True, copy=False)

    current_approver_id = fields.Many2one(
        'res.users', string='Current Approver', readonly=True,
        tracking=True
    )
    workflow_instance_id = fields.Many2one(
        'workflow.instance', string='Workflow Instance',
        readonly=True, copy=False
    )

    # Related records
    claim_line_ids = fields.One2many(
        'expense.claim.line', 'claim_id', string='Expense Lines',
        readonly=True, states={'draft': [('readonly', False)]},
        copy=True
    )
    approval_log_ids = fields.One2many(
        'approval.log', 'expense_id', string='Approval History',
        readonly=True
    )

    # OCR extracted fields
    ocr_vendor_name = fields.Char(string='Vendor Name (OCR)', readonly=True)
    ocr_vendor_address = fields.Char(string='Vendor Address (OCR)', readonly=True)
    ocr_vendor_gst = fields.Char(string='Vendor GST (OCR)', readonly=True)
    ocr_date = fields.Char(string='Date (OCR)', readonly=True)
    ocr_invoice_number = fields.Char(string='Invoice Number (OCR)', readonly=True)
    ocr_subtotal = fields.Float(string='Subtotal (OCR)', readonly=True)
    ocr_tax = fields.Float(string='Tax (OCR)', readonly=True)
    ocr_total = fields.Float(string='Total (OCR)', readonly=True)
    ocr_payment_method = fields.Char(string='Payment Method (OCR)', readonly=True)
    ocr_confidence_score = fields.Float(string='OCR Confidence (%)', readonly=True)
    ocr_raw_data = fields.Text(string='OCR Raw Data', readonly=True)

    # Policy violation
    policy_violation = fields.Boolean(
        string='Policy Violation', default=False, readonly=True,
        help='Flagged if expense exceeds configured policy limits.'
    )
    policy_warning = fields.Text(
        string='Policy Warning', readonly=True,
        help='Details about the policy violation.'
    )

    # Computed
    approval_count = fields.Integer(
        string='Approval Count', compute='_compute_approval_count'
    )

    @api.depends('approval_log_ids')
    def _compute_approval_count(self):
        for rec in self:
            rec.approval_count = len(rec.approval_log_ids)

    def action_view_approval_logs(self):
        """Open approval log records for this expense."""
        self.ensure_one()
        return {
            'name': _('Approval History'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.log',
            'view_mode': 'tree,form',
            'domain': [('expense_id', '=', self.id)],
            'context': {'default_expense_id': self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('expense.claim') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_submit(self):
        """Submit expense for approval. Converts currency and starts workflow."""
        self.ensure_one()

        if self.status != 'draft':
            raise UserError(_('Only draft expenses can be submitted.'))

        if self.amount_original <= 0:
            raise ValidationError(_('Expense amount must be greater than zero.'))

        if not self.company_id:
            raise UserError(_('Your user must be assigned to an expense company before submitting.'))

        # Convert currency if different from company currency
        self._convert_currency()

        # Check expense policies
        self._check_policy()

        # Find and assign workflow
        workflow = self._find_workflow()
        if not workflow:
            raise UserError(_('No approval workflow is configured for your company. Please contact your admin.'))

        # Create workflow instance and start it
        instance = self.env['workflow.instance'].create({
            'expense_id': self.id,
            'workflow_id': workflow.id,
        })
        instance.start_workflow()

        self.write({
            'status': 'pending',
            'workflow_instance_id': instance.id,
            'current_approver_id': instance.get_current_approver_id(),
        })

        # Log submission
        self.env['approval.log'].create({
            'expense_id': self.id,
            'user_id': self.env.uid,
            'action': 'submitted',
            'comment': _('Expense submitted for approval.'),
            'step_sequence': 0,
        })

        # Notify first approver
        self._notify_approver()

        # Send submission email
        self._send_email_template('expense_management.email_template_expense_submitted')

        return True

    def action_approve(self):
        """Approve the expense at the current workflow step."""
        self.ensure_one()

        if self.status != 'pending':
            raise UserError(_('Only pending expenses can be approved.'))

        user = self.env.user
        instance = self.workflow_instance_id

        if not instance:
            raise UserError(_('No workflow instance found for this expense.'))

        # Delegate to workflow engine
        result = instance.process_approval(user, 'approve')

        # Update expense based on workflow result
        if instance.status == 'approved':
            self.write({
                'status': 'approved',
                'current_approver_id': False,
            })
            self.message_post(body=_('Expense has been fully approved.'))
            self._send_email_template('expense_management.email_template_expense_approved')
        else:
            # Move to next approver
            self.write({
                'current_approver_id': instance.get_current_approver_id(),
            })
            self._notify_approver()

        return True

    def action_reject(self):
        """Reject the expense."""
        self.ensure_one()

        if self.status != 'pending':
            raise UserError(_('Only pending expenses can be rejected.'))

        instance = self.workflow_instance_id
        if instance:
            instance.process_approval(self.env.user, 'reject')

        self.write({
            'status': 'rejected',
            'current_approver_id': False,
        })

        self.message_post(body=_('Expense has been rejected.'))
        self._send_email_template('expense_management.email_template_expense_rejected')
        return True

    def action_reset_to_draft(self):
        """Reset a rejected expense back to draft."""
        self.ensure_one()
        if self.status not in ('rejected',):
            raise UserError(_('Only rejected expenses can be reset to draft.'))

        self.write({
            'status': 'draft',
            'workflow_instance_id': False,
            'current_approver_id': False,
        })
        return True

    def action_scan_receipt(self):
        """Scan the uploaded receipt using OCR and auto-fill fields."""
        self.ensure_one()

        if not self.receipt:
            raise UserError(_('Please upload a receipt image first.'))

        try:
            from ..services.ocr_parser import process_receipt

            result = process_receipt(self.receipt, self.receipt_filename or 'receipt.png')

            if not result:
                raise UserError(_('OCR processing returned no results.'))

            # Map OCR results to fields
            vendor = result.get('vendor', {})
            transaction = result.get('transaction', {})
            amounts = result.get('amounts', {})
            payment = result.get('payment', {})

            update_vals = {
                'ocr_vendor_name': vendor.get('name', ''),
                'ocr_vendor_address': vendor.get('address', ''),
                'ocr_vendor_gst': vendor.get('gst_number', ''),
                'ocr_date': transaction.get('date', ''),
                'ocr_invoice_number': transaction.get('invoice_number', ''),
                'ocr_subtotal': amounts.get('subtotal', 0),
                'ocr_tax': amounts.get('tax', 0),
                'ocr_total': amounts.get('total', 0),
                'ocr_payment_method': payment.get('method', ''),
                'ocr_confidence_score': result.get('confidence_score', 0),
                'ocr_raw_data': str(result),
            }

            # Auto-fill main fields if in draft
            if self.status == 'draft':
                if amounts.get('total'):
                    update_vals['amount_original'] = amounts['total']
                if amounts.get('currency'):
                    update_vals['currency_original'] = amounts['currency']
                if result.get('category'):
                    # Map OCR category to selection
                    category_map = {
                        'food': 'meals', 'restaurant': 'meals', 'dining': 'meals',
                        'hotel': 'accommodation', 'lodging': 'accommodation',
                        'taxi': 'transport', 'cab': 'transport', 'uber': 'transport',
                        'travel': 'travel', 'flight': 'travel', 'train': 'travel',
                        'office': 'office_supplies', 'stationery': 'office_supplies',
                        'medical': 'medical', 'pharmacy': 'medical',
                        'training': 'training', 'education': 'training',
                    }
                    ocr_cat = result['category'].lower()
                    for key, val in category_map.items():
                        if key in ocr_cat:
                            update_vals['category'] = val
                            break

                if vendor.get('name') and not self.description:
                    update_vals['description'] = _('Expense at %s') % vendor['name']

            self.write(update_vals)

            # Create line items from OCR
            line_items = result.get('line_items', [])
            if line_items and self.status == 'draft':
                # Remove existing lines
                self.claim_line_ids.unlink()
                for item in line_items:
                    self.env['expense.claim.line'].create({
                        'claim_id': self.id,
                        'name': item.get('name', 'Unknown Item'),
                        'quantity': item.get('quantity', 1),
                        'unit_price': item.get('unit_price', 0),
                    })

            self.message_post(body=_(
                'Receipt scanned successfully. Confidence: %.1f%%'
            ) % result.get('confidence_score', 0))

        except ImportError:
            raise UserError(_(
                'DocStrange is not installed. Please run: pip install docstrange'
            ))
        except Exception as e:
            _logger.error("OCR processing failed: %s", str(e))
            raise UserError(_('OCR processing failed: %s') % str(e))

        return True

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    def _convert_currency(self):
        """Convert expense amount to company currency using ExchangeRate API."""
        self.ensure_one()

        company_currency = self.company_id.currency_code
        expense_currency = self.currency_original.upper().strip()

        if not company_currency:
            raise UserError(_('Company currency is not configured.'))

        if expense_currency == company_currency:
            self.write({
                'amount_converted': self.amount_original,
                'exchange_rate': 1.0,
            })
            return

        try:
            from ..services.currency_service import convert_currency, get_exchange_rate

            rate = get_exchange_rate(expense_currency, company_currency)
            converted = convert_currency(self.amount_original, expense_currency, company_currency)

            self.write({
                'amount_converted': round(converted, 2),
                'exchange_rate': rate,
            })

            _logger.info(
                "Converted %s %s → %s %s (rate: %s)",
                self.amount_original, expense_currency,
                converted, company_currency, rate
            )

        except Exception as e:
            _logger.error("Currency conversion failed: %s", str(e))
            # Fallback: use original amount
            self.write({
                'amount_converted': self.amount_original,
                'exchange_rate': 1.0,
            })
            self.message_post(body=_(
                'Currency conversion failed (%s). Using original amount.'
            ) % str(e))

    def _find_workflow(self):
        """Find an active workflow for the employee's company."""
        return self.env['approval.workflow'].search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ], limit=1)

    def _check_policy(self):
        """Check expense against configured policies for the company."""
        self.ensure_one()
        if not self.company_id:
            return

        policies = self.env['expense.policy'].search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
            '|',
            ('category', '=', self.category),
            ('category', '=', 'all'),
        ])

        warnings = []
        for policy in policies:
            amount = self.amount_converted or self.amount_original
            if policy.max_amount > 0 and amount > policy.max_amount:
                warnings.append(_(
                    'Exceeds %s limit of %s %s (claimed: %s %s)'
                ) % (
                    dict(self._fields['category'].selection).get(self.category, self.category),
                    policy.max_amount, self.company_currency or 'INR',
                    amount, self.company_currency or 'INR',
                ))

            if policy.require_receipt and not self.receipt:
                warnings.append(_(
                    'Receipt is required for %s expenses over %s %s'
                ) % (
                    dict(self._fields['category'].selection).get(self.category, self.category),
                    policy.receipt_threshold, self.company_currency or 'INR',
                ))

        if warnings:
            self.write({
                'policy_violation': True,
                'policy_warning': '\n'.join(warnings),
            })
            self.message_post(body=_(
                '⚠️ Policy Warning:\n%s'
            ) % '\n'.join(warnings))

    def _notify_approver(self):
        """Send notification to the current approver via mail activity."""
        if not self.current_approver_id:
            return

        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.current_approver_id.id,
            summary=_('Expense Approval Required: %s') % self.name,
            note=_(
                'Expense claim %s by %s for %s %s requires your approval.'
            ) % (self.name, self.employee_id.name,
                 self.amount_original, self.currency_original),
        )

    def _send_email_template(self, template_xmlid):
        """Send an email using the specified template (fail silently)."""
        try:
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=False)
        except Exception as e:
            _logger.warning("Email template send failed (%s): %s", template_xmlid, str(e))
