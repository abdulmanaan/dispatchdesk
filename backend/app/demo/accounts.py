"""Fixed identities used by the public demo.

Demo accounts get random passwords: visitors sign in through the one-click
demo login (``POST /auth/demo-login``), which only works in demo mode.
"""

from app.models.enums import UserRole

DEMO_DOMAIN = "demo.dispatchdesk.test"
# Background drivers driven by the simulator. The demo driver is never simulated.
SIMULATED_DOMAIN = "sim.dispatchdesk.test"

DEMO_EMAILS: dict[UserRole, str] = {
    UserRole.ADMIN: f"admin@{DEMO_DOMAIN}",
    UserRole.BUSINESS: f"biryani@{DEMO_DOMAIN}",
    UserRole.DRIVER: f"kamran@{DEMO_DOMAIN}",
}

DEMO_DESCRIPTIONS: dict[UserRole, str] = {
    UserRole.ADMIN: "See every order and driver, dispatch and review activity.",
    UserRole.BUSINESS: "Create delivery orders for a restaurant in Gulberg and track them.",
    UserRole.DRIVER: "Go online, accept orders and deliver them around Lahore.",
}


def is_simulated_email(email: str) -> bool:
    return email.endswith(f"@{SIMULATED_DOMAIN}")
