"""App access on the User form: the one place K Garden people get, change and lose access.

A user's ``kg_app_access`` rows say which apps they may use, with which role and scope.
``kg_superadmin`` opens every app as admin. On save:

* only Administrator or a KG Super Admin may change these fields;
* the Frappe roles follow the rows: each granted app's access role (the OAuth Client checks it at
  sign-in), the ERPNext roles of the desk app's role, KG Super Admin + System Manager for a super
  admin; managed roles nobody granted are removed, so the form is the whole truth;
* after save, OAuth tokens of apps the user may no longer use are revoked at once.

Users never given access (integration accounts, Administrator) are left alone: the sync runs only
for users this form has managed (``kg_access_managed``).
"""

import frappe
from frappe import _

from kgarden.access.login import sync_login_name
from kgarden.k_garden.doctype.kg_app.kg_app import SUPER_ADMIN_ROLE, split_roles

ACCESS_FIELDS = ("kg_superadmin", "kg_employee_code", "kg_app_access")
SKIP_USERS = ("Administrator", "Guest")


def is_super_admin(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or SUPER_ADMIN_ROLE in frappe.get_roles(user)


def _apps() -> dict[str, frappe._dict]:
	apps = {}
	for app in frappe.get_all("KG App", fields=["name", "app_name", "enabled", "is_desk", "access_role",
	                                            "scope_doctype", "scope_required"]):
		app.roles = {
			r.role_code: split_roles(r.erpnext_roles)
			for r in frappe.get_all("KG App Role", filters={"parent": app.name, "parenttype": "KG App"},
			                        fields=["role_code", "erpnext_roles"])
		}
		apps[app.name] = app
	return apps


def _access_snapshot(doc) -> tuple:
	rows = tuple(sorted((r.app, r.app_role, r.scope_value or "") for r in doc.get("kg_app_access") or []))
	return (int(doc.get("kg_superadmin") or 0), doc.get("kg_employee_code") or "", rows)


def before_validate(doc, method=None):
	if doc.name in SKIP_USERS:
		return
	before = doc.get_doc_before_save()
	changed = _access_snapshot(doc) != (_access_snapshot(before) if before else (0, "", ()))
	if changed and not is_super_admin():
		frappe.throw(_("Only a K Garden super admin can change which apps a user may use"), frappe.PermissionError)

	if doc.kg_employee_code:
		doc.kg_employee_code = doc.kg_employee_code.strip().upper()
	sync_login_name(doc, before)
	if doc.kg_superadmin or doc.get("kg_app_access"):
		doc.kg_access_managed = 1
	if not doc.kg_access_managed:
		return
	# Everyone signs in with their employee code; checked when access is given or changed, so people
	# set up before this rule are asked for it the next time a super admin changes their access.
	if doc.enabled and not doc.kg_employee_code and (changed or doc.is_new()):
		frappe.throw(_("ใส่รหัสพนักงานก่อน: ทุกระบบของ K Garden เข้าสู่ระบบด้วยรหัสพนักงานและรหัสผ่าน"))

	apps = _apps()
	granted, seen = set(), set()
	for row in doc.get("kg_app_access") or []:
		app = apps.get(row.app)
		if not app:
			frappe.throw(_("Row {0}: unknown app {1}").format(row.idx, row.app))
		if row.app_role not in app.roles:
			frappe.throw(_("Row {0}: {1} has no role {2} (roles: {3})").format(
				row.idx, app.app_name, row.app_role, ", ".join(sorted(app.roles))))
		row.scope_doctype = app.scope_doctype or ""
		if not app.scope_doctype:
			row.scope_value = None
		elif app.scope_required and not row.scope_value:
			frappe.throw(_("Row {0}: {1} needs a {2}").format(row.idx, app.app_name, app.scope_doctype))
		key = (row.app, row.scope_value or "")
		if key in seen:
			frappe.throw(_("Row {0}: {1} is granted twice for the same scope").format(row.idx, app.app_name))
		seen.add(key)
		if not app.enabled:
			continue  # kept on the form, grants nothing while the app is switched off
		granted.add(app.access_role)
		granted.update(app.roles[row.app_role])
	if doc.kg_superadmin:
		granted.update({SUPER_ADMIN_ROLE, "System Manager"})

	managed = {SUPER_ADMIN_ROLE, "System Manager"}
	for app in apps.values():
		managed.add(app.access_role)
		for roles in app.roles.values():
			managed.update(roles)

	current = {r.role for r in doc.get("roles")}
	doc.set("roles", [r for r in doc.get("roles") if r.role not in managed or r.role in granted])
	for role in sorted(granted - current):
		doc.append("roles", {"role": role})


def on_update(doc, method=None):
	if doc.name in SKIP_USERS or not doc.get("kg_access_managed"):
		return
	revoke_tokens_without_access(doc.name, enabled=bool(doc.enabled))


def revoke_tokens_without_access(user: str, enabled: bool = True) -> int:
	"""Revoke the user's active OAuth tokens for every client they may no longer use."""
	roles = set(frappe.get_roles(user)) if enabled else set()
	revoked = 0
	for token in frappe.get_all("OAuth Bearer Token", filters={"user": user, "status": "Active"},
	                            fields=["name", "client"]):
		allowed = {r.role for r in frappe.get_doc("OAuth Client", token.client).allowed_roles}
		if not (allowed & roles):
			frappe.db.set_value("OAuth Bearer Token", token.name, "status", "Revoked")
			revoked += 1
	return revoked


def app_access(user: str, app_code: str) -> dict:
	"""What a user may do in one app: granted?, role, scopes. Super admins get every app as admin."""
	u = frappe.db.get_value("User", user, ["enabled", "full_name", "kg_superadmin", "kg_employee_code"], as_dict=True)
	if not u:
		return {"granted": False}
	# Administrator is the site owner: every app, as a super admin.
	superadmin = bool(u.kg_superadmin) or user == "Administrator"
	result = {"user": user, "full_name": u.full_name, "employee_code": u.kg_employee_code or "",
	          "superadmin": superadmin, "app": app_code, "granted": False, "role": None, "scopes": []}
	app = frappe.db.get_value("KG App", app_code, ["enabled", "scope_doctype"], as_dict=True)
	if not u.enabled or not app or not app.enabled:
		return result
	result["scope_doctype"] = app.scope_doctype or ""
	if superadmin:
		result.update(granted=True, role="superadmin", scopes=[])
		return result
	rows = frappe.get_all("KG User App Access", filters={"parent": user, "parenttype": "User", "app": app_code},
	                      fields=["app_role", "scope_value"], order_by="idx")
	if rows:
		# One role per app; scopes are the union of the rows (an empty scope means everything).
		result.update(granted=True, role=rows[0].app_role,
		              scopes=[] if any(not r.scope_value for r in rows) else [r.scope_value for r in rows])
	result["scope_refs"] = scope_refs(app.scope_doctype, result["scopes"])
	return result


def scope_refs(scope_doctype: str | None, scopes: list[str]) -> dict[str, str]:
	"""The app's own ids of the scope records, when the records carry one (``kg_cerp_id`` on a
	Project booked from ConstructionERP), so the app does not have to look ERPNext names up."""
	if not scope_doctype or not scopes or not frappe.get_meta(scope_doctype).has_field("kg_cerp_id"):
		return {}
	rows = frappe.get_all(scope_doctype, filters={"name": ["in", scopes]}, fields=["name", "kg_cerp_id"])
	return {r.name: r.kg_cerp_id for r in rows if r.kg_cerp_id}
