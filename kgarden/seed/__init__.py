"""Load the K Garden golden dataset (golden_dataset.json) into a site.

    bench --site erp.localhost execute kgarden.seed.load

Safe to re-run: warehouses and items are upserted, and a BOM is only created
when its item has no active default BOM yet.
"""

import json
from pathlib import Path

import frappe

DATASET = Path(__file__).with_name("golden_dataset.json")


def load(path: str | None = None) -> dict:
	data = json.loads(Path(path or DATASET).read_text(encoding="utf-8"))
	company = data["company"]
	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		frappe.throw(f"Company {company!r} not found; run the setup wizard first")

	def wh(name: str) -> str:
		return f"{name} - {abbr}"

	summary = {"warehouses": 0, "items": 0, "boms": 0}

	for row in data["warehouses"]:
		if not frappe.db.exists("Warehouse", wh(row["warehouse_name"])):
			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": row["warehouse_name"],
					"parent_warehouse": wh(row["parent"]),
					"company": company,
				}
			).insert()
			summary["warehouses"] += 1

	for row in data["items"]:
		if frappe.db.exists("Item", row["item_code"]):
			item = frappe.get_doc("Item", row["item_code"])
		else:
			item = frappe.new_doc("Item")
			item.item_code = row["item_code"]
			item.stock_uom = row["stock_uom"]
			item.is_stock_item = 1
			summary["items"] += 1
		item.item_name = row["item_name"]
		item.item_group = row["item_group"]
		item.valuation_rate = row.get("valuation_rate", 0)
		item.set("item_defaults", [{"company": company, "default_warehouse": wh(row["default_warehouse"])}])
		item.save()

	# Default WIP / finished-goods warehouses for Work Orders live on Company in this ERPNext version.
	company_doc = frappe.get_doc("Company", company)
	for field, warehouse in data.get("company_warehouse_defaults", {}).items():
		if not company_doc.meta.has_field(field):
			frappe.throw(f"Company has no field {field!r}")
		company_doc.set(field, wh(warehouse))
	company_doc.save()

	# BOMs are listed children-first, so each sub-assembly BOM exists before its parent needs it.
	for row in data["boms"]:
		if frappe.db.exists("BOM", {"item": row["item"], "is_active": 1, "is_default": 1, "docstatus": 1}):
			continue
		bom = frappe.get_doc(
			{
				"doctype": "BOM",
				"item": row["item"],
				"company": company,
				"quantity": row["quantity"],
				"rm_cost_as_per": "Valuation Rate",
				"is_active": 1,
				"is_default": 1,
				"items": [{"item_code": i["item_code"], "qty": i["qty"]} for i in row["items"]],
			}
		)
		bom.insert()
		bom.submit()
		summary["boms"] += 1

	frappe.db.commit()
	return summary
