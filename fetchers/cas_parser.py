"""
fetchers/cas_parser.py
-----------------------
Parses Consolidated Account Statement (CAS) PDFs from CAMS and KFintech.

How to get your CAS:
  CAMS    → https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement
  KFintech → https://mfs.kfintech.com/investor/General/ConsolidatedAccountStatement

Both send a password-protected PDF to your registered email.
Password = PAN (uppercase) + date of birth in DDMMYYYY  e.g. ABCDE1234F01011990

What we extract:
  - Fund name
  - Folio number
  - Current units
  - Current NAV
  - Current value
  - Transaction history (date, type, units, NAV, amount)

The PDF format is not standardised — CAMS and KFintech use different layouts.
We use heuristic regex patterns that cover the most common formats.
"""

import re
import io
import logging
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


def parse_cas_pdf(pdf_bytes: bytes, password: str = "") -> Optional[dict]:
    """
    Parse a CAS PDF and return structured data.

    Args:
        pdf_bytes: Raw PDF file bytes (from Streamlit file_uploader)
        password:  PDF password (PAN + DOB, e.g. ABCDE1234F01011990)

    Returns:
        {
          "investor_name": str,
          "pan":           str,
          "holdings": [
            {
              "fund_name":    str,
              "amfi_code":    str (if detectable),
              "folio":        str,
              "units":        float,
              "nav":          float,
              "value":        float,
              "transactions": [{"date", "type", "units", "nav", "amount"}]
            }
          ]
        }
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return None

    try:
        pdf_file = io.BytesIO(pdf_bytes)

        # Try to open with password, then without
        for pwd in ([password] if password else []) + [""]:
            try:
                with pdfplumber.open(pdf_file, password=pwd) as pdf:
                    full_text = "\n".join(
                        page.extract_text() or "" for page in pdf.pages
                    )
                break
            except Exception:
                pdf_file.seek(0)
                continue
        else:
            logger.error("Could not open PDF — wrong password or corrupted file")
            return None

        return _parse_text(full_text)

    except Exception as exc:
        logger.error("CAS parsing failed: %s", exc)
        return None


def _parse_text(text: str) -> dict:
    """Heuristic parser for CAS text content."""
    result = {
        "investor_name": _extract_investor_name(text),
        "pan":           _extract_pan(text),
        "holdings":      _extract_holdings(text),
    }
    return result


def _extract_investor_name(text: str) -> str:
    patterns = [
        r"Name\s*:\s*([A-Z][A-Z\s]+?)(?:\n|PAN|Email)",
        r"Investor Name\s*:\s*([A-Z][A-Z\s]+?)(?:\n)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "Unknown"


def _extract_pan(text: str) -> str:
    m = re.search(r"PAN\s*:?\s*([A-Z]{5}[0-9]{4}[A-Z])", text)
    return m.group(1) if m else "Unknown"


def _extract_holdings(text: str) -> list:
    """
    Extract individual fund holdings.
    Looks for blocks that start with a fund name and contain transaction tables.
    """
    holdings = []

    # Split by fund sections — CAMS format typically has "Folio No:" as delimiter
    folio_pattern = re.compile(
        r"((?:Folio No|Folio)\s*[:\.]?\s*\d[\d/\-]+)",
        re.IGNORECASE
    )
    sections = folio_pattern.split(text)

    i = 0
    while i < len(sections) - 1:
        if folio_pattern.match(sections[i].strip()):
            folio_line = sections[i].strip()
            body       = sections[i + 1] if i + 1 < len(sections) else ""
            i += 2
        else:
            i += 1
            continue

        folio = re.search(r"[\d/\-]+", folio_line)
        folio = folio.group(0) if folio else "Unknown"

        fund_name = _extract_fund_name_from_block(body)
        units, nav, value = _extract_current_position(body)
        transactions = _extract_transactions(body)

        if fund_name:
            holdings.append({
                "fund_name":    fund_name,
                "amfi_code":    "",   # Not in CAS; user maps manually
                "folio":        folio,
                "units":        units,
                "nav":          nav,
                "value":        value,
                "transactions": transactions,
            })

    return holdings


def _extract_fund_name_from_block(block: str) -> str:
    # Fund name is usually the first non-empty non-numeric line
    for line in block.strip().splitlines():
        line = line.strip()
        if len(line) > 10 and re.search(r"[A-Za-z]{4,}", line):
            if not re.match(r"^[\d\s,\.]+$", line):
                return line
    return ""


def _extract_current_position(block: str) -> tuple:
    """Extract closing units, NAV, value from block."""
    units, nav, value = 0.0, 0.0, 0.0

    # Pattern: "Closing Balance: 150.234 Units @ 42.55 = 6391.45"
    m = re.search(
        r"[Cc]losing\s+[Bb]alance[\s\S]*?(\d[\d,]*\.?\d*)\s+[Uu]nits?\s*[@\s]+(\d[\d,]*\.?\d*)\s*[=\s]+(\d[\d,]*\.?\d*)",
        block
    )
    if m:
        units = float(m.group(1).replace(",", ""))
        nav   = float(m.group(2).replace(",", ""))
        value = float(m.group(3).replace(",", ""))
        return units, nav, value

    # Fallback: look for unit count
    m2 = re.search(r"[Uu]nits?\s*[:\s]+(\d[\d,]*\.?\d{3,})", block)
    if m2:
        units = float(m2.group(1).replace(",", ""))

    return units, nav, value


def _extract_transactions(block: str) -> list:
    """Extract transaction rows: date, type, amount, units, NAV."""
    transactions = []
    # Common CAS row pattern:
    # 01-Jun-2021  Purchase  5,000.00  117.234  42.649
    pattern = re.compile(
        r"(\d{2}[-/]\w{3}[-/]\d{4})\s+"          # date
        r"(Purchase|SIP|Redemption|Switch|Dividend)"  # type
        r"[\s\S]*?"
        r"([\d,]+\.\d{2})\s+"                     # amount
        r"(\d+\.\d{3,})\s+"                        # units
        r"(\d+\.\d{3,})",                          # NAV
        re.IGNORECASE
    )
    for m in pattern.finditer(block):
        txn_type = m.group(2).upper()
        if txn_type in ("REDEMPTION", "SWITCH"):
            txn_type = "REDEEM"
        elif "SIP" in txn_type:
            txn_type = "SIP"
        else:
            txn_type = "BUY"

        try:
            date = pd.to_datetime(m.group(1), dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            continue

        transactions.append({
            "date":   date,
            "type":   txn_type,
            "amount": float(m.group(3).replace(",", "")),
            "units":  float(m.group(4)),
            "nav":    float(m.group(5)),
        })

    return transactions
