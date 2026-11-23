"""Desktop icons for the K Garden apps (the grid people see first on the ERPNext desk).

One icon per app that has an address (KG App.base_url), opening it in a new tab. An icon is shown
only to people who may use the app (its access role, given from the User form) and to super
admins, so each person's desktop lists exactly the apps they can sign in to. Idempotent: runs after
migrate, when a KG App changes, and from deploy.provision.
"""

import frappe

from kgarden.k_garden.doctype.kg_app.kg_app import SUPER_ADMIN_ROLE

# app_code -> (desktop label, logo)
ICONS = {
	"MES_FLOOR": ("แท็บเล็ตหน้างานผลิต (MES)", "/assets/kgarden/images/apps/mes.svg"),
	"CERP": ("ConstructionERP", "/assets/kgarden/images/apps/cerp.svg"),
	"WMS": ("WMS คลังวัตถุดิบ", "/assets/kgarden/images/apps/wms.svg"),
}


def sync_desktop_icons() -> None:
	from frappe.desk.doctype.desktop_icon.desktop_icon import clear_every_users_desktop_icons

	changed = False
	for app in frappe.get_all("KG App", fields=["name", "enabled", "is_desk", "base_url", "access_role"]):
		if app.is_desk or app.name not in ICONS:
			continue
		label, logo = ICONS[app.name]
		want_hidden = 0 if (app.enabled and app.base_url) else 1
		roles = sorted({app.access_role, SUPER_ADMIN_ROLE} - {None})
		if frappe.db.exists("Desktop Icon", label):
			icon = frappe.get_doc("Desktop Icon", label)
		else:
			icon = frappe.new_doc("Desktop Icon")
			icon.label = label
		before = (icon.link, icon.hidden, icon.logo_url, sorted(r.role for r in icon.roles))
		icon.update({
			"icon_type": "App", "link_type": "External", "app": "kgarden", "standard": 1,
			"link": (app.base_url or "").rstrip("/"), "logo_url": logo, "hidden": want_hidden,
			"restrict_removal": 1,
		})
		icon.set("roles", [{"role": r} for r in roles])
		if icon.is_new() or before != (icon.link, icon.hidden, icon.logo_url, roles):
			icon.save(ignore_permissions=True)
			changed = True
	if changed:
		clear_every_users_desktop_icons()
