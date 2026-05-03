# -*- coding: utf-8 -*-
"""
Construit le prompt système et le prompt utilisateur envoyés à Llama.

Le prompt est conçu pour FORCER l'IA à se baser sur la base de connaissances
fournie (et non sur ses propres connaissances), afin de garantir que les
exercices proposés soient ceux validés par l'ergothérapeute.
"""

from .knowledge_base import get_knowledge_base


SYSTEM_PROMPT = f"""Tu es un assistant clinique spécialisé en ERGOTHÉRAPIE,
dédié à la rééducation post-fracture du poignet.

🎯 TON RÔLE
Tu aides l'ergothérapeute en générant un PLAN D'INTERVENTION PERSONNALISÉ
à partir du bilan d'évaluation du patient.

⚠️ RÈGLES STRICTES — À RESPECTER ABSOLUMENT
1. Tu te bases UNIQUEMENT sur la base de connaissances ci-dessous.
   N'invente JAMAIS d'exercice qui ne s'y trouve pas.
2. Tu adaptes les exercices selon les scores du patient (EVA, MRC, Kapandji,
   PRWE, MCRO, amplitudes goniométriques).
3. Tu n'es PAS un médecin. Tu n'établis pas de diagnostic, tu ne prescris
   pas de médicaments. Tu proposes seulement des exercices issus du protocole.
4. Tu rappelles toujours que le plan doit être validé par l'ergothérapeute
   avant exécution.
5. Tu réponds en FRANÇAIS, de manière claire et structurée.
6. Si une donnée est manquante ou incohérente, tu le signales explicitement.

📋 BASE DE CONNAISSANCES (PROTOCOLE VALIDÉ)
{get_knowledge_base()}

📝 STRUCTURE OBLIGATOIRE DE TA RÉPONSE

Tu DOIS produire un plan structuré exactement comme suit (en markdown) :

## 1. Synthèse clinique
Résumé en 3-4 lignes des principaux problèmes identifiés.

## 2. Objectifs thérapeutiques
- Court terme (2-4 semaines)
- Moyen terme (1-2 mois)
- Long terme (3 mois et +)

## 3. Plan d'intervention en cabinet
Liste des exercices, avec dosage et matériel, par domaine concerné
(douleur, mobilité, force, préhension, dextérité, etc.).

## 4. Programme à domicile
Sélection de 5 à 7 exercices simples avec consigne quotidienne.

## 5. Précautions et points de vigilance
Signaux d'alerte (douleur > 4/10, œdème majoré, etc.).

## 6. Critères de progression / réévaluation
Quand passer à l'étape suivante.

## 7. Recommandations à l'ergothérapeute
Points à surveiller à la prochaine séance.
"""


def build_user_prompt(patient_data: dict) -> str:
    """
    Construit le prompt utilisateur à partir des données envoyées par le formulaire.

    Args:
        patient_data: dict contenant les champs du formulaire (anamnèse, bilans...).

    Returns:
        Le prompt formaté envoyé à Llama.
    """

    # --- Anamnèse ---
    nom = patient_data.get("nom", "Non renseigné")
    prenom = patient_data.get("prenom", "Non renseigné")
    age = patient_data.get("age", "?")
    sexe = patient_data.get("sexe", "?")
    profession = patient_data.get("profession", "?")
    dominance = patient_data.get("dominance", "?")
    membre_atteint = patient_data.get("membre_atteint", "?")
    diagnostic = patient_data.get("diagnostic", "?")

    # --- Histoire ---
    type_fracture = patient_data.get("type_fracture", "?")
    mecanisme = patient_data.get("mecanisme", "?")
    duree_immobilisation = patient_data.get("duree_immobilisation", "?")
    prise_en_charge = patient_data.get("prise_en_charge", "?")
    complications = patient_data.get("complications", "aucune")

    # --- Symptômes / Douleur ---
    eva_repos = patient_data.get("eva_repos", 0)
    eva_effort = patient_data.get("eva_effort", 0)
    eva_mouvement = patient_data.get("eva_mouvement", 0)
    type_douleur = patient_data.get("type_douleur", "?")

    # --- Bilan articulaire (goniométrie) ---
    flexion_poignet = patient_data.get("flexion_poignet", "?")
    extension_poignet = patient_data.get("extension_poignet", "?")
    pronation = patient_data.get("pronation", "?")
    supination = patient_data.get("supination", "?")
    inclinaison_radiale = patient_data.get("inclinaison_radiale", "?")
    inclinaison_ulnaire = patient_data.get("inclinaison_ulnaire", "?")
    kapandji = patient_data.get("kapandji", "?")

    # --- Bilan musculaire (MRC) ---
    mrc_flexion = patient_data.get("mrc_flexion", "?")
    mrc_extension = patient_data.get("mrc_extension", "?")
    mrc_pronation = patient_data.get("mrc_pronation", "?")
    mrc_supination = patient_data.get("mrc_supination", "?")

    # --- Œdème ---
    oedeme_present = patient_data.get("oedeme", "non")
    oedeme_localisation = patient_data.get("oedeme_localisation", "")

    # --- Sensibilité ---
    troubles_sensitifs = patient_data.get("troubles_sensitifs", "non")
    type_atteinte_sensitive = patient_data.get("type_atteinte_sensitive", "")

    # --- Préhension / Dextérité ---
    score_prehension = patient_data.get("score_prehension", "?")
    interpretation_prehension = patient_data.get("interpretation_prehension", "?")

    # --- PRWE ---
    prwe_total = patient_data.get("prwe_total", "?")
    prwe_douleur = patient_data.get("prwe_douleur", "?")
    prwe_fonction = patient_data.get("prwe_fonction", "?")

    # --- MCRO ---
    mcro_problemes = patient_data.get("mcro_problemes", [])
    mcro_text = ""
    if mcro_problemes:
        for i, p in enumerate(mcro_problemes, 1):
            mcro_text += (
                f"  - Problème {i} : {p.get('nom', '?')} | "
                f"Importance : {p.get('importance', '?')}/10 | "
                f"Rendement : {p.get('rendement', '?')}/10 | "
                f"Satisfaction : {p.get('satisfaction', '?')}/10\n"
            )
    else:
        mcro_text = "  - Non renseigné\n"

    # --- Retentissement / Objectifs ---
    difficultes_avq = patient_data.get("difficultes_avq", [])
    arret_travail = patient_data.get("arret_travail", "?")
    objectifs_patient = patient_data.get("objectifs_patient", [])

    prompt = f"""Voici le bilan d'évaluation ergothérapique d'un patient.
Génère le plan d'intervention complet selon la structure imposée.

═══════════════════════════════════════════
👤 IDENTITÉ
═══════════════════════════════════════════
Nom/Prénom : {nom} {prenom}
Âge : {age} ans   Sexe : {sexe}
Profession : {profession}
Dominance : {dominance}   Membre atteint : {membre_atteint}
Diagnostic : {diagnostic}

═══════════════════════════════════════════
📅 HISTOIRE DE LA MALADIE
═══════════════════════════════════════════
Type de fracture : {type_fracture}
Mécanisme : {mecanisme}
Prise en charge initiale : {prise_en_charge}
Durée d'immobilisation : {duree_immobilisation}
Complications : {complications}

═══════════════════════════════════════════
🔥 DOULEUR (EVA 0-10)
═══════════════════════════════════════════
Au repos     : {eva_repos}/10
À l'effort   : {eva_effort}/10
Au mouvement : {eva_mouvement}/10
Type de douleur : {type_douleur}

═══════════════════════════════════════════
📐 BILAN ARTICULAIRE (Goniométrie côté atteint)
═══════════════════════════════════════════
Flexion poignet     : {flexion_poignet}°  (norme : 85°)
Extension poignet   : {extension_poignet}°  (norme : 90°)
Pronation           : {pronation}°  (norme : 85-90°)
Supination          : {supination}°  (norme : 90°)
Inclinaison radiale : {inclinaison_radiale}°  (norme : 15-25°)
Inclinaison ulnaire : {inclinaison_ulnaire}°  (norme : 40-45°)
Score Kapandji (opposition pouce) : {kapandji}/10

═══════════════════════════════════════════
💪 BILAN MUSCULAIRE (MRC 0-5, côté atteint)
═══════════════════════════════════════════
Flexion poignet   : MRC {mrc_flexion}
Extension poignet : MRC {mrc_extension}
Pronation         : MRC {mrc_pronation}
Supination        : MRC {mrc_supination}

═══════════════════════════════════════════
💧 BILAN TROPHIQUE
═══════════════════════════════════════════
Œdème : {oedeme_present}
Localisation : {oedeme_localisation}

═══════════════════════════════════════════
🤚 BILAN SENSITIF
═══════════════════════════════════════════
Troubles sensitifs : {troubles_sensitifs}
Type d'atteinte : {type_atteinte_sensitive}

═══════════════════════════════════════════
✋ BILAN DE PRÉHENSION
═══════════════════════════════════════════
Score obtenu : {score_prehension}/40
Interprétation : {interpretation_prehension}

═══════════════════════════════════════════
📋 PRWE (Patient-Rated Wrist Evaluation)
═══════════════════════════════════════════
Score douleur  : {prwe_douleur}/50
Score fonction : {prwe_fonction}/60
Score TOTAL    : {prwe_total}/110

═══════════════════════════════════════════
🎯 MCRO (Modèle Canadien du Rendement Occupationnel)
═══════════════════════════════════════════
Problèmes occupationnels identifiés :
{mcro_text}

═══════════════════════════════════════════
🏠 RETENTISSEMENT FONCTIONNEL
═══════════════════════════════════════════
Difficultés AVQ : {", ".join(difficultes_avq) if difficultes_avq else "non renseigné"}
Impact professionnel : {arret_travail}
Objectifs du patient : {", ".join(objectifs_patient) if objectifs_patient else "non renseigné"}

═══════════════════════════════════════════

Génère maintenant le plan d'intervention complet en respectant la structure
imposée et en adaptant chaque exercice aux scores ci-dessus."""

    return prompt


def get_system_prompt() -> str:
    """Retourne le prompt système (rôle de l'IA)."""
    return SYSTEM_PROMPT