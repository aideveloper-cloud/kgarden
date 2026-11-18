"""Schema customisations K Garden needs on standard ERPNext doctypes.

Applied on install and after every `bench migrate`, so they are safe to re-run.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

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
	]
}


def ensure_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, update=True)
