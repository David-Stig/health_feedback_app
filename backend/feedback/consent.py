from django.utils.translation import gettext_lazy as _


CONSENT_VERSION = "1.0"
CONSENT_HEADING = _("Participant Information & Consent")
CONSENT_TEXT = _(
    "We are conducting a short survey to understand your experience at this health facility "
    "and help improve health services. Participation is voluntary, and you may skip any question "
    "or stop at any time. No personal information is collected, and your responses will be kept "
    "confidential. Your participation will not affect the health services you receive, and there "
    "is no payment or cost for taking part."
)
CONSENT_CHECKBOX_LABEL = _(
    "I have read and understood the information above and agree to participate."
)
CONSENT_VALIDATION_MESSAGE = _(
    "Please confirm that you agree to participate before submitting your feedback."
)


def get_consent_content():
    return {
        "version": CONSENT_VERSION,
        "heading": CONSENT_HEADING,
        "text": CONSENT_TEXT,
        "checkbox_label": CONSENT_CHECKBOX_LABEL,
        "validation_message": CONSENT_VALIDATION_MESSAGE,
    }
