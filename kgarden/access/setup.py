"""K Garden apps, their roles and their OAuth Clients (sign-in through ERPNext).

Idempotent; runs after migrate. Redirect URIs are the local development addresses; change them on
the OAuth Client when an app is deployed.
"""

import frappe

from kgarden.k_garden.doctype.kg_app.kg_app import SUPER_ADMIN_ROLE, ensure_role
from kgarden.access.api import SERVICE_ROLE

APPS = [
	{
		"app_code": "ERPNEXT",
		"app_name": "ERPNext (บัญชี / จัดซื้อ / วางแผน)",
		"is_desk": 1,
		"roles": [
			("accounting", "บัญชี", "Accounts User"),
			("accounting_manager", "ผู้จัดการบัญชี", "Accounts User, Accounts Manager"),
			("purchasing", "จัดซื้อ", "Purchase User"),
			("stock", "คลังสินค้า", "Stock User"),
			("manufacturing", "วางแผนผลิต", "Manufacturing User, Stock User"),
			("manager", "ผู้บริหาร", "Accounts Manager, Purchase Manager, Stock Manager, Manufacturing Manager"),
		],
	},
	{
		"app_code": "WMS",
		"app_name": "WMS คลังวัตถุดิบ (production-pos)",
		"scope_doctype": "Warehouse",
		"redirect": "http://127.0.0.1:8300/auth/kgarden/callback",
		"base_url": "http://127.0.0.1:8300",
		"roles": [("operator", "พนักงานคลัง", ""), ("supervisor", "หัวหน้าคลัง", ""), ("admin", "ผู้ดูแล WMS", "")],
	},
	{
		"app_code": "CERP",
		"app_name": "ConstructionERP (KGF Construction)",
		"scope_doctype": "Project",
		"redirect": "http://127.0.0.1:5173/auth/oidc/callback",  # ConstructionERP's own OIDC callback route
		"token_auth": "Client Secret Post",  # ConstructionERP sends the secret in the form body
		"base_url": "http://127.0.0.1:5173",
		"roles": [
			("viewer", "ดูอย่างเดียว", ""),
			("purchaser", "จัดซื้อ", ""),
			("approver", "ผู้อนุมัติ", ""),
			("project_manager", "ผู้จัดการโครงการ", ""),
			("accountant", "บัญชี", ""),
			("admin", "ผู้ดูแล ConstructionERP", ""),
		],
	},
	{
		"app_code": "MES_FLOOR",
		"app_name": "แท็บเล็ตหน้างานผลิต (MES)",
		"redirect": "http://127.0.0.1:5180/auth/callback",
		"base_url": "http://127.0.0.1:5180",
		"roles": [("operator", "ผู้ปฏิบัติงาน", ""), ("supervisor", "หัวหน้างาน", "")],
	},
]


def ensure():
	ensure_role(SUPER_ADMIN_ROLE, desk_access=1)
	ensure_role(SERVICE_ROLE, desk_access=0)
	for spec in APPS:
		client = _oauth_client(spec) if spec.get("redirect") else None
		name = spec["app_code"]
		doc = frappe.get_doc("KG App", name) if frappe.db.exists("KG App", name) else frappe.new_doc("KG App")
		doc.update(
			{
				"app_code": name,
				"app_name": spec["app_name"],
				"is_desk": spec.get("is_desk", 0),
				"scope_doctype": spec.get("scope_doctype"),
				"base_url": spec.get("base_url"),
				"oauth_client": client or doc.get("oauth_client"),
			}
		)
		if doc.is_new():
			doc.enabled = 1
		have = {r.role_code for r in doc.roles}
		for code, label, erp_roles in spec["roles"]:
			if code not in have:
				doc.append("roles", {"role_code": code, "role_label": label, "erpnext_roles": erp_roles})
		doc.save(ignore_permissions=True)
	frappe.db.commit()


def _oauth_client(spec) -> str:
	existing = frappe.db.get_value("OAuth Client", {"app_name": spec["app_name"]}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "OAuth Client",
			"app_name": spec["app_name"],
			"scopes": "openid all",
			"redirect_uris": spec["redirect"],
			"default_redirect_uri": spec["redirect"],
			"grant_type": "Authorization Code",
			"response_type": "Code",
			"skip_authorization": 1,  # company apps: no consent screen
			"token_endpoint_auth_method": spec.get("token_auth", "Client Secret Basic"),
		}
	).insert(ignore_permissions=True)
	return doc.name
