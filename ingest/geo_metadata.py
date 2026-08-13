"""Geographic metadata helpers for deterministic case-study queries."""

from __future__ import annotations

import re


COUNTRY_ALIASES = {
    "USA": "United States",
    "United States of America": "United States",
    "UK": "United Kingdom",
}


COUNTRY_TO_CONTINENT = {
    "Australia": "Oceania",
    "Austria": "Europe",
    "Brazil": "South America",
    "Canada": "North America",
    "China": "Asia",
    "Colombia": "South America",
    "Ethiopia": "Africa",
    "Fiji": "Oceania",
    "Germany": "Europe",
    "India": "Asia",
    "Malawi": "Africa",
    "Mozambique": "Africa",
    "Nepal": "Asia",
    "New Zealand": "Oceania",
    "Peru": "South America",
    "Philippines": "Asia",
    "Rwanda": "Africa",
    "Solomon Islands": "Oceania",
    "Sri Lanka": "Asia",
    "Taiwan": "Asia",
    "United Kingdom": "Europe",
    "United States": "North America",
    "Vanuatu": "Oceania",
    "Zambia": "Africa",
}


US_STATE_ABBREVIATIONS = {
    "AK": "Alaska",
    "AL": "Alabama",
    "AR": "Arkansas",
    "AZ": "Arizona",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DC": "District of Columbia",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "IA": "Iowa",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MO": "Missouri",
    "MS": "Mississippi",
    "MT": "Montana",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NV": "Nevada",
    "NY": "New York",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VA": "Virginia",
    "VT": "Vermont",
    "WA": "Washington",
    "WI": "Wisconsin",
    "WV": "West Virginia",
    "WY": "Wyoming",
}


def normalize_country(country: str) -> str:
    country = (country or "Unknown").strip()
    return COUNTRY_ALIASES.get(country, country)


def country_to_continent(country: str) -> str:
    return COUNTRY_TO_CONTINENT.get(normalize_country(country), "Unknown")


def infer_admin_area(location: str, country: str) -> str:
    """Best-effort state/province/region extraction from local case metadata."""
    location = location or ""
    country = normalize_country(country)

    if country == "United States":
        for state in US_STATE_ABBREVIATIONS.values():
            if re.search(rf"\b{re.escape(state)}\b", location):
                return state
        for abbr, state in US_STATE_ABBREVIATIONS.items():
            if re.search(rf"\b{abbr}\b", location):
                return state

    parts = [part.strip() for part in location.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[-1]
    return ""


def geographic_metadata(location: str, country: str) -> dict[str, str]:
    normalized_country = normalize_country(country)
    return {
        "country_normalized": normalized_country,
        "continent": country_to_continent(normalized_country),
        "admin_area": infer_admin_area(location, normalized_country),
    }
