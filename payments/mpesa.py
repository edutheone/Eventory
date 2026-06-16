import base64
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime
import os

logger = logging.getLogger(__name__)


# Fallback helper to mimic decouple.config()
def config(key, default=None):
    val = os.environ.get(key)
    if val is None:
        if default is not None:
            return default
        logger.warning(f"Environment variable '{key}' is not set.")
        return ""
    return val


# standard-library urllib request compatibility wrappers
class UrllibResponse:
    def __init__(self, content, status_code):
        self.content = content
        self.text = content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content
        self.status_code = status_code

    def json(self):
        try:
            return json.loads(self.text)
        except Exception:
            return {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error {self.status_code}: {self.text}")


def urllib_request(method, url, data=None, headers=None, auth=None, timeout=10):
    req_headers = {}
    if headers:
        for k, v in headers.items():
            req_headers[k] = v

    if auth:
        auth_str = f"{auth[0]}:{auth[1]}"
        auth_encoded = base64.b64encode(auth_str.encode()).decode()
        req_headers["Authorization"] = f"Basic {auth_encoded}"

    req_data = None
    if data:
        if isinstance(data, (dict, list)):
            req_data = json.dumps(data).encode('utf-8')
            if 'Content-Type' not in req_headers:
                req_headers['Content-Type'] = 'application/json'
        elif isinstance(data, str):
            req_data = data.encode('utf-8')
        else:
            req_data = data

    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return UrllibResponse(response.read(), response.status)
    except urllib.error.HTTPError as e:
        return UrllibResponse(e.read(), e.code)
    except Exception as e:
        return UrllibResponse(str(e).encode('utf-8'), 500)


class MpesaClient:
    def __init__(self):
        self.env = config("MPESA_ENVIRONMENT", default="sandbox")
        self.consumer_key = config("MPESA_CONSUMER_KEY")
        self.consumer_secret = config("MPESA_CONSUMER_SECRET")
        self.shortcode = config("MPESA_SHORTCODE", default="174379")
        self.passkey = config("MPESA_PASSKEY")
        self.callback_url = config("MPESA_CALLBACK_URL")

        if self.env == "production":
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"

    @classmethod
    def is_configured(cls):
        """True when platform STK credentials are present in environment."""
        client = cls()
        return bool(
            client.consumer_key
            and client.consumer_secret
            and client.passkey
            and client.shortcode
            and client.callback_url
        )

    @staticmethod
    def normalize_phone(phone_number):
        phone = str(phone_number).strip().replace(' ', '')
        if phone.startswith('+'):
            phone = phone[1:]
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        if phone.startswith('7') and len(phone) == 9:
            phone = '254' + phone
        return phone

    def get_access_token(self):
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        response = urllib_request("GET", url, auth=(self.consumer_key, self.consumer_secret))
        response.raise_for_status()
        return response.json()["access_token"]

    def get_password(self):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{self.shortcode}{self.passkey}{timestamp}"
        encoded = base64.b64encode(raw.encode()).decode()
        return encoded, timestamp

    def stk_push(self, phone_number, amount, account_ref, description):
        if not self.is_configured():
            return {
                'errorMessage': 'M-Pesa STK is not configured on the server.',
            }

        access_token = self.get_access_token()
        password, timestamp = self.get_password()
        phone = self.normalize_phone(phone_number)

        account_ref = str(account_ref)[:12]
        description = str(description)[:13]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        # Sandbox shortcode 174379 uses Pay Bill; production till uses Buy Goods.
        transaction_type = (
            "CustomerBuyGoodsOnline"
            if self.env == "production"
            else "CustomerPayBillOnline"
        )
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": transaction_type,
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": account_ref,
            "TransactionDesc": description,
        }

        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        response = urllib_request("POST", url, data=payload, headers=headers)
        try:
            return response.json()
        except Exception:
            logger.exception('M-Pesa STK push returned non-JSON response: %s', response.text)
            return {
                'errorMessage': response.text or 'M-Pesa STK push failed.',
            }