"""ERPNext side of the ConstructionERP integration (decided 2026-11-18).

ConstructionERP keeps purchasing (PR -> PO -> approval); ERPNext books it, as a separate company.
`ensure()` is idempotent: bench --site <site> execute kgarden.construction.setup.ensure
"""

import frappe

COMPANY = "KGF Construction"
ABBR = "KGFC"
ITEM_GROUP = "Construction Costs"

# One non-stock purchase item per ConstructionERP cost category; the PO line keeps its own text.
COST_ITEMS = {
	"CON-MATERIAL": "วัสดุก่อสร้าง (Material)",
	"CON-LABOR": "ค่าแรง (Labour)",
	"CON-SUBCONTRACT": "ผู้รับเหมาช่วง (Subcontract)",
	"CON-EQUIPMENT": "เครื่องจักร/อุปกรณ์ (Equipment)",
	"CON-OTHER": "ค่าใช้จ่ายอื่น (Other)",
}

API_USER = "cerp.integration@example.com"
API_ROLES = ("Purchase User", "Purchase Manager", "Purchase Master Manager", "Projects Manager", "Item Manager")


def ensure():
	_company()
	_item_group()
	for code, name in COST_ITEMS.items():
		_cost_item(code, name)
	_api_user()
	frappe.db.commit()
	print("company:", COMPANY, "| items:", ", ".join(COST_ITEMS), "| user:", API_USER)


def _company():
	if frappe.db.exists("Company", COMPANY):
		return
	frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": COMPANY,
			"abbr": ABBR,
			"country": "Thailand",
			"default_currency": "THB",
			"create_chart_of_accounts_based_on": "Standard Template",
			"chart_of_accounts": "Standard",
		}
	).insert()


def _item_group():
	if not frappe.db.exists("Item Group", ITEM_GROUP):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": ITEM_GROUP, "parent_item_group": "All Item Groups"}
		).insert()


def _cost_item(code, name):
	if frappe.db.exists("Item", code):
		return
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": name,
			"item_group": ITEM_GROUP,
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_purchase_item": 1,
			"is_sales_item": 0,
			"include_item_in_manufacturing": 0,
			"description": "ConstructionERP cost category, used for PO lines booked from ConstructionERP",
		}
	).insert()


def _api_user():
	if not frappe.db.exists("User", API_USER):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": API_USER,
				"first_name": "ConstructionERP Integration",
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	user = frappe.get_doc("User", API_USER)
	have = {r.role for r in user.roles}
	for role in API_ROLES:
		if role not in have:
			user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
