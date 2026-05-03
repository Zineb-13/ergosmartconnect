# -*- coding: utf-8 -*-
"""Module IA — génération de plans d'intervention ergothérapique via Llama/Groq."""

from .groq_service import generate_intervention_plan, analyze_patient_data

__all__ = ["generate_intervention_plan", "analyze_patient_data"]