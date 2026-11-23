# Copyright (c) 2026, K Garden and contributors
# For license information, please see license.txt

"""An application K Garden people sign in to through ERPNext (the core).

Each app has an access role. A user may open the app only with that role (or KG Super Admin):
the app's OAuth Client allows exactly those two roles, so ERPNext refuses to sign anyone else in.
"""

import frappe
from frappe import _
from frappe.model.document import Document

SUPER_ADMIN_ROLE = "KG Super Admin"


def access_role_name(app_code: str) -> str:
	return f"KG App: {app_code}"


class KGApp(Document):
	def validate(self):
		self.app_code = (self.app_code or "").strip().upper()
		codes = [r.role_code.strip() for r in self.roles]
		if len(codes) != len(set(codes)):
			frappe.throw(_("Role codes must be unique within an app"))
		for row in self.roles:
			row.role_code = row.role_code.strip()
			for role in split_roles(row.erpnext_roles):
				if not frappe.db.exists("Role", role):
					frappe.throw(_("Row {0}: ERPNext role {1} does not exist").format(row.idx, role))
		if not self.is_desk and any(split_roles(r.erpnext_roles) for r in self.roles):
			frappe.throw(_("Only the ERPNext desk app can grant ERPNext roles"))
		self.access_role = access_role_name(self.app_code)
		ensure_role(self.access_role, desk_access=0)

	def on_update(self):
		if self.oauth_client:
			set_client_roles(self.oauth_client, [self.access_role, SUPER_ADMIN_ROLE])
		from kgarden.access.desktop import sync_desktop_icons

		sync_desktop_icons()


def split_roles(value: str | None) -> list[str]:
	return [r.strip() for r in (value or "").split(",") if r.strip()]


def ensure_role(name: str, desk_access: int) -> None:
	if not frappe.db.exists("Role", name):
		frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": desk_access}).insert(
			ignore_permissions=True
		)


def set_client_roles(client: str, roles: list[str]) -> None:
	doc = frappe.get_doc("OAuth Client", client)
	if sorted(r.role for r in doc.allowed_roles) == sorted(roles):
		return
	doc.set("allowed_roles", [{"role": r} for r in roles])
	doc.save(ignore_permissions=True)
