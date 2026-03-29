# -*- coding: utf-8 -*-
"""
OCR Receipt Parser Service — DocStrange Docker Edition
=======================================================
Sends receipt images to the DocStrange Docker container for OCR extraction,
then parses the raw text through a regex/heuristic pipeline to produce
structured JSON matching the RECEIPT_SCHEMA.

Architecture:
    Receipt (binary) → DocStrange API (/api/extract) → raw text → regex pipeline → JSON

Fallback:
    If the DocStrange container is unreachable, falls back to a pure-regex stub.
"""

import base64
import json
import logging
import os
import re
import tempfile

import requests as http_requests

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# DocStrange Docker container URL (docker-compose service name = 'docstrange')
# Inside Docker network: http://docstrange:5000
# From host machine:     http://localhost:5000
DOCSTRANGE_URL = os.environ.get('DOCSTRANGE_URL', 'http://docstrange:5000')
DOCSTRANGE_EXTRACT_ENDPOINT = f'{DOCSTRANGE_URL}/api/extract'
DOCSTRANGE_HEALTH_ENDPOINT = f'{DOCSTRANGE_URL}/api/health'
DOCSTRANGE_TIMEOUT = 60  # seconds

# Receipt extraction schema — target output format
RECEIPT_SCHEMA = {
    "vendor": {"name": "string", "gst_number": "string", "address": "string"},
    "transaction": {"date": "string", "time": "string", "invoice_number": "string"},
    "amounts": {"subtotal": "number", "tax": "number", "total": "number", "currency": "string"},
    "line_items": [{"name": "string", "quantity": "number", "unit_price": "number", "total_price": "number"}],
    "payment": {"method": "string", "last4_digits": "string"},
    "category": "string",
    "confidence_score": "number"
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_receipt(image_binary, filename='receipt.png'):
    """
    Process a receipt image using the DocStrange Docker OCR service.

    Pipeline:
        1. Write binary to temp file
        2. POST to DocStrange /api/extract (output_format=text)
        3. Parse raw text with regex pipeline
        4. Return structured JSON

    Args:
        image_binary: Base64-encoded binary data of the receipt image.
        filename:     Original filename of the receipt.

    Returns:
        dict: Structured receipt data matching RECEIPT_SCHEMA.
    """
    temp_path = None
    try:
        # Decode base64 binary to file
        image_data = base64.b64decode(image_binary)

        # Determine file extension
        ext = os.path.splitext(filename)[1].lower() if filename else '.png'
        if ext not in ('.png', '.jpg', '.jpeg', '.pdf', '.webp', '.tiff'):
            ext = '.png'

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(image_data)
            temp_path = tmp.name

        _logger.info("Processing receipt: %s (%d bytes)", filename, len(image_data))

        # ------------------------------------------------------------------
        # Step 1: Try DocStrange Docker API extraction
        # ------------------------------------------------------------------
        raw_text = _extract_via_docstrange_api(temp_path, filename)

        if raw_text and len(raw_text.strip()) > 10:
            _logger.info("DocStrange API returned %d chars of text", len(raw_text))
            result = _parse_receipt_text(raw_text)
            result['_extraction_method'] = 'docstrange_docker_api'
            return result

        # ------------------------------------------------------------------
        # Step 2: Try DocStrange JSON extraction
        # ------------------------------------------------------------------
        json_data = _extract_json_via_docstrange_api(temp_path, filename)
        if json_data:
            _logger.info("DocStrange JSON extraction succeeded")
            result = _parse_json_result(json_data)
            result['_extraction_method'] = 'docstrange_docker_json'
            return result

        # ------------------------------------------------------------------
        # Step 3: Fallback — empty result
        # ------------------------------------------------------------------
        _logger.warning("All extraction methods failed, returning empty result")
        return _empty_result()

    except Exception as e:
        _logger.error("Receipt processing error: %s", str(e))
        return _empty_result()
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# DocStrange Docker API integration
# ---------------------------------------------------------------------------

def _extract_via_docstrange_api(file_path, filename='receipt.png'):
    """
    Send a file to the DocStrange Docker container API for text extraction.

    POST /api/extract with multipart form data.
    Returns raw extracted text or None on failure.
    """
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {
                'output_format': 'text',
                'processing_mode': 'cloud',
            }
            response = http_requests.post(
                DOCSTRANGE_EXTRACT_ENDPOINT,
                files=files,
                data=data,
                timeout=DOCSTRANGE_TIMEOUT
            )

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return result.get('content', '')
            else:
                _logger.warning("DocStrange API returned success=false: %s",
                                result.get('error', 'unknown'))
        else:
            _logger.warning("DocStrange API HTTP %d: %s",
                            response.status_code, response.text[:200])

    except http_requests.exceptions.ConnectionError:
        _logger.warning("Cannot connect to DocStrange at %s — is the container running?",
                        DOCSTRANGE_URL)
    except http_requests.exceptions.Timeout:
        _logger.warning("DocStrange API timed out after %ds", DOCSTRANGE_TIMEOUT)
    except Exception as e:
        _logger.error("DocStrange API error: %s", str(e))

    return None


def _extract_json_via_docstrange_api(file_path, filename='receipt.png'):
    """
    Send a file to DocStrange Docker API for JSON extraction.
    Returns parsed JSON dict or None.
    """
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {
                'output_format': 'json',
                'processing_mode': 'cloud',
            }
            response = http_requests.post(
                DOCSTRANGE_EXTRACT_ENDPOINT,
                files=files,
                data=data,
                timeout=DOCSTRANGE_TIMEOUT
            )

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                content = result.get('content', '')
                if isinstance(content, str):
                    return json.loads(content)
                return content

    except Exception as e:
        _logger.error("DocStrange JSON API error: %s", str(e))

    return None


def check_docstrange_health():
    """Check if the DocStrange Docker service is healthy."""
    try:
        resp = http_requests.get(DOCSTRANGE_HEALTH_ENDPOINT, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Parse JSON result from DocStrange into RECEIPT_SCHEMA
# ---------------------------------------------------------------------------

def _parse_json_result(data):
    """Map DocStrange JSON output to our receipt schema."""
    if not data or not isinstance(data, dict):
        return _empty_result()

    result = _empty_result()

    # Try to extract text content and parse it
    text = json.dumps(data)
    if text:
        result = _parse_receipt_text(text)

    return result


# ---------------------------------------------------------------------------
# Regex/heuristic receipt text parsing pipeline
# ---------------------------------------------------------------------------

def _parse_receipt_text(text):
    """Parse raw receipt text using regex patterns and heuristics."""
    data = _empty_result()

    if not text:
        return data

    lines = text.strip().split('\n')

    # Vendor name — typically first non-empty line
    data['vendor']['name'] = extract_vendor_name(lines)

    # GST number
    data['vendor']['gst_number'] = extract_gst(text)

    # Address
    data['vendor']['address'] = extract_address(text)

    # Date
    data['transaction']['date'] = extract_date(text)

    # Time
    data['transaction']['time'] = extract_time(text)

    # Invoice number
    data['transaction']['invoice_number'] = extract_invoice_number(text)

    # Amounts
    amounts = extract_amounts(text)
    data['amounts'] = amounts

    # Payment method
    data['payment']['method'] = extract_payment_method(text)
    data['payment']['last4_digits'] = extract_card_digits(text)

    # Line items
    data['line_items'] = extract_line_items(text)

    # Category guess
    data['category'] = guess_category(text, data['vendor']['name'])

    # Confidence
    data['confidence_score'] = calculate_confidence(data)

    return data


# ---------------------------------------------------------------------------
# Extraction helper functions
# ---------------------------------------------------------------------------

def extract_vendor_name(lines):
    """Extract vendor name from the first meaningful lines."""
    for line in lines[:5]:
        clean = line.strip()
        if clean and len(clean) > 2 and not re.match(r'^[\d\-/]+$', clean):
            # Skip lines that look like dates/numbers
            if not re.match(r'^\d{2}[/\-]\d{2}[/\-]\d{2,4}', clean):
                return clean
    return ''


def extract_gst(text):
    """Extract GST/GSTIN number."""
    patterns = [
        r'(?:GST(?:IN)?[\s:]*?)(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d][A-Z\d])',
        r'(?:GST\s*No\.?\s*:?\s*)([A-Z0-9]{15})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ''


def extract_address(text):
    """Extract address — look for lines with street/city/pin patterns."""
    pin_match = re.search(r'(\d{6})', text)
    if pin_match:
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if pin_match.group(1) in line:
                addr_lines = []
                if i > 0:
                    addr_lines.append(lines[i - 1].strip())
                addr_lines.append(line.strip())
                return ', '.join(addr_lines)
    return ''


def extract_date(text):
    """Extract date from various formats."""
    patterns = [
        r'(\d{2}[/\-]\d{2}[/\-]\d{4})',          # DD/MM/YYYY or DD-MM-YYYY
        r'(\d{4}[/\-]\d{2}[/\-]\d{2})',          # YYYY-MM-DD
        r'(\d{2}\s+\w{3,9}\s+\d{4})',             # DD Month YYYY
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',    # D/M/YY
        r'Date\s*:?\s*(\S+)',                      # Date: value
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ''


def extract_time(text):
    """Extract time from receipt text."""
    patterns = [
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',     # 12-hour format
        r'(\d{1,2}:\d{2}:\d{2})',                   # HH:MM:SS
        r'Time\s*:?\s*(\d{1,2}:\d{2})',             # Time: HH:MM
        r'(\d{2}:\d{2})',                            # HH:MM
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ''


def extract_invoice_number(text):
    """Extract invoice/receipt number."""
    patterns = [
        r'(?:Invoice|Receipt|Bill|Inv)[\s#:]*([A-Z0-9\-/]+)',
        r'(?:No\.?|Number)[\s:]*([A-Z0-9\-/]+)',
        r'(?:Ref)[\s:]*([A-Z0-9\-/]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ''


def extract_amounts(text):
    """Extract subtotal, tax, and total from text."""
    amounts = {'subtotal': 0, 'tax': 0, 'total': 0, 'currency': 'INR'}

    # Currency detection
    if re.search(r'(?:USD|\$)', text):
        amounts['currency'] = 'USD'
    elif re.search(r'(?:EUR|€)', text):
        amounts['currency'] = 'EUR'
    elif re.search(r'(?:GBP|£)', text):
        amounts['currency'] = 'GBP'
    elif re.search(r'(?:Rs\.?|INR|₹)', text):
        amounts['currency'] = 'INR'

    # Total — look for the largest amount near "total" keyword
    total_patterns = [
        r'(?:Grand\s*)?Total\s*:?\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
        r'(?:Amount\s*(?:Due|Payable))\s*:?\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
        r'(?:Net\s*Amount)\s*:?\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
    ]
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amounts['total'] = float(match.group(1).replace(',', ''))
            break

    # Subtotal
    sub_patterns = [
        r'Sub\s*[-]?\s*Total\s*:?\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
        r'(?:Before\s*Tax)\s*:?\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
    ]
    for pattern in sub_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amounts['subtotal'] = float(match.group(1).replace(',', ''))
            break

    # Tax
    tax_patterns = [
        r'(?:CGST|SGST|IGST|GST|Tax|VAT)\s*(?:\d*\.?\d*\s*%?)?\s*:?\s*(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
    ]
    total_tax = 0
    for pattern in tax_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                total_tax += float(match.group(1).replace(',', ''))
            except ValueError:
                pass
    amounts['tax'] = total_tax

    # If no subtotal but total and tax, compute
    if amounts['total'] and amounts['tax'] and not amounts['subtotal']:
        amounts['subtotal'] = amounts['total'] - amounts['tax']

    return amounts


def extract_payment_method(text):
    """Extract payment method."""
    methods = {
        'visa': 'Visa', 'mastercard': 'MasterCard', 'amex': 'Amex',
        'upi': 'UPI', 'cash': 'Cash', 'debit': 'Debit Card',
        'credit': 'Credit Card', 'gpay': 'Google Pay', 'paytm': 'Paytm',
        'phonepe': 'PhonePe', 'net banking': 'Net Banking',
        'corporate card': 'Corporate Card', 'cheque': 'Cheque',
    }
    text_lower = text.lower()
    for key, value in methods.items():
        if key in text_lower:
            return value
    return ''


def extract_card_digits(text):
    """Extract last 4 digits of card."""
    patterns = [
        r'(?:ending|last\s*4|card)\s*(?:in|:)?\s*(\d{4})',
        r'[*xX]{4,}\s*(\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ''


def extract_line_items(text):
    """Extract line items from receipt text."""
    items = []
    lines = text.split('\n')

    item_patterns = [
        r'(\d+)\s*[xX×]\s+(.+?)\s+(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
        r'(.+?)\s+(\d+)\s+(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)\s+(?:Rs\.?|INR|₹|\$|€|£)?\s*([\d,]+\.?\d*)',
    ]

    for line in lines:
        clean = line.strip()
        if not clean or len(clean) < 5:
            continue

        # Skip header/footer lines
        if any(kw in clean.lower() for kw in ['total', 'subtotal', 'tax', 'gst', 'payment', 'date', 'invoice']):
            continue

        for pattern in item_patterns:
            match = re.match(pattern, clean)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    items.append({
                        'name': groups[1].strip(),
                        'quantity': float(groups[0]),
                        'unit_price': float(groups[2].replace(',', '')),
                        'total_price': float(groups[0]) * float(groups[2].replace(',', '')),
                    })
                elif len(groups) == 4:
                    items.append({
                        'name': groups[0].strip(),
                        'quantity': float(groups[1]),
                        'unit_price': float(groups[2].replace(',', '')),
                        'total_price': float(groups[3].replace(',', '')),
                    })
                break

    return items


def guess_category(text, vendor_name=''):
    """Guess expense category from text content."""
    text_lower = (text + ' ' + vendor_name).lower()

    category_keywords = {
        'meals': ['restaurant', 'food', 'dining', 'cafe', 'coffee', 'lunch',
                  'dinner', 'breakfast', 'biryani', 'pizza', 'swiggy', 'zomato'],
        'accommodation': ['hotel', 'inn', 'resort', 'lodge', 'airbnb',
                          'room charge', 'check-in', 'check-out', 'oyo'],
        'transport': ['taxi', 'cab', 'uber', 'ola', 'lyft', 'auto',
                      'rickshaw', 'fare', 'toll', 'rapido'],
        'travel': ['flight', 'airline', 'train', 'railway', 'bus',
                   'travel', 'boarding', 'makemytrip', 'irctc'],
        'office_supplies': ['staples', 'stationery', 'office', 'paper',
                            'printer', 'ink', 'pen', 'amazon'],
        'medical': ['pharmacy', 'medical', 'hospital', 'doctor',
                    'clinic', 'health', 'apollo', 'medplus'],
        'training': ['training', 'course', 'seminar', 'workshop',
                     'conference', 'education', 'udemy'],
    }

    for category, keywords in category_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return category

    return 'miscellaneous'


def calculate_confidence(data):
    """Calculate confidence score (0-100) based on which fields were extracted."""
    if not data:
        return 0

    score = 0
    checks = [
        (data.get('vendor', {}).get('name'), 15),
        (data.get('vendor', {}).get('address'), 5),
        (data.get('vendor', {}).get('gst_number'), 10),
        (data.get('transaction', {}).get('date'), 15),
        (data.get('transaction', {}).get('invoice_number'), 10),
        (data.get('amounts', {}).get('total'), 20),
        (data.get('amounts', {}).get('subtotal'), 5),
        (data.get('amounts', {}).get('tax'), 5),
        (data.get('payment', {}).get('method'), 5),
        (data.get('line_items'), 5),
        (data.get('category'), 5),
    ]

    for value, weight in checks:
        if value:
            score += weight

    return min(score, 100)


def _empty_result():
    """Return empty result matching RECEIPT_SCHEMA."""
    return {
        'vendor': {'name': '', 'gst_number': '', 'address': ''},
        'transaction': {'date': '', 'time': '', 'invoice_number': ''},
        'amounts': {'subtotal': 0, 'tax': 0, 'total': 0, 'currency': 'INR'},
        'line_items': [],
        'payment': {'method': '', 'last4_digits': ''},
        'category': 'miscellaneous',
        'confidence_score': 0
    }
