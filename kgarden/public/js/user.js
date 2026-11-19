// K Garden central access: the tablet PIN of a person is set here, by a K Garden super admin.
// The PIN is sent once to kgarden.access.api.set_pin and stored only as a hash; the form shows
// whether a PIN is set and when, never the PIN itself.

frappe.ui.form.on("User", {
	refresh(frm) {
		if (frm.is_new() || !kgardenIsSuperAdmin()) return;
		frm.add_custom_button("ตั้ง PIN แท็บเล็ต", () => kgardenSetPin(frm));
		kgardenShowPinStatus(frm);
	},
	kg_employee_code(frm) {
		kgardenShowPinStatus(frm);
	},
});

function kgardenIsSuperAdmin() {
	return frappe.session.user === "Administrator" || frappe.user.has_role("KG Super Admin");
}

function kgardenShowPinStatus(frm) {
	if (frm.is_new() || !kgardenIsSuperAdmin()) return;
	const base = "ใช้ยืนยันตัวที่แท็บเล็ตหน้างานคู่กับ PIN";
	frappe
		.xcall("kgarden.access.api.pin_status", { user: frm.doc.name }, "GET")
		.then((s) => {
			const status = s.pin_set
				? `PIN ตั้งแล้วเมื่อ ${frappe.datetime.str_to_user(s.set_on)} โดย ${frappe.utils.escape_html(s.set_by || "")}`
				: "ยังไม่ได้ตั้ง PIN";
			frm.set_df_property("kg_employee_code", "description", `${base} · ${status}`);
		})
		.catch(() => {});
}

function kgardenSetPin(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint("บันทึกฟอร์มก่อน แล้วค่อยตั้ง PIN");
		return;
	}
	if (!frm.doc.kg_employee_code) {
		frappe.msgprint("ใส่รหัสพนักงานแล้วบันทึกก่อน แท็บเล็ตใช้รหัสพนักงานคู่กับ PIN");
		return;
	}
	const d = new frappe.ui.Dialog({
		title: `ตั้ง PIN แท็บเล็ต: ${frm.doc.full_name || frm.doc.name} (${frm.doc.kg_employee_code})`,
		fields: [
			{ fieldname: "pin", fieldtype: "Password", label: "PIN ใหม่ (ตัวเลข 4–6 หลัก)", reqd: 1 },
			{ fieldname: "pin_again", fieldtype: "Password", label: "ใส่ PIN อีกครั้ง", reqd: 1 },
			{
				fieldname: "note",
				fieldtype: "HTML",
				options:
					'<p class="text-muted small">ระบบเก็บเฉพาะค่าแฮช ไม่มีใครดู PIN ย้อนหลังได้ ' +
					"ถ้าพนักงานลืม ให้ตั้งใหม่ที่นี่ PIN เดิมจะใช้ไม่ได้ทันที</p>",
			},
		],
		primary_action_label: "ตั้ง PIN",
		primary_action(values) {
			const pin = (values.pin || "").trim();
			if (!/^[0-9]{4,6}$/.test(pin)) {
				frappe.msgprint("PIN ต้องเป็นตัวเลข 4 ถึง 6 หลัก");
				return;
			}
			if (pin !== (values.pin_again || "").trim()) {
				frappe.msgprint("PIN สองช่องไม่ตรงกัน");
				return;
			}
			frappe
				.xcall("kgarden.access.api.set_pin", { user: frm.doc.name, pin })
				.then(() => {
					d.hide();
					frappe.show_alert({ message: "ตั้ง PIN แล้ว", indicator: "green" });
					kgardenShowPinStatus(frm);
				});
		},
	});
	d.show();
}
