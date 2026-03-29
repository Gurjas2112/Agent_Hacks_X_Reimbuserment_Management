# -*- coding: utf-8 -*-
"""
Receipt Upload Controller
=========================
HTTP endpoint for uploading and scanning receipt images via OCR.
The OCR is handled by the DocStrange Docker container service.
"""

import base64
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.pdf', '.webp', '.tiff'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class ReceiptController(http.Controller):

    @http.route('/upload_receipt', type='http', auth='user', methods=['POST'],
                csrf=False)
    def upload_receipt(self, **kwargs):
        """
        Upload a receipt image for OCR processing.

        Accepts multipart form data with a 'file' field.
        Returns JSON with extracted receipt data.

        Usage:
            curl -X POST http://localhost:8069/upload_receipt \
                -F "file=@receipt.png" \
                -H "Cookie: session_id=..."
        """
        try:
            # Get uploaded file
            uploaded_file = kwargs.get('file') or request.httprequest.files.get('file')

            if not uploaded_file:
                return self._json_error('No file uploaded. Please include a "file" field.', 400)

            filename = uploaded_file.filename
            content = uploaded_file.read()

            # Validate file
            import os
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                return self._json_error(
                    f'Unsupported file type: {ext}. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
                    400
                )

            if len(content) > MAX_FILE_SIZE:
                return self._json_error(
                    f'File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB',
                    400
                )

            if len(content) == 0:
                return self._json_error('Empty file uploaded.', 400)

            # Process via OCR (calls DocStrange Docker API)
            from ..services.ocr_parser import process_receipt

            image_b64 = base64.b64encode(content)
            result = process_receipt(image_b64, filename)

            _logger.info("Receipt processed: %s (confidence: %.1f%%)",
                         filename, result.get('confidence_score', 0))

            return request.make_json_response({
                'success': True,
                'filename': filename,
                'data': result,
            })

        except Exception as e:
            _logger.error("Receipt upload error: %s", str(e))
            return self._json_error(f'Processing failed: {str(e)}', 500)

    @http.route('/upload_receipt/schema', type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_receipt_schema(self, **kwargs):
        """Return the expected OCR extraction schema."""
        from ..services.ocr_parser import RECEIPT_SCHEMA

        return request.make_json_response({
            'success': True,
            'schema': RECEIPT_SCHEMA,
            'description': 'Expected JSON schema for receipt OCR extraction',
        })

    @http.route('/upload_receipt/health', type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_ocr_health(self, **kwargs):
        """Check if the DocStrange OCR service is reachable."""
        from ..services.ocr_parser import check_docstrange_health

        healthy = check_docstrange_health()
        return request.make_json_response({
            'success': True,
            'docstrange_healthy': healthy,
            'message': 'DocStrange OCR service is running' if healthy
                       else 'DocStrange OCR service is not reachable',
        })

    def _json_error(self, message, status_code=400):
        """Return a JSON error response."""
        return request.make_json_response(
            {'success': False, 'error': message},
            status=status_code,
        )
