from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


@dataclass
class ResearchResult:
    company_summary: str
    industry: str
    likely_buyer_type: str
    relevant_use_cases: str
    evidence_snippets: str
    contact_route: str
    confidence_score_0_100: int
    risk_notes: str
    research_status: str
    research_source_urls: str


def research_lead(conn: sqlite3.Connection, lead_id: int, timeout: int = 12) -> ResearchResult:
    lead = conn.execute("SELECT * FROM leads WHERE lead_id = ?", (lead_id,)).fetchone()
    if lead is None:
        raise ValueError("Lead not found")

    texts: list[str] = []
    urls: list[str] = []
    risk_notes = ""

    if lead["website"]:
        try:
            homepage_html = _fetch(lead["website"], timeout)
            homepage_text = _extract_text(homepage_html)
            texts.append(homepage_text)
            urls.append(lead["website"])
            for link in _candidate_links(homepage_html, lead["website"])[:3]:
                try:
                    html = _fetch(link, timeout)
                    texts.append(_extract_text(html))
                    urls.append(link)
                except requests.RequestException:
                    continue
        except requests.RequestException as exc:
            risk_notes = f"Website fetch failed: {exc}"

    lead_context = " ".join(
        str(lead[field] or "")
        for field in ["company_name", "industry", "country", "notes", "source_url"]
    )
    combined = _clean_text(" ".join([lead_context] + texts))
    summary = combined[:900] if combined else "Not enough context available from lead data or website."
    status = "researched" if combined else "needs_manual_review"
    confidence = 65 if texts else (35 if lead_context.strip() else 10)

    result = ResearchResult(
        company_summary=summary,
        industry=lead["industry"] or _guess_industry(combined),
        likely_buyer_type=_guess_buyer_type(combined),
        relevant_use_cases=_guess_use_cases(combined),
        evidence_snippets=combined[:500],
        contact_route=lead["contact_page_url"] or (urls[-1] if urls else lead["website"]),
        confidence_score_0_100=confidence,
        risk_notes=risk_notes,
        research_status=status,
        research_source_urls="\n".join(dict.fromkeys(urls)),
    )
    save_research(conn, lead_id, result)
    conn.execute("UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE lead_id = ?", (status, lead_id))
    conn.commit()
    return result


def save_research(conn: sqlite3.Connection, lead_id: int, result: ResearchResult) -> int:
    cur = conn.execute(
        """
        INSERT INTO recipient_research (
            lead_id, company_summary, industry, likely_buyer_type, relevant_use_cases,
            evidence_snippets, contact_route, confidence_score_0_100, risk_notes,
            research_status, research_source_urls
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            result.company_summary,
            result.industry,
            result.likely_buyer_type,
            result.relevant_use_cases,
            result.evidence_snippets,
            result.contact_route,
            result.confidence_score_0_100,
            result.risk_notes,
            result.research_status,
            result.research_source_urls,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _fetch(url: str, timeout: int) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "NusaPitch/0.1 local research bot"},
    )
    response.raise_for_status()
    return response.text


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return _clean_text(soup.get_text(" "))


def _candidate_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    wanted = ("about", "contact", "product", "service", "solution")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        label = f"{anchor.get_text(' ')} {href}".lower()
        if any(word in label for word in wanted):
            links.append(urljoin(base_url, href))
    return list(dict.fromkeys(links))


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _guess_industry(text: str) -> str:
    lowered = text.lower()
    for keyword, industry in {
        "biomass": "Bioenergy",
        "compost": "Compost",
        "fertilizer": "Agriculture",
        "import": "Import trading",
        "manufacturing": "Manufacturing",
    }.items():
        if keyword in lowered:
            return industry
    return ""


def _guess_buyer_type(text: str) -> str:
    lowered = text.lower()
    if "procurement" in lowered or "sourcing" in lowered:
        return "Procurement team"
    if "manufacturer" in lowered or "factory" in lowered:
        return "Manufacturer"
    if "import" in lowered or "trading" in lowered:
        return "Importer or trader"
    return "B2B company"


def _guess_use_cases(text: str) -> str:
    lowered = text.lower()
    use_cases = []
    if "biomass" in lowered or "boiler" in lowered:
        use_cases.append("biomass fuel sourcing")
    if "compost" in lowered or "agriculture" in lowered:
        use_cases.append("agriculture or compost inputs")
    if "import" in lowered or "trading" in lowered:
        use_cases.append("import sourcing")
    return ", ".join(use_cases)
