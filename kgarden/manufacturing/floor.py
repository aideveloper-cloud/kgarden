"""Work Orders for the production POS in the WMS (production-pos ``/pos/production``).

The shop floor lives in the WMS tablet POS. It reads the open Work Orders from here with the WMS
service account (role KG Access Service) and reports finished quantity as WMS stock receipts;
the stock bridge turns each receipt into a Manufacture Stock Entry against the Work Order.
"""

import frappe
from frappe.utils import flt

from kgarden.access.api import _require_service

OPEN_STATUSES = ("Not Started", "In Process")


@frappe.whitelist(methods=["GET"])
def work_orders(name: str | None = None) -> list[dict]:
	"""Submitted Work Orders that still have quantity to make, oldest planned first.

	With ``name``, only that Work Order (in any status), so the POS can check one before it
	records output against it.
	"""
	_require_service()
	filters = {"docstatus": 1}
	if name:
		filters["name"] = name
	else:
		filters["status"] = ("in", OPEN_STATUSES)

	rows = frappe.get_all(
		"Work Order",
		filters=filters,
		fields=[
			"name",
			"status",
			"production_item",
			"item_name",
			"bom_no",
			"qty",
			"produced_qty",
			"stock_uom",
			"planned_start_date",
			"expected_delivery_date",
			"company",
		],
		order_by="planned_start_date asc, name asc",
		limit_page_length=0 if name else 200,
		ignore_permissions=True,  # the service account is checked above
	)
	out = []
	for row in rows:
		remaining = flt(row.qty) - flt(row.produced_qty)
		if not name and remaining <= 0:
			continue
		row["remaining_qty"] = remaining
		row["open"] = row.status in OPEN_STATUSES
		out.append(row)
	return out
