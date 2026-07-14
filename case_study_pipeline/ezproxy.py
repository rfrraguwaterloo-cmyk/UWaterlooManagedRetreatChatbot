"""
ezproxy.py — UWaterloo EZproxy URL helper.

UWaterloo's EZproxy uses "domain dash-translation": any publisher hostname
can be proxied by replacing dots with dashes and appending
".proxy.lib.uwaterloo.ca". E.g.:

    link.springer.com                  -> link-springer-com.proxy.lib.uwaterloo.ca
    agupubs.onlinelibrary.wiley.com    -> agupubs-onlinelibrary-wiley-com.proxy.lib.uwaterloo.ca

This only grants access if you already have an authenticated EZproxy
session in the browser (see case_study_pipeline/README.md for the one-time
login + the Chrome-assisted download procedure).
"""

from __future__ import annotations
from urllib.parse import urlparse, urlunparse

EZPROXY_SUFFIX = ".proxy.lib.uwaterloo.ca"


def to_ezproxy_url(article_url: str) -> str:
    """Convert a publisher article URL into its UWaterloo EZproxy equivalent."""
    parsed = urlparse(article_url)
    dashed_host = parsed.netloc.replace(".", "-")
    proxied_netloc = dashed_host + EZPROXY_SUFFIX
    return urlunparse(parsed._replace(netloc=proxied_netloc))


def doi_redirect_url(doi: str) -> str:
    """The DOI resolver URL — navigating here redirects to the publisher's page."""
    return "https://doi.org/{}".format(doi)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python3 -m case_study_pipeline.ezproxy <publisher_article_url>")
        sys.exit(1)
    print(to_ezproxy_url(sys.argv[1]))
