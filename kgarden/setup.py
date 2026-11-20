"""Schema customisations K Garden needs on standard ERPNext doctypes.

Applied on install and after every `bench migrate`, so they are safe to re-run.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def _cerp_id_field(insert_after: str) -> dict:
	# The ConstructionERP row this record was created from; unique so a retry finds it again.
	return {
		"fieldname": "kg_cerp_id",
		"label": "ConstructionERP ID",
		"fieldtype": "Data",
		"insert_after": insert_after,
		"unique": 1,
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"search_index": 1,
	}


def _key_field(insert_after: str) -> dict:
	# Set by the K Garden bridges; unique so a retried post finds its document instead of a second one.
	return {
		"fieldname": "kg_idempotency_key",
		"label": "K Garden Idempotency Key",
		"fieldtype": "Data",
		"insert_after": insert_after,
		"unique": 1,
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"search_index": 1,
	}


CUSTOM_FIELDS = {
	"Stock Entry": [
		{
			# Set by the K Garden platform (MES/WMS outbox). The unique index makes a retried
			# post fail instead of creating a second stock movement.
			"fieldname": "kg_idempotency_key",
			"label": "K Garden Idempotency Key",
			"fieldtype": "Data",
			"insert_after": "stock_entry_type",
			"unique": 1,
			"read_only": 1,
			"no_copy": 1,
			"print_hide": 1,
			"search_index": 1,
		}
	],
	# ConstructionERP bridge: purchase orders approved in ConstructionERP are booked here.
	"Purchase Order": [
		{
			"fieldname": "kg_idempotency_key",
			"label": "K Garden Idempotency Key",
			"fieldtype": "Data",
			"insert_after": "supplier",
			"unique": 1,
			"read_only": 1,
			"no_copy": 1,
			"print_hide": 1,
			"search_index": 1,
		},
		{
			"fieldname": "kg_cerp_po_number",
			"label": "ConstructionERP PO No.",
			"fieldtype": "Data",
			"insert_after": "kg_idempotency_key",
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
			"search_index": 1,
		},
	],
	"Purchase Receipt": [_key_field("supplier")],
	"Purchase Invoice": [
		_key_field("supplier"),
		{
			"fieldname": "kg_cerp_invoice_number",
			"label": "ConstructionERP Invoice No.",
			"fieldtype": "Data",
			"insert_after": "kg_idempotency_key",
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
			"search_index": 1,
		},
	],
	# Thai withholding tax deducted on the payment (หัก ณ ที่จ่าย), for ภ.ง.ด.3 / 53.
	"Payment Entry": [
		_key_field("party"),
		{
			"fieldname": "kg_wht_type",
			"label": "WHT Income Type",
			"fieldtype": "Data",
			"insert_after": "kg_idempotency_key",
			"read_only": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": "kg_wht_rate",
			"label": "WHT Rate (%)",
			"fieldtype": "Float",
			"insert_after": "kg_wht_type",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "kg_wht_certificate_no",
			"label": "WHT Certificate No.",
			"fieldtype": "Data",
			"insert_after": "kg_wht_rate",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
		},
	],
	# App access: the one place a person gets, changes and loses access to the K Garden apps.
	"User": [
		{
			"fieldname": "kg_access_section",
			"label": "K Garden: สิทธิ์เข้าใช้แอป",
			"fieldtype": "Section Break",
			"insert_after": "roles_permissions_tab",
		},
		{
			"fieldname": "kg_employee_code",
			"label": "รหัสพนักงาน",
			"fieldtype": "Data",
			"insert_after": "kg_access_section",
			"unique": 1,
			"search_index": 1,
			"description": "ใช้ยืนยันตัวที่แท็บเล็ตหน้างานคู่กับ PIN",
		},
		{
			"fieldname": "kg_superadmin",
			"label": "ผู้ดูแลระบบสูงสุด (เข้าได้ทุกแอปในฐานะแอดมิน)",
			"fieldtype": "Check",
			"insert_after": "kg_employee_code",
		},
		{
			"fieldname": "kg_access_managed",
			"label": "K Garden Access Managed",
			"fieldtype": "Check",
			"insert_after": "kg_superadmin",
			"hidden": 1,
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "kg_app_access",
			"label": "แอปที่เข้าใช้ได้",
			"fieldtype": "Table",
			"options": "KG User App Access",
			"insert_after": "kg_access_managed",
			"description": "ไม่ได้อยู่ในตาราง = เข้าแอปนั้นไม่ได้ (ยกเว้นผู้ดูแลระบบสูงสุด)",
		},
	],
	"Supplier": [_cerp_id_field("supplier_name")],
	"Project": [_cerp_id_field("project_name")],
}


def ensure_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, update=True)


def after_migrate():
	ensure_custom_fields()
	from kgarden.access.setup import ensure as ensure_access

	ensure_access()
	from kgarden.access.login import ensure as ensure_login

	ensure_login()
