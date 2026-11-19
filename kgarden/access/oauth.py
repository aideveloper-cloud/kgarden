"""Sign-in through ERPNext (OpenID Connect) with K Garden app access.

Frappe's OAuth server already refuses a client whose ``allowed_roles`` the user lacks (each app's
OAuth Client allows its access role and KG Super Admin, see KG App). These overrides only:

* ``authorize``: show a Thai "no access" page instead of the bare OAuth error JSON;
* ``openid_profile`` (userinfo): add what the user may do in the app asking - ``kg_app``,
  ``kg_role``, ``kg_scopes``, ``kg_scope_doctype``, ``kg_superadmin``, ``kg_employee_code``.
"""

import frappe
from frappe.integrations import oauth2 as core
from frappe.integrations.doctype.oauth_bearer_token.oauth_bearer_token import get_oauth_token_hash

from kgarden.access.user import app_access


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def authorize(**kwargs):
	client_id = frappe.form_dict.get("client_id")
	if frappe.session.user != "Guest" and client_id and frappe.db.exists("OAuth Client", client_id):
		client = frappe.get_doc("OAuth Client", client_id)
		if not client.user_has_allowed_role():
			app = frappe.db.get_value("KG App", {"oauth_client": client_id}, "app_name") or client.app_name
			frappe.respond_as_web_page(
				"ไม่มีสิทธิ์เข้าใช้",
				f"บัญชี <b>{frappe.utils.escape_html(frappe.session.user)}</b> ยังไม่ได้รับสิทธิ์เข้าใช้ "
				f"<b>{frappe.utils.escape_html(app)}</b><br>ติดต่อผู้ดูแลระบบ K Garden เพื่อขอสิทธิ์",
				http_status_code=403,
				indicator_color="red",
			)
			return
	return core.authorize(**kwargs)


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def openid_profile(*args, **kwargs):
	core.openid_profile(*args, **kwargs)
	profile = frappe.local.response
	if not profile.get("email"):
		return  # an OAuth error response
	auth = frappe.get_request_header("Authorization") or ""
	token = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else ""
	# Frappe stores bearer tokens hashed.
	row = frappe.db.get_value(
		"OAuth Bearer Token", {"access_token": get_oauth_token_hash(token), "status": "Active"},
		["user", "client"], as_dict=True,
	) if token else None
	if not row:
		return
	app_code = frappe.db.get_value("KG App", {"oauth_client": row.client}, "name")
	if not app_code:
		return
	access = app_access(row.user, app_code)
	profile.update(
		{
			"kg_app": app_code,
			"kg_access": access.get("granted", False),
			"kg_role": access.get("role"),
			"kg_scopes": access.get("scopes", []),
			"kg_scope_doctype": access.get("scope_doctype", ""),
			"kg_superadmin": access.get("superadmin", False),
			"kg_employee_code": access.get("employee_code", ""),
			"kg_scope_refs": access.get("scope_refs", {}),
		}
	)
