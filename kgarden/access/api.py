"""API the K Garden apps call with their service account (role KG Access Service).

* ``verify_pin``: shared floor tablets identify a person by employee code + PIN; the answer says
  whether that person may use the app (and the scope, e.g. a warehouse) and with which role.
* ``access_changes``: who gained, changed or lost access to an app since a time, so the app can
  end sessions without waiting for them to expire.
* ``set_pin``: a super admin sets a person's tablet PIN (stored as a hash only).
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_datetime, now_datetime
from passlib.hash import pbkdf2_sha256

from kgarden.access.user import app_access, is_super_admin

SERVICE_ROLE = "KG Access Service"


def _require_service():
	if not (SERVICE_ROLE in frappe.get_roles() or is_super_admin()):
		frappe.throw(_("Only a K Garden app service account may call this"), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
def set_pin(user: str, pin: str) -> dict:
	if not is_super_admin():
		frappe.throw(_("Only a K Garden super admin can set a PIN"), frappe.PermissionError)
	pin = (pin or "").strip()
	if not (pin.isdigit() and 4 <= len(pin) <= 6):
		frappe.throw(_("A PIN is 4 to 6 digits"))
	if not frappe.db.exists("User", user):
		frappe.throw(_("No user {0}").format(user))
	values = {"pin_hash": pbkdf2_sha256.hash(pin), "set_on": now_datetime(), "set_by": frappe.session.user}
	if frappe.db.exists("KG User PIN", user):
		frappe.db.set_value("KG User PIN", user, values)
	else:
		frappe.get_doc({"doctype": "KG User PIN", "user": user, **values}).insert(ignore_permissions=True)
	return {"user": user, "pin_set": True}


@frappe.whitelist(methods=["POST"])
@rate_limit(key="employee_code", limit=10, seconds=300, ip_based=False)
def verify_pin(app_code: str, employee_code: str, pin: str, scope_value: str | None = None) -> dict:
	"""Who is at the tablet, and may they use this app (here)? Never says which part was wrong."""
	_require_service()
	denied = {"ok": False, "reason": "ไม่พบรหัสพนักงาน หรือ PIN ไม่ถูกต้อง หรือไม่มีสิทธิ์ใช้งาน"}
	user = frappe.db.get_value("User", {"kg_employee_code": (employee_code or "").strip().upper(), "enabled": 1}, "name")
	pin_hash = frappe.db.get_value("KG User PIN", user, "pin_hash") if user else None
	if not pin_hash or not pbkdf2_sha256.verify((pin or "").strip(), pin_hash):
		return denied
	access = app_access(user, app_code)
	if not access.get("granted"):
		return denied
	if scope_value and access.get("scopes") and scope_value not in access["scopes"]:
		return denied
	return {"ok": True, **access}


@frappe.whitelist(methods=["GET"])
def access_changes(app_code: str, since: str) -> list[dict]:
	"""Current access to one app of every managed user changed since ``since`` (ISO datetime)."""
	_require_service()
	users = frappe.get_all(
		"User",
		filters={"kg_access_managed": 1, "modified": [">=", get_datetime(since)]},
		fields=["name", "modified"],
		order_by="modified asc",
		limit_page_length=1000,
	)
	return [{**app_access(u.name, app_code), "user": u.name, "changed_at": str(u.modified)} for u in users]
