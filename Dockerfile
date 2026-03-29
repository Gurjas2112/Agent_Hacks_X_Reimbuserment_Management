# =============================================================================
# Dockerfile — Expense Management (Odoo 19) — Lightweight Build
# =============================================================================
# Uses official Odoo 19 image with only lightweight deps added.
# docstrange OCR is OPTIONAL — the module falls back to regex-based parsing.
# =============================================================================

FROM odoo:19.0

USER root

# Install lightweight system deps (tesseract for local OCR fallback)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Odoo config
COPY ./config/odoo.conf /etc/odoo/odoo.conf

# Copy the expense_management module
COPY ./reimbursement_mgt_system/expense_management /mnt/extra-addons/expense_management

# Copy sample docs for testing
COPY ./sample_doc_upload /mnt/sample_doc_upload

# Fix ownership
RUN chown -R odoo:odoo /mnt/extra-addons /mnt/sample_doc_upload /etc/odoo/odoo.conf

USER odoo

EXPOSE 8069 8072
