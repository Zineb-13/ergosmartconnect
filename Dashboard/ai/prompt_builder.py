# -*- coding: utf-8 -*-
"""Construit des prompts propres pour les fonctions IA du dossier patient."""

from .knowledge_base import get_knowledge_base


def _repair_text(value):
    text = str(value or "")
    try:
        text = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    replacements = {
        "\u00e2\u20ac\u2122": "’",
        "\u00e2\u20ac\u0153": "“",
        "\u00e2\u20ac\u009d": "”",
        "\u00e2\u20ac\u201c": "-",
        "\u00e2\u20ac\u201d": "-",
        "â‰¥": "≥",
        "â‰¤": "≤",
        "Â°": "°",
        "\u00c3\u2014": "×",
        "Å“": "œ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def _short(value, limit=220):
    text = _repair_text(value).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text or "Non renseigné"


def _field(patient_data, key, default="Non renseigné"):
    value = patient_data.get(key)
    return _short(value if value not in (None, "") else default)


def _nested_summary(data, max_chars=4500):
    dossier = data.get("dossier_complet") or {}
    if not isinstance(dossier, dict):
        return ""

    lines = []
    useful_sections = [
        "anamnese", "histoire", "symptomes", "retentissement", "objectifs",
        "musculaire", "articulaire", "douleur", "trophique", "sensitif",
        "prehension", "dexterite", "endurance", "mcro", "prwe", "synthese",
    ]

    def add_value(prefix, value):
        if value in (None, "", [], {}):
            return
        if isinstance(value, dict):
            for k, v in value.items():
                add_value(f"{prefix} / {k}", v)
            return
        if isinstance(value, list):
            clean_items = [_short(item, 90) for item in value if item not in (None, "", [], {})]
            if clean_items:
                lines.append(f"- {prefix}: {', '.join(clean_items[:8])}")
            return
        lines.append(f"- {prefix}: {_short(value, 160)}")

    for section in useful_sections:
        section_data = dossier.get(section)
        if section_data:
            add_value(section, section_data)

    summary = "\n".join(lines)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit("\n", 1)[0] + "\n- Données complémentaires présentes mais abrégées."
    return summary


def get_system_prompt() -> str:
    knowledge = _repair_text(get_knowledge_base())

    return f"""Tu es un assistant clinique spécialisé en ergothérapie, dédié à la rééducation post-fracture du poignet.

Règles strictes :
1. Tu respectes uniquement le modèle clinique et la base de connaissances fournis ci-dessous.
2. Tu n’inventes jamais d’exercice, de score, de douleur, de diagnostic ou d’information absente du dossier.
3. Tu adaptes automatiquement le contenu à chaque patient selon ses données réelles : douleur, PRWE, MCRO, force, mobilité, sensibilité, préhension, objectifs et AVQ.
4. Tu gardes la structure demandée pour le plan d’intervention. Tu peux signaler les données manquantes, mais tu ne les remplaces pas par de fausses valeurs.
5. Tu aides le thérapeute, tu ne remplaces pas son jugement clinique.
6. Tu ne poses pas de diagnostic médical et tu ne prescris pas de médicament.
7. Tu réponds en français clair, structuré, sans texte encodé cassé.

Base de connaissances validée à respecter :
{knowledge}

Structure obligatoire du plan :
## 1. Synthèse clinique
## 2. Objectifs thérapeutiques
## 3. Plan d’intervention en cabinet
## 4. Programme à domicile
## 5. Précautions et points de vigilance
## 6. Critères de progression / réévaluation
## 7. Recommandations au thérapeute
"""


def build_user_prompt(patient_data: dict) -> str:
    mcro_problemes = patient_data.get("mcro_problemes") or []
    mcro_text = "Non renseigné"
    if mcro_problemes:
        mcro_text = "\n".join(
            f"- {_short(p.get('nom'))}: importance {p.get('importance', '?')}/10, "
            f"rendement {p.get('rendement', '?')}/10, satisfaction {p.get('satisfaction', '?')}/10"
            for p in mcro_problemes
            if isinstance(p, dict)
        ) or "Non renseigné"

    dossier_resume = _nested_summary(patient_data)

    return f"""Données patient à analyser :

Identité :
- Patient: {_field(patient_data, "nom")} {_field(patient_data, "prenom", "")}
- Âge: {_field(patient_data, "age")}
- Sexe: {_field(patient_data, "sexe")}
- Dominance: {_field(patient_data, "dominance")}
- Membre atteint: {_field(patient_data, "membre_atteint")}
- Diagnostic indiqué dans le dossier: {_field(patient_data, "diagnostic")}

Douleur et scores :
- EVA repos: {_field(patient_data, "eva_repos", "0")}/10
- EVA effort: {_field(patient_data, "eva_effort", "0")}/10
- EVA mouvement: {_field(patient_data, "eva_mouvement", "0")}/10
- PRWE total: {_field(patient_data, "prwe_total", "0")}/110
- PRWE douleur: {_field(patient_data, "prwe_douleur", "0")}/50
- PRWE fonction: {_field(patient_data, "prwe_fonction", "0")}/60

Bilan fonctionnel :
- Œdème: {_field(patient_data, "oedeme", "non")}
- Troubles sensitifs: {_field(patient_data, "troubles_sensitifs", "non")}
- Préhension: {_field(patient_data, "interpretation_prehension")}
- Objectifs patient: {_short(", ".join(patient_data.get("objectifs_patient") or []), 500)}
- Difficultés AVQ: {_short(", ".join(patient_data.get("difficultes_avq") or []), 500)}

MCRO :
{mcro_text}

Données détaillées du dossier :
{dossier_resume or "Aucune donnée détaillée supplémentaire transmise."}

Génère maintenant une réponse adaptée à ce patient, concrète et utilisable par le thérapeute.
"""
