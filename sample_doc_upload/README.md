# Sample Documents for OCR Testing

This directory contains sample receipts and invoices for testing the expense management
system's OCR receipt scanning feature (powered by DocStrange).

## 📁 Contents

| File | Type | Category | Amount (INR) | Description |
|------|------|----------|--------------|-------------|
| `restaurant_receipt.png` | Thermal receipt | Meals | ₹1,281.00 | Restaurant dinner receipt with GST breakdown |
| `hotel_invoice.png` | Formal invoice | Accommodation | ₹15,104.00 | 2-night hotel stay with itemized charges |
| `taxi_receipt.png` | Cab receipt | Transport | ₹441.13 | Local taxi ride with distance/toll breakdown |
| `office_supplies_receipt.png` | Store receipt | Office Supplies | ₹3,049.12 | Stationery & supplies purchase |

## 🧪 Ground Truth Files

Each receipt has a corresponding `ground_truth_*.json` file containing the expected
OCR extraction output. Use these to validate OCR accuracy:

- `ground_truth_restaurant.json` — Expected output for restaurant receipt
- `ground_truth_hotel.json` — Expected output for hotel invoice
- `ground_truth_taxi.json` — Expected output for taxi receipt
- `ground_truth_office_supplies.json` — Expected output for office supplies receipt

## 📋 Expected JSON Schema

All ground truth files follow the OCR extraction schema:

```json
{
  "vendor": {
    "name": "string",
    "gst_number": "string",
    "address": "string"
  },
  "transaction": {
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "invoice_number": "string"
  },
  "amounts": {
    "subtotal": "number",
    "tax": "number",
    "total": "number",
    "currency": "string"
  },
  "line_items": [
    {
      "name": "string",
      "quantity": "number",
      "unit_price": "number",
      "total_price": "number"
    }
  ],
  "payment": {
    "method": "string",
    "last4_digits": "string"
  },
  "category": "string",
  "confidence_score": "number"
}
```

## 🚀 How to Test

### Via Odoo UI
1. Navigate to **Expense Management → Submit Expense**
2. Upload a receipt image from this directory
3. Click **"Scan Receipt"** button
4. Verify auto-filled fields match the corresponding ground truth JSON

### Via API Endpoint
```bash
curl -X POST http://localhost:8069/upload_receipt \
  -F "file=@restaurant_receipt.png" \
  -H "Content-Type: multipart/form-data"
```

### Via Python Script
```python
from docstrange import DocumentExtractor

extractor = DocumentExtractor()  # cloud mode
result = extractor.extract("restaurant_receipt.png")

# Method 1: Structured extraction with schema
schema = {
    "vendor": {"name": "string", "gst_number": "string", "address": "string"},
    "transaction": {"date": "string", "time": "string", "invoice_number": "string"},
    "amounts": {"subtotal": "number", "tax": "number", "total": "number", "currency": "string"},
    "line_items": [{"name": "string", "quantity": "number", "unit_price": "number", "total_price": "number"}],
    "payment": {"method": "string", "last4_digits": "string"},
    "category": "string",
    "confidence_score": "number"
}
data = result.extract_data(json_schema=schema)
print(data)

# Method 2: Raw markdown for inspection
print(result.extract_markdown())
```

## 📊 Test Coverage Matrix

| Test Case | Receipt | What to Verify |
|-----------|---------|----------------|
| Basic OCR | Restaurant | Vendor name, items, total extracted correctly |
| GST extraction | Restaurant, Office | GST number parsed from receipt |
| Multi-line items | All | Line items with quantity, unit price, total |
| Tax breakdown | Restaurant (CGST/SGST), Hotel (GST 18%) | Tax amounts correctly separated |
| Payment method | Restaurant (Visa), Hotel (Corp Card), Taxi (Cash), Office (UPI) | Various payment types |
| Date formats | All | Different date format parsing |
| Large amounts | Hotel (₹15,104) | High-value receipt handling |
| Category auto-detect | All | Correct expense category assignment |
