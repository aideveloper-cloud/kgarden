"""/kgarden-apps: the K Garden apps the signed-in person may open (the K Garden tile on the desk)."""

import frappe

from kgarden.access.desktop import my_apps

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/kgarden-apps"
		raise frappe.Redirect
	context.apps = my_apps()
	context.full_name = frappe.utils.get_fullname(frappe.session.user)
	context.no_breadcrumbs = 1
	context.title = "K Garden"
