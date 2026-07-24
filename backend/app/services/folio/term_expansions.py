"""Domain-aware legal term expansions and branch signal words.

Consumer narratives use natural language that benefits from domain-specific
expansion before FOLIO search: when a consumer says "fired", we also search
"wrongful termination".

**This is a consumer-narrative seam, deliberately NOT the shared library's.**
An earlier docstring here claimed the module was "ported from folio-mapper's
folio_service.py"; the *idea* was, but none of the data is, and the two solve
opposite problems:

* ``folio_resolve.LEGAL_TERM_EXPANSIONS`` maps a legal content word to FOLIO
  *label suffixes* ("litigation" -> "practice", "service") to widen ontology
  label search. It is applied inside the library scorer / term generator.
* This module maps *lay language* to legal phrases ("fired" -> "wrongful
  termination", "eviction" -> "unlawful detainer"), which is what an intake
  narrative needs and no ontology-side expansion can supply.

Likewise ``SEARCH_STOPWORDS`` here drops first/second-person pronouns and
auxiliaries so a narrative becomes a usable query; the library's scoring
stopwords drop legal filler ("law", "legal", "type"). Both vocabularies are
live, in different jobs -- see ``concept_resolver`` for the split.
"""

from __future__ import annotations

# Map natural language terms to legal/FOLIO-aligned expansions.
# When a consumer says "fired", we also search "wrongful termination" etc.
LEGAL_TERM_EXPANSIONS: dict[str, list[str]] = {
    # Employment
    "fired": ["wrongful termination", "employment termination", "discharge"],
    "terminated": ["wrongful termination", "employment termination"],
    "laid off": ["layoff", "reduction in force", "unemployment"],
    # Family
    "custody": ["child custody", "parental rights", "custodial arrangement"],
    "divorce": ["dissolution of marriage", "marital dissolution"],
    "alimony": ["spousal support", "spousal maintenance"],
    # Housing
    "eviction": ["unlawful detainer", "forcible entry", "landlord tenant"],
    "landlord": ["landlord tenant", "lease agreement", "rental dispute"],
    "rent": ["rental agreement", "lease dispute", "housing"],
    # Criminal
    "arrested": ["criminal arrest", "detention", "law enforcement encounter"],
    "charged": ["criminal charge", "indictment", "arraignment"],
    "stolen": ["theft", "larceny", "property crime", "stolen property"],
    "ticket": ["traffic violation", "citation", "infraction"],
    # Personal injury / tort
    "accident": ["personal injury", "negligence", "tort"],
    "injury": ["personal injury", "bodily harm", "physical injury", "damages"],
    "slip": ["slip and fall", "premises liability"],
    # Debt / financial
    "debt": ["debt collection", "creditor", "consumer debt", "fair debt"],
    "bankruptcy": ["chapter 7", "chapter 13", "insolvency", "debt relief"],
    "foreclosure": ["mortgage foreclosure", "property seizure", "deed in lieu"],
    # Civil rights
    "discrimination": ["employment discrimination", "civil rights violation", "protected class"],
    "harassment": ["workplace harassment", "hostile work environment", "sexual harassment"],
    "abuse": ["domestic violence", "child abuse", "elder abuse", "physical abuse"],
    # Immigration
    "immigration": ["immigration status", "visa", "deportation", "asylum"],
    "deported": ["deportation", "removal proceedings", "immigration enforcement"],
    # Estate / wills
    "will": ["estate planning", "testamentary", "probate", "last will and testament"],
    "inheritance": ["estate", "probate", "succession", "heir"],
    # Contract
    "contract": ["breach of contract", "contractual obligation", "agreement"],
    "agreement": ["contract", "settlement agreement", "binding agreement"],
    # Insurance
    "insurance": ["insurance claim", "coverage denial", "bad faith insurance"],
    "claim": ["insurance claim", "legal claim", "cause of action"],
    # Benefits
    "benefits": ["government benefits", "social security", "disability benefits", "unemployment"],
    "disability": ["disability benefits", "ADA", "disability discrimination"],
    # Consumer
    "scam": ["fraud", "consumer fraud", "deceptive practices"],
    "warranty": ["warranty claim", "product liability", "consumer protection"],
}

# Map FOLIO branch names to signal words that indicate relevance.
# Used to prioritize which branches to search for a given consumer narrative.
BRANCH_SIGNAL_WORDS: dict[str, list[str]] = {
    "Objectives": ["claim", "defense", "cause of action", "remedy", "right", "relief"],
    "Area of Law": ["law", "legal area", "practice area", "jurisdiction", "statute"],
    "Legal Authorities": ["statute", "regulation", "case law", "constitutional", "ordinance", "code"],
    "Location": ["state", "county", "city", "federal", "jurisdiction", "country", "district"],
    "Actor-Player": ["plaintiff", "defendant", "attorney", "judge", "witness", "party"],
    "Asset Type": ["property", "real estate", "asset", "money", "vehicle", "account"],
    "Event": ["incident", "occurrence", "accident", "crime", "hearing", "trial"],
    "Legal Entity": ["corporation", "LLC", "partnership", "organization", "company"],
    "Document-Artifact": ["contract", "lease", "deed", "complaint", "motion", "filing"],
    "Governmental Body": ["court", "agency", "department", "commission", "board"],
    "Service": ["legal service", "representation", "mediation", "arbitration", "counsel"],
    "Forums and Venues": ["court", "tribunal", "administrative hearing", "venue", "forum"],
    "Industry and Market": ["employment", "healthcare", "finance", "real estate", "insurance"],
}

# Common words to filter from search queries
SEARCH_STOPWORDS: set[str] = {
    "the", "a", "an", "is", "was", "were", "been", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "shall", "can", "need", "dare", "ought", "used", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "about",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
    "them", "this", "that", "these", "those", "am", "are", "not", "no",
}


def expand_legal_terms(text: str) -> list[str]:
    """Expand natural language text into legal search queries.

    Tokenizes text, checks each token (and bigrams) against LEGAL_TERM_EXPANSIONS,
    and returns a list of expanded query strings. Filters SEARCH_STOPWORDS from
    the original text.

    Args:
        text: Consumer narrative text to expand.

    Returns:
        List of expanded query strings suitable for FOLIO concept search.
    """
    words = text.lower().split()
    expansions: list[str] = []
    seen: set[str] = set()

    # Check single tokens
    for word in words:
        clean = word.strip(".,!?;:'\"()[]{}").lower()
        if clean in SEARCH_STOPWORDS:
            continue
        if clean in LEGAL_TERM_EXPANSIONS:
            for expansion in LEGAL_TERM_EXPANSIONS[clean]:
                if expansion not in seen:
                    expansions.append(expansion)
                    seen.add(expansion)

    # Check bigrams
    for i in range(len(words) - 1):
        bigram = (
            words[i].strip(".,!?;:'\"()[]{}").lower()
            + " "
            + words[i + 1].strip(".,!?;:'\"()[]{}").lower()
        )
        if bigram in LEGAL_TERM_EXPANSIONS:
            for expansion in LEGAL_TERM_EXPANSIONS[bigram]:
                if expansion not in seen:
                    expansions.append(expansion)
                    seen.add(expansion)

    # Also include the filtered original text as a query
    filtered_words = [
        w.strip(".,!?;:'\"()[]{}").lower()
        for w in words
        if w.strip(".,!?;:'\"()[]{}").lower() not in SEARCH_STOPWORDS
    ]
    if filtered_words:
        filtered_text = " ".join(filtered_words)
        if filtered_text not in seen:
            expansions.append(filtered_text)
            seen.add(filtered_text)

    return expansions


def get_branch_signals(text: str) -> list[str]:
    """Check text against BRANCH_SIGNAL_WORDS and return matching branch names.

    Used to prioritize which FOLIO branches to search for a given text.

    Args:
        text: Consumer narrative text to analyze.

    Returns:
        List of FOLIO branch names that have signal word matches.
    """
    text_lower = text.lower()
    matching_branches: list[str] = []

    for branch_name, signal_words in BRANCH_SIGNAL_WORDS.items():
        for signal in signal_words:
            if signal.lower() in text_lower:
                matching_branches.append(branch_name)
                break  # One match per branch is enough

    return matching_branches
