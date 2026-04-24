"""
Visa Sponsorship Checker — UK gov.uk Tier-2 register + EU curated data
Checks whether companies sponsor work visas
"""
import requests
import json
import re
import io


# UK gov.uk publishes a CSV of licensed Skilled Worker (Tier 2) sponsors
UK_SPONSOR_REGISTER_URL = (
    "https://assets.publishing.service.gov.uk/media/"
    "67f6eb9cb9d6e36a41f4bb7a/2025-04-10_Tier_2_5_Register.csv"
)

# Curated EU tech visa sponsorship data (based on public company statements)
EU_SPONSOR_DATA = {
    # Germany — "Blue Card" / company-sponsored work visa
    "de": {
        "known_sponsors": [
            "Google", "Amazon", "Meta", "Microsoft", "SAP", "Zalando", "Delivery Hero",
            "N26", "Celonis", "FlixBus", "Helsing", "Aleph Alpha", "DeepL",
            "Bosch", "Siemens", "BMW", "Volkswagen", "Deutsche Bank",
        ],
        "visa_type": "EU Blue Card / German Skilled Worker Visa",
        "language": "German (B1 often required for non-tech roles; English accepted at most tech companies)",
        "info_url": "https://www.make-it-in-germany.com/en/visa-residence/types/skilled-workers",
    },
    # Netherlands — Highly Skilled Migrant permit
    "nl": {
        "known_sponsors": [
            "ASML", "Booking.com", "Adyen", "Philips", "Shell", "ING", "Coolblue",
            "TomTom", "Elastic", "Mollie", "Takeaway.com", "Exact",
            "Google", "Microsoft", "Amazon",
        ],
        "visa_type": "Highly Skilled Migrant Permit (Kennismigrant)",
        "language": "Dutch (not required at most tech companies; English sufficient)",
        "info_url": "https://ind.nl/en/residence-permits/work/highly-skilled-migrant",
    },
    # Switzerland
    "ch": {
        "known_sponsors": [
            "Google", "Microsoft", "Apple", "ABB", "Roche", "Novartis", "UBS",
            "Credit Suisse", "Nestlé", "Logitech", "Zurich Insurance",
        ],
        "visa_type": "Swiss L/B Work Permit (employer-sponsored)",
        "language": "German/French/Italian (English widely used in Zurich/Geneva tech)",
        "info_url": "https://www.sem.admin.ch/sem/en/home/themen/arbeit.html",
    },
    # Sweden
    "se": {
        "known_sponsors": [
            "Spotify", "Klarna", "King", "Mojang", "Ericsson", "Volvo",
            "IKEA", "H&M", "Electrolux", "ABB", "Axis",
        ],
        "visa_type": "Swedish Work Permit",
        "language": "Swedish (not required at most tech startups; English sufficient)",
        "info_url": "https://www.migrationsverket.se/English/Private-individuals/Working-in-Sweden.html",
    },
    # France
    "fr": {
        "known_sponsors": [
            "Mistral AI", "Contentsquare", "Dataiku", "BlaBlaCar", "Criteo",
            "Deezer", "Doctolib", "Ledger", "Meero", "Oodrive",
            "Google", "Amazon", "Microsoft", "Meta",
        ],
        "visa_type": "French Tech Visa / Passeport Talent",
        "language": "French (required for most non-tech roles; English sufficient at international companies)",
        "info_url": "https://visa.lafrenchtech.com/",
    },
    # Ireland
    "ie": {
        "known_sponsors": [
            "Google", "Meta", "Apple", "LinkedIn", "Twitter/X", "Stripe", "HubSpot",
            "Salesforce", "Amazon", "Microsoft", "Accenture", "KPMG",
        ],
        "visa_type": "Critical Skills Employment Permit",
        "language": "English",
        "info_url": "https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/",
    },
}

_uk_sponsor_cache: set | None = None


def _load_uk_sponsors() -> set:
    """Download and cache the UK Skilled Worker sponsor register."""
    global _uk_sponsor_cache
    if _uk_sponsor_cache is not None:
        return _uk_sponsor_cache

    try:
        resp = requests.get(UK_SPONSOR_REGISTER_URL, timeout=15,
                            headers={"User-Agent": "JobCopilot/1.0"})
        if resp.status_code == 200:
            lines = resp.text.split("\n")
            sponsors = set()
            for line in lines[1:]:  # skip header
                if line.strip():
                    # Format: "Company Name","Town/City","County","Type & Rating","Route"
                    parts = line.split(",")
                    if parts:
                        name = parts[0].strip().strip('"').lower()
                        sponsors.add(name)
            _uk_sponsor_cache = sponsors
            return sponsors
    except Exception:
        pass
    _uk_sponsor_cache = set()
    return _uk_sponsor_cache


def check_visa_sponsorship(company: str, country: str) -> str:
    """
    Check if a company sponsors work visas in a European country.
    Uses UK gov.uk Tier-2 register for UK; curated data for EU countries.

    Args:
        company: Company name (e.g. 'DeepMind', 'Zalando')
        country: Country name or code (e.g. 'uk', 'germany', 'netherlands')

    Returns:
        JSON with sponsorship status, visa type, and language requirements
    """
    try:
        country_lower = country.lower()

        # Normalise to country code
        code = "gb"
        if any(k in country_lower for k in ["uk", "england", "britain", "london"]):
            code = "gb"
        elif any(k in country_lower for k in ["germany", "berlin", "munich", "de"]):
            code = "de"
        elif any(k in country_lower for k in ["netherlands", "amsterdam", "dutch", "nl"]):
            code = "nl"
        elif any(k in country_lower for k in ["switzerland", "zurich", "ch"]):
            code = "ch"
        elif any(k in country_lower for k in ["sweden", "stockholm", "se"]):
            code = "se"
        elif any(k in country_lower for k in ["france", "paris", "fr"]):
            code = "fr"
        elif any(k in country_lower for k in ["ireland", "dublin", "ie"]):
            code = "ie"

        company_lower = company.lower()

        if code == "gb":
            sponsors = _load_uk_sponsors()
            # Fuzzy match: check if company name is contained in any sponsor
            found = any(company_lower in s or s in company_lower for s in sponsors)
            return json.dumps({
                "company": company,
                "country": "United Kingdom",
                "visa_type": "UK Skilled Worker Visa",
                "sponsors_visa": found,
                "confidence": "high" if found else "medium",
                "language_requirements": "English (IELTS/equivalent if non-native)",
                "source": "UK Home Office Licensed Sponsor Register (live)",
                "source_url": "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
                "note": "Register updated frequently. Always verify on gov.uk before applying.",
            })

        elif code in EU_SPONSOR_DATA:
            eu = EU_SPONSOR_DATA[code]
            known = eu["known_sponsors"]
            found = any(company_lower in k.lower() or k.lower() in company_lower for k in known)
            return json.dumps({
                "company": company,
                "country": country,
                "visa_type": eu["visa_type"],
                "sponsors_visa": found,
                "confidence": "medium",
                "language_requirements": eu["language"],
                "info_url": eu["info_url"],
                "note": "Based on curated data. Verify directly with the company's careers page.",
                "other_known_sponsors_in_country": known[:10],
            })

        return json.dumps({
            "company": company,
            "country": country,
            "note": "No visa data available for this country in our database. Check the company's careers page directly.",
        })

    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})
