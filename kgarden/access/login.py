"""People sign in to ERPNext - and so to every K Garden app, which signs in through ERPNext - with
their employee code and password.

Frappe can log in by username (System Settings "Allow Login using User Name"), so a person's
employee code is kept as their Frappe username. Email still works, for accounts without an employee
code (Administrator, integration and service accounts). Shared tablets keep employee code + PIN.

Frappe compares the username as typed, so codes are stored in capitals and the login page turns
what is typed into capitals unless it is an email (``public/js/login.js``).
"""

import frappe
from frappe import _

LOGIN_LABEL = "รหัสพนักงาน"
LOGIN_PLACEHOLDER = "เช่น EMP101"


def sync_login_name(doc, before) -> None:
	"""Keep the user's username equal to their employee code (called from User before_validate)."""
	code = doc.get("kg_employee_code") or ""
	old = (before.get("kg_employee_code") or "") if before else ""
	if code:
		holder = frappe.db.get_value("User", {"username": code, "name": ("!=", doc.name)}, "name")
		if holder:
			frappe.throw(_("รหัสพนักงาน {0} ถูกใช้เป็นชื่อเข้าสู่ระบบของ {1} แล้ว").format(code, holder))
		doc.username = code
	elif old and doc.username == old:
		doc.username = None  # the code was taken away: it no longer signs this person in


def ensure() -> None:
	"""Turn on login by username and give every person with an employee code that code as username."""
	frappe.db.set_single_value("System Settings", "allow_login_using_user_name", 1)
	for user in frappe.get_all(
		"User",
		filters={"kg_employee_code": ("is", "set")},
		fields=["name", "username", "kg_employee_code"],
	):
		code = user.kg_employee_code
		if user.username == code:
			continue
		holder = frappe.db.get_value("User", {"username": code, "name": ("!=", user.name)}, "name")
		if holder:
			print(f"K Garden: employee code {code} of {user.name} is already the username of {holder}")
			continue
		frappe.db.set_value("User", user.name, "username", code, update_modified=False)
	frappe.db.commit()


def update_website_context(context):
	"""Call the login field what people type in it."""
	if (context.get("path") or "").strip("/") == "login":
		return {"login_label": LOGIN_LABEL, "login_name_placeholder": LOGIN_PLACEHOLDER}
