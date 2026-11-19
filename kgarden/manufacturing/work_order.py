"""K Garden Work Order policy: raw materials are consumed (backflushed) from the WIP warehouse.

The WMS (production-pos) moves raw materials from the warehouses into the company's WIP warehouse
when the floor cuts or consumes them; the MES then reports finished quantity and ERPNext consumes
the BOM materials from WIP. Without this rule a Work Order could backflush from a store warehouse
that the WMS also issues from, and the same material would leave ERPNext twice.
"""

import frappe
from frappe import _


def enforce_wip_backflush(doc, method=None):
	# Applies while the Work Order is a draft or being submitted (also a REST insert with
	# docstatus=1, which saves and submits in one call); never to one that was already submitted.
	before = doc.get_doc_before_save()
	if doc.docstatus == 2 or (before and before.docstatus == 1):
		return
	wip = frappe.get_cached_value("Company", doc.company, "default_wip_warehouse")
	if not wip:
		frappe.throw(
			_("Set the Default Work In Progress Warehouse on Company {0}: K Garden Work Orders consume raw materials from it.").format(
				doc.company
			)
		)
	doc.skip_transfer = 1
	doc.source_warehouse = wip
	doc.wip_warehouse = wip
	for row in doc.get("required_items") or []:
		row.source_warehouse = wip
