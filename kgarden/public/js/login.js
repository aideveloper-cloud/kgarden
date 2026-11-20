// K Garden: people sign in with their employee code, stored in capitals (kgarden/access/login.py).
// Frappe compares it as typed, so turn a typed code into capitals; leave an email as it is.
document.addEventListener(
	"submit",
	() => {
		const field = document.getElementById("login_email");
		if (field && field.value && !field.value.includes("@")) {
			field.value = field.value.trim().toUpperCase();
		}
	},
	true
);
