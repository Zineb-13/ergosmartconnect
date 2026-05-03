# -*- coding: utf-8 -*-
"""
Service d'appel à l'API Groq (Llama 3.3 70B) pour générer
le plan d'intervention ergothérapique.

API Groq : https://console.groq.com
Documentation : https://console.groq.com/docs
"""

import os
import logging
from typing import Optional

from groq import Groq, APIError, APIConnectionError, RateLimitError

from .prompt_builder import get_system_prompt, build_user_prompt

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────
# Modèle recommandé : llama-3.3-70b-versatile
# Alternatives :
#   - "llama-3.1-8b-instant"      → rapide et gratuit (moins intelligent)
#   - "llama-3.3-70b-versatile"   → meilleur compromis qualité/vitesse  ✅
#   - "openai/gpt-oss-120b"       → le plus intelligent
GROQ_MODEL = os.getenv("GROQ_PLAN_MODEL", "llama-3.3-70b-versatile")
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")

# Température : 0.3 = précis, factuel (recommandé en clinique)
TEMPERATURE = 0.3

# Tokens max en sortie (un plan complet = ~2000-3000 tokens)
MAX_TOKENS = int(os.getenv("GROQ_PLAN_MAX_TOKENS", "2200"))


def _get_client(timeout: int = 45) -> Groq:
    """Crée le client Groq à partir de la variable d'environnement."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY manquante. "
            "Ajoutez-la dans votre fichier .env ou settings.py. "
            "Obtenez votre clé sur https://console.groq.com/keys"
        )
    return Groq(api_key=api_key, timeout=timeout, max_retries=1)


def generate_intervention_plan(patient_data: dict) -> dict:
    """
    Génère un plan d'intervention ergothérapique personnalisé.

    Args:
        patient_data: dictionnaire des données du formulaire patient
                      (anamnèse, EVA, MRC, goniométrie, PRWE, MCRO, etc.).

    Returns:
        {
            "success": bool,
            "plan": str,          # plan en markdown si success=True
            "error": str | None,  # message d'erreur sinon
            "model": str,         # modèle utilisé
            "tokens_used": int    # nb tokens consommés (si dispo)
        }
    """
    try:
        client = _get_client(timeout=55)

        system_prompt = get_system_prompt()
        user_prompt = build_user_prompt(patient_data)

        logger.info(
            "Appel Groq pour patient %s %s",
            patient_data.get("nom", "?"),
            patient_data.get("prenom", "?"),
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=0.9,
            stream=False,
        )

        plan = response.choices[0].message.content
        tokens = getattr(response.usage, "total_tokens", 0) if response.usage else 0

        return {
            "success": True,
            "plan": plan,
            "error": None,
            "model": GROQ_MODEL,
            "tokens_used": tokens,
        }

    except RateLimitError as e:
        logger.warning("Rate limit Groq atteint : %s", e)
        return {
            "success": False,
            "plan": None,
            "error": "Limite de requêtes atteinte (free tier = 30/min). Réessayez dans 1 minute.",
            "model": GROQ_MODEL,
            "tokens_used": 0,
        }

    except APIConnectionError as e:
        logger.error("Erreur de connexion Groq : %s", e)
        return {
            "success": False,
            "plan": None,
            "error": "Impossible de joindre Groq. Vérifiez votre connexion Internet.",
            "model": GROQ_MODEL,
            "tokens_used": 0,
        }

    except APIError as e:
        logger.error("Erreur API Groq : %s", e)
        return {
            "success": False,
            "plan": None,
            "error": f"Erreur API Groq : {str(e)}",
            "model": GROQ_MODEL,
            "tokens_used": 0,
        }

    except ValueError as e:
        # Clé API manquante
        logger.error("Configuration Groq invalide : %s", e)
        return {
            "success": False,
            "plan": None,
            "error": str(e),
            "model": GROQ_MODEL,
            "tokens_used": 0,
        }

    except Exception as e:
        logger.exception("Erreur inattendue lors de l'appel Groq")
        return {
            "success": False,
            "plan": None,
            "error": f"Erreur inattendue : {str(e)}",
            "model": GROQ_MODEL,
            "tokens_used": 0,
        }


def analyze_patient_data(patient_data: dict) -> dict:
    """
    Analyse rapide des données patient (utilisée par le bouton 'Analyser avec IA').
    Donne un avis synthétique sans plan complet.
    """
    try:
        client = _get_client(timeout=25)

        system = """Tu es un thérapeute expert en rééducation du poignet.
Analyse les données patient en français clair.
Réponds en 3 blocs courts :
1. Résumé clinique
2. Priorités de prise en charge
3. Recommandation principale
Reste factuel, ne pose pas de diagnostic médical."""

        user = build_user_prompt(patient_data)

        response = client.chat.completions.create(
            model=GROQ_FAST_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=420,
        )

        return {
            "success": True,
            "analysis": response.choices[0].message.content,
            "error": None,
        }

    except Exception as e:
        logger.exception("Erreur analyse rapide")
        return {
            "success": False,
            "analysis": None,
            "error": str(e),
        }
