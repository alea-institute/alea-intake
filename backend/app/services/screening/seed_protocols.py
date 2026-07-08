"""16 curated seed screening protocols and idempotent DB loader.

Ships with the system as the default protocol library. Covers three severity tiers:
- Critical (5): Immediate safety interrupts with mandatory questions and resources
- Elevated (5): Queued for next conversation pause with follow-up questions
- Advisory (6): Folded into exploration rounds as additional signals

All critical protocols include:
- "Are you safe right now?" as the first mandatory question (D-13)
- Safety planning resources with real hotline numbers
- Mandated reporting awareness flag
- Trauma-informed question framing (D-14)

All questions follow trauma-informed design:
- Normalize the inquiry ("Many people in your situation...")
- Offer opt-out ("You don't have to answer this")
- Explain purpose when transparency enabled (text_transparent field)
- Never use clinical or legal jargon
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ProtocolVersion, ScreeningProtocol

# ---------------------------------------------------------------------------
# Safety Question Template (reused across critical protocols)
# ---------------------------------------------------------------------------

_SAFETY_OPENER = {
    "question_id": "safety-check-01",
    "text": "Are you safe right now?",
    "text_transparent": (
        "I want to make sure you're in a safe situation before we continue. "
        "Are you safe right now? If not, I can connect you with immediate help."
    ),
    "priority": 1,
    "is_mandatory": True,
    "follow_up_if_yes": None,
    "follow_up_if_no": "safety-resources",
    "trauma_informed_framing": "Your safety is the most important thing right now.",
}

# ---------------------------------------------------------------------------
# Critical Tier (5 protocols) -- Immediate interrupt
# ---------------------------------------------------------------------------

_DV_IPV = {
    "name": "Domestic Violence / Intimate Partner Violence",
    "slug": "dv-ipv",
    "severity_tier": "critical",
    "description": (
        "Screens for domestic violence and intimate partner violence indicators. "
        "Runs across all areas of law, not just family law (D-11)."
    ),
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "domestic violence", "afraid of partner", "hitting me", "abusive relationship",
            "partner threatens", "spouse hits", "beaten by", "afraid to go home",
            "controlling behavior", "restraining order", "protection order",
            "order for protection", "intimate partner violence", "ipv", "dv",
            # BUG-20: real intake narratives describe DV in lay terms, not the
            # phrase "domestic violence". A family-custody DV text thread ("you
            # left a bruise on me in front of the kids", "don't you dare call the
            # cops") previously fired NO safety protocol, so the DV hotline never
            # surfaced. These high-precision lay-DV phrases close that gap.
            "left a bruise", "gave me a bruise", "left a mark on me",
            "grabbed me", "grabbed my arm", "afraid to call the police",
            "afraid to call the cops", "won't let me leave", "wont let me leave",
        ],
        "regex_patterns": [
            r"(partner|spouse|husband|wife|boyfriend|girlfriend)\s+(hit|beat|hurt|threaten|choke|strangle)",
            r"afraid\s+(of|to\s+leave)\s+(my\s+)?(partner|spouse|husband|wife)",
            # BUG-20: lay-described intimate-partner violence.
            r"(left|gave)\s+(me\s+)?(a\s+)?(bruise|mark|welt)",
            r"(bruise|mark|welt)\s+on\s+(my|your|her|his)\s+(arm|face|neck|body|wrist)",
            r"(grab|grabb)(ed|ing)?\s+(me|my|her|his|your)\s*(arm|wrist|neck)?",
            r"(don'?t|do\s+not|dare)\s+(you\s+)?call\s+the\s+(cops|police)",
            r"(never\s+see\s+(them|the\s+kids|the\s+children)\s+again)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.3,
    },
    "questions": [
        _SAFETY_OPENER,
        {
            "question_id": "dv-02",
            "text": "Has anyone in your household made you feel afraid or unsafe?",
            "text_transparent": (
                "Many people dealing with legal issues also experience conflict at home. "
                "Has anyone in your household made you feel afraid or unsafe? "
                "You don't have to answer this if you're not comfortable."
            ),
            "priority": 2,
            "is_mandatory": False,
            "follow_up_if_yes": "dv-03",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Many people in your situation experience this. You are not alone.",
        },
        {
            "question_id": "dv-03",
            "text": "Are there children in the home who may be affected?",
            "text_transparent": (
                "This helps us understand if children may need protection too. "
                "Are there children in the home who may be affected?"
            ),
            "priority": 3,
            "is_mandatory": False,
            "follow_up_if_yes": None,
            "follow_up_if_no": None,
            "trauma_informed_framing": "We ask this to make sure everyone is protected.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": True,
        "mandated_reporting_flag": True,
        "mandated_reporting_note": "Jurisdiction-specific mandatory reporting obligations may apply.",
        "flag_for_attorney_review": True,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "National Domestic Violence Hotline", "phone": "1-800-799-7233", "text": "START to 88788", "url": "https://www.thehotline.org"},
            {"name": "National Dating Abuse Helpline", "phone": "1-866-331-9474", "text": "LOVEIS to 22522"},
        ],
        "emergency": "If you are in immediate danger, call 911.",
        "safety_planning": "A safety plan can help you prepare for emergencies. The National DV Hotline can help create one.",
    },
}

_CHILD_ABUSE = {
    "name": "Child Abuse / Neglect",
    "slug": "child-abuse",
    "severity_tier": "critical",
    "description": "Screens for indicators of child abuse, neglect, or endangerment.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "child abuse", "child neglect", "hurt my child", "hitting the kids",
            "cps", "child protective services", "endangerment",
            "bruises on child", "afraid for my children", "children taken away",
        ],
        "regex_patterns": [
            r"(child|kid|minor|son|daughter)\s+(abuse|neglect|endanger|hurt|beaten)",
            r"cps\s+(took|investigation|report|visit)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.3,
    },
    "questions": [
        _SAFETY_OPENER,
        {
            "question_id": "ca-02",
            "text": "Are the children currently in a safe place?",
            "text_transparent": (
                "We want to make sure any children involved are safe. "
                "Are the children currently in a safe place?"
            ),
            "priority": 2,
            "is_mandatory": True,
            "follow_up_if_yes": None,
            "follow_up_if_no": "safety-resources",
            "trauma_informed_framing": "Protecting children is a priority. There are people who can help.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": True,
        "mandated_reporting_flag": True,
        "mandated_reporting_note": "All states require reporting of suspected child abuse or neglect.",
        "flag_for_attorney_review": True,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "Childhelp National Child Abuse Hotline", "phone": "1-800-422-4453", "url": "https://www.childhelp.org"},
        ],
        "emergency": "If a child is in immediate danger, call 911.",
    },
}

_ELDER_ABUSE = {
    "name": "Elder / Dependent Adult Abuse",
    "slug": "elder-abuse",
    "severity_tier": "critical",
    "description": "Screens for elder abuse, neglect, or exploitation of dependent adults.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "elder abuse", "elderly neglect", "nursing home abuse", "caregiver abuse",
            "taking advantage of elderly", "financial exploitation elderly",
            "dependent adult abuse", "adult protective services",
        ],
        "regex_patterns": [
            r"(elder|elderly|senior|nursing\s+home|caregiver)\s+(abuse|neglect|exploit|mistreat)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.3,
    },
    "questions": [
        _SAFETY_OPENER,
        {
            "question_id": "ea-02",
            "text": "Is the person receiving adequate food, medication, and basic care?",
            "text_transparent": (
                "We want to make sure basic needs are being met. "
                "Is the person receiving adequate food, medication, and basic care?"
            ),
            "priority": 2,
            "is_mandatory": False,
            "follow_up_if_yes": None,
            "follow_up_if_no": "ea-03",
            "trauma_informed_framing": "Many families face challenges providing care. Help is available.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": True,
        "mandated_reporting_flag": True,
        "mandated_reporting_note": "Most states require reporting of suspected elder/dependent adult abuse.",
        "flag_for_attorney_review": True,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "Eldercare Locator", "phone": "1-800-677-1116", "url": "https://eldercare.acl.gov"},
            {"name": "Adult Protective Services", "phone": "Contact your local APS agency"},
        ],
        "emergency": "If someone is in immediate danger, call 911.",
    },
}

_SELF_HARM = {
    "name": "Self-Harm / Suicidal Ideation",
    "slug": "self-harm",
    "severity_tier": "critical",
    "description": "Screens for self-harm or suicidal ideation indicators.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "want to die", "kill myself", "suicidal", "self-harm", "end my life",
            "no reason to live", "better off dead", "can't go on",
            "hurting myself", "cutting myself",
        ],
        "regex_patterns": [
            r"(want|going|plan|thinking)\s+(to\s+)?(die|kill\s+myself|end\s+(it|my\s+life))",
            r"(self[- ]?harm|self[- ]?injur)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.2,
    },
    "questions": [
        _SAFETY_OPENER,
        {
            "question_id": "sh-02",
            "text": "Are you having thoughts of hurting yourself right now?",
            "text_transparent": (
                "Sometimes when people are going through difficult legal situations, "
                "they may have thoughts about hurting themselves. "
                "Are you having any of those thoughts right now? There is help available."
            ),
            "priority": 2,
            "is_mandatory": True,
            "follow_up_if_yes": "safety-resources",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Legal problems can feel overwhelming. You don't have to face this alone.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": True,
        "mandated_reporting_flag": True,
        "mandated_reporting_note": "Imminent risk of harm may trigger duty-to-warn obligations.",
        "flag_for_attorney_review": True,
        "pause_analysis": True,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "988 Suicide & Crisis Lifeline", "phone": "988", "text": "988", "url": "https://988lifeline.org"},
            {"name": "Crisis Text Line", "text": "HOME to 741741"},
        ],
        "emergency": "If you are in immediate danger, call 911 or go to your nearest emergency room.",
    },
}

_HUMAN_TRAFFICKING = {
    "name": "Human Trafficking",
    "slug": "human-trafficking",
    "severity_tier": "critical",
    "description": "Screens for indicators of human trafficking, forced labor, or sex trafficking.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "human trafficking", "forced labor", "sex trafficking", "trafficked",
            "forced to work", "held against will", "can't leave",
            "taken passport", "labor exploitation", "modern slavery",
        ],
        "regex_patterns": [
            r"(forced|made)\s+(to\s+)?(work|prostitut|sex)",
            r"(passport|documents?)\s+(taken|confiscated|held)",
            r"(can'?t|cannot|not\s+allowed\s+to)\s+leave",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.3,
    },
    "questions": [
        _SAFETY_OPENER,
        {
            "question_id": "ht-02",
            "text": "Are you free to leave your current living or work situation?",
            "text_transparent": (
                "We want to make sure you have freedom in your daily life. "
                "Are you free to leave your current living or work situation if you wanted to?"
            ),
            "priority": 2,
            "is_mandatory": True,
            "follow_up_if_yes": None,
            "follow_up_if_no": "safety-resources",
            "trauma_informed_framing": "Everyone deserves freedom and safety. Help is available.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": True,
        "mandated_reporting_flag": True,
        "mandated_reporting_note": "Federal law requires reporting of known or suspected human trafficking.",
        "flag_for_attorney_review": True,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "National Human Trafficking Hotline", "phone": "1-888-373-7888", "text": "233733", "url": "https://humantraffickinghotline.org"},
        ],
        "emergency": "If you are in immediate danger, call 911.",
    },
}

# ---------------------------------------------------------------------------
# Elevated Tier (5 protocols) -- Queued for next pause
# ---------------------------------------------------------------------------

_STALKING = {
    "name": "Stalking / Harassment",
    "slug": "stalking",
    "severity_tier": "elevated",
    "description": "Screens for stalking, harassment, or persistent unwanted contact.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "stalking", "stalker", "following me", "watching me",
            "harassment", "threatening messages", "won't leave me alone",
            "cyberstalking", "tracking my phone",
        ],
        "regex_patterns": [
            r"stalk(ing|er|ed)",
            r"follow(ing|ed)\s+me",
            r"(harass|threaten)(ing|ed|ment)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.4,
    },
    "questions": [
        {
            "question_id": "st-01",
            "text": "Has someone been contacting you or showing up uninvited repeatedly?",
            "text_transparent": (
                "Repeated unwanted contact can be a legal issue. "
                "Has someone been contacting you or showing up uninvited repeatedly?"
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "st-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "You have a right to feel safe. There are legal protections available.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": True,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "Stalking Prevention, Awareness, and Resource Center (SPARC)", "url": "https://www.stalkingawareness.org"},
        ],
    },
}

_SEXUAL_ASSAULT = {
    "name": "Sexual Assault",
    "slug": "sexual-assault",
    "severity_tier": "elevated",
    "description": "Screens for sexual assault, rape, or sexual abuse indicators.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "sexual assault", "raped", "rape", "sexually abused",
            "molested", "unwanted sexual", "forced sex",
            "sexual harassment", "groped",
        ],
        "regex_patterns": [
            r"sexual(ly)?\s+(assault|abuse|harass|violence)",
            r"(raped?|molest)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.3,
    },
    "questions": [
        {
            "question_id": "sa-01",
            "text": "Have you experienced unwanted sexual contact or behavior?",
            "text_transparent": (
                "Some legal situations involve unwanted sexual experiences. "
                "Have you experienced unwanted sexual contact or behavior? "
                "You don't have to share details you're not comfortable with."
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "sa-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "What happened to you is not your fault. Support is available.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": True,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "RAINN National Sexual Assault Hotline", "phone": "1-800-656-4673", "url": "https://www.rainn.org"},
        ],
    },
}

_SUBSTANCE_ABUSE = {
    "name": "Substance Abuse",
    "slug": "substance-abuse",
    "severity_tier": "elevated",
    "description": "Screens for substance abuse issues that may affect legal proceedings or safety.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "substance abuse", "addiction", "drug problem", "alcoholism",
            "rehab", "overdose", "drug court", "sobriety",
            "drinking problem", "using drugs",
        ],
        "regex_patterns": [
            r"(substance|drug|alcohol)\s+(abuse|addiction|depend|problem)",
            r"(overdos|relaps)(e|ed|ing)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.4,
    },
    "questions": [
        {
            "question_id": "sub-01",
            "text": "Has substance use been a factor in your current situation?",
            "text_transparent": (
                "Substance use can affect legal matters and available options. "
                "Has substance use been a factor in your current situation? "
                "This is not a judgment -- it helps us find the right resources."
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "sub-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Many people face substance use challenges. Treatment and support exist.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "SAMHSA National Helpline", "phone": "1-800-662-4357", "url": "https://www.samhsa.gov/find-help/national-helpline"},
        ],
    },
}

_MENTAL_HEALTH_CRISIS = {
    "name": "Mental Health Crisis",
    "slug": "mental-health-crisis",
    "severity_tier": "elevated",
    "description": "Screens for acute mental health crises that may affect legal capacity or safety.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "mental health crisis", "psychiatric emergency", "breakdown",
            "can't cope", "losing my mind", "hearing voices",
            "severe anxiety", "panic attacks", "mental institution",
        ],
        "regex_patterns": [
            r"mental\s+health\s+(crisis|emergency|breakdown)",
            r"(psychiatric|psych)\s+(emergency|hospital|hold|ward)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.4,
    },
    "questions": [
        {
            "question_id": "mh-01",
            "text": "Are you experiencing a mental health crisis that needs immediate attention?",
            "text_transparent": (
                "Legal situations can be very stressful on mental health. "
                "Are you experiencing a mental health crisis that needs immediate attention? "
                "We can connect you with support."
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "safety-resources",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Your mental health matters. It's okay to ask for help.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "988 Suicide & Crisis Lifeline", "phone": "988", "url": "https://988lifeline.org"},
            {"name": "NAMI Helpline", "phone": "1-800-950-6264", "url": "https://www.nami.org/help"},
        ],
    },
}

_IMMIGRATION_DETENTION = {
    "name": "Immigration Detention Risk",
    "slug": "immigration-detention",
    "severity_tier": "elevated",
    "description": "Screens for immigration detention risk, deportation threats, or status-related vulnerability.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "deportation", "immigration detention", "ice",
            "undocumented", "immigration status", "detained by immigration",
            "visa expired", "removal proceedings", "asylum",
        ],
        "regex_patterns": [
            r"(deport|detain|remov)(ation|ed|ing)\s*(by\s+)?(ice|immigration|cbp)?",
            r"immigration\s+(court|judge|hearing|detention)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.4,
    },
    "questions": [
        {
            "question_id": "imm-01",
            "text": "Are you concerned about your immigration status affecting your legal situation?",
            "text_transparent": (
                "Immigration status can affect legal options and protections available. "
                "Are you concerned about your immigration status? "
                "This information is kept confidential."
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "imm-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Everyone deserves legal protection regardless of immigration status.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": True,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "National Immigrant Women's Advocacy Project", "url": "https://niwaplibrary.wcl.american.edu"},
            {"name": "Immigration Advocates Network", "url": "https://www.immigrationadvocates.org"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Advisory Tier (6 protocols) -- Folded into exploration
# ---------------------------------------------------------------------------

_HOUSING_INSTABILITY = {
    "name": "Housing Instability",
    "slug": "housing-instability",
    "severity_tier": "advisory",
    "description": "Screens for housing instability, homelessness risk, or unsafe living conditions.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "homeless", "eviction", "about to lose housing", "sleeping in car",
            "shelter", "couch surfing", "housing instability",
            "condemned building", "no place to live",
        ],
        "regex_patterns": [
            r"(evict|homeless|unhoused)(ed|ion|ness)?",
            r"(lose|losing|lost)\s+(my\s+)?(home|house|apartment|housing)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.5,
    },
    "questions": [
        {
            "question_id": "hi-01",
            "text": "Are you at risk of losing your housing or currently without stable housing?",
            "text_transparent": (
                "Housing stability affects many legal situations. "
                "Are you at risk of losing your housing? There may be legal protections available."
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "hi-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Housing challenges are common. Legal options may be available.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {
        "hotlines": [
            {"name": "HUD Housing Counseling", "phone": "1-800-569-4287"},
        ],
    },
}

_EMPLOYMENT_RETALIATION = {
    "name": "Employment Retaliation",
    "slug": "employment-retaliation",
    "severity_tier": "advisory",
    "description": "Screens for workplace retaliation, wrongful termination, or whistleblower issues.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "retaliation", "fired for reporting", "whistleblower",
            "wrongful termination", "demoted for complaining",
            "punished for speaking up", "hostile work environment",
        ],
        "regex_patterns": [
            r"(fired|terminated|demoted|punished)\s+(for|after)\s+(report|complain|speaking|whistleblow)",
            r"retaliat(ion|ed|ing)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.5,
    },
    "questions": [
        {
            "question_id": "er-01",
            "text": "Did any negative action at work happen after you reported a concern or exercised a right?",
            "text_transparent": (
                "Sometimes employers take action against employees who report problems. "
                "Did anything negative happen at work after you reported a concern?"
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "er-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "You have a right to speak up without punishment.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {},
}

_FINANCIAL_EXPLOITATION = {
    "name": "Financial Exploitation",
    "slug": "financial-exploitation",
    "severity_tier": "advisory",
    "description": "Screens for financial exploitation, fraud, or predatory lending.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "financial exploitation", "stolen money", "identity theft",
            "predatory lending", "scammed", "fraud", "took my money",
            "forged signature", "unauthorized charges",
        ],
        "regex_patterns": [
            r"(stole|stealing|taken)\s+(my\s+)?(money|savings|identity|finances)",
            r"(predatory|payday)\s+l(oan|ending)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.5,
    },
    "questions": [
        {
            "question_id": "fe-01",
            "text": "Has someone taken or misused your money or financial accounts without permission?",
            "text_transparent": (
                "Financial exploitation is more common than people think. "
                "Has someone taken or misused your money without permission?"
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "fe-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Financial exploitation can happen to anyone. Legal remedies exist.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {},
}

_FIREARMS_ACCESS = {
    "name": "Firearms Access",
    "slug": "firearms-access",
    "severity_tier": "advisory",
    "description": "Screens for firearms access in situations involving conflict, threats, or protection orders.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "gun", "firearm", "weapon", "threatened with gun",
            "has a gun", "firearms access", "armed",
            "gun in the house", "concealed carry",
        ],
        "regex_patterns": [
            r"(gun|firearm|weapon)\s+(in|at|near)\s+(the\s+)?(home|house)",
            r"threaten(ed|ing)?\s+(with\s+)?(a\s+)?(gun|firearm|weapon)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.5,
    },
    "questions": [
        {
            "question_id": "fa-01",
            "text": "Are there firearms in the home or accessible to anyone involved in your situation?",
            "text_transparent": (
                "The presence of firearms can affect safety planning and legal options. "
                "Are there firearms accessible to anyone involved?"
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "fa-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "This question helps us assess safety considerations.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {},
}

_CUSTODY_ALIENATION = {
    "name": "Custody / Parental Alienation",
    "slug": "custody-alienation",
    "severity_tier": "advisory",
    "description": "Screens for custody disputes involving parental alienation or interference.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "parental alienation", "turning kids against me", "custody battle",
            "won't let me see my kids", "kidnapped children",
            "hiding the children", "custody interference",
            "violating custody order", "parental kidnapping",
        ],
        "regex_patterns": [
            r"(parental\s+)?alienat(ion|ing|ed)",
            r"(won'?t|refuse|denied)\s+(let|allow)\s+(me\s+)?(see|visit)\s+(my\s+)?(child|kid|son|daughter)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.5,
    },
    "questions": [
        {
            "question_id": "ca-01",
            "text": "Is the other parent preventing you from seeing your children?",
            "text_transparent": (
                "Custody disputes can sometimes involve one parent limiting the other's access. "
                "Is the other parent preventing you from seeing your children?"
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "ca-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Custody situations are stressful. Legal options exist to protect your rights.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {},
}

_MEDICAL_NEGLECT = {
    "name": "Medical Neglect",
    "slug": "medical-neglect",
    "severity_tier": "advisory",
    "description": "Screens for medical neglect of children, elderly, or dependent adults.",
    "version": "1.0.0",
    "trigger_conditions": {
        "keywords": [
            "medical neglect", "denied medical care", "won't take to doctor",
            "refusing treatment", "no medical care",
            "withholding medication", "medical abuse",
        ],
        "regex_patterns": [
            r"(medical|health)\s+(neglect|abuse|deny|denied|withhold)",
            r"(won'?t|refuse|denied)\s+(take|bring)\s+(to\s+)?(doctor|hospital|clinic)",
        ],
        "folio_concept_iris": [],
        "area_of_law_iris": [],
        "exclude_keywords": [],
        "min_confidence": 0.5,
    },
    "questions": [
        {
            "question_id": "mn-01",
            "text": "Is someone being denied necessary medical care or medication?",
            "text_transparent": (
                "Denying necessary medical care can be a form of neglect with legal implications. "
                "Is someone being denied necessary medical care or medication?"
            ),
            "priority": 1,
            "is_mandatory": False,
            "follow_up_if_yes": "mn-02",
            "follow_up_if_no": None,
            "trauma_informed_framing": "Everyone deserves access to medical care. Help may be available.",
        },
    ],
    "escalation_actions": {
        "immediate_resources": False,
        "mandated_reporting_flag": False,
        "flag_for_attorney_review": False,
        "pause_analysis": False,
    },
    "safety_resources": {},
}

# ---------------------------------------------------------------------------
# Complete Seed Protocol List
# ---------------------------------------------------------------------------

SEED_PROTOCOLS: list[dict] = [
    # Critical (5)
    _DV_IPV,
    _CHILD_ABUSE,
    _ELDER_ABUSE,
    _SELF_HARM,
    _HUMAN_TRAFFICKING,
    # Elevated (5)
    _STALKING,
    _SEXUAL_ASSAULT,
    _SUBSTANCE_ABUSE,
    _MENTAL_HEALTH_CRISIS,
    _IMMIGRATION_DETENTION,
    # Advisory (6)
    _HOUSING_INSTABILITY,
    _EMPLOYMENT_RETALIATION,
    _FINANCIAL_EXPLOITATION,
    _FIREARMS_ACCESS,
    _CUSTODY_ALIENATION,
    _MEDICAL_NEGLECT,
]


# ---------------------------------------------------------------------------
# Idempotent DB Loader
# ---------------------------------------------------------------------------


async def seed_protocols_to_db(session: AsyncSession) -> int:
    """Insert all 16 seed protocols and their v1.0.0 versions into the database.

    Uses slug-based deduplication for idempotency: if a protocol with the same
    slug already exists, it is skipped. Returns count of newly inserted protocols.
    """
    inserted_count = 0

    # Get existing slugs
    result = await session.execute(
        select(ScreeningProtocol.slug).where(ScreeningProtocol.is_seed.is_(True))
    )
    existing_slugs = {row[0] for row in result.all()}

    for proto_def in SEED_PROTOCOLS:
        if proto_def["slug"] in existing_slugs:
            continue

        # Create protocol record
        protocol = ScreeningProtocol(
            name=proto_def["name"],
            slug=proto_def["slug"],
            description=proto_def.get("description"),
            severity_tier=proto_def["severity_tier"],
            owner_org_id=None,  # System seed -- no org owner
            is_shared=True,  # Seeds are visible to all
            is_seed=True,
        )
        session.add(protocol)
        await session.flush()  # Get protocol.id

        # Create initial version
        version = ProtocolVersion(
            protocol_id=protocol.id,
            version=proto_def.get("version", "1.0.0"),
            trigger_conditions_json=proto_def["trigger_conditions"],
            questions_json=proto_def["questions"],
            escalation_actions_json=proto_def["escalation_actions"],
            safety_resources_json=proto_def.get("safety_resources"),
            is_active=True,
        )
        session.add(version)
        inserted_count += 1

    await session.flush()
    return inserted_count
