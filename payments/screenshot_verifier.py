import os
import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from django.conf import settings
from PIL import Image, ImageEnhance

try:
    import pytesseract
except ImportError:
    pytesseract = None

TESSERACT_CMD = os.environ.get('TESSERACT_CMD', '')
if pytesseract and TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def _normalize_text(text):
    return re.sub(r'\s+', ' ', (text or '').upper().strip())


def _extract_amounts(text):
    amounts = []
    patterns = [
        r'KES\s*([\d,]+(?:\.\d{1,2})?)',
        r'KSH\s*([\d,]+(?:\.\d{1,2})?)',
        r'(?:AMOUNT|PAID|TOTAL|SENT|RECEIVED)\s*[:\-]?\s*([\d,]+(?:\.\d{1,2})?)',
        r'(?:^|\s)([\d,]+(?:\.\d{1,2})?)\s*(?:KES|KSH)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group(1).replace(',', '')
            try:
                amounts.append(Decimal(raw))
            except InvalidOperation:
                continue
    return amounts


def _amount_matches(expected, extracted_amounts):
    expected = Decimal(str(expected)).quantize(Decimal('0.01'))
    for amount in extracted_amounts:
        if amount.quantize(Decimal('0.01')) == expected:
            return True, amount
    return False, None


def _fuzzy_name_match(expected_name, text):
    expected = _normalize_text(expected_name)
    if not expected:
        return False, 0.0
    normalized_text = _normalize_text(text)
    if expected in normalized_text:
        return True, 1.0
    ratio = SequenceMatcher(None, expected, normalized_text).ratio()
    if ratio >= 0.75:
        return True, ratio
    for window in range(len(normalized_text.split()) - len(expected.split()) + 1):
        chunk = ' '.join(normalized_text.split()[window:window + len(expected.split()) + 2])
        chunk_ratio = SequenceMatcher(None, expected, chunk).ratio()
        if chunk_ratio >= 0.75:
            return True, chunk_ratio
    return False, ratio


def _number_in_text(numbers, text):
    normalized = re.sub(r'\D', '', text or '')
    for number in numbers:
        digits = re.sub(r'\D', '', number or '')
        if digits and digits in normalized:
            return True, number
    return False, None


def preprocess_image(image):
    img = Image.open(image)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img = img.convert('L')
    img = ImageEnhance.Contrast(img).enhance(2.0)
    return img


def extract_text_from_image(image):
    if pytesseract is None:
        raise RuntimeError('pytesseract is not installed.')
    processed = preprocess_image(image)
    return pytesseract.image_to_string(processed)


def verify_screenshot(image, expected_name, expected_amount, organizer_numbers=None):
    organizer_numbers = organizer_numbers or []
    result = {
        'success': False,
        'amount_matched': False,
        'name_matched': False,
        'number_matched': False,
        'extracted_amount': None,
        'ocr_text': '',
        'notes': '',
    }

    try:
        ocr_text = extract_text_from_image(image)
    except Exception as exc:
        result['notes'] = f'OCR failed: {exc}'
        return result

    result['ocr_text'] = ocr_text
    if not ocr_text.strip():
        result['notes'] = 'Could not read any text from the screenshot.'
        return result

    amounts = _extract_amounts(ocr_text)
    amount_ok, matched_amount = _amount_matches(expected_amount, amounts)
    result['amount_matched'] = amount_ok
    result['extracted_amount'] = str(matched_amount) if matched_amount is not None else None

    name_ok, name_ratio = _fuzzy_name_match(expected_name, ocr_text)
    result['name_matched'] = name_ok

    number_ok = False
    if not name_ok and organizer_numbers:
        number_ok, matched_number = _number_in_text(organizer_numbers, ocr_text)
        result['number_matched'] = number_ok
        if number_ok:
            result['notes'] = f'Organizer payment number {matched_number} found in screenshot.'

    recipient_ok = name_ok or result['number_matched']
    result['success'] = amount_ok and recipient_ok

    if not result['success']:
        parts = []
        if not amount_ok:
            parts.append('payment amount does not match')
        if not recipient_ok:
            parts.append('recipient name or number does not match')
        result['notes'] = '; '.join(parts).capitalize() + '.'
    else:
        result['notes'] = 'Screenshot verification passed.'

    return result
