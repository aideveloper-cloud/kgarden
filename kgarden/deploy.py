"""First install of a production site (deploy/kg.sh in kgarden-platform runs these with bench execute).

* ``setup_company``: the ERPNext setup wizard without the browser (company, country, currency,
  language, fiscal year), so a rehearsal and the real install end up the same.
* ``provision``: KGF Construction and its accounts, the service accounts the K Garden apps call
  ERPNext with (API keys), and the OAuth clients' addresses for the deployed apps. Idempotent:
  existing API secrets are kept unless ``rotate`` is set. Returns the settings for deploy/.env and
  for the apps' own configuration.
"""

import json
from urllib.parse import urlparse

import frappe

from kgarden.access.setup import APPS

# user -> (user type, roles). The access accounts only call kgarden.access.api.
SERVICE_USERS = {
	"integration@example.com": ("System User", ("Stock User", "Stock Manager", "Manufacturing User", "Item Manager")),
	"mes.access@example.com": ("Website User", ("KG Access Service",)),
	"wms.access@example.com": ("Website User", ("KG Access Service",)),
	"cerp.access@example.com": ("Website User", ("KG Access Service",)),
}


def setup_company(company: str, abbr: str, admin_email: str, language: str = "th",
                  chart_of_accounts: str = "Standard", fy_start: str | None = None) -> str:
	if frappe.db.get_single_value("System Settings", "setup_complete"):
		return "setup already complete"
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	year = frappe.utils.getdate().year
	fy_start = fy_start or f"{year}-01-01"
	fy_end = frappe.utils.add_days(frappe.utils.add_years(fy_start, 1), -1)
	setup_complete({
		"language": language, "country": "Thailand", "timezone": "Asia/Bangkok", "currency": "THB",
		"full_name": "Administrator", "email": admin_email,
		"company_name": company, "company_abbr": abbr, "chart_of_accounts": chart_of_accounts,
		"fy_start_date": fy_start, "fy_end_date": str(fy_end), "setup_demo": 0,
	})
	frappe.db.commit()
	return f"setup complete: {company} ({abbr})"


def provision(urls: str | dict | None = None, rotate: int = 0) -> str:
	"""urls: {"MES_FLOOR": "https://mes...", "CERP": "https://construction...", "WMS": "https://pos..."}"""
	if isinstance(urls, str):
		urls = json.loads(urls or "{}")
	urls = urls or {}
	from kgarden.access.setup import ensure as ensure_access
	from kgarden.construction import setup as construction

	ensure_access()
	construction.ensure()
	keys = {user: _service_user(user, kind, roles, bool(int(rotate))) for user, (kind, roles) in SERVICE_USERS.items()}
	keys[construction.API_USER] = _api_keys(construction.API_USER, bool(int(rotate)))

	clients = {}
	for spec in APPS:
		code, base = spec["app_code"], (urls.get(spec["app_code"]) or "").rstrip("/")
		app = frappe.get_doc("KG App", code)
		if base and spec.get("redirect"):
			redirect = base + urlparse(spec["redirect"]).path
			frappe.db.set_value("OAuth Client", app.oauth_client,
			                    {"redirect_uris": redirect, "default_redirect_uri": redirect})
			app.db_set("base_url", base)
		if app.oauth_client:
			c = frappe.get_doc("OAuth Client", app.oauth_client)
			clients[code] = (c.client_id, c.get_password("client_secret"))
	frappe.db.commit()

	abbr = frappe.db.get_value("Company", construction.COMPANY, "abbr")
	vat = frappe.db.get_value("Account", {"company": construction.COMPANY, "account_type": "Tax",
	                                      "account_name": ["like", "%VAT%"], "is_group": 0}, "name")
	integ, mes_acc, cerp_int = keys["integration@example.com"], keys["mes.access@example.com"], keys[construction.API_USER]
	env = {
		"MES_ERPNEXT_API_KEY": integ[0], "MES_ERPNEXT_API_SECRET": integ[1],
		"WMS_ERPNEXT_API_KEY": integ[0], "WMS_ERPNEXT_API_SECRET": integ[1],
		"MES_ACCESS_API_KEY": mes_acc[0], "MES_ACCESS_API_SECRET": mes_acc[1],
		"MES_OIDC_CLIENT_ID": clients["MES_FLOOR"][0], "MES_OIDC_CLIENT_SECRET": clients["MES_FLOOR"][1],
		"CERP_ERPNEXT_API_KEY": cerp_int[0], "CERP_ERPNEXT_API_SECRET": cerp_int[1],
		"CERP_BRIDGE_COMPANY": construction.COMPANY,
		"CERP_BRIDGE_VAT_ACCOUNT": vat or "",
		"CERP_BRIDGE_WHT_ACCOUNT": f"{construction.WHT_ACCOUNT_NAME} - {abbr}",
		"CERP_BRIDGE_SUPPLIER_GROUP": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "",
	}
	# For the apps' own configuration (ConstructionERP and WMS .env), not for the K Garden stack.
	apps = {
		"CERP_KGARDEN_ACCESS_API_KEY": keys["cerp.access@example.com"][0],
		"CERP_KGARDEN_ACCESS_API_SECRET": keys["cerp.access@example.com"][1],
		"CERP_OIDC_CLIENT_ID": clients["CERP"][0], "CERP_OIDC_CLIENT_SECRET": clients["CERP"][1],
		"WMS_KGARDEN_ACCESS_API_KEY": keys["wms.access@example.com"][0],
		"WMS_KGARDEN_ACCESS_API_SECRET": keys["wms.access@example.com"][1],
		"WMS_OIDC_CLIENT_ID": clients["WMS"][0], "WMS_OIDC_CLIENT_SECRET": clients["WMS"][1],
	}
	return json.dumps({"env": env, "apps": apps})


def _service_user(user: str, user_type: str, roles: tuple, rotate: bool) -> tuple[str, str]:
	if not frappe.db.exists("User", user):
		frappe.get_doc({"doctype": "User", "email": user, "first_name": user.split("@")[0],
		                "user_type": user_type, "send_welcome_email": 0}).insert(ignore_permissions=True)
	doc = frappe.get_doc("User", user)
	have = {r.role for r in doc.roles}
	for role in roles:
		if role not in have:
			doc.append("roles", {"role": role})
	doc.save(ignore_permissions=True)
	return _api_keys(user, rotate)


def _api_keys(user: str, rotate: bool) -> tuple[str, str]:
	doc = frappe.get_doc("User", user)
	secret = doc.get_password("api_secret", raise_exception=False) if doc.api_key else None
	if not doc.api_key or not secret or rotate:
		doc.api_key = doc.api_key or frappe.generate_hash(length=15)
		secret = frappe.generate_hash(length=15)
		doc.api_secret = secret
		doc.save(ignore_permissions=True)
	return doc.api_key, secret
