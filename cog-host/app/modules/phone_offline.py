"""Offline phone checks using the phonenumbers library, plus a wa.me link
the user clicks themselves. No network calls in this module.
"""
import phonenumbers
from phonenumbers import carrier as pn_carrier
from phonenumbers import geocoder as pn_geocoder

from app.models import Confidence, Finding, Kind

name = "phone_offline"
timeout_seconds = 2.0
quota_cost = 0

NUMBER_TYPE_NAMES = {
    phonenumbers.PhoneNumberType.FIXED_LINE: "fixed line",
    phonenumbers.PhoneNumberType.MOBILE: "mobile",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed line or mobile",
    phonenumbers.PhoneNumberType.TOLL_FREE: "toll free",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "premium rate",
    phonenumbers.PhoneNumberType.VOIP: "VoIP",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "personal number",
    phonenumbers.PhoneNumberType.PAGER: "pager",
    phonenumbers.PhoneNumberType.UAN: "UAN",
    phonenumbers.PhoneNumberType.UNKNOWN: "unknown",
}

LANDLINE_TYPES = {phonenumbers.PhoneNumberType.FIXED_LINE, phonenumbers.PhoneNumberType.TOLL_FREE}


async def run(query: str, ctx: dict) -> list[Finding]:
    parsed = phonenumbers.parse(query, None)
    number_type = phonenumbers.number_type(parsed)
    type_name = NUMBER_TYPE_NAMES.get(number_type, "unknown")
    region = pn_geocoder.description_for_number(parsed, "en") or "unknown region"
    carrier_name = pn_carrier.name_for_number(parsed, "en")

    findings = [
        Finding(
            module=name,
            kind=Kind.LINE_INFO,
            title=f"{query}: {type_name}, {region}" + (f", {carrier_name}" if carrier_name else ""),
            confidence=Confidence.HIGH,
            detail={
                "type": type_name,
                "region": region,
                "carrier": carrier_name or None,
                "country_code": parsed.country_code,
            },
        )
    ]

    digits_only = query.lstrip("+")
    if number_type in LANDLINE_TYPES:
        findings.append(
            Finding(
                module=name,
                kind=Kind.NOTE,
                title="Landline numbers cannot have WhatsApp",
                confidence=Confidence.HIGH,
            )
        )
    else:
        findings.append(
            Finding(
                module="whatsapp",
                kind=Kind.LINK,
                title=f"Open wa.me link for {query}",
                url=f"https://wa.me/{digits_only}",
                confidence=Confidence.LOW,
                detail={
                    "note": (
                        "Opens WhatsApp. If the number is not registered, WhatsApp says so. "
                        "Nothing here is automated."
                    )
                },
            )
        )

    return findings
