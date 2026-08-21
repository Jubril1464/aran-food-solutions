from app.models.notification import NotificationType

_TEMPLATES: dict[NotificationType, tuple[str, str]] = {
    NotificationType.ORDER_CONFIRMED: (
        "Your order {order_number} is confirmed",
        "Hi {full_name}, your order {order_number} has been confirmed and is now attached to procurement "
        "cycle {cycle_name}. We'll notify you as it progresses.",
    ),
    NotificationType.PAYMENT_CONFIRMED: (
        "Payment received for order {order_number}",
        "Hi {full_name}, we've received your payment of NGN {amount} for order {order_number}. Thank you!",
    ),
    NotificationType.PAYMENT_FAILED: (
        "Payment failed for order {order_number}",
        "Hi {full_name}, your payment attempt for order {order_number} was not successful. "
        "Please try again from your order history page.",
    ),
    NotificationType.CYCLE_CLOSING: (
        "Procurement cycle {cycle_name} has closed",
        "Hi {full_name}, the procurement cycle {cycle_name} has closed and your order {order_number} is "
        "now being aggregated for bulk procurement.",
    ),
    NotificationType.CANCELLATION: (
        "Order {order_number} cancelled",
        "Hi {full_name}, your order {order_number} has been cancelled.",
    ),
    NotificationType.REFUND: (
        "Refund issued for order {order_number}",
        "Hi {full_name}, a refund has been issued for order {order_number}.",
    ),
    NotificationType.ACCOUNT_VERIFICATION: (
        "Verify your account",
        "Hi {full_name}, please verify your account using this link: {verify_url}",
    ),
    NotificationType.PASSWORD_RESET: (
        "Reset your password",
        "Hi {full_name}, use this link to reset your password: {reset_url}",
    ),
}


def render(notification_type: NotificationType, payload: dict) -> tuple[str, str]:
    subject_tpl, body_tpl = _TEMPLATES[notification_type]
    return subject_tpl.format(**payload), body_tpl.format(**payload)
