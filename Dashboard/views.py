from email.mime import message
from pyexpat.errors import messages
from urllib import request
from datetime import timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from datetime import date, datetime, timedelta
import json

from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.utils.timezone import localtime
from zoneinfo import ZoneInfo
from .models import ConnexionPatient, PatientProfile, Contact, RessourcePatient, Evaluation,DemandeRendezVous,ReponseRendezVous,SignalementRendezVous, DossierPatient, ProgrammeExercice, Exercice, BibliothequeExerciceMedia, BibliothequeExercice, ResultatExercice, ProgressionPatient, Message, RDV, Ressource, IA_Recommendation, HistoriqueAction, Recompense, JournalPatient, ExerciceMedia, ProgrammeEnvoye, QuestionJour, ReponseQuestionJour
from django.db.models import Avg, Count, Max
from django.db.models import Q, Exists, OuterRef
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils.dateparse import parse_datetime
from django.urls import reverse
import mimetypes

# Fuseau horaire de l'Algérie
ALGERIA_TZ = ZoneInfo("Africa/Algiers")
ALGERIA_TZ_OFFSET = timedelta(hours=1)
import json
import logging

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .ai import generate_intervention_plan, analyze_patient_data

logger = logging.getLogger(__name__)


def _patient_from_ai_payload(patient_data):
    patient_id = patient_data.get("patient_id") or patient_data.get("patientId")
    if patient_id:
        patient = PatientProfile.objects.filter(id=patient_id).select_related("user").first()
        if patient:
            return patient

    raw_name = " ".join([
        str(patient_data.get("nom") or ""),
        str(patient_data.get("prenom") or ""),
    ]).strip().lower()
    if not raw_name:
        return None

    for patient in PatientProfile.objects.select_related("user").all():
        full_name = f"{patient.user.nom or ''} {patient.user.prenom or ''}".strip().lower()
        reverse_name = f"{patient.user.prenom or ''} {patient.user.nom or ''}".strip().lower()
        if full_name and (full_name in raw_name or reverse_name in raw_name or raw_name in full_name):
            return patient

    return None


def _priority_from_ai_text(text):
    content = (text or "").lower()
    if any(word in content for word in ["urgent", "critique", "réévaluation", "reevaluation", "alerte majeure"]):
        return "critical"
    if any(word in content for word in ["douleur", "alerte", "surveillance", "ajustement"]):
        return "warning"
    if any(word in content for word in ["bonne progression", "progression positive", "continuer"]):
        return "success"
    return "info"


# ═══════════════════════════════════════════════════════════════════
#  GÉNÉRATION DU PLAN D'INTERVENTION COMPLET
#  → bouton "📋 Générer le plan d'intervention" du formulaire
# ═══════════════════════════════════════════════════════════════════
@login_required
@require_POST
def generate_plan_view(request):
    """
    Reçoit les données JSON du formulaire (anamnèse + bilans),
    appelle Llama via Groq, et retourne le plan d'intervention.

    URL : POST /ergo/ai/generate-plan/
    Body: JSON contenant les champs du formulaire patient.
    """
    try:
        # 1. Parser le JSON envoyé par le frontend
        try:
            patient_data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("JSON invalide")

        # 2. Validation minimale : il faut au moins quelques champs clés
        if not patient_data:
            return JsonResponse(
                {"success": False, "error": "Aucune donnée reçue"},
                status=400,
            )

        # 3. Appel de l'IA
        result = generate_intervention_plan(patient_data)

        # 4. Réponse au frontend
        if result["success"]:
            patient = _patient_from_ai_payload(patient_data)
            analyse = None
            if patient:
                from .models import AnalyseIA
                analyse = AnalyseIA.objects.create(
                    patient=patient,
                    priorite=_priority_from_ai_text(result["plan"]),
                    confiance=90,
                    resume="Plan d’intervention généré par IA",
                    programme_genere=result["plan"],
                    douleur_repos=int(patient_data.get("eva_repos") or 0),
                    douleur_effort=int(patient_data.get("eva_effort") or patient_data.get("eva_mouvement") or 0),
                )
                tracer_action(
                    utilisateur=request.user,
                    patient=patient,
                    type_action='ia',
                    action='Plan intervention IA généré',
                    details={
                        'analyse_id': analyse.id,
                        'motif': 'Génération depuis le dossier patient',
                        'tokens_used': result.get("tokens_used", 0),
                    }
                )
            logger.info(
                "Plan généré avec succès — %s tokens utilisés",
                result.get("tokens_used", 0),
            )
            return JsonResponse(
                {
                    "success": True,
                    "plan": result["plan"],
                    "model": result["model"],
                    "tokens_used": result["tokens_used"],
                    "saved": bool(analyse),
                    "analyse_id": analyse.id if analyse else None,
                    "patient_id": patient.id if patient else None,
                }
            )
        else:
            logger.warning("Échec génération plan : %s", result["error"])
            return JsonResponse(
                {"success": False, "error": result["error"]},
                status=500,
            )

    except Exception as e:
        logger.exception("Erreur inattendue dans generate_plan_view")
        return JsonResponse(
            {"success": False, "error": f"Erreur serveur : {str(e)}"},
            status=500,
        )


# ═══════════════════════════════════════════════════════════════════
#  ANALYSE RAPIDE (bouton "🤖 Analyser avec IA")
# ═══════════════════════════════════════════════════════════════════
@login_required
@require_POST
def analyze_view(request):
    """
    Analyse rapide des données patient (résumé + priorités).

    URL : POST /ergo/ai/analyze/
    """
    try:
        try:
            patient_data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("JSON invalide")

        result = analyze_patient_data(patient_data)

        if result["success"]:
            patient = _patient_from_ai_payload(patient_data)
            analyse = None
            if patient:
                from .models import AnalyseIA
                analysis_text = result["analysis"]
                analyse = AnalyseIA.objects.create(
                    patient=patient,
                    priorite=_priority_from_ai_text(analysis_text),
                    confiance=88,
                    resume=analysis_text,
                    programme_genere="",
                    douleur_repos=int(patient_data.get("eva_repos") or 0),
                    douleur_effort=int(patient_data.get("eva_effort") or patient_data.get("eva_mouvement") or 0),
                )
                tracer_action(
                    utilisateur=request.user,
                    patient=patient,
                    type_action='ia',
                    action='Analyse IA générée',
                    details={
                        'analyse_id': analyse.id,
                        'motif': 'Analyse rapide depuis le dossier patient',
                    }
                )
            return JsonResponse({
                "success": True,
                "analysis": result["analysis"],
                "saved": bool(analyse),
                "analyse_id": analyse.id if analyse else None,
                "patient_id": patient.id if patient else None,
            })
        else:
            return JsonResponse(
                {"success": False, "error": result["error"]},
                status=500,
            )

    except Exception as e:
        logger.exception("Erreur dans analyze_view")
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500,
        )
    
def algeria_localtime(dt):
    """Convertit une datetime en heure locale Algérie."""
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return timezone.localtime(dt, ALGERIA_TZ)
from django.contrib.auth import get_user_model
User = get_user_model()

PRIMARY_ERGO_USERNAME = "Youbi Zineb"   # â† avec l'espace 


def get_default_ergo():
    """
    Retourne l'ergothérapeute principal utilisé pour toute la messagerie.
    """
    ergo = User.objects.filter(username=PRIMARY_ERGO_USERNAME, role='ergo').first()
    if ergo:
        return ergo

    ergo = User.objects.filter(
        role='ergo',
        nom__iexact='Youbi',
        prenom__iexact='Zineb'
    ).first()
    if ergo:
        return ergo

    return User.objects.filter(role='ergo').order_by('id').first()


def get_ergotherapeutes():
    return User.objects.filter(role='ergo')
def index(request):
    return render(request, 'index.html') 

def page_connexion(request):
    return render(request, 'login.html') 

def inscr(request):
    return render(request, 'inscription.html') 

@login_required
def ergotherapeute(request):
    # Récupérer la langue de l'utilisateur
    lang = 'fr'
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        lang = _normaliser_code_langue(request.user.patient_profile.langue)
    elif request.session.get('lang'):
        lang = request.session.get('lang')
    
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())

    # Données réelles
    patients = PatientProfile.objects.select_related('user').all()
    total_patients = patients.count()
    actifs = patients.filter(statut_programme='en_cours').count()
    a_reevaluer = patients.filter(douleur_effort__gte=7).count()

    rdv_aujourdhui = RDV.objects.filter(date_heure__date=today, valide=True, statut='actif').count()
    rdv_semaine = RDV.objects.filter(date_heure__date__gte=week_start, date_heure__date__lte=today, valide=True).count()
    resultats = ResultatExercice.objects.select_related('patient', 'exercice', 'exercice__programme')
    resultats_semaine = resultats.filter(date_realisation__date__gte=week_start)
    total_exercices_prevus = Exercice.objects.filter(programme__patient__isnull=False).count()
    exercices_realises = resultats.values('exercice_id', 'patient_id').distinct().count()

    def percent(value, total):
        return round((value / total) * 100) if total else 0

    progression_moyenne = round(ProgressionPatient.objects.aggregate(avg=Avg('progression_globale'))['avg'] or 0)
    satisfaction_moyenne = resultats.aggregate(avg=Avg('satisfaction'))['avg'] or 0
    satisfaction_pct = round((satisfaction_moyenne / 5) * 100) if satisfaction_moyenne else 0
    jours_actifs = resultats.dates('date_realisation', 'day').count()
    jours_attendus = max(total_patients * 7, 1) if total_patients else 0
    objectifs_renseignes = patients.exclude(objectif_principal='').count()
    objectifs_pct = percent(objectifs_renseignes, total_patients)
    compliance_pct = percent(exercices_realises, total_exercices_prevus)
    presence_pct = percent(jours_actifs, jours_attendus)

    exercices_du_jour = []
    for res in resultats.select_related(
        'patient__user',
        'exercice',
        'exercice__programme',
    ).order_by('-date_realisation')[:3]:
        date_locale = algeria_localtime(res.date_realisation) if res.date_realisation else None
        exercices_du_jour.append({
            'id': res.id,
            'name': res.exercice.nom if res.exercice else 'Exercice',
            'patient': f"{res.patient.user.prenom} {res.patient.user.nom}".strip(),
            'patientId': res.patient.id,
            'programmeId': res.exercice.programme_id if res.exercice and res.exercice.programme_id else '',
            'resultUrl': f"/Programmes/?programme_id={res.exercice.programme_id}&tab=results&resultat_id={res.id}" if res.exercice and res.exercice.programme_id else f"/Programmes/?patient_id={res.patient.id}&tab=results&resultat_id={res.id}",
            'patientUrl': f"/Programmes/?patient_id={res.patient.id}",
            'date': date_locale.strftime('%d/%m/%Y %H:%M') if date_locale else '',
            'series': res.exercice.series if res.exercice else 0,
            'reps': res.exercice.repetitions if res.exercice else 0,
            'minutes': date_locale.strftime('%d/%m %H:%M') if date_locale else '',
            'progress': 100,
            'pain': res.douleur,
            'satisfaction': res.satisfaction,
            'status': res.get_statut_ergo_display() if hasattr(res, 'get_statut_ergo_display') else res.statut_ergo,
        })

    patients_dashboard = [
        {
            'id': p.id,
            'name': f"{p.user.prenom} {p.user.nom}".strip(),
            'url': f"/Programmes/?patient_id={p.id}&tab=results",
            'latestResult': algeria_localtime(p.last_result).strftime('%d/%m/%Y %H:%M') if getattr(p, 'last_result', None) else '-',
        }
        for p in patients.annotate(last_result=Max('resultats_exercices__date_realisation')).order_by('-last_result', 'user__nom')[:30]
    ]

    # Derniers patients (3 derniers)
    derniers_patients = patients.order_by('-user__date_joined')[:3]
    patients_recents = []
    for p in derniers_patients:
        derniere_progression = ProgressionPatient.objects.filter(patient=p).order_by('-date').first()
        dernier_rdv = RDV.objects.filter(patient=p.user, date_heure__lt=timezone.now()).order_by('-date_heure').first()
        prochain_rdv = RDV.objects.filter(patient=p.user, date_heure__gte=timezone.now(), statut='actif', valide=True).order_by('date_heure').first()
        patients_recents.append({
            'initials': f"{(p.user.prenom or 'P')[:1]}{(p.user.nom or '')[:1]}".upper(),
            'name': f"{p.user.prenom} {p.user.nom}".strip(),
            'age': f"{p.age()} ans" if hasattr(p, 'age') else '',
            'fracture': p.get_type_fracture_display() if hasattr(p, 'get_type_fracture_display') else p.type_fracture,
            'progress': derniere_progression.progression_globale if derniere_progression else max(0, 100 - int(p.douleur_effort or 0) * 10),
            'lastRdv': localtime(dernier_rdv.date_heure).strftime('%d/%m/%Y') if dernier_rdv else '-',
            'nextRdv': localtime(prochain_rdv.date_heure).strftime('%d/%m/%Y') if prochain_rdv else '-',
        })

    pending_results = ResultatExercice.objects.filter(statut_ergo='pending').count()
    unread_messages = Message.objects.filter(destinataire=request.user, est_lu_par_destinataire=False).count()
    ia_en_attente = IA_Recommendation.objects.filter(est_valide=False).count()
    questions_recues = ReponseQuestionJour.objects.count()
    notifications_count = pending_results + unread_messages + ia_en_attente + questions_recues

    ia_recommendations = IA_Recommendation.objects.select_related('patient', 'patient__user').order_by('-date_generation')[:5]
    ia_suggestions = [
        f"{ia.patient.user.prenom} {ia.patient.user.nom} : {(ia.programme_genere or '').splitlines()[0][:90]}"
        for ia in ia_recommendations
    ]

    bilans_total = Evaluation.objects.count()
    bilans_termine = Evaluation.objects.filter(consentement=True).count()
    dashboard_data = {
        'notificationsCount': notifications_count,
        'kpis': {
            'patientsActifs': actifs,
            'patientsTrend': PatientProfile.objects.filter(user__date_joined__date__gte=week_start).count(),
            'rdvToday': rdv_aujourdhui,
            'rdvPerHour': rdv_semaine,
            'nouveauxMessages': unread_messages,
        },
        'exercicesDuJour': exercices_du_jour,
        'patientsList': patients_dashboard,
        'patientsRecents': patients_recents,
        'circles': [
            {'label': 'Compliance', 'value': compliance_pct},
            {'label': 'Présence', 'value': presence_pct},
            {'label': 'Progression', 'value': progression_moyenne},
            {'label': 'Satisfaction', 'value': satisfaction_pct},
            {'label': 'Objectifs', 'value': objectifs_pct},
        ],
        'ia': {
            'patientsAnalyses': f"{IA_Recommendation.objects.values('patient_id').distinct().count()}/{total_patients}",
            'pertinence': f"{percent(IA_Recommendation.objects.filter(est_valide=True).count(), max(IA_Recommendation.objects.count(), 1))}%",
            'alertes': a_reevaluer + ia_en_attente + pending_results,
            'suggestions': ia_suggestions,
            'predictions': [
                f"{resultats_semaine.count()} résultat(s) reçu(s) cette semaine.",
                f"{a_reevaluer} patient(s) avec douleur élevée à réévaluer.",
                f"{unread_messages} message(s) non lu(s).",
            ],
            'observance': compliance_pct,
            'observanceTarget': 80,
            'progression': progression_moyenne,
            'progressionTarget': 75,
            'satisfaction': satisfaction_pct,
            'satisfactionTarget': 85,
        },
        'bilans': {
            'total': bilans_total,
            'termines': bilans_termine,
            'enCours': max(bilans_total - bilans_termine, 0),
            'aFaire': total_patients,
        },
    }
    
    context = {
        'total_patients': total_patients,
        'actifs': actifs,
        'a_reevaluer': a_reevaluer,
        'derniers_patients': derniers_patients,
        'dashboard_data': dashboard_data,
        'current_lang': lang,
        'today': date.today(),
    }
    return render(request, 'ergotherapeute.html', context)

def patient(request):
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        return redirect('patient_dashboard')
    lang = 'fr'
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        lang = _normaliser_code_langue(request.user.patient_profile.langue)
    elif request.session.get('lang'):
        lang = _normaliser_code_langue(request.session.get('lang'))
    return render(request, 'patient.html', {'current_lang': lang})


def login_view(request):
    print("message")
    message = ""

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        print("login views ")
        # vérifier si le username existe
        if not User.objects.filter(username=username).exists():
            message = "Nom d'utilisateur incorrect"

        else:
            user = authenticate(request, username=username, password=password)

            if user is None:
                message = "Mot de passe incorrect"
            else:
                login(request, user)

                if user.role == "patient":
                    return redirect("patient_dashboard")
                else:
                    return redirect("ergotherapeute")

    return render(request, "login.html", {"message": message})

def logout_view(request):
    logout(request)
    return redirect("page_connexion")
    

def contact_view(request):
    success_message = ""
    error_message = ""

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        subject = request.POST.get("subject")
        message = request.POST.get("message")

        if name and email and subject and message:
            try:
                Contact.objects.create(
                    nom=name,
                    email=email,
                    sujet=subject,
                    message=message
                )
                success_message = "Votre message a été envoyé avec succès !"
            except Exception as e:
                error_message = "Une erreur est survenue, veuillez réessayer."
        else:
            error_message = "Veuillez remplir tous les champs."

    return render(request, "index.html", {
        "success_message": success_message,
        "error_message": error_message
    })    
from django.utils import timezone

from django.shortcuts import render, redirect
from django.contrib.auth import login




def register_patient(request):

    message = ""

    if request.method == "POST":

        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        password_confirm = request.POST.get("password_confirm") or ""

        nom = request.POST.get("last_name")
        prenom = request.POST.get("first_name")
        email = request.POST.get("email")

        if not username:
            message = "Le nom d'utilisateur doit être défini"
            return render(request, "inscription.html", {"message": message})

        if not password:
            message = "Le mot de passe doit être défini"
            return render(request, "inscription.html", {"message": message})

        if password != password_confirm:
            message = "Les mots de passe ne correspondent pas"
            return render(request, "inscription.html", {"message": message})

        if User.objects.filter(username=username).exists():
            message = "Nom d'utilisateur déjà utilisé"
            return render(request, "inscription.html", {"message": message})

        # Création utilisateur
        user = User.objects.create_user(
            username=username,
            password=password,
            nom=nom,
            prenom=prenom,
            email=email,
            role="patient"
        )

        # Création profil patient
        patient_profile = PatientProfile.objects.create(

            user=user,

            date_naissance=request.POST.get("birth_date"),
            sexe=request.POST.get("gender"),
            telephone=request.POST.get("phone"),
            adresse=request.POST.get("address"),
            nom_affichage=request.POST.get("display_name"),
            langue=request.POST.get("preferred_lang"),

            type_fracture=request.POST.get("fracture_type"),
            date_fracture=request.POST.get("fracture_date"),
            cote_atteint=request.POST.get("side"),
            main_dominante=request.POST.get("dominant_hand") == "on",

            traitement_recu=request.POST.get("treatment"),

            douleur_repos=request.POST.get("pain_rest"),
            douleur_effort=request.POST.get("pain_effort"),
            raideur_gonflement=request.POST.get("swelling"),

            limitations=",".join(request.POST.getlist("limits")),
            autres_problemes_sante=request.POST.get("comorb"),
            medicaments=request.POST.get("meds"),
            allergies=request.POST.get("allergies"),

            profession=request.POST.get("job"),
            impact_travail=request.POST.get("work_impact"),

            activites_anciennes=request.POST.get("activities"),
            autres_activite=request.POST.get("activities_other"),

            objectif_principal=request.POST.get("main_goal"),
            objectif_autre=request.POST.get("main_goal_other"),

            Comment_avez_vous_entendu=request.POST.get("source"),
            Comment_avez_vous_entendu_autre=request.POST.get("source_other"),

            cgu_accepte=request.POST.get("cgu") == "on",
            consentement_sante=request.POST.get("privacy") == "on",
            aide_ia_anonyme=request.POST.get("ai_help") == "on",
            recevoir_rappels=request.POST.get("tips_optin") == "on",
        )

        tracer_action(
            utilisateur=user,
            patient=patient_profile,
            type_action='patient',
            action='Patient créé',
            details={
                'nom': user.nom,
                'prenom': user.prenom,
                'email': user.email
            }
        )
        
        login(request, user)

        return redirect("patients")

    return render(request, "inscription.html", {"message": message})

# 
@login_required
def patients(request):
    patients = PatientProfile.objects.select_related("user").all()

    filtre = request.GET.get('filtre', 'tous')

    if filtre == 'actifs':
        patients = patients.filter(recevoir_rappels=True)

    elif filtre == 'alertes':
        patients = patients.filter(
            Q(douleur_effort__gte=7) |
            Q(raideur_gonflement='important')
        )

    for p in patients:
        p.progression_calc = p.progression()
        p.age_calc = p.age()

    total = PatientProfile.objects.count()
    actifs = PatientProfile.objects.filter(recevoir_rappels=True).count()
    alertes = PatientProfile.objects.filter(
        Q(douleur_effort__gte=7) |
        Q(raideur_gonflement='important')
    ).count()

    total_affiche = patients.count()

    lang = 'fr'
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        lang = _normaliser_code_langue(request.user.patient_profile.langue)
    elif request.session.get('lang'):
        lang = request.session.get('lang')

    context = {
        "patients": patients,
        "total": total,
        "actifs": actifs,
        "alertes": alertes,
        "total_affiche": total_affiche,
        "filtre_actif": filtre,
        "current_lang": lang,
        "today": date.today(),
    }
    return render(request, "patients.html", context)
# Dossiers 

from datetime import date, timedelta
from .models import PatientProfile, Evaluation, DonneesCliniques, BilanMusculaire, BilanArticulaire, BilanDouleur, BilanTrophique, BilanSensitif, BilanPrehension, BilanDexterite, BilanEndurance, ProgrammeExercice, Exercice, ResultatExercice, ProgressionPatient, Message, RDV, Ressource, IA_Recommendation, HistoriqueAction, Recompense, JournalPatient

@login_required
def Dossiers(request):
    tracer_action(
            utilisateur=request.user,
            type_action='dossier',
            action='Liste des dossiers consultée',
            details={}
        )
    """
    Page de gestion des Dossiers - VERSION CORRIGÉE
    """
    from datetime import date, timedelta
    import json
    
    # ==================== 1. DONNÉES POUR LA LISTE DES DOSSIERS ====================
    # Récupérer tous les patients
    patients = PatientProfile.objects.select_related('user').all().order_by('-user__date_joined')
    
    # Préparer les données pour chaque patient
    for p in patients:
        # Âge
        p.age_calc = p.age()
        
        # Progression (basée sur la douleur)
        p.progression_calc = max(0, 100 - (p.douleur_effort * 10))
        
        # Date d'inscription (POUR TOUS LES PATIENTS)
        p.date_inscription = p.user.date_joined
        p.date_inscription_str = p.user.date_joined.strftime('%d/%m/%Y')
        
        # Dernière évaluation et date de réévaluation
        derniere_eval = Evaluation.objects.filter(patient=p).order_by('-date').first()
        if derniere_eval:
            p.derniere_eval_date = derniere_eval.date
            p.derniere_eval_date_str = derniere_eval.date.strftime('%d/%m/%Y')
            p.prochaine_reeval_date = derniere_eval.date + timedelta(days=30)
            p.prochaine_reeval_str = p.prochaine_reeval_date.strftime('%d/%m/%Y')
            
            # CRITÈRE "À RÉÉVALUER" : si la date de réévaluation est aujourd'hui ou dépassée
            p.a_reevaluer = p.prochaine_reeval_date <= date.today()
        else:
            p.derniere_eval_date = None
            p.derniere_eval_date_str = '--'
            p.prochaine_reeval_date = None
            p.prochaine_reeval_str = '--'
            p.a_reevaluer = False
        
        # Côté atteint en texte
        if p.cote_atteint == 'D':
            p.cote_texte = 'Droit'
        elif p.cote_atteint == 'G':
            p.cote_texte = 'Gauche'
        else:
            p.cote_texte = 'Les deux'
        
        # Type de fracture en texte
        types_fracture = {
            'pouteau': 'Pouteau-Colles',
            'scaphoide': 'Scaphoïde',
            'articulaire': 'Articulaire',
            'autre': 'Autre'
        }
        p.type_fracture_texte = types_fracture.get(p.type_fracture, p.type_fracture)
    
    # ===== STATISTIQUES =====
    total_dossiers = patients.count()
    actifs = patients.filter(recevoir_rappels=True).count()
    
    # COMPTER LES PATIENTS À RÉÉVALUER (basé sur le critère défini dans la boucle)
    a_reevaluer = sum(1 for p in patients if p.a_reevaluer)
    
    # ==================== 2. DONNÉES POUR LA VUE DÉTAIL (SI UN PATIENT EST SÉLECTIONNÉ) ====================
    patient_id = request.GET.get('patient_id') or request.POST.get('patient_id')
    patient = None
    evaluations = []
    evaluation_t1 = None
    evaluation_t2 = None
    donnees_cliniques = None
    
    # Bilans
    bilan_musculaire = None
    bilan_articulaire = None
    bilan_douleur = None
    bilan_trophique = None
    bilan_sensitif = None
    bilan_prehension = None
    bilan_dexterite = None
    bilan_endurance = None
    
    if patient_id:
        patient = get_object_or_404(PatientProfile, id=patient_id)

        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='dossier',
            action='Dossier consulté',
            details={
                'patient_id': patient.id
            }
        )

        evaluations = Evaluation.objects.filter(patient=patient).order_by('-date')
        evaluation_t1 = evaluations.filter(type='T1').first()
        evaluation_t2 = evaluations.filter(type='T2').last()

        if evaluation_t1:
            tracer_action(
                utilisateur=request.user,
                patient=patient,
                type_action='dossier',
                action='Évaluation T1 consultée',
                details={'evaluation_id': evaluation_t1.id}
            )

        if evaluation_t2:
            tracer_action(
                utilisateur=request.user,
                patient=patient,
                type_action='dossier',
                action='Évaluation T2 consultée',
                details={'evaluation_id': evaluation_t2.id}
            )

        donnees_cliniques, created = DonneesCliniques.objects.get_or_create(patient=patient)

        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='dossier',
            action='Données cliniques consultées',
            details={}
        )

        derniere_eval = evaluations.first()
        if derniere_eval:
            bilan_musculaire = BilanMusculaire.objects.filter(evaluation=derniere_eval).first()
            bilan_articulaire = BilanArticulaire.objects.filter(evaluation=derniere_eval).first()
            bilan_douleur = BilanDouleur.objects.filter(evaluation=derniere_eval).first()
            bilan_trophique = BilanTrophique.objects.filter(evaluation=derniere_eval).first()
            bilan_sensitif = BilanSensitif.objects.filter(evaluation=derniere_eval).first()
            bilan_prehension = BilanPrehension.objects.filter(evaluation=derniere_eval).first()
            bilan_dexterite = BilanDexterite.objects.filter(evaluation=derniere_eval).first()
            bilan_endurance = BilanEndurance.objects.filter(evaluation=derniere_eval).first()

            tracer_action(
                utilisateur=request.user,
                patient=patient,
                type_action='dossier',
                action='Bilans consultés',
                details={'evaluation_id': derniere_eval.id}
            )
    # ==================== 3. DONNÉES POUR LES GRAPHIQUES MCRO ====================
    mcro_total_perf_t1 = evaluation_t1.mcro_rendement_t1 if evaluation_t1 else 0
    mcro_total_sat_t1 = evaluation_t1.mcro_satisfaction_t1 if evaluation_t1 else 0
    mcro_total_perf_t2 = evaluation_t2.mcro_rendement_t2 if evaluation_t2 else 0
    mcro_total_sat_t2 = evaluation_t2.mcro_satisfaction_t2 if evaluation_t2 else 0
    
    nb_problemes = 5
    mcro_avg_perf_t1 = mcro_total_perf_t1 / nb_problemes if nb_problemes > 0 else 0
    mcro_avg_sat_t1 = mcro_total_sat_t1 / nb_problemes if nb_problemes > 0 else 0
    mcro_avg_perf_t2 = mcro_total_perf_t2 / nb_problemes if nb_problemes > 0 else 0
    mcro_avg_sat_t2 = mcro_total_sat_t2 / nb_problemes if nb_problemes > 0 else 0
    
    mcro_change_perf = mcro_avg_perf_t2 - mcro_avg_perf_t1
    mcro_change_sat = mcro_avg_sat_t2 - mcro_avg_sat_t1
    
    # ==================== 4. DONNÉES POUR PRWE ====================
    prwe_douleur = evaluation_t2.prwe_douleur if evaluation_t2 else (evaluation_t1.prwe_douleur if evaluation_t1 else 0)
    prwe_fonction = evaluation_t2.prwe_fonction if evaluation_t2 else (evaluation_t1.prwe_fonction if evaluation_t1 else 0)
    prwe_total = evaluation_t2.prwe_total if evaluation_t2 else (evaluation_t1.prwe_total if evaluation_t1 else 0)
    
    # ==================== 5. DONNÉES POUR LA SYNTHÈSE ====================
    synthese_observations = evaluation_t2.synthese_observations if evaluation_t2 else (evaluation_t1.synthese_observations if evaluation_t1 else '')
    synthese_impact = evaluation_t2.synthese_impact if evaluation_t2 else (evaluation_t1.synthese_impact if evaluation_t1 else '')
    synthese_objectifs = evaluation_t2.synthese_objectifs if evaluation_t2 else (evaluation_t1.synthese_objectifs if evaluation_t1 else '')
    synthese_recommandations = evaluation_t2.synthese_recommandations if evaluation_t2 else (evaluation_t1.synthese_recommandations if evaluation_t1 else '')
    
    # ==================== 6. DONNÉES POUR LA SIGNATURE ====================
    signature_ergo = evaluation_t2.signature_ergo if evaluation_t2 else (evaluation_t1.signature_ergo if evaluation_t1 else '')
    signature_date = evaluation_t2.signature_date if evaluation_t2 else (evaluation_t1.signature_date if evaluation_t1 else date.today())
    signature_lieu = evaluation_t2.signature_lieu if evaluation_t2 else (evaluation_t1.signature_lieu if evaluation_t1 else '')
    consentement = evaluation_t2.consentement if evaluation_t2 else (evaluation_t1.consentement if evaluation_t1 else False)
    
    # ==================== 7. DONNÉES POUR LA TRACABILITÉ ====================
    evaluations_list = []
    for eval in evaluations:
        evaluations_list.append({
            'id': eval.id,
            'type': eval.type,
            'nom': f"{eval.get_type_display()} #{eval.numero}",
            'date': eval.date.strftime('%d/%m/%Y %H:%M'),
            'mcro_rendement': eval.mcro_rendement_t2 or eval.mcro_rendement_t1,
            'mcro_satisfaction': eval.mcro_satisfaction_t2 or eval.mcro_satisfaction_t1,
            'prwe_total': eval.prwe_total,
        })
    
    # ==================== 8. CONTEXTE COMPLET ====================
    context = {
        # Données liste des patients
        'patients': patients,
        'total_dossiers': total_dossiers,
        'actifs': actifs,
        'a_reevaluer': a_reevaluer,
        'today': date.today(),
        
        # Données du patient sélectionné
        'patient': patient,
        'evaluations': evaluations,
        'evaluation_t1': evaluation_t1,
        'evaluation_t2': evaluation_t2,
        'donnees_cliniques': donnees_cliniques,
        
        # Bilans
        'bilan_musculaire': bilan_musculaire,
        'bilan_articulaire': bilan_articulaire,
        'bilan_douleur': bilan_douleur,
        'bilan_trophique': bilan_trophique,
        'bilan_sensitif': bilan_sensitif,
        'bilan_prehension': bilan_prehension,
        'bilan_dexterite': bilan_dexterite,
        'bilan_endurance': bilan_endurance,
        
        # MCRO
        'mcro_total_perf_t1': mcro_total_perf_t1,
        'mcro_total_sat_t1': mcro_total_sat_t1,
        'mcro_total_perf_t2': mcro_total_perf_t2,
        'mcro_total_sat_t2': mcro_total_sat_t2,
        'mcro_avg_perf_t1': round(mcro_avg_perf_t1, 1),
        'mcro_avg_sat_t1': round(mcro_avg_sat_t1, 1),
        'mcro_avg_perf_t2': round(mcro_avg_perf_t2, 1),
        'mcro_avg_sat_t2': round(mcro_avg_sat_t2, 1),
        'mcro_change_perf': round(mcro_change_perf, 1),
        'mcro_change_sat': round(mcro_change_sat, 1),
        
        # PRWE
        'prwe_douleur': prwe_douleur,
        'prwe_fonction': prwe_fonction,
        'prwe_total': prwe_total,
        
        # Synthèse
        'synthese_observations': synthese_observations,
        'synthese_impact': synthese_impact,
        'synthese_objectifs': synthese_objectifs,
        'synthese_recommandations': synthese_recommandations,
        
        # Signature
        'signature_ergo': signature_ergo,
        'signature_date': signature_date,
        'signature_lieu': signature_lieu,
        'consentement': consentement,
        
        # Traçabilité
        'evaluations_list': json.dumps(evaluations_list, default=str),
        
        # Langue
        'current_lang': _normaliser_code_langue(request.user.patient_profile.langue) if hasattr(request.user, 'patient_profile') else 'fr',
    }

    if request.method == "POST":
        action = request.POST.get("action")
        print("POST DOSSIERS")
        print("ACTION =", action)
        print("POST DATA =", request.POST)
        # ==================== AJOUT ÉVALUATION ====================
        if action == "ajouter_evaluation":
            evaluation = Evaluation.objects.create(
                patient=patient,
                type=request.POST.get("type"),
                date=timezone.now()
            )

            tracer_action(
                utilisateur=request.user,
                type_action='dossier',
                action='Évaluation ajoutée',
                patient=patient,
                details={
                    'evaluation_id': evaluation.id,
                    'type': evaluation.type
                }
            )

        # ==================== MODIFIER ÉVALUATION ====================
        elif action == "modifier_evaluation":
            eval_id = request.POST.get("evaluation_id")
            evaluation = get_object_or_404(Evaluation, id=eval_id)

            ancien_type = evaluation.type
            evaluation.type = request.POST.get("type")
            evaluation.save()

            tracer_action(
                utilisateur=request.user,
                type_action='dossier',
                action='Évaluation modifiée',
                patient=patient,
                details={
                    'evaluation_id': evaluation.id,
                    'ancien_type': ancien_type,
                    'nouveau_type': evaluation.type
                }
            )

        # ==================== SUPPRIMER ÉVALUATION ====================
        elif action == "supprimer_evaluation":
            eval_id = request.POST.get("evaluation_id")
            evaluation = get_object_or_404(Evaluation, id=eval_id)

            tracer_action(
                utilisateur=request.user,
                type_action='dossier',
                action='Évaluation supprimée',
                patient=patient,
                details={
                    'evaluation_id': evaluation.id,
                    'type': evaluation.type
                }
            )

            evaluation.delete()

        # ==================== MODIFIER DONNÉES CLINIQUES ====================
        elif action == "modifier_donnees":
            if donnees_cliniques:
                ancienne_valeur = getattr(donnees_cliniques, "some_field", None)
                donnees_cliniques.some_field = request.POST.get("some_field")
                donnees_cliniques.save()

                tracer_action(
                    utilisateur=request.user,
                    type_action='dossier',
                    action='Données cliniques modifiées',
                    patient=patient,
                    details={
                        'champ': 'some_field',
                        'ancienne_valeur': ancienne_valeur,
                        'nouvelle_valeur': donnees_cliniques.some_field
                    }
                )

        # ==================== MODIFIER SYNTHÈSE ====================
        elif action == "modifier_synthese":
            evaluation_id = request.POST.get("evaluation_id")
            evaluation = get_object_or_404(Evaluation, id=evaluation_id)

            ancienne_obs = evaluation.synthese_observations
            ancien_impact = evaluation.synthese_impact
            anciens_objectifs = evaluation.synthese_objectifs
            anciennes_recommandations = evaluation.synthese_recommandations

            evaluation.synthese_observations = request.POST.get("synthese_observations", evaluation.synthese_observations)
            evaluation.synthese_impact = request.POST.get("synthese_impact", evaluation.synthese_impact)
            evaluation.synthese_objectifs = request.POST.get("synthese_objectifs", evaluation.synthese_objectifs)
            evaluation.synthese_recommandations = request.POST.get("synthese_recommandations", evaluation.synthese_recommandations)
            evaluation.save()

            tracer_action(
                utilisateur=request.user,
                patient=patient,
                type_action='dossier',
                action='Synthèse modifiée',
                details={
                    'evaluation_id': evaluation.id,
                    'ancienne_observation': ancienne_obs,
                    'nouvelle_observation': evaluation.synthese_observations,
                    'ancien_impact': ancien_impact,
                    'nouvel_impact': evaluation.synthese_impact,
                    'anciens_objectifs': anciens_objectifs,
                    'nouveaux_objectifs': evaluation.synthese_objectifs,
                    'anciennes_recommandations': anciennes_recommandations,
                    'nouvelles_recommandations': evaluation.synthese_recommandations,
                }
            )

        # ==================== MODIFIER SIGNATURE ====================
        elif action == "modifier_signature":
            evaluation_id = request.POST.get("evaluation_id")
            evaluation = get_object_or_404(Evaluation, id=evaluation_id)

            ancienne_signature = evaluation.signature_ergo
            ancienne_date = evaluation.signature_date
            ancien_lieu = evaluation.signature_lieu
            ancien_consentement = evaluation.consentement

            evaluation.signature_ergo = request.POST.get("signature_ergo", evaluation.signature_ergo)
            evaluation.signature_date = request.POST.get("signature_date") or evaluation.signature_date
            evaluation.signature_lieu = request.POST.get("signature_lieu", evaluation.signature_lieu)
            evaluation.consentement = request.POST.get("consentement") == "on"
            evaluation.save()

            tracer_action(
                utilisateur=request.user,
                patient=patient,
                type_action='dossier',
                action='Signature modifiée',
                details={
                    'evaluation_id': evaluation.id,
                    'ancienne_signature': ancienne_signature,
                    'nouvelle_signature': evaluation.signature_ergo,
                    'ancienne_date': str(ancienne_date),
                    'nouvelle_date': str(evaluation.signature_date),
                    'ancien_lieu': ancien_lieu,
                    'nouveau_lieu': evaluation.signature_lieu,
                    'ancien_consentement': ancien_consentement,
                    'nouveau_consentement': evaluation.consentement,
                }
            )

        # ==================== MODIFIER SCORES ====================
        elif action == "modifier_scores":
            evaluation_id = request.POST.get("evaluation_id")
            evaluation = get_object_or_404(Evaluation, id=evaluation_id)

            ancien_prwe_douleur = evaluation.prwe_douleur
            ancien_prwe_fonction = evaluation.prwe_fonction
            ancien_prwe_total = evaluation.prwe_total
            ancien_mcro_rendement_t1 = evaluation.mcro_rendement_t1
            ancien_mcro_satisfaction_t1 = evaluation.mcro_satisfaction_t1
            ancien_mcro_rendement_t2 = evaluation.mcro_rendement_t2
            ancien_mcro_satisfaction_t2 = evaluation.mcro_satisfaction_t2

            evaluation.prwe_douleur = request.POST.get("prwe_douleur") or evaluation.prwe_douleur
            evaluation.prwe_fonction = request.POST.get("prwe_fonction") or evaluation.prwe_fonction
            evaluation.prwe_total = request.POST.get("prwe_total") or evaluation.prwe_total
            evaluation.mcro_rendement_t1 = request.POST.get("mcro_rendement_t1") or evaluation.mcro_rendement_t1
            evaluation.mcro_satisfaction_t1 = request.POST.get("mcro_satisfaction_t1") or evaluation.mcro_satisfaction_t1
            evaluation.mcro_rendement_t2 = request.POST.get("mcro_rendement_t2") or evaluation.mcro_rendement_t2
            evaluation.mcro_satisfaction_t2 = request.POST.get("mcro_satisfaction_t2") or evaluation.mcro_satisfaction_t2
            evaluation.save()

            tracer_action(
                utilisateur=request.user,
                patient=patient,
                type_action='dossier',
                action='Scores modifiés',
                details={
                    'evaluation_id': evaluation.id,
                    'ancien_prwe_douleur': ancien_prwe_douleur,
                    'nouveau_prwe_douleur': evaluation.prwe_douleur,
                    'ancien_prwe_fonction': ancien_prwe_fonction,
                    'nouveau_prwe_fonction': evaluation.prwe_fonction,
                    'ancien_prwe_total': ancien_prwe_total,
                    'nouveau_prwe_total': evaluation.prwe_total,
                    'ancien_mcro_rendement_t1': ancien_mcro_rendement_t1,
                    'nouveau_mcro_rendement_t1': evaluation.mcro_rendement_t1,
                    'ancien_mcro_satisfaction_t1': ancien_mcro_satisfaction_t1,
                    'nouveau_mcro_satisfaction_t1': evaluation.mcro_satisfaction_t1,
                    'ancien_mcro_rendement_t2': ancien_mcro_rendement_t2,
                    'nouveau_mcro_rendement_t2': evaluation.mcro_rendement_t2,
                    'ancien_mcro_satisfaction_t2': ancien_mcro_satisfaction_t2,
                    'nouveau_mcro_satisfaction_t2': evaluation.mcro_satisfaction_t2,
                }
            )

        return redirect(f"{request.path}?patient_id={patient.id}" if patient else request.path)

    return render(request, 'Dossiers.html', context)
    
from django.db.models import Avg, Max
@login_required
def Programmes(request):
    programmes = ProgrammeExercice.objects.select_related('patient__user').filter(patient__isnull=False)

    for programme in programmes:
        if programme.patient:
            programme.patient.age_calc = programme.patient.age()

    total = programmes.count()
    actifs = programmes.filter(actif=True).count()

    programme_id = request.GET.get('programme_id')
    patient_id = request.GET.get('patient_id')
    creer_programme = request.GET.get('creer_programme')

    programme_selectionne = None
    patient_selectionne = None
    exercices = []
    resultats = []

    adherence = 0
    assiduite = 0
    implication = 0
    visites = 0
    moyenne_note = 0
    total_seances = 0
    total_seances_prevues = 0
    total_exercices_valides = 0
    progression_deg = 0

    bibliotheque_exercices = BibliothequeExercice.objects.none()
    
    # ===== 1. Si on ouvre un programme directement =====
    if programme_id:
        programme_selectionne = get_object_or_404(
            ProgrammeExercice.objects.select_related('patient__user'),
            id=programme_id
        )

        if programme_selectionne.patient:
            programme_selectionne.patient.age_calc = programme_selectionne.patient.age()
            patient_selectionne = programme_selectionne.patient

            bibliotheque_exercices = BibliothequeExercice.objects.filter(
                patient=patient_selectionne
            ).order_by('nom')
    # ===== 2. Si on a sélectionné un patient =====
    elif patient_id:
        patient_selectionne = get_object_or_404(
            PatientProfile.objects.select_related('user'),
            id=patient_id
        )
        patient_selectionne.age_calc = patient_selectionne.age()

        programme_selectionne = ProgrammeExercice.objects.filter(
            patient=patient_selectionne,
            actif=True
        ).order_by('-date_debut').first()

        bibliotheque_exercices = BibliothequeExercice.objects.filter(
            patient=patient_selectionne
        ).order_by('nom')

        if creer_programme == "1" and programme_selectionne is None:
            programme_selectionne = ProgrammeExercice.objects.create(
                patient=patient_selectionne,
                ergotherapeute=request.user,
                nom=f"Programme - {patient_selectionne.user.nom} {patient_selectionne.user.prenom}",
                actif=True,
                date_debut=date.today(),
                description="Programme créé automatiquement"
            )

            tracer_action(
                utilisateur=request.user,
                patient=patient_selectionne,
                type_action='programme',
                action='Programme créé',
                details={
                    'nom': programme_selectionne.nom
                }
            )

            return redirect(f"{request.path}?programme_id={programme_selectionne.id}")

    # ===== 3. Si un programme est sélectionné =====
    if programme_selectionne:
        tracer_action(
            utilisateur=request.user,
            patient=programme_selectionne.patient,
            type_action='programme',
            action='Programme consulté',
            details={
                'programme': programme_selectionne.nom
            }
        )
        exercices = programme_selectionne.exercices.all().order_by('-id')
        resultats = ResultatExercice.objects.filter(
            patient=programme_selectionne.patient
        ).select_related('exercice', 'exercice__programme').order_by('-date_realisation')

        total_resultats = resultats.count()
        total_exercices = exercices.count()
        total_seances_prevues = total_exercices 

        moyenne_note = resultats.aggregate(m=Avg('satisfaction'))['m'] or 0
        total_seances = total_resultats
        total_exercices_valides = resultats.filter(valide_par_ergo=True).count()
        visites = HistoriqueAction.objects.filter(
            patient=programme_selectionne.patient,
            utilisateur=programme_selectionne.patient.user,
            type_action__in=['programme', 'message', 'ressource', 'dossier', 'ia', 'patient', 'visite', 'seance']
        ).count()
        if visites == 0:
            visites = total_resultats

        if total_exercices > 0:
            implication = round((total_exercices_valides / total_exercices) * 100)

        adherence = round((total_resultats / 20) * 100) if total_resultats else 0
        assiduite = total_resultats

        progression_deg = resultats.aggregate(
            max_amp=Max('amplitude_atteinte')
        )['max_amp'] or 0

    tous_les_resultats = ResultatExercice.objects.none()
    questions_patient = QuestionJour.objects.none()
    reponses_questions_patient = ReponseQuestionJour.objects.none()
    evaluations_patient = ProgressionPatient.objects.none()
    if patient_selectionne:
        tous_les_resultats = ResultatExercice.objects.filter(
            patient=patient_selectionne
        )
        tous_les_resultats = tous_les_resultats.select_related('exercice', 'exercice__programme').order_by('-date_realisation')
        questions_patient = QuestionJour.objects.filter(
            Q(patient=patient_selectionne) | Q(patient__isnull=True),
            active=True,
        ).select_related('cree_par').order_by('-date_creation')[:20]
        reponses_questions_patient = ReponseQuestionJour.objects.filter(
            patient=patient_selectionne
        ).select_related('question').order_by('-date_reponse')[:20]
        evaluations_patient = ProgressionPatient.objects.filter(
            patient=patient_selectionne
        ).order_by('-date')[:20]

    # ===== 4. Actions POST =====
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # ===== VALIDER UN EXERCICE =====
        if action == 'valider_exercice':
            resultat_id = request.POST.get('resultat_id')
            commentaire = (request.POST.get('commentaire_ergo') or '').strip()
        
            if resultat_id:
                resultat = get_object_or_404(ResultatExercice, id=resultat_id)
                resultat.valide_par_ergo = True
                resultat.statut_ergo = 'validated'
                resultat.commentaire_ergo = commentaire
                resultat.save()

                tracer_action(
                    utilisateur=request.user,
                    patient=resultat.patient,
                    type_action='programme',
                    action='Resultat valide par therapeute',
                    details={
                        'exercice': resultat.exercice.nom,
                        'commentaire': commentaire,
                    }
                )
                
                verifier_et_debloquer_defis(resultat.patient, resultat)
                
                messages.success(request, "Exercice validé avec succès !")
            
            return redirect(f"{request.path}?programme_id={programme_selectionne.id}")

        # ===== AJOUTER À LA BIBLIOTHÈQUE =====
        elif action == 'ajouter_bibliotheque':
            patient_id_post = request.POST.get('patient_id')
            if patient_id_post:
                patient_cible = get_object_or_404(PatientProfile, id=patient_id_post)

                nouvel_exercice = BibliothequeExercice.objects.create(
                    patient=patient_cible,
                    nom=request.POST.get('nom'),
                    categorie=request.POST.get('categorie') or '',
                    series=int(request.POST.get('series') or 1),
                    repetitions=int(request.POST.get('repetitions') or 1),
                    temps_exercice=request.POST.get('temps_exercice') or '',
                    repos=request.POST.get('repos') or '45s',
                    objectif=request.POST.get('objectif') or '',
                    instructions=request.POST.get('instructions') or '',
                    materiel_necessaire=request.POST.get('materiel_necessaire') or '',
                    ordre=int(request.POST.get('ordre') or 1),
                    created_by=request.user
                )

                tracer_action(
                    utilisateur=request.user,
                    patient=patient_cible,
                    type_action='programme',
                    action='Exercice ajouté à la bibliothèque',
                    details={
                        'exercice': nouvel_exercice.nom,
                        'categorie': nouvel_exercice.categorie
                    }
                )

                fichiers = request.FILES.getlist('media_demo')
                for fichier in fichiers:
                    if fichier:
                        BibliothequeExerciceMedia.objects.create(
                            exercice=nouvel_exercice,
                            fichier=fichier
                        )

                # ✅ VÉRIFIER SI C'EST UNE REQUÊTE AJAX
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'exercice_id': nouvel_exercice.id,
                        'exercice_nom': nouvel_exercice.nom
                    })
                else:
                    return redirect(f"{request.path}?patient_id={patient_cible.id}&tab=exercises")
            
            return redirect(request.path)

        # ===== AJOUTER UN DÉFI =====
        elif action == 'ajouter_defi':
            from .models import Defi
            nom_defi = (request.POST.get('defi_nom') or '').strip()
            description_defi = (request.POST.get('defi_description') or '').strip()
            points_defi = int(request.POST.get('defi_points') or 10)
            niveau_requis = request.POST.get('defi_niveau_requis') or 'bronze'
            ordre_defi = int(request.POST.get('defi_ordre') or 0)

            if nom_defi:
                defi = Defi.objects.create(
                    nom=nom_defi,
                    description=description_defi,
                    points=points_defi,
                    niveau_requis=niveau_requis,
                    ordre=ordre_defi
                )

                tracer_action(
                    utilisateur=request.user,
                    patient=programme_selectionne.patient if programme_selectionne else None,
                    type_action='programme',
                    action='Défi créé',
                    details={
                        'defi': defi.nom,
                        'points': defi.points,
                        'niveau': defi.get_niveau_requis_display()
                    }
                )

                patient_id_post = request.POST.get('patient_id')
                programme_id_post = request.POST.get('programme_id')
                patient_cible = None
                programme_cible = None

                if programme_id_post:
                    programme_cible = ProgrammeExercice.objects.filter(id=programme_id_post).first()
                    if programme_cible:
                        patient_cible = programme_cible.patient

                if not patient_cible and patient_id_post:
                    patient_cible = get_object_or_404(PatientProfile, id=patient_id_post)

                if patient_cible:
                    if not programme_cible:
                        programme_cible = ProgrammeExercice.objects.filter(patient=patient_cible, actif=True).first()

                    if not programme_cible:
                        programme_cible = ProgrammeExercice.objects.create(
                            patient=patient_cible,
                            ergotherapeute=request.user,
                            nom=f"Programme - {patient_cible.user.nom} {patient_cible.user.prenom}",
                            actif=True,
                            date_debut=date.today(),
                            description="Programme créé automatiquement"
                        )
                        tracer_action(
                            utilisateur=request.user,
                            patient=patient_cible,
                            type_action='programme',
                            action='Programme créé',
                            details={
                                'nom': programme_cible.nom
                            }
                        )

                    nouvel_exercice = Exercice.objects.create(
                        programme=programme_cible,
                        nom=f"[Défi] {defi.nom}",
                        categorie='Défi',
                        series=1,
                        repetitions=1,
                        temps_exercice='',
                        repos='',
                        objectif=defi.description,
                        instructions=f"Défi de niveau {defi.get_niveau_requis_display()} - {defi.points} pts.",
                        materiel_necessaire='',
                        ordre=programme_cible.exercices.count() + 1
                    )

                    tracer_action(
                        utilisateur=request.user,
                        patient=patient_cible,
                        type_action='programme',
                        action='Défi ajouté au programme',
                        details={
                            'defi': defi.nom,
                            'programme': programme_cible.nom
                        }
                    )

                    programme_actualise = programme_cible.exercices.all().order_by('-id')
                    _sauvegarder_programme_envoye(
                        patient_cible,
                        _construire_programme_patient(programme_actualise, mode='programme_complet')
                    )

                    from .models import DefiPatient
                    DefiPatient.objects.get_or_create(
                        patient=patient_cible,
                        defi=defi,
                        defaults={'points_gagnes': 0, 'statut': 'assigned'}
                    )

            programme_id_post = request.POST.get('programme_id')
            if programme_id_post:
                return redirect(f"{request.path}?programme_id={programme_id_post}&tab=exercises")
            if request.POST.get('patient_id'):
                return redirect(f"{request.path}?patient_id={request.POST.get('patient_id')}&tab=exercises")
            return redirect(request.path)

        elif action == 'ajouter_defi_au_programme':
            from .models import Defi
            defi_id = request.POST.get('defi_id')
            patient_id_post = request.POST.get('patient_id')
            programme_id_post = request.POST.get('programme_id')

            if defi_id and patient_id_post:
                patient_cible = get_object_or_404(PatientProfile, id=patient_id_post)
                defi = get_object_or_404(Defi, id=defi_id)

                programme_cible = ProgrammeExercice.objects.filter(id=programme_id_post).first() if programme_id_post else None
                if not programme_cible:
                    programme_cible = ProgrammeExercice.objects.filter(patient=patient_cible, actif=True).first()

                if not programme_cible:
                    programme_cible = ProgrammeExercice.objects.create(
                        patient=patient_cible,
                        ergotherapeute=request.user,
                        nom=f"Programme - {patient_cible.user.nom} {patient_cible.user.prenom}",
                        actif=True,
                        date_debut=date.today(),
                        description="Programme créé automatiquement"
                    )
                    tracer_action(
                        utilisateur=request.user,
                        patient=patient_cible,
                        type_action='programme',
                        action='Programme créé',
                        details={
                            'nom': programme_cible.nom
                        }
                    )

                nouvel_exercice = Exercice.objects.create(
                    programme=programme_cible,
                    nom=f"[Défi] {defi.nom}",
                    categorie='Défi',
                    series=1,
                    repetitions=1,
                    temps_exercice='',
                    repos='',
                    objectif=defi.description,
                    instructions=f"Défi de niveau {defi.get_niveau_requis_display()} - {defi.points} pts.",
                    materiel_necessaire='',
                    ordre=programme_cible.exercices.count() + 1
                )

                tracer_action(
                    utilisateur=request.user,
                    patient=patient_cible,
                    type_action='programme',
                    action='Défi ajouté au programme',
                    details={
                        'defi': defi.nom,
                        'programme': programme_cible.nom
                    }
                )

                programme_actualise = programme_cible.exercices.all().order_by('-id')
                _sauvegarder_programme_envoye(
                    patient_cible,
                    _construire_programme_patient(programme_actualise, mode='programme_complet')
                )

                from .models import DefiPatient
                DefiPatient.objects.get_or_create(
                    patient=patient_cible,
                    defi=defi,
                    defaults={'points_gagnes': 0, 'statut': 'assigned'}
                )

            if programme_id_post:
                return redirect(f"{request.path}?programme_id={programme_id_post}&tab=exercises")
            if patient_id_post:
                return redirect(f"{request.path}?patient_id={patient_id_post}&tab=exercises")
            return redirect(request.path)

        # ===== SUPPRIMER DE LA BIBLIOTHÈQUE =====
        elif action == 'supprimer_bibliotheque':
            bibliotheque_id = request.POST.get('bibliotheque_id')
            patient_id_post = request.POST.get('patient_id')

            exercice_bib = get_object_or_404(BibliothequeExercice, id=bibliotheque_id)
            patient_cible = exercice_bib.patient
            nom_exercice = exercice_bib.nom

            tracer_action(
                utilisateur=request.user,
                patient=patient_cible,
                type_action='programme',
                action='Exercice supprimé de la bibliothèque',
                details={
                    'exercice': nom_exercice
                }
            )
            exercice_bib.delete()

            if patient_id_post:
                return redirect(f"{request.path}?patient_id={patient_id_post}&tab=exercises")
            return redirect(request.path)

        # ===== AJOUTER AU PROGRAMME =====
        elif action == 'ajouter_au_programme':
            bibliotheque_id = request.POST.get('bibliotheque_id')
            patient_id_post = request.POST.get('patient_id')
            programme_id_post = request.POST.get('programme_id')

            if not patient_id_post or not bibliotheque_id:
                return redirect(request.path)

            patient_cible = get_object_or_404(PatientProfile, id=patient_id_post)
            exercice_source = get_object_or_404(BibliothequeExercice, id=bibliotheque_id)

            if programme_id_post:
                programme_cible = get_object_or_404(ProgrammeExercice, id=programme_id_post)
            else:
                programme_cible = ProgrammeExercice.objects.filter(
                    patient=patient_cible,
                    actif=True
                ).first()

                if not programme_cible:
                    programme_cible = ProgrammeExercice.objects.create(
                        patient=patient_cible,
                        ergotherapeute=request.user,
                        nom=f"Programme - {patient_cible.user.nom} {patient_cible.user.prenom}",
                        actif=True,
                        date_debut=date.today(),
                        description="Programme créé automatiquement"
                    )

                    tracer_action(
                        utilisateur=request.user,
                        patient=patient_cible,
                        type_action='programme',
                        action='Programme créé',
                        details={
                            'nom': programme_cible.nom
                        }
                    )

            nouvel_exercice = Exercice.objects.create(
                programme=programme_cible,
                bibliotheque_exercice=exercice_source,
                nom=exercice_source.nom,
                categorie=exercice_source.categorie,
                series=exercice_source.series,
                repetitions=exercice_source.repetitions,
                temps_exercice=exercice_source.temps_exercice,
                repos=exercice_source.repos,  # â† AJOUTER
                objectif=exercice_source.objectif,
                instructions=exercice_source.instructions,
                materiel_necessaire=exercice_source.materiel_necessaire,
                ordre=programme_cible.exercices.count() + 1
            )

            tracer_action(
                utilisateur=request.user,
                patient=patient_cible,
                type_action='programme',
                action='Exercice ajouté au programme',
                details={
                    'exercice': nouvel_exercice.nom,
                    'programme': programme_cible.nom
                }
            )

            for media in exercice_source.medias.all():
                nouveau_media = ExerciceMedia.objects.create(
                    exercice=nouvel_exercice,
                    fichier=media.fichier
                )
                nouvel_exercice.medias.add(nouveau_media)

            programme_actualise = programme_cible.exercices.all().order_by('-id')
            _sauvegarder_programme_envoye(
                patient_cible,
                _construire_programme_patient(programme_actualise, mode='programme_complet')
            )

            return redirect(f"{request.path}?programme_id={programme_cible.id}")

        elif action == 'ajouter_selection_programme':
            patient_id_post = request.POST.get('patient_id')
            programme_id_post = request.POST.get('programme_id')
            bibliotheque_ids = request.POST.getlist('bibliotheque_ids')

            if not patient_id_post or not bibliotheque_ids:
                messages.warning(request, "Sélectionnez au moins un exercice.")
                return redirect(request.path)

            patient_cible = get_object_or_404(PatientProfile, id=patient_id_post)

            if programme_id_post:
                programme_cible = get_object_or_404(ProgrammeExercice, id=programme_id_post)
            else:
                programme_cible = ProgrammeExercice.objects.filter(
                    patient=patient_cible,
                    actif=True
                ).first()

                if not programme_cible:
                    programme_cible = ProgrammeExercice.objects.create(
                        patient=patient_cible,
                        ergotherapeute=request.user,
                        nom=f"Programme - {patient_cible.user.nom} {patient_cible.user.prenom}",
                        actif=True,
                        date_debut=date.today(),
                        description="Programme créé automatiquement"
                    )

                    tracer_action(
                        utilisateur=request.user,
                        patient=patient_cible,
                        type_action='programme',
                        action='Programme créé',
                        details={'nom': programme_cible.nom}
                    )

            exercices_sources = list(
                BibliothequeExercice.objects.filter(
                    id__in=bibliotheque_ids,
                    patient=patient_cible
                ).prefetch_related('medias')
            )

            ordre_depart = programme_cible.exercices.count()
            ajoutes = []

            for index, exercice_source in enumerate(exercices_sources, start=1):
                nouvel_exercice = Exercice.objects.create(
                    programme=programme_cible,
                    bibliotheque_exercice=exercice_source,
                    nom=exercice_source.nom,
                    categorie=exercice_source.categorie,
                    series=exercice_source.series,
                    repetitions=exercice_source.repetitions,
                    temps_exercice=exercice_source.temps_exercice,
                    repos=exercice_source.repos,
                    objectif=exercice_source.objectif,
                    instructions=exercice_source.instructions,
                    materiel_necessaire=exercice_source.materiel_necessaire,
                    ordre=ordre_depart + index
                )

                for media in exercice_source.medias.all():
                    ExerciceMedia.objects.create(
                        exercice=nouvel_exercice,
                        fichier=media.fichier
                    )

                ajoutes.append(nouvel_exercice.nom)

            if ajoutes:
                tracer_action(
                    utilisateur=request.user,
                    patient=patient_cible,
                    type_action='programme',
                    action='Exercices ajoutés au programme',
                    details={
                        'programme': programme_cible.nom,
                        'nombre': len(ajoutes),
                        'exercices': ", ".join(ajoutes),
                    }
                )

                programme_actualise = programme_cible.exercices.all().order_by('-id')
                _sauvegarder_programme_envoye(
                    patient_cible,
                    _construire_programme_patient(programme_actualise, mode='programme_complet')
                )
                messages.success(request, f"{len(ajoutes)} exercice(s) ajouté(s) au programme.")

            return redirect(f"{request.path}?programme_id={programme_cible.id}")

        # ===== SUPPRIMER EXERCICE DU PROGRAMME =====
        elif action == 'supprimer_exercice_programme':
            exercice_id = request.POST.get('exercice_id')
            programme_id_post = request.POST.get('programme_id')

            if exercice_id:
                exercice_prog = get_object_or_404(Exercice, id=exercice_id)
                programme_cible = exercice_prog.programme
                patient_cible = programme_cible.patient
                nom_exercice = exercice_prog.nom
                nom_programme = programme_cible.nom

                tracer_action(
                    utilisateur=request.user,
                    patient=patient_cible,
                    type_action='programme',
                    action='Exercice supprimé du programme',
                    details={
                        'exercice': nom_exercice,
                        'programme': nom_programme
                    }
                )

                exercice_prog.delete()

                programme_actualise = programme_cible.exercices.all().order_by('-id')
                _sauvegarder_programme_envoye(
                    patient_cible,
                    _construire_programme_patient(programme_actualise, mode='programme_complet')
                )

            if programme_id_post:
                return redirect(f"{request.path}?programme_id={programme_id_post}")
            return redirect(request.path)

        # Si aucune action ne correspond, rediriger
        return redirect(request.path)

    # ===== CALCULS AVANCÉS POUR INDICATEURS =====
    if programme_selectionne and programme_selectionne.patient:
        patient = programme_selectionne.patient
        
        # Récupérer tous les exercices du programme et leurs résultats
        exercices_programme = Exercice.objects.filter(programme=programme_selectionne)
        total_exercices_programme = exercices_programme.count()
        
        # Les indicateurs restent cumulatifs patient : un nouveau programme ne
        # doit pas remettre les compteurs, la douleur ou la satisfaction a zero.
        resultats_patient = ResultatExercice.objects.filter(patient=patient)
        
        # ===== CALCUL DE L'ÉVOLUTION DE LA DOULEUR =====
        today = date.today()
        
        # Semaine 1 (il y a 4 semaines)
        semaine1_debut = today - timedelta(days=28)
        semaine1_fin = today - timedelta(days=21)
        # Semaine 2 (il y a 3 semaines)
        semaine2_debut = today - timedelta(days=21)
        semaine2_fin = today - timedelta(days=14)
        # Semaine 3 (il y a 2 semaines)
        semaine3_debut = today - timedelta(days=14)
        semaine3_fin = today - timedelta(days=7)
        # Semaine 4 (la semaine dernière)
        semaine4_debut = today - timedelta(days=7)
        semaine4_fin = today
        
        # Calculer la douleur moyenne par semaine
        resultats_par_semaine = {
            'semaine1': {'douleur_repos': 0, 'douleur_effort': 0, 'count': 0},
            'semaine2': {'douleur_repos': 0, 'douleur_effort': 0, 'count': 0},
            'semaine3': {'douleur_repos': 0, 'douleur_effort': 0, 'count': 0},
            'semaine4': {'douleur_repos': 0, 'douleur_effort': 0, 'count': 0},
        }
        
        for resultat in resultats_patient:
            if resultat.date_realisation:
                date_resultat = resultat.date_realisation.date()
                douleur_repos = float(getattr(resultat, 'douleur_repos', getattr(resultat, 'douleur', 0)) or 0)
                douleur_effort = float(getattr(resultat, 'douleur_effort', getattr(resultat, 'douleur', 0)) or 0)
                
                if semaine1_debut <= date_resultat < semaine1_fin:
                    resultats_par_semaine['semaine1']['douleur_repos'] += douleur_repos
                    resultats_par_semaine['semaine1']['douleur_effort'] += douleur_effort
                    resultats_par_semaine['semaine1']['count'] += 1
                elif semaine2_debut <= date_resultat < semaine2_fin:
                    resultats_par_semaine['semaine2']['douleur_repos'] += douleur_repos
                    resultats_par_semaine['semaine2']['douleur_effort'] += douleur_effort
                    resultats_par_semaine['semaine2']['count'] += 1
                elif semaine3_debut <= date_resultat < semaine3_fin:
                    resultats_par_semaine['semaine3']['douleur_repos'] += douleur_repos
                    resultats_par_semaine['semaine3']['douleur_effort'] += douleur_effort
                    resultats_par_semaine['semaine3']['count'] += 1
                elif semaine4_debut <= date_resultat <= semaine4_fin:
                    resultats_par_semaine['semaine4']['douleur_repos'] += douleur_repos
                    resultats_par_semaine['semaine4']['douleur_effort'] += douleur_effort
                    resultats_par_semaine['semaine4']['count'] += 1
        
        # Calculer les moyennes
        douleur_repos_s1 = round(resultats_par_semaine['semaine1']['douleur_repos'] / resultats_par_semaine['semaine1']['count'], 1) if resultats_par_semaine['semaine1']['count'] > 0 else 0
        douleur_effort_s1 = round(resultats_par_semaine['semaine1']['douleur_effort'] / resultats_par_semaine['semaine1']['count'], 1) if resultats_par_semaine['semaine1']['count'] > 0 else 0
        
        douleur_repos_s2 = round(resultats_par_semaine['semaine2']['douleur_repos'] / resultats_par_semaine['semaine2']['count'], 1) if resultats_par_semaine['semaine2']['count'] > 0 else 0
        douleur_effort_s2 = round(resultats_par_semaine['semaine2']['douleur_effort'] / resultats_par_semaine['semaine2']['count'], 1) if resultats_par_semaine['semaine2']['count'] > 0 else 0
        
        douleur_repos_s3 = round(resultats_par_semaine['semaine3']['douleur_repos'] / resultats_par_semaine['semaine3']['count'], 1) if resultats_par_semaine['semaine3']['count'] > 0 else 0
        douleur_effort_s3 = round(resultats_par_semaine['semaine3']['douleur_effort'] / resultats_par_semaine['semaine3']['count'], 1) if resultats_par_semaine['semaine3']['count'] > 0 else 0
        
        douleur_repos_s4 = round(resultats_par_semaine['semaine4']['douleur_repos'] / resultats_par_semaine['semaine4']['count'], 1) if resultats_par_semaine['semaine4']['count'] > 0 else 0
        douleur_effort_s4 = round(resultats_par_semaine['semaine4']['douleur_effort'] / resultats_par_semaine['semaine4']['count'], 1) if resultats_par_semaine['semaine4']['count'] > 0 else 0
        
        stats_patient = calculer_indicateurs_programmes_patient(patient)
        adherence = stats_patient['adherence']
        assiduite = stats_patient['assiduite']
        implication = stats_patient['implication']
        visites = stats_patient['visites']
        total_seances = stats_patient['total_seances']
        total_seances_prevues = stats_patient['total_seances_prevues']
        moyenne_note = stats_patient['moyenne_note']
        total_exercices_valides = stats_patient['total_exercices_valides']
        total_exercices_reference = stats_patient['total_exercices_reference']
        
        # Progression par défis
        progression_data = calculer_progression_defis(patient)
        progression_deg = progression_data['pourcentage']
        progression_niveau = progression_data['niveau_texte']
        progression_points = progression_data['points']
        progression_defis = progression_data['defis_completes']
        progression_total_defis = progression_data['total_defis']
        progression_points_restants = progression_data['points_restants']
        progression_prochain_niveau = progression_data['prochain_niveau']  
        progression_pourcentage = progression_data['pourcentage']      

        from .models import Defi

        exercices_avec_amplitude = []
    else:
        exercices_avec_amplitude = []
        total_exercices_reference = 0
        evolution_satisfaction = 0
        douleur_labels = []
        douleur_repos_data = []
        douleur_effort_data = []

    evolution_adherence = round(adherence - (adherence * 0.8), 1) if adherence > 0 else 0
    evolution_assiduite = 0
    evolution_implication = round(implication - (implication * 0.85), 1) if implication > 0 else 0
    evolution_visites = round(visites - (visites * 0.8), 1) if visites > 0 else 0
    
    evolution_journaliere = calculer_evolution_journaliere(
        programme_selectionne.patient
    ) if programme_selectionne and programme_selectionne.patient else calculer_evolution_journaliere(None)
    satisfaction_labels = evolution_journaliere['labels']
    satisfaction_data = evolution_journaliere['satisfaction_data']
    douleur_labels = evolution_journaliere['labels']
    douleur_data = evolution_journaliere['douleur_data']
    evolution_satisfaction = evolution_journaliere['evolution_satisfaction']

    context = {
        'programmes': programmes,
        'patients_programmes': PatientProfile.objects.select_related('user').all().order_by('user__nom', 'user__prenom'),
        'total': total,
        'actifs': actifs,
        'programme_selectionne': programme_selectionne,
        'patient_selectionne': patient_selectionne,
        'exercices': exercices,
        'tous_les_resultats': tous_les_resultats,
        'questions_patient': questions_patient,
        'reponses_questions_patient': reponses_questions_patient,
        'evaluations_patient': evaluations_patient,
        'bibliotheque_exercices': bibliotheque_exercices,
        'resultats': resultats[:20] if 'resultats' in locals() else [],
        'adherence': adherence,
        'assiduite': assiduite,
        'implication': implication,
        'visites': visites,
        'moyenne_note': round(moyenne_note, 1),
        'total_seances': total_seances,
        'total_exercices_valides': total_exercices_valides,
        'total_exercices_reference': total_exercices_reference if 'total_exercices_reference' in locals() else 0,
        'progression_deg': progression_deg,
        'evolution_satisfaction': evolution_satisfaction,
        'exercices_amplitude': exercices_avec_amplitude,
        'today': date.today(),
        'satisfaction_labels': satisfaction_labels,
        'satisfaction_data': satisfaction_data,
        'douleur_labels': douleur_labels,
        'douleur_data': douleur_data,
        'evolution_adherence': evolution_adherence,
        'evolution_assiduite': evolution_assiduite,
        'evolution_implication': evolution_implication,
        'evolution_visites': evolution_visites,
        'satisfaction_labels': satisfaction_labels,
        'satisfaction_data': satisfaction_data,
        'total_seances_prevues': total_seances_prevues if 'total_seances_prevues' in locals() else 0,
        'progression_niveau': progression_niveau if 'progression_niveau' in locals() else 'Bronze',
        'progression_points': progression_points if 'progression_points' in locals() else 0,
        'progression_defis': progression_defis if 'progression_defis' in locals() else 0,
        'progression_total_defis': progression_total_defis if 'progression_total_defis' in locals() else 0,
        'progression_points_restants': progression_points_restants if 'progression_points_restants' in locals() else 10,
        'progression_prochain_niveau': progression_prochain_niveau if 'progression_prochain_niveau' in locals() else 'Argent',
        'progression_pourcentage': progression_pourcentage if 'progression_pourcentage' in locals() else 0,
        'progression_niveau_badge': progression_data['niveau_badge'] if 'progression_data' in locals() else '🥉 Bronze',
        'progression_prochain_niveau_badge': progression_data['prochain_niveau_badge'] if 'progression_data' in locals() else '🥈 Argent',
    }
    
    return render(request, 'Programmes.html', context)
@login_required
def ajouter_exercice_bibliotheque_ajax(request):
    """Version AJAX pour ajouter un exercice sans recharger la page"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            patient_id = request.POST.get('patient_id')
            if not patient_id:
                return JsonResponse({'success': False, 'error': 'Patient non spécifié'})
            
            patient_cible = get_object_or_404(PatientProfile, id=patient_id)
            
            nouvel_exercice = BibliothequeExercice.objects.create(
                patient=patient_cible,
                nom=request.POST.get('nom'),
                categorie=request.POST.get('categorie') or '',
                series=int(request.POST.get('series') or 1),
                repetitions=int(request.POST.get('repetitions') or 1),
                temps_exercice=request.POST.get('temps_exercice') or '',
                objectif=request.POST.get('objectif') or '',
                instructions=request.POST.get('instructions') or '',
                materiel_necessaire=request.POST.get('materiel_necessaire') or '',
                ordre=int(request.POST.get('ordre') or 1),
                created_by=request.user
            )
            
            fichiers = request.FILES.getlist('media_demo')
            for fichier in fichiers:
                if fichier:
                    BibliothequeExerciceMedia.objects.create(
                        exercice=nouvel_exercice,
                        fichier=fichier
                    )
            
            tracer_action(
                utilisateur=request.user,
                patient=patient_cible,
                type_action='programme',
                action='Exercice ajouté à la bibliothèque',
                details={'exercice': nouvel_exercice.nom}
            )
            
            return JsonResponse({
                'success': True,
                'exercice_id': nouvel_exercice.id,
                'exercice_nom': nouvel_exercice.nom
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Q
from .models import AnalyseIA, HistoriqueAnalyseIA
from Dashboard.models import PatientProfile

@login_required
def page_ia(request):
    # Récupérer l'ID de recommandation si présent dans l'URL
    reco_id = request.GET.get('reco_id')
    reco_detail = None
    
    # ===== STATISTIQUES =====
    # 1. Total des analyses
    total_analyses = AnalyseIA.objects.count()
    
    # 2. Alertes actives (priorité critical ou warning non validées)
    alertes_actives = AnalyseIA.objects.filter(
        Q(priorite='critical') | Q(priorite='warning'),
        est_valide=False
    ).count()
    
    # 3. Précision moyenne (moyenne des confiances)
    precision_moyenne = AnalyseIA.objects.filter(
        confiance__isnull=False
    ).aggregate(Avg('confiance'))['confiance__avg'] or 0
    precision_moyenne = round(precision_moyenne)
    
    # 4. Analyses validées
    analyses_validees = AnalyseIA.objects.filter(est_valide=True).count()
    
    # ===== LISTE DES RECOMMANDATIONS =====
    recommandations = AnalyseIA.objects.select_related('patient__user').all()
    
    # ===== DÉTAIL D'UNE ANALYSE SPÉCIFIQUE =====
    if reco_id:
        reco_detail = get_object_or_404(AnalyseIA, id=reco_id)
        tracer_action(
            utilisateur=request.user,
            patient=reco_detail.patient,
            type_action='ia',
            action='Analyse IA consultée',
            details={
                'analyse_id': reco_detail.id,
                'priorite': reco_detail.priorite
            }
        )
        # Récupérer l'historique pour cette analyse
        historique_ia = HistoriqueAnalyseIA.objects.filter(analyse=reco_detail)
    else:
        historique_ia = []
    
    context = {
        'total_analyses': total_analyses,
        'alertes_actives': alertes_actives,
        'precision_moyenne': precision_moyenne,
        'analyses_validees': analyses_validees,
        'recommandations': recommandations,
        'reco_detail': reco_detail,
        'historique_ia': historique_ia,
    }
    
    return render(request, 'IA.html', context)

@login_required
def generer_analyse_ia(request, patient_id):
    from django.utils import timezone
    import random

    patient = get_object_or_404(PatientProfile, id=patient_id)

    douleur_effort = patient.douleur_effort if hasattr(patient, 'douleur_effort') else random.randint(2, 8)

    if douleur_effort >= 7:
        priorite = 'critical'
        resume = "Douleur importante détectée à l'effort. Une réévaluation est nécessaire."
    elif douleur_effort >= 4:
        priorite = 'warning'
        resume = "Douleur modérée à l'effort. Ajustement du programme recommandé."
    else:
        priorite = 'success'
        resume = "Bonne progression. Continuer le programme actuel."

    analyse = AnalyseIA.objects.create(
        patient=patient,
        priorite=priorite,
        confiance=random.randint(75, 98),
        resume=resume,
        douleur_repos=patient.douleur_repos if hasattr(patient, 'douleur_repos') else random.randint(0, 3),
        douleur_effort=douleur_effort,
    )

    tracer_action(
        utilisateur=request.user,
        patient=patient,
        type_action='ia',
        action='Analyse IA générée',
        details={
            'priorite': priorite,
            'confiance': analyse.confiance,
            'douleur_effort': douleur_effort
        }
    )

    return redirect('page_ia')

@login_required
def IA(request):
    """Page IA - Affiche les analyses et recommandations"""
    from .models import AnalyseIA
    from django.db.models import Q, Avg
    
    patient_id = request.GET.get('patient_id')
    reco_id = request.GET.get('reco_id')
    reco_detail = None
    patient_selectionne = None
    analyses_patient = []
    analyse_rapide_patient = None
    plan_intervention_patient = None
    patients_avec_contenu_ia = []
    
    # ===== STATISTIQUES =====
    # 1. Total des analyses
    total_analyses = AnalyseIA.objects.count()
    
    # 2. Alertes actives (priorité critical ou warning non validées)
    alertes_actives = AnalyseIA.objects.filter(
        Q(priorite='critical') | Q(priorite='warning'),
        est_valide=False
    ).count()
    
    # 3. Précision moyenne (moyenne des confiances)
    precision_moyenne = AnalyseIA.objects.filter(
        confiance__isnull=False
    ).aggregate(Avg('confiance'))['confiance__avg'] or 0
    precision_moyenne = round(precision_moyenne)
    
    # 4. Analyses validées
    analyses_validees = AnalyseIA.objects.filter(est_valide=True).count()
    
    patients_ia = list(PatientProfile.objects.select_related('user').all().order_by('user__nom', 'user__prenom'))
    for patient in patients_ia:
        analyses = AnalyseIA.objects.filter(patient=patient).order_by('-date_generation')
        patient.nb_analyses_ia = analyses.count()
        patient.derniere_analyse_ia = analyses.first()
        if patient.nb_analyses_ia:
            patients_avec_contenu_ia.append(patient)
    
    # ===== DÉTAIL D'UNE ANALYSE SPÉCIFIQUE =====
    if reco_id:
        reco_detail = get_object_or_404(AnalyseIA, id=reco_id)
        patient_selectionne = reco_detail.patient
        historique_ia = HistoriqueAnalyseIA.objects.filter(analyse=reco_detail)
    elif patient_id:
        patient_selectionne = get_object_or_404(PatientProfile.objects.select_related('user'), id=patient_id)
        reco_detail = AnalyseIA.objects.filter(patient=patient_selectionne).order_by('-date_generation').first()
        historique_ia = HistoriqueAnalyseIA.objects.filter(analyse=reco_detail) if reco_detail else []
    else:
        historique_ia = []

    if patient_selectionne:
        analyses_patient = AnalyseIA.objects.filter(patient=patient_selectionne).order_by('-date_generation')
        analyse_rapide_patient = analyses_patient.filter(programme_genere='').first()
        plan_intervention_patient = analyses_patient.exclude(programme_genere='').first()
        tracer_action(
            utilisateur=request.user,
            patient=patient_selectionne,
            type_action='ia',
            action='Patient consulté dans la page IA',
            details={
                'patient_id': patient_selectionne.id,
                'analyse_id': reco_detail.id if reco_detail else None,
            }
        )
    
    context = {
        'total_analyses': total_analyses,
        'alertes_actives': alertes_actives,
        'precision_moyenne': precision_moyenne,
        'analyses_validees': analyses_validees,
        'patients_ia': patients_ia,
        'reco_detail': reco_detail,
        'patient_selectionne': patient_selectionne,
        'analyses_patient': analyses_patient,
        'analyse_rapide_patient': analyse_rapide_patient,
        'plan_intervention_patient': plan_intervention_patient,
        'patients_avec_contenu_ia': patients_avec_contenu_ia,
        'historique_ia': historique_ia,
    }
    
    return render(request, 'IA.html', context)

@login_required
def valider_analyse_ia(request, analyse_id):
    """Valider une analyse IA (marquer comme traitée)"""
    analyse = get_object_or_404(AnalyseIA, id=analyse_id)
    analyse.est_valide = True
    analyse.save()

    tracer_action(
        utilisateur=request.user,
        patient=analyse.patient,
        type_action='ia',
        action='Analyse IA validée',
        details={
            'analyse_id': analyse.id
        }
    )
    
    return redirect(f"{reverse('IA')}?patient_id={analyse.patient_id}")


def _contenu_patient_neutre(content):
    replacements = {
        'Intelligence Artificielle': 'suivi thérapeutique',
        'intelligence artificielle': 'suivi thérapeutique',
        'Analyse IA': 'Synthèse thérapeutique',
        'analyse IA': 'synthèse thérapeutique',
        'Plan IA': 'Programme thérapeutique',
        'plan IA': 'programme thérapeutique',
        'Recommandations IA': 'Recommandations thérapeutiques',
        'recommandations IA': 'recommandations thérapeutiques',
        'Contenu IA': 'Contenu thérapeutique',
        'contenu IA': 'contenu thérapeutique',
        'IA': 'suivi',
        'AI': 'therapeutic follow-up',
    }
    neutral = content or ''
    for old, new in replacements.items():
        neutral = neutral.replace(old, new)
    return neutral.strip()


def _envoyer_contenu_en_programme_patient(*, patient, ergo, content, analyse=None, source='suivi_therapeutique'):
    jours_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    programme_patient = {jour: [] for jour in jours_fr}
    jour_actuel = jours_fr[date.today().weekday()]
    titre = "Programme"

    programme_exercice = ProgrammeExercice.objects.create(
        patient=patient,
        ergotherapeute=ergo,
        nom=titre,
        description=content,
        date_debut=date.today(),
        phase='Suivi',
        actif=True
    )
    exercice_suivi = Exercice.objects.create(
        programme=programme_exercice,
        nom=titre,
        categorie='Suivi',
        series=0,
        repetitions=0,
        temps_exercice='',
        repos='',
        objectif="Recommandation de votre ergothérapeute",
        instructions=content,
        materiel_necessaire='',
        ordre=1
    )
    programme_patient[jour_actuel].append({
        'id': exercice_suivi.id,
        'nom': titre,
        'name': {'fr': titre, 'en': titre, 'ar': titre},
        'instructions': content,
        'objectif': "Recommandation de votre ergothérapeute",
        'objective': "Recommandation de votre ergothérapeute",
        'materiel_necessaire': '',
        'categorie': 'Suivi',
        'temps_exercice': '',
        'repos': '',
        'completed': False,
        'medias': [],
        'source': source,
    })
    nouveau_programme = _sauvegarder_programme_envoye(patient, programme_patient, archive_existing=False)

    details = {
        'programme_exercice_id': programme_exercice.id,
        'exercice_id': exercice_suivi.id,
        'programme_envoye_id': nouveau_programme.id
    }
    if analyse:
        details['analyse_id'] = analyse.id

    tracer_action(
        utilisateur=ergo,
        patient=patient,
        type_action='programme',
        action='Programme thérapeutique envoyé au patient',
        details=details
    )

    return nouveau_programme, programme_exercice, exercice_suivi


def _creer_programme_therapeute_depuis_contenu(*, patient, ergo, content, analyse=None):
    titre = "Programme"
    programme_exercice = ProgrammeExercice.objects.create(
        patient=patient,
        ergotherapeute=ergo,
        nom=titre,
        description=content,
        date_debut=date.today(),
        phase='Suivi',
        actif=True
    )
    exercice_suivi = Exercice.objects.create(
        programme=programme_exercice,
        nom=titre,
        categorie='Suivi',
        series=0,
        repetitions=0,
        temps_exercice='',
        repos='',
        objectif="Recommandation a valider par l'ergothérapeute",
        instructions=content,
        materiel_necessaire='',
        ordre=1
    )
    details = {
        'programme_exercice_id': programme_exercice.id,
        'exercice_id': exercice_suivi.id,
    }
    if analyse:
        details['analyse_id'] = analyse.id

    tracer_action(
        utilisateur=ergo,
        patient=patient,
        type_action='programme',
        action='Programme préparé côté ergothérapeute',
        details=details
    )
    return programme_exercice, exercice_suivi


@login_required
@require_POST
def api_envoyer_contenu_therapeutique(request):
    if getattr(request.user, 'role', '') != 'ergo':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalide'}, status=400)

    patient_id = data.get('patient_id')
    content = (data.get('content') or '').strip()
    destination = data.get('destination') or 'programme'

    if not patient_id:
        return JsonResponse({'success': False, 'error': 'Patient non sélectionné'}, status=400)
    if not content:
        return JsonResponse({'success': False, 'error': 'Contenu vide'}, status=400)

    patient = get_object_or_404(PatientProfile.objects.select_related('user'), id=patient_id)

    if destination == 'message':
        Message.objects.create(
            expediteur=request.user,
            destinataire=patient.user,
            sujet='Programme thérapeutique',
            contenu=content
        )
        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='message',
            action='Message thérapeutique envoyé au patient',
            details={'source': 'programmes'}
        )
        return JsonResponse({'success': True, 'destination': 'message', 'patient_id': patient.id})

    nouveau_programme, programme_exercice, exercice_suivi = _envoyer_contenu_en_programme_patient(
        patient=patient,
        ergo=request.user,
        content=content,
        source='programme_therapeute'
    )
    return JsonResponse({
        'success': True,
        'destination': 'programme',
        'patient_id': patient.id,
        'programme_id': programme_exercice.id,
        'programme_envoye_id': nouveau_programme.id,
        'exercice_id': exercice_suivi.id,
        'programme_url': f"{reverse('Programmes')}?patient_id={patient.id}&programme_id={programme_exercice.id}"
    })


@login_required
@require_POST
def api_action_analyse_ia(request, analyse_id):
    if getattr(request.user, 'role', '') != 'ergo':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    analyse = get_object_or_404(AnalyseIA, id=analyse_id)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalide'}, status=400)

    action = data.get('action')
    content = (data.get('content') or '').strip()
    is_plan = bool(analyse.programme_genere)

    if action == 'modifier':
        if not content:
            return JsonResponse({'success': False, 'error': 'Le contenu ne peut pas être vide.'}, status=400)
        if is_plan:
            analyse.programme_genere = content
            analyse.resume = analyse.resume or 'Plan d’intervention généré par IA'
        else:
            analyse.resume = content
        analyse.est_valide = False
        analyse.save()
        tracer_action(
            utilisateur=request.user,
            patient=analyse.patient,
            type_action='ia',
            action='Contenu IA modifié',
            details={'analyse_id': analyse.id, 'type': 'plan' if is_plan else 'analyse'}
        )
        return JsonResponse({'success': True, 'content': content, 'validated': analyse.est_valide})

    if action == 'valider':
        analyse.est_valide = True
        analyse.save()
        tracer_action(
            utilisateur=request.user,
            patient=analyse.patient,
            type_action='ia',
            action='Contenu IA validé',
            details={'analyse_id': analyse.id, 'type': 'plan' if is_plan else 'analyse'}
        )
        return JsonResponse({'success': True, 'validated': True})

    if action == 'supprimer':
        patient = analyse.patient
        patient_id = analyse.patient_id
        analyse_id_supprime = analyse.id
        analyse.delete()
        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='ia',
            action='Analyse IA supprimée',
            details={'analyse_id': analyse_id_supprime}
        )
        return JsonResponse({'success': True, 'deleted': True, 'patient_id': patient_id})

    if action == 'envoyer':
        selected_content = (data.get('content') or '').strip()
        message_content = _contenu_patient_neutre(selected_content or (analyse.programme_genere if is_plan else analyse.resume))
        destination = data.get('destination') or 'message'
        target_patient_id = data.get('patient_id') or data.get('target_patient_id')
        target_patient = analyse.patient
        if target_patient_id:
            target_patient = get_object_or_404(PatientProfile, id=target_patient_id)
        if not message_content:
            return JsonResponse({'success': False, 'error': 'Contenu vide'}, status=400)
        if not analyse.est_valide:
            analyse.est_valide = True
            analyse.save(update_fields=['est_valide'])

        if destination == 'programme':
            nouveau_programme, programme_exercice, exercice_suivi = _envoyer_contenu_en_programme_patient(
                patient=target_patient,
                ergo=request.user,
                content=message_content,
                analyse=analyse,
                source='suivi_therapeutique'
            )
            return JsonResponse({
                'success': True,
                'sent': True,
                'destination': 'programme',
                'patient_id': target_patient.id,
                'programme_id': programme_exercice.id,
                'programme_envoye_id': nouveau_programme.id,
                'programme_url': f"{reverse('Programmes')}?patient_id={target_patient.id}&programme_id={programme_exercice.id}"
            })

        if destination in ['ia', 'programme_therapeute']:
            programme_exercice, exercice_suivi = _creer_programme_therapeute_depuis_contenu(
                patient=target_patient,
                ergo=request.user,
                content=message_content,
                analyse=analyse,
            )
            return JsonResponse({
                'success': True,
                'sent': True,
                'destination': 'ia' if destination == 'ia' else 'programme_therapeute',
                'patient_id': target_patient.id,
                'programme_id': programme_exercice.id,
                'exercice_id': exercice_suivi.id,
                'programme_url': f"{reverse('Programmes')}?patient_id={target_patient.id}&programme_id={programme_exercice.id}&tab=ia"
            })

        if destination == 'ressource':
            titre = "Conseil thérapeutique"
            ressource = Ressource.objects.create(
                titre=titre,
                description=message_content,
                type_ressource='link',
                objectif_therapeutique="Suivi prescrit par votre ergothérapeute",
                consigne=message_content,
                cree_par=request.user
            )
            partage, _ = RessourcePatient.objects.get_or_create(
                ressource=ressource,
                patient=target_patient,
                defaults={'statut': 'non_vue', 'partage_par': request.user}
            )
            tracer_action(
                utilisateur=request.user,
                patient=target_patient,
                type_action='ressource',
                action='Ressource thérapeutique envoyée au patient',
                details={'ressource_id': ressource.id, 'partage_id': partage.id}
            )
            return JsonResponse({
                'success': True,
                'sent': True,
                'destination': 'ressource',
                'patient_id': target_patient.id,
                'ressource_id': ressource.id,
                'ressource_url': reverse('patient_ressources')
            })

        subject = "Message"
        Message.objects.create(
            expediteur=request.user,
            destinataire=target_patient.user,
            sujet=subject,
            contenu=message_content
        )
        tracer_action(
            utilisateur=request.user,
            patient=target_patient,
            type_action='message',
            action='Message thérapeutique envoyé au patient',
            details={'analyse_id': analyse.id, 'type': 'plan' if is_plan else 'analyse', 'selection': bool(selected_content)}
        )
        return JsonResponse({
            'success': True,
            'sent': True,
            'destination': 'message',
            'patient_id': target_patient.id,
            'message_url': reverse('patient_messages')
        })

    return JsonResponse({'success': False, 'error': 'Action invalide'}, status=400)
@login_required
def Agenda(request):
    patients = PatientProfile.objects.select_related('user').all().order_by('user__prenom', 'user__nom')

    lang = 'fr'
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        lang = _normaliser_code_langue(request.user.patient_profile.langue)
    elif request.session.get('lang'):
        lang = request.session.get('lang')

    context = {
        'patients': patients,
        'current_lang': lang,
        'today': date.today(),
    }
    return render(request, 'Agenda.html', context)
@login_required
@require_GET
def agenda_rdv_list(request):
    rdvs = RDV.objects.select_related('patient', 'ergo').filter(ergo=request.user).order_by('date_heure')

    data = []
    for rdv in rdvs:
        # ✅ Affichage DIRECT sans aucune modification
        data.append({
            'id': rdv.id,
            'patient': f"{rdv.patient.prenom} {rdv.patient.nom}",
            'patient_id': rdv.patient.id,
            'date': rdv.date_heure.strftime('%Y-%m-%d'),
            'time': rdv.date_heure.strftime('%H:%M'),
            'date_creation': (rdv.created_at + timedelta(hours=2)).strftime('%d/%m/%Y à %H:%M'),
            'duration': rdv.duree,
            'type': rdv.type_seance,
            'notes': rdv.notes or '',
            'status': rdv.statut,
            'notification_envoyee': rdv.notification_envoyee,
            'old_date': rdv.ancienne_date_heure.strftime('%Y-%m-%d') if rdv.ancienne_date_heure else None,
            'old_time': rdv.ancienne_date_heure.strftime('%H:%M') if rdv.ancienne_date_heure else None,
        })
    return JsonResponse({'rdvs': data})

@login_required
@csrf_exempt
@require_POST
def agenda_rdv_notify(request, rdv_id):
    try:
        rdv = get_object_or_404(RDV, id=rdv_id, ergo=request.user)
        rdv.notification_envoyee = True
        rdv.save(update_fields=['notification_envoyee', 'updated_at'])
        patient_profile = getattr(rdv.patient, 'patient_profile', None)

        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='seance',
            action='Notification de rendez-vous envoyée',
            details={
                'date': rdv.date_heure.strftime('%Y-%m-%d'),
                'heure': rdv.date_heure.strftime('%H:%M')
            }
        )
        return JsonResponse({
            'success': True,
            'message': f"Le rendez-vous a bien été confirmé pour {rdv.patient.prenom} {rdv.patient.nom}."
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
@require_POST
def agenda_rdv_create(request):
    try:
        data = json.loads(request.body)

        patient_id = data.get('patient_id')
        date_str = data.get('date')
        time_str = data.get('time')
        duration = int(data.get('duration', 30))
        type_seance = data.get('type', 'presentiel')
        notes = data.get('notes', '').strip()
        therapist_name = data.get('therapist', '')

        if not patient_id or not date_str or not time_str:
            return JsonResponse({'success': False, 'error': 'Champs obligatoires manquants'}, status=400)

        patient_profile = get_object_or_404(PatientProfile, user_id=patient_id)
        patient_user = patient_profile.user

        from datetime import datetime
        
        date_heure_str = f"{date_str} {time_str}"
        date_heure = datetime.strptime(date_heure_str, "%Y-%m-%d %H:%M")
        date_heure = date_heure + timedelta(hours=1)
        
        # STOCKAGE DIRECT - AUCUNE MODIFICATION
        rdv = RDV.objects.create(
            patient=patient_user,
            ergo=request.user,
            date_heure=date_heure,
            duree=duration,
            type_seance=type_seance,
            notes=notes,
            motif=notes[:200] if notes else '',
            statut='actif',
            valide=True
        )

        if therapist_name:
            rdv.therapist_name = therapist_name
            rdv.save(update_fields=['therapist_name'])

        return JsonResponse({'success': True, 'id': rdv.id})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
@csrf_exempt
@require_POST
def agenda_rdv_update(request, rdv_id):
    try:
        rdv = get_object_or_404(RDV, id=rdv_id, ergo=request.user)
        data = json.loads(request.body)

        patient_id = data.get('patient_id')
        date_str = data.get('date')
        time_str = data.get('time')
        duration = int(data.get('duration', 30))
        type_seance = data.get('type', 'presentiel')
        notes = data.get('notes', '').strip()
        mode = data.get('mode', 'edit')

        if not patient_id or not date_str or not time_str:
            return JsonResponse({'success': False, 'error': 'Champs obligatoires manquants'}, status=400)

        patient_profile = get_object_or_404(PatientProfile, user_id=patient_id)
        patient_user = patient_profile.user

        from datetime import datetime
        date_heure_str = f"{date_str} {time_str}"
        date_heure_locale = datetime.strptime(date_heure_str, "%Y-%m-%d %H:%M")
        
        # ✅ STOCKAGE DIRECT - AUCUNE modification
        nouvelle_date_heure = date_heure_locale + timedelta(hours=1)
        if mode == 'reprogram':
            rdv.ancienne_date_heure = rdv.date_heure
            rdv.statut = 'reprogramme'
        elif rdv.statut != 'annule':
            rdv.statut = 'actif'
            rdv.ancienne_date_heure = None

        rdv.patient = patient_user
        rdv.date_heure = nouvelle_date_heure
        rdv.duree = duration
        rdv.type_seance = type_seance
        rdv.notes = notes
        rdv.motif = notes[:200] if notes else ''
        rdv.save()

        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='seance',
            action='Rendez-vous modifié',
            details={
                'date': date_str,
                'heure': time_str,
                'type': type_seance,
                'duree': duration,
                'mode': mode
            }
        )

        return JsonResponse({'success': True})

    except Exception as e:
        print(f"âŒ ERREUR modification RDV: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
@csrf_exempt
@require_POST
def agenda_rdv_cancel(request, rdv_id):
    try:
        rdv = get_object_or_404(RDV, id=rdv_id, ergo=request.user)
        patient_profile = getattr(rdv.patient, 'patient_profile', None)

        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='seance',
            action='Rendez-vous annulé et supprimé',
            details={
                'date': rdv.date_heure.strftime('%Y-%m-%d'),
                'heure': rdv.date_heure.strftime('%H:%M')
            }
        )
        
        # ✅ SUPPRESSION DIRECTE (pas seulement annulation)
        rdv.delete()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def Messages(request):
    """Page de gestion des Messages"""
    return render(request, 'Messages.html')  
@login_required
@csrf_exempt
@require_POST
def agenda_rdv_delete(request, rdv_id):
    try:
        rdv = get_object_or_404(RDV, id=rdv_id, ergo=request.user)
        patient_profile = getattr(rdv.patient, 'patient_profile', None)

        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='seance',
            action='Rendez-vous supprimé',
            details={
                'date': rdv.date_heure.strftime('%Y-%m-%d'),
                'heure': rdv.date_heure.strftime('%H:%M')
            }
        )
        rdv.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def Ressources(request):
    ressources = Ressource.objects.all().order_by('-date_creation')

    total = ressources.count()
    ressources_pdf = ressources.filter(type_ressource='pdf').count()
    ressources_video = ressources.filter(type_ressource='video').count()

    ressources_json = []

    for res in ressources:
        partages = res.partages_patient.select_related('patient__user').all().order_by('-date_partage')

        shared_with = []
        completed_by = []

        for partage in partages:
            # Données de base du patient
            patient_base = {
                "partage_id": partage.id,
                "patient_id": partage.patient.id,
                "nom": partage.patient.user.nom,
                "prenom": partage.patient.user.prenom,
                "statut": partage.statut,
            }
            
            # Date de partage (une seule fois)
            if partage.date_partage:
                patient_data_share = {
                    **patient_base,
                    "date_partage": (algeria_localtime(partage.date_partage) + timedelta(hours=1)).strftime('%d/%m/%Y %H:%M'),
                }
                shared_with.append(patient_data_share)
            
            # Fin (une seule fois)
            if partage.date_fin:
                fin_data = {
                    **patient_base,
                    "date_fin": (algeria_localtime(partage.date_fin) + timedelta(hours=1)).strftime('%d/%m/%Y %H:%M'),
                }
                completed_by.append(fin_data)

        # Pour les vues des patients (depuis HistoriqueAction)
        views_actions = HistoriqueAction.objects.filter(
            type_action='ressource',
            action='Ressource vue par le patient',
            details__icontains=res.titre
        ).select_related('patient__user').order_by('-date_action')

        viewed_by = []
        for action in views_actions:
            if action.patient:
                viewed_by.append({
                    "patient_id": action.patient.id,
                    "nom": action.patient.user.nom,
                    "prenom": action.patient.user.prenom,
                    "date_vue": (algeria_localtime(action.date_action) + timedelta(hours=1)).strftime('%d/%m/%Y %H:%M'),
                })

        # Pour les téléchargements des patients (depuis HistoriqueAction)
        downloads_actions = HistoriqueAction.objects.filter(
            type_action='ressource',
            action='Ressource téléchargée par le patient',
            details__icontains=res.titre
        ).select_related('patient__user').order_by('-date_action')

        downloaded_by = []
        for action in downloads_actions:
            if action.patient:
                downloaded_by.append({
                    "patient_id": action.patient.id,
                    "nom": action.patient.user.nom,
                    "prenom": action.patient.user.prenom,
                    "date_telechargement": (algeria_localtime(action.date_action) + timedelta(hours=1)).strftime('%d/%m/%Y %H:%M'),
                })

        # Récupérer les actions de la fondatrice - SANS DOUBLONS
        actions_fondatrice = HistoriqueAction.objects.filter(
            type_action='ressource',
            details__icontains=res.titre,
            utilisateur=request.user
        ).order_by('-date_action')

        fondatrice_views = []
        fondatrice_downloads = []
        vues_vues = set()
        downloads_vues = set()

        for action in actions_fondatrice:
            action_key = f"{action.date_action.strftime('%Y-%m-%d %H:%M:%S')}_{action.action}"
            
            if 'vue' in action.action.lower():
                if action_key not in vues_vues:
                    vues_vues.add(action_key)
                    fondatrice_views.append({
                        "nom": "Fondatrice",
                        "prenom": "",
                        "date": (algeria_localtime(action.date_action) + timedelta(hours=1)).strftime('%d/%m/%Y %H:%M:%S')
                    })
            elif 'téléchargée' in action.action.lower() or 'telechargee' in action.action.lower():
                if action_key not in downloads_vues:
                    downloads_vues.add(action_key)
                    fondatrice_downloads.append({
                        "nom": "Fondatrice",
                        "prenom": "",
                        "date": (algeria_localtime(action.date_action) + timedelta(hours=1)).strftime('%d/%m/%Y %H:%M:%S')
                    })

        ressources_json.append({
            "id": str(res.id),
            "title": res.titre,
            "description": res.description or "",
            "details": res.consigne or res.description or "",
            "type": res.type_ressource,
            "data": res.url if res.type_ressource == "link" else (res.fichier.url if res.fichier else ""),
            "views": res.nombre_vues or 0,
            "downloads": res.nombre_telechargements or 0,
            "sharedCount": partages.count(),
            "date": algeria_localtime(res.date_creation).isoformat() if res.date_creation else "",
            "date_display": algeria_localtime(res.date_creation).strftime('%d/%m/%Y') if res.date_creation else "",
            "time_display": algeria_localtime(res.date_creation).strftime('%H:%M') if res.date_creation else "",
            "sharedWith": shared_with,
            "viewedBy": viewed_by,
            "downloadedBy": downloaded_by,
            "completedBy": completed_by,
            "fondatrice_views": fondatrice_views,
            "fondatrice_downloads": fondatrice_downloads,
        })

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            "ressources": ressources_json,
            "total": total,
            "ressources_pdf": ressources_pdf,
            "ressources_video": ressources_video,
        })

    ressources_avec_dates = []
    for res in ressources:
        res.date_creation_local = algeria_localtime(res.date_creation) if res.date_creation else None
        ressources_avec_dates.append(res)

    context = {
        'ressources': ressources_avec_dates,
        'ressources_json': ressources_json,
        'total': total,
        'ressources_pdf': ressources_pdf,
        'ressources_video': ressources_video,
    }
    return render(request, 'Ressources.html', context)


@login_required
@require_POST
def api_envoyer_question_jour(request):
    if getattr(request.user, 'role', '') != 'ergo':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalide'}, status=400)

    question = (data.get('question') or '').strip()
    patient_ids = data.get('patient_ids') or []
    if not question:
        return JsonResponse({'success': False, 'error': 'Question vide'}, status=400)

    if not patient_ids or 'all' in patient_ids:
        QuestionJour.objects.create(question=question, patient=None, cree_par=request.user)
        nombre = PatientProfile.objects.count()
    else:
        patients = PatientProfile.objects.filter(id__in=patient_ids)
        nombre = 0
        for patient in patients:
            QuestionJour.objects.create(question=question, patient=patient, cree_par=request.user)
            nombre += 1

    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='programme',
        action='Question du jour envoyée',
        details={'question': question, 'patients': nombre},
    )
    return JsonResponse({'success': True, 'created': nombre})

@login_required
@require_POST
def tracer_telechargement_ressource(request, ressource_id):
    ressource = get_object_or_404(Ressource, id=ressource_id)
    
    # Incrémenter le compteur à CHAQUE téléchargement
    ressource.nombre_telechargements += 1
    ressource.save(update_fields=['nombre_telechargements'])
    
    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='ressource',
        action='Ressource téléchargée par fondatrice',
        details={
            'ressource': ressource.titre,
            'type': ressource.type_ressource
        }
    )
    
    return JsonResponse({'success': True})

@login_required
@require_POST
def tracer_vision_ressource_ergo(request, ressource_id):
    ressource = get_object_or_404(Ressource, id=ressource_id)
    
    # Incrémenter le compteur à CHAQUE vue
    ressource.nombre_vues += 1
    ressource.save(update_fields=['nombre_vues'])
    
    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='ressource',
        action='Ressource vue par fondatrice',
        details={
            'ressource': ressource.titre,
            'type': ressource.type_ressource
        }
    )
    
    return JsonResponse({'success': True})
@login_required
@require_POST
def ajouter_ressource(request):
    titre = request.POST.get('titre')
    description = request.POST.get('description', '')
    type_ressource = request.POST.get('type_ressource')
    fichier = request.FILES.get('fichier')
    url = request.POST.get('url', '')

    if not titre or not type_ressource:
        return JsonResponse({
            'success': False,
            'error': 'Titre ou type manquant'
        }, status=400)

    # Validation selon le type
    if type_ressource == 'link':
        if not url:
            return JsonResponse({
                'success': False,
                'error': 'URL manquante pour une ressource de type lien'
            }, status=400)
    else:
        if not fichier:
            return JsonResponse({
                'success': False,
                'error': 'Fichier manquant'
            }, status=400)

    ressource = Ressource.objects.create(
        titre=titre,
        description=description,
        type_ressource=type_ressource,
        fichier=fichier if fichier else None,
        url=url if url else None,
        cree_par=request.user,
        date_creation=datetime.now() + ALGERIA_TZ_OFFSET  # Force timezone Algeria
    )

    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='ressource',
        action=f'Ressource ajoutée : {ressource.titre}',
        details={
            'titre': ressource.titre,
            'type': ressource.type_ressource
        }
    )

    return JsonResponse({
        'success': True,
        'message': 'Ressource ajoutée avec succès',
        'ressource_id': ressource.id
    })


@login_required
@require_POST
def supprimer_ressource(request, ressource_id):
    ressource = get_object_or_404(Ressource, id=ressource_id)

    # ✅ AJOUTER CET APPEL AVANT LA SUPPRESSION
    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='ressource',
        action=f'Ressource supprimée : {ressource.titre}',
        details={
            'titre': ressource.titre,
            'type': ressource.type_ressource
        }
    )

    ressource.delete()
    return redirect('Ressources')
@login_required
@require_POST
def modifier_ressource(request, ressource_id):
    ressource = get_object_or_404(Ressource, id=ressource_id)

    ancien_titre = ressource.titre
    ancien_type = ressource.type_ressource
    
    ressource.titre = request.POST.get('titre', ressource.titre)
    ressource.type_ressource = request.POST.get('type_ressource', ressource.type_ressource)

    if request.FILES.get('fichier'):
        ressource.fichier = request.FILES.get('fichier')

    ressource.save()

    # ✅ AJOUTER CET APPEL
    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='ressource',
        action=f'Ressource modifiée : {ressource.titre}',
        details={
            'ancien_titre': ancien_titre,
            'nouveau_titre': ressource.titre,
            'ancien_type': ancien_type,
            'nouveau_type': ressource.type_ressource
        }
    )

    return redirect('Ressources')
@login_required
@require_POST
def partager_ressource_patient(request):
    try:
        data = json.loads(request.body)
        ressource_id = data.get('ressource_id')
        patient_user_id = data.get('patient_id')  # C'est l'ID du User, pas du PatientProfile
        
        # 1. Récupérer la ressource
        ressource = get_object_or_404(Ressource, id=ressource_id)
        
        # 2. Récupérer l'utilisateur patient par son ID (User)
        patient_user = get_object_or_404(User, id=patient_user_id, role='patient')
        
        # 3. Récupérer le PatientProfile associé à cet User
        patient_profile = get_object_or_404(PatientProfile, user=patient_user)
        
        # 4. Créer ou récupérer le partage
        partage, created = RessourcePatient.objects.get_or_create(
            ressource=ressource,
            patient=patient_profile,
            defaults={
                'statut': 'non_vue',
                'partage_par': request.user
            }
        )
        
        # 5. Journaliser l'action
        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='ressource',
            action='Ressource partagée au patient',
            details={
                'ressource': ressource.titre,
                'statut_initial': partage.statut
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Ressource partagée avec succès',
            'partage_id': partage.id
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Patient non trouvé'}, status=404)
        
    except PatientProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Profil patient non trouvé'}, status=404)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
@require_POST
def marquer_ressource_vue(request, partage_id):
    partage = get_object_or_404(RessourcePatient, id=partage_id)
    
    partage.ressource.nombre_vues += 1
    partage.ressource.save(update_fields=['nombre_vues'])
    
    tracer_action(
        utilisateur=request.user,
        patient=partage.patient,
        type_action='ressource',
        action='Ressource vue par le patient',
        details={
            'ressource': partage.ressource.titre,
            'type': partage.ressource.type_ressource,
            'partage_id': partage.id
        }
    )
    
    return JsonResponse({
        'success': True,
        'url': partage.ressource.url if partage.ressource.type_ressource == 'link'
               else (partage.ressource.fichier.url if partage.ressource.fichier else '')
    })

@login_required
@require_POST
def marquer_ressource_telechargee(request, partage_id):
    partage = get_object_or_404(RessourcePatient, id=partage_id)
    
    partage.ressource.nombre_telechargements += 1
    partage.ressource.save(update_fields=['nombre_telechargements'])
    
    tracer_action(
        utilisateur=request.user,
        patient=partage.patient,
        type_action='ressource',
        action='Ressource téléchargée par le patient',
        details={
            'ressource': partage.ressource.titre,
            'type': partage.ressource.type_ressource,
            'partage_id': partage.id
        }
    )
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def marquer_ressource_terminee(request, partage_id):
    partage = get_object_or_404(RessourcePatient, id=partage_id)

    partage.statut = 'terminee'
    partage.date_fin = timezone.now()
    partage.save()
    tracer_action(
        utilisateur=request.user,
        patient=partage.patient,
        type_action='ressource',
        action='Ressource terminée par le patient',
        details={
            'ressource': partage.ressource.titre
        }
    )
    return JsonResponse({'success': True})

from django.utils.dateparse import parse_date

from datetime import date
@login_required
def Historique(request):
    type_action = request.GET.get('type_action', 'all')
    patient_id = request.GET.get('patient_id', 'all')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search = request.GET.get('search', '').strip()
    historique = _historique_queryset_for_user(request.user, patient_id).order_by('-date_action')

    if type_action != 'all':
        historique = historique.filter(type_action=type_action)

    if patient_id != 'all':
        historique = historique.filter(patient_id=patient_id)

    if date_from:
        historique = historique.filter(date_action__date__gte=date_from)

    if date_to:
        historique = historique.filter(date_action__date__lte=date_to)

    if search:
        historique = historique.filter(
            Q(action__icontains=search) |
            Q(patient__user__nom__icontains=search) |
            Q(patient__user__prenom__icontains=search)
        )

    stats_base = _historique_queryset_for_user(request.user, patient_id)

    stats = {
        'seances': stats_base.filter(type_action='seance').count(),
        'messages': stats_base.filter(type_action='message').count(),
        'ressources': stats_base.filter(type_action='ressource').count(),
        'dossiers': stats_base.filter(type_action='dossier').count(),
        'programmes': stats_base.filter(type_action='programme').count(),
        'ia': stats_base.filter(type_action='ia').count(),
        'patients': stats_base.filter(type_action='patient').count(),
        'visites': stats_base.filter(type_action='visite').count(),
    }

    patients = PatientProfile.objects.select_related('user').all().order_by('user__nom', 'user__prenom')

    for event in historique:
        event.date_action_local = localtime(event.date_action)
        formatted = _format_historique_event_for_display(event, request.user)
        event.action_affichage = formatted['title']
        event.details_affichage = formatted['description'] or "Aucune précision"
        event.target_url = formatted.get('target_url')
        event.can_delete = True

    context = {
        'historique': historique[:200],
        'stats': stats,
        'total': stats_base.count(),
        'patients': patients,
        'filtre_type_action': type_action,
        'filtre_patient_id': patient_id,
        'filtre_date_from': date_from or '',
        'filtre_date_to': date_to or '',
        'filtre_search': search,
        'today': date.today(),
    }

    return render(request, 'Historique.html', context)

@login_required
def patient_detail(request, id):
    patient = get_object_or_404(PatientProfile, id=id)
    tracer_action(
    utilisateur=request.user,
    patient=patient,
    type_action='patient',
    action='Fiche patient consultée',
    details={
        'patient_id': patient.id
    }
)
    return render(request, "patient_detail.html", {
        "p": patient
    })




# ===== ESPACE PATIENT =====

@login_required
def patient_dashboard(request):
    compter_visite_patient(request, 'dashboard')
    patient = request.user.patient_profile
    lang = _normaliser_code_langue(patient.langue)
    today = timezone.localdate()
    
    # Programme actif
    programme_actif = ProgrammeExercice.objects.filter(
        patient=patient, actif=True
    ).order_by('-date_debut').first()

    tracer_action(
        utilisateur=request.user,
        patient=patient,
        type_action='programme',
        action='Programme consulté par le patient',
        details={
            'programme': programme_actif.nom if programme_actif else '',
            'motif': 'Ouverture de la page Mon programme',
        }
    )
    
    # Programme du jour : priorite au dernier programme envoye au patient.
    exercices_aujourdhui = []
    programmes_envoyes_dashboard = ProgrammeEnvoye.objects.filter(patient=patient).order_by('-date_envoi')
    programme_envoye_dashboard, _ = _fusionner_programmes_envoyes(programmes_envoyes_dashboard)
    programme_envoye_dashboard = _appliquer_resultats_au_programme_patient(programme_envoye_dashboard, patient)
    today_key = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'][today.weekday()]
    exercices_envoyes = programme_envoye_dashboard.get(today_key, []) if isinstance(programme_envoye_dashboard, dict) else []
    if not exercices_envoyes and isinstance(programme_envoye_dashboard, dict):
        for items in programme_envoye_dashboard.values():
            if isinstance(items, list):
                exercices_envoyes.extend(items)

    if exercices_envoyes:
        for item in exercices_envoyes[:5]:
            exercices_aujourdhui.append({
                'id': item.get('id'),
                'nom': item.get('nom') or 'Exercice',
                'series': item.get('series') or 0,
                'reps': item.get('repetitions') or item.get('reps') or 0,
                'instructions': item.get('instructions') or '',
                'details': f"{item.get('series') or 0} séries x {item.get('repetitions') or item.get('reps') or 0} répétitions",
                'completed': bool(item.get('completed')),
            })
    elif programme_actif:
        exercices = Exercice.objects.filter(programme=programme_actif).order_by('-id')[:5]
        for ex in exercices:
            dernier_resultat = ResultatExercice.objects.filter(patient=patient, exercice=ex).order_by('-date_realisation').first()
            exercices_aujourdhui.append({
                'id': ex.id,
                'nom': ex.nom,
                'series': ex.series,
                'reps': ex.repetitions,
                'instructions': ex.instructions,
                'details': f"{ex.series} séries x {ex.repetitions} répétitions",
                'completed': bool(dernier_resultat),
            })
    
    # Progression
    progressions = ProgressionPatient.objects.filter(patient=patient).order_by('-date')[:7]
    if progressions:
        progression_globale = sum([p.progression_globale for p in progressions]) / len(progressions)
    else:
        progression_globale = 0
    
    resultats_patient = ResultatExercice.objects.filter(patient=patient).order_by('date_realisation')

    # Messages non lus
    messages_non_lus = Message.objects.filter(
        destinataire=request.user,
        est_lu_par_destinataire=False
    ).count()
    
    # Récompenses
    recompenses = Recompense.objects.filter(patient=patient).order_by('-date_obtention')[:5]
    
    # Journal
    journal_recent = JournalPatient.objects.filter(patient=patient).order_by('-date')[:3]

    prochaine_reeval = patient.get_prochaine_reeval() if hasattr(patient, 'get_prochaine_reeval') else None
    prochain_rdv = RDV.objects.filter(
        patient=request.user,
        date_heure__gte=timezone.now(),
        valide=True,
        statut='actif'
    ).order_by('date_heure').first()
    question_du_jour = QuestionJour.objects.filter(
        Q(patient=patient) | Q(patient__isnull=True),
        active=True,
    ).order_by('-date_creation').first()

    progressions_ordre = list(ProgressionPatient.objects.filter(patient=patient).order_by('date')[:30])
    resultats_chart = list(resultats_patient[:12])
    labels = [algeria_localtime(r.date_realisation).strftime('%d/%m') for r in resultats_chart]
    douleur_data = [int(r.douleur or 0) for r in resultats_chart]
    satisfaction_data = [int(r.satisfaction or 0) * 20 for r in resultats_chart]
    if not labels:
        labels = [p.date.strftime('%d/%m') for p in progressions_ordre]
        douleur_data = [int(p.douleur or 0) for p in progressions_ordre]
        satisfaction_data = [int(p.satisfaction or 0) * 20 for p in progressions_ordre]
    zero_like = [0 for _ in labels]

    humeur_score = {'happy': 100, 'neutral': 55, 'sad': 25, '😊': 100, '😐': 55, '☹️': 25}
    humeur_par_date = {
        p.date: humeur_score.get((p.humeur or '').strip(), int(p.satisfaction or 0) * 20)
        for p in progressions_ordre
    }
    mood_data = [
        humeur_par_date.get(algeria_localtime(r.date_realisation).date(), int(r.satisfaction or 0) * 20)
        for r in resultats_chart
    ] or [
        humeur_score.get((p.humeur or '').strip(), int(p.satisfaction or 0) * 20)
        for p in progressions_ordre
    ]

    chart_data = {
        'labels': labels or [today.strftime('%d/%m')],
        'pain': douleur_data or [int(patient.douleur_effort or patient.douleur_repos or 0)],
        'satisfaction': satisfaction_data or [0],
        'mood': mood_data or satisfaction_data or [0],
        'mobility': [int(p.mobilite or 0) for p in progressions_ordre] or zero_like or [0],
        'strength': [int(p.force or 0) for p in progressions_ordre] or zero_like or [0],
        'endurance': [int(p.endurance or 0) for p in progressions_ordre] or zero_like or [0],
        'dexterity': [int(p.dexterite or 0) for p in progressions_ordre] or zero_like or [0],
        'sensitivity': [int(p.sensibilite or 0) for p in progressions_ordre] or zero_like or [0],
        'grip': [int(p.prehension or 0) for p in progressions_ordre] or zero_like or [0],
    }
    ressentis_jours = [
        {
            'date': p.date.strftime('%d/%m/%Y'),
            'douleur': int(p.douleur or 0),
            'fatigue': int(p.fatigue or 0),
            'humeur': p.humeur or '-',
            'satisfaction': int(p.satisfaction or 0),
        }
        for p in ProgressionPatient.objects.filter(patient=patient).order_by('-date')[:14]
    ]

    derniers_messages = Message.objects.filter(
        Q(expediteur=request.user) | Q(destinataire=request.user)
    ).select_related('expediteur').order_by('-date_envoi')[:3]

    objectifs = []
    if patient.objectif_principal:
        objectifs.append({'name': patient.get_objectif_principal_display() if hasattr(patient, 'get_objectif_principal_display') else patient.objectif_principal, 'percent': round(progression_globale)})
    if patient.objectif_autre:
        objectifs.append({'name': patient.objectif_autre, 'percent': round(progression_globale)})
    if not objectifs:
        objectifs.append({'name': 'Objectif thérapeutique à définir', 'percent': round(progression_globale)})

    jours_reeducation = (today - patient.date_fracture).days if patient.date_fracture else 0
    douleur_moyenne = resultats_patient.aggregate(avg=Avg('douleur'))['avg']
    if douleur_moyenne is None:
        douleur_moyenne = patient.douleur_effort or patient.douleur_repos or 0

    dashboard_data = {
        'patientName': f"{patient.user.prenom} {patient.user.nom}".strip() or patient.user.username,
        'stats': {
            'days': max(jours_reeducation, 0),
            'progression': round(progression_globale),
            'painAverage': round(float(douleur_moyenne), 1),
        },
        'fracture': {
            'type': patient.get_type_fracture_display() if hasattr(patient, 'get_type_fracture_display') else patient.type_fracture,
            'date': patient.date_fracture.strftime('%d/%m/%Y') if patient.date_fracture else '-',
            'side': patient.get_cote_atteint_display() if hasattr(patient, 'get_cote_atteint_display') else patient.cote_atteint,
            'treatment': patient.get_traitement_recu_display() if hasattr(patient, 'get_traitement_recu_display') else patient.traitement_recu,
            'start': programme_actif.date_debut.strftime('%d/%m/%Y') if programme_actif and programme_actif.date_debut else '-',
        },
        'exercises': exercices_aujourdhui,
        'dailyQuestion': {
            'id': question_du_jour.id if question_du_jour else None,
            'text': question_du_jour.question if question_du_jour else 'Aucune question pour le moment.',
        },
        'charts': chart_data,
        'feelingsDays': ressentis_jours,
        'reminders': [
            {'time': '10:00', 'text': 'Exercices du programme du jour', 'badge': 'quotidien'},
            {'time': '18:00', 'text': 'Auto-évaluation douleur et satisfaction', 'badge': 'suivi'},
        ] if patient.recevoir_rappels else [],
        'goals': objectifs,
        'challenges': [
            {
                'name': 'Exercices réalisés',
                'progress': resultats_patient.count(),
                'total': max(Exercice.objects.filter(programme__patient=patient).count(), resultats_patient.count(), 1),
            },
            {
                'name': 'Jours actifs',
                'progress': resultats_patient.dates('date_realisation', 'day').count(),
                'total': 7,
            },
        ],
        'nextAppointment': {
            'date': f"Prochain suivi: {localtime(prochain_rdv.date_heure).strftime('%d/%m/%Y')}" if prochain_rdv else 'Prochain suivi: -',
            'type': prochain_rdv.get_type_seance_display() if prochain_rdv else '-',
            'url': reverse('patient_rendezvous'),
        },
        'recentMessages': [
            {
                'from': f"{m.expediteur.prenom} {m.expediteur.nom}".strip(),
                'text': m.contenu[:90] or m.sujet,
                'date': algeria_localtime(m.date_envoi).strftime('%d/%m %H:%M'),
            }
            for m in derniers_messages
        ],
        'journal': [
            {'date': j.date.strftime('%d/%m/%Y'), 'mood': j.humeur or '', 'text': j.contenu}
            for j in journal_recent
        ],
        'rewards': [
            {'icon': r.icone or 'bi-award', 'name': r.nom}
            for r in recompenses
        ],
        'streak': resultats_patient.dates('date_realisation', 'day').count(),
    }
    
    context = {
        'patient': patient,
        'programme_actif': programme_actif,
        'exercices_aujourdhui': exercices_aujourdhui,
        'progressions': progressions,
        'progression_globale': round(progression_globale),
        'messages_non_lus': messages_non_lus,
        'recompenses': recompenses,
        'journal_recent': journal_recent,
        'dashboard_data': dashboard_data,
        'current_lang': lang,
        'today': date.today(),
    }
    return render(request, 'patient.html', context)


@login_required
@require_POST
def api_patient_dashboard_evaluation(request):
    if not hasattr(request.user, 'patient_profile'):
        return JsonResponse({'success': False, 'error': 'Profil patient introuvable.'}, status=403)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalide'}, status=400)

    patient = request.user.patient_profile
    has_douleur = 'douleur' in data
    has_fatigue = 'fatigue' in data
    has_satisfaction = 'satisfaction' in data
    has_humeur = 'humeur' in data
    douleur = int(data.get('douleur') or 0) if has_douleur else None
    fatigue = int(data.get('fatigue') or 0) if has_fatigue else None
    satisfaction = int(data.get('satisfaction') or 0) if has_satisfaction else None
    humeur = (data.get('humeur') or '').strip()
    notes = (data.get('notes') or '').strip()
    reponse_question = (data.get('reponse_question') or '').strip()
    question_id = data.get('question_id')

    latest = ProgressionPatient.objects.filter(patient=patient, date=timezone.localdate()).first()
    if latest:
        if has_douleur:
            latest.douleur = douleur
        if has_fatigue:
            latest.fatigue = fatigue
        if has_humeur:
            latest.humeur = humeur
        if has_satisfaction:
            latest.satisfaction = satisfaction
        latest.notes = notes or latest.notes
        latest.reponse_question = reponse_question or latest.reponse_question
        if has_douleur:
            latest.progression_globale = max(latest.progression_globale, max(0, 100 - douleur * 10))
        latest.save()
    else:
        douleur_create = douleur if douleur is not None else 0
        latest = ProgressionPatient.objects.create(
            patient=patient,
            douleur=douleur_create,
            fatigue=fatigue if fatigue is not None else 0,
            humeur=humeur,
            satisfaction=satisfaction if satisfaction is not None else 0,
            progression_globale=max(0, 100 - douleur_create * 10),
            notes=notes,
            reponse_question=reponse_question,
        )

    if notes:
        JournalPatient.objects.create(patient=patient, contenu=notes, humeur=humeur)

    if reponse_question and question_id:
        question = QuestionJour.objects.filter(
            Q(patient=patient) | Q(patient__isnull=True),
            id=question_id,
            active=True,
        ).first()
        if question:
            ReponseQuestionJour.objects.create(
                question=question,
                patient=patient,
                reponse=reponse_question,
                douleur=latest.douleur,
                fatigue=latest.fatigue,
                humeur=humeur,
                satisfaction=latest.satisfaction,
                notes=notes,
            )

    tracer_action(
        utilisateur=request.user,
        patient=patient,
        type_action='visite',
        action='Auto-évaluation patient enregistrée',
        details={'douleur': latest.douleur, 'fatigue': latest.fatigue, 'humeur': latest.humeur, 'satisfaction': latest.satisfaction, 'reponse_question': reponse_question},
    )

    return JsonResponse({'success': True, 'progression_id': latest.id})

@login_required
def patient_programme(request):
    from .models import ProgrammeEnvoye

    compter_visite_patient(request, 'mon_programme')
    patient = request.user.patient_profile
    
    programme_actif = ProgrammeExercice.objects.filter(
        patient=patient, actif=True
    ).order_by('-date_debut').first()
    
    exercices = []
    if programme_actif:
        exercices = Exercice.objects.filter(programme=programme_actif).order_by('-id')
        if exercices.exists() and not ProgrammeEnvoye.objects.filter(
            patient=patient,
            archive=False
        ).exists():
            _sauvegarder_programme_envoye(
                patient,
                _construire_programme_patient(exercices, mode='programme_complet')
            )
    
    resultats = ResultatExercice.objects.filter(patient=patient).order_by('-date_realisation')[:20]
    question_du_jour = QuestionJour.objects.filter(
        Q(patient=patient) | Q(patient__isnull=True),
        active=True,
    ).order_by('-date_creation').first()
    programmes_envoyes = ProgrammeEnvoye.objects.filter(
        patient=patient
    ).order_by('-date_envoi')
    programme_patient_initial, _ = _fusionner_programmes_envoyes(programmes_envoyes)
    programme_patient_initial = _appliquer_resultats_au_programme_patient(programme_patient_initial, patient)
    # Le programme reste non lu tant que le patient ne le marque pas via les notifications.
    
    context = {
        'patient': patient,
        'programme_actif': programme_actif,
        'exercices': exercices,
        'resultats': resultats,
        'programme_patient_initial': programme_patient_initial,
        'question_du_jour': question_du_jour,
        'current_lang': _normaliser_code_langue(patient.langue),
        'today': date.today(),
        'today_key': ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'][date.today().weekday()],
    }
    return render(request, 'Mon programme.html', context)

@login_required
def patient_progression(request):
    compter_visite_patient(request, 'progression')
    patient = request.user.patient_profile
    
    progressions = ProgressionPatient.objects.filter(patient=patient).order_by('date')
    resultats_patient = ResultatExercice.objects.filter(patient=patient).order_by('date_realisation')

    resultats_recent = list(resultats_patient[:30])
    dates = [algeria_localtime(r.date_realisation).strftime('%d/%m') for r in resultats_recent] or [timezone.localdate().strftime('%d/%m')]
    douleur_data = [int(r.douleur or 0) for r in resultats_recent] or [int(patient.douleur_effort or patient.douleur_repos or 0)]
    satisfaction_data = [int(r.satisfaction or 0) * 20 for r in resultats_recent] or [0]

    humeur_score = {'happy': 100, 'neutral': 55, 'sad': 25, '😊': 100, '😐': 55, '☹️': 25}
    humeur_par_date = {
        p.date: humeur_score.get((p.humeur or '').strip(), int(p.satisfaction or 0) * 20)
        for p in progressions
    }
    mood_data = [
        humeur_par_date.get(algeria_localtime(r.date_realisation).date(), int(r.satisfaction or 0) * 20)
        for r in resultats_recent
    ] or [0]

    mobilite_data = [0 for _ in dates]
    force_data = [0 for _ in dates]
    endurance_data = [0 for _ in dates]
    dexterite_data = [0 for _ in dates]
    sensibilite_data = [0 for _ in dates]
    prehension_data = [0 for _ in dates]
    progression_globale = round(progressions.aggregate(avg=Avg('progression_globale'))['avg'] or 0) if progressions.exists() else 0

    progression_defis = calculer_progression_defis(patient)
    ressentis_jours = [
        {
            'date': p.date.strftime('%d/%m/%Y'),
            'douleur': int(p.douleur or 0),
            'fatigue': int(p.fatigue or 0),
            'humeur': p.humeur or '-',
            'satisfaction': int(p.satisfaction or 0),
        }
        for p in progressions.order_by('-date')[:30]
    ]
    
    context = {
        'progressions': progressions,
        'progression_page_data': {
            'labels': dates,
            'pain': douleur_data,
            'satisfaction': satisfaction_data,
            'mood': mood_data,
            'mobility': mobilite_data,
            'strength': force_data,
            'endurance': endurance_data,
            'dexterity': dexterite_data,
            'sensitivity': sensibilite_data,
            'grip': prehension_data,
            'global': progression_globale,
            'latestPain': douleur_data[-1] if douleur_data else None,
            'latestSatisfaction': satisfaction_data[-1] if satisfaction_data else None,
            'latestMood': mood_data[-1] if mood_data else None,
            'progressionDefis': progression_defis,
            'feelingsDays': ressentis_jours,
        },
        'patient': patient,
        'current_lang': _normaliser_code_langue(patient.langue),
    }
    return render(request, 'progression.html', context)
@login_required
def patient_rendezvous(request):
    compter_visite_patient(request, 'rendez_vous')
    patient_user = request.user

    now = timezone.now()

    # 🔥 CORRECTION : Exclure les rendez-vous annulés et reprogrammés
    rdvs = RDV.objects.filter(
        patient=patient_user,
        valide=True
    ).exclude(
        statut__in=['annule', 'reprogramme']  # ← EXCLURE ceux qui sont annulés ou reprogrammés
    ).select_related('ergo').order_by('date_heure')

    rdv_a_venir = rdvs.filter(date_heure__gte=now, statut='actif').order_by('date_heure')
    rdv_passes = rdvs.filter(date_heure__lt=now).order_by('-date_heure')
    prochain_rdv = rdv_a_venir.first()

    appointments_data = {
        "next": None,
        "upcoming": [],
        "history": [],
    }

    # Prochain rendez-vous
    if prochain_rdv:
        if prochain_rdv.therapist_name:
            ergo_nom = prochain_rdv.therapist_name
        elif prochain_rdv.ergo:
            ergo_nom = f"{prochain_rdv.ergo.prenom} {prochain_rdv.ergo.nom}"
        else:
            ergo_nom = "SmartWrist Rehab"

        date_iso = prochain_rdv.date_heure.strftime("%Y-%m-%d")
        time_str = prochain_rdv.date_heure.strftime("%H:%M")

        appointments_data["next"] = {
            "id": prochain_rdv.id,
            "date": date_iso,
            "time": time_str,
            "duration": prochain_rdv.duree or 30,
            "type": prochain_rdv.type_seance,
            "therapist": ergo_nom,
            "note": prochain_rdv.notes or "",
            "status": prochain_rdv.statut,
            "old_date": prochain_rdv.ancienne_date_heure.strftime("%Y-%m-%d") if prochain_rdv.ancienne_date_heure else "",
            "old_time": prochain_rdv.ancienne_date_heure.strftime("%H:%M") if prochain_rdv.ancienne_date_heure else "",
        }

    # Rendez-vous à venir (sauf le prochain)
    for rdv in rdv_a_venir:
        if prochain_rdv and rdv.id == prochain_rdv.id:
            continue
            
        if rdv.therapist_name:
            ergo_nom = rdv.therapist_name
        elif rdv.ergo:
            ergo_nom = f"{rdv.ergo.prenom} {rdv.ergo.nom}"
        else:
            ergo_nom = "SmartWrist Rehab"

        date_iso = rdv.date_heure.strftime("%Y-%m-%d")
        time_str = rdv.date_heure.strftime("%H:%M")

        appointments_data["upcoming"].append({
            "id": rdv.id,
            "date": date_iso,
            "time": time_str,
            "duration": rdv.duree or 30,
            "type": rdv.type_seance,
            "therapist": ergo_nom,
            "note": rdv.notes or "",
            "status": rdv.statut,
            "old_date": rdv.ancienne_date_heure.strftime("%Y-%m-%d") if rdv.ancienne_date_heure else "",
            "old_time": rdv.ancienne_date_heure.strftime("%H:%M") if rdv.ancienne_date_heure else "",
        })

    # Historique (rendez-vous passés)
    for rdv in rdv_passes:
        if rdv.therapist_name:
            ergo_nom = rdv.therapist_name
        elif rdv.ergo:
            ergo_nom = f"{rdv.ergo.prenom} {rdv.ergo.nom}"
        else:
            ergo_nom = "SmartWrist Rehab"

        date_iso = rdv.date_heure.strftime("%Y-%m-%d")
        time_str = rdv.date_heure.strftime("%H:%M")

        appointments_data["history"].append({
            "id": rdv.id,
            "date": date_iso,
            "time": time_str,
            "duration": rdv.duree or 30,
            "type": rdv.type_seance,
            "therapist": ergo_nom,
            "note": rdv.notes or "",
            "status": rdv.statut,
            "old_date": rdv.ancienne_date_heure.strftime("%Y-%m-%d") if rdv.ancienne_date_heure else "",
            "old_time": rdv.ancienne_date_heure.strftime("%H:%M") if rdv.ancienne_date_heure else "",
        })

    context = {
        "appointments_data": appointments_data,
        "today": date.today(),
        "current_lang": _normaliser_code_langue(patient_user.patient_profile.langue) if hasattr(patient_user, 'patient_profile') else 'fr',
    }

    return render(request, "RDV.html", context)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Message

@login_required
def patient_messages(request):
    compter_visite_patient(request, 'messages')
    patient_user = request.user
    ergo = get_default_ergo()
    ergos_qs = User.objects.filter(role='ergo')

    messages_qs = Message.objects.none()
    last_message = None

    if ergos_qs.exists():
        messages_qs = Message.objects.filter(
            Q(expediteur=patient_user, destinataire__in=ergos_qs) |
            Q(expediteur__in=ergos_qs, destinataire=patient_user)
        ).select_related('reponse_a').order_by('date_envoi')

        # Marquer comme lus les messages reçus par le patient
        Message.objects.filter(
            expediteur__in=ergos_qs,
            destinataire=patient_user,
            est_lu_par_destinataire=False
        ).update(est_lu_par_destinataire=True)

    messages_list = list(messages_qs)

    for msg in messages_list:
        msg.date_envoi_local = localtime(msg.date_envoi)
        msg.date_separateur = msg.date_envoi_local.date()

    if messages_list:
        last_message = messages_list[-1]

    context = {
        'messages': messages_list,
        'total_messages': len(messages_list),
        'last_message': last_message,
        'correspondant': ergo,
        'current_lang': _normaliser_code_langue(patient_user.patient_profile.langue) if hasattr(patient_user, 'patient_profile') else 'fr',
    }

    return render(request, 'Messages du patient.html', context)
@login_required
def patient_messages_notifications(request):
    patient_user = request.user
    ergo = get_default_ergo()
    ergos_qs = User.objects.filter(role='ergo')

    patient_profile = getattr(patient_user, 'patient_profile', None)
    deleted_messages = set(str(item) for item in request.session.get('patient_deleted_message_notifications', []))
    deleted_actions = set(str(item) for item in request.session.get('patient_deleted_action_notifications', []))
    unread_messages_count = 0
    all_messages = Message.objects.none()
    if ergos_qs.exists():
        messages_queryset = Message.objects.filter(
            expediteur__in=ergos_qs,
            destinataire=patient_user
        ).exclude(
            id__in=deleted_messages
        ).order_by('-date_envoi')
        unread_messages_count = messages_queryset.filter(est_lu_par_destinataire=False).count()
        all_messages = messages_queryset[:20]

    notifications = []
    for msg in all_messages:
        notifications.append({
            "notification_type": "message",
            "message_id": msg.id,
            "sender_name": f"{msg.expediteur.prenom} {msg.expediteur.nom}",
            "text": msg.contenu[:100],
            "time": msg.date_envoi.isoformat(),
            "is_read": bool(msg.est_lu_par_destinataire),
        })

    programmes_queryset = ProgrammeEnvoye.objects.filter(
        patient=patient_profile
    ).exclude(
        id__in=deleted_actions
    ).order_by('-date_envoi')

    unread_programmes_count = programmes_queryset.filter(est_lu=False).count()
    all_programmes = programmes_queryset[:20]

    for programme in all_programmes:
        nombre_exercices = 0
        if isinstance(programme.programme, dict):
            nombre_exercices = sum(len(items or []) for items in programme.programme.values())
        notifications.append({
            "notification_type": "action",
            "action_id": programme.id,
            "message_id": None,
            "sender_name": f"{ergo.prenom} {ergo.nom}".strip() if ergo else "Thérapeute",
            "text": "Programme reçu",
            "details": f"{nombre_exercices} exercice(s) disponible(s)" if nombre_exercices else "Nouveau programme disponible",
            "time": programme.date_envoi.isoformat(),
            "target_url": "/patient/programme/",
            "is_read": bool(programme.est_lu),
        })

    notifications.sort(key=lambda item: item.get("time") or "", reverse=True)
    notifications = notifications[:20]
    unread_count = unread_messages_count + unread_programmes_count

    return JsonResponse({
        "count": unread_count,
        "unread_count": unread_count,
        "total_count": len(notifications),
        "notifications": notifications
    })
@login_required
@require_POST
def patient_read_notification(request, message_id):
    patient_user = request.user

    message = get_object_or_404(
        Message,
        id=message_id,
        expediteur__role='ergo',
        destinataire=patient_user
    )

    if not message.est_lu_par_destinataire:
        message.est_lu_par_destinataire = True
        message.save(update_fields=['est_lu_par_destinataire'])

    return JsonResponse({"success": True})


@login_required
@require_POST
def patient_read_action_notification(request, action_id):
    patient_profile = getattr(request.user, 'patient_profile', None)
    programme = get_object_or_404(
        ProgrammeEnvoye,
        id=action_id,
        patient=patient_profile
    )

    if not programme.est_lu:
        programme.est_lu = True
        programme.save(update_fields=['est_lu'])

    return JsonResponse({"success": True})


@login_required
@require_POST
def patient_read_all_notifications(request):
    patient_profile = getattr(request.user, 'patient_profile', None)
    if not patient_profile:
        return JsonResponse({"success": False, "error": "Profil patient introuvable"}, status=400)

    Message.objects.filter(
        expediteur__role='ergo',
        destinataire=request.user,
        est_lu_par_destinataire=False
    ).update(est_lu_par_destinataire=True)

    ProgrammeEnvoye.objects.filter(
        patient=patient_profile,
        archive=False,
        est_lu=False
    ).update(est_lu=True)

    return JsonResponse({"success": True})


@login_required
@require_POST
def patient_delete_notification(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = request.POST

    notification_type = data.get('notification_type') or data.get('type')
    notification_id = data.get('notification_id') or data.get('id')

    if notification_type not in ['message', 'action'] or not notification_id:
        return JsonResponse({"success": False, "error": "Notification invalide"}, status=400)

    if notification_type == 'message':
        message = get_object_or_404(
            Message,
            id=notification_id,
            expediteur__role='ergo',
            destinataire=request.user
        )
        if not message.est_lu_par_destinataire:
            message.est_lu_par_destinataire = True
            message.save(update_fields=['est_lu_par_destinataire'])

        deleted = set(str(item) for item in request.session.get('patient_deleted_message_notifications', []))
        deleted.add(str(message.id))
        request.session['patient_deleted_message_notifications'] = list(deleted)
    else:
        patient_profile = getattr(request.user, 'patient_profile', None)
        programme = get_object_or_404(
            ProgrammeEnvoye,
            id=notification_id,
            patient=patient_profile
        )
        if not programme.est_lu:
            programme.est_lu = True
            programme.save(update_fields=['est_lu'])

        deleted = set(str(item) for item in request.session.get('patient_deleted_action_notifications', []))
        deleted.add(str(programme.id))
        request.session['patient_deleted_action_notifications'] = list(deleted)

    request.session.modified = True
    return JsonResponse({"success": True})


@login_required
@require_POST
def patient_delete_all_notifications(request):
    patient_profile = getattr(request.user, 'patient_profile', None)
    if not patient_profile:
        return JsonResponse({"success": False, "error": "Profil patient introuvable"}, status=400)

    message_ids = list(Message.objects.filter(
        expediteur__role='ergo',
        destinataire=request.user
    ).values_list('id', flat=True))

    programme_ids = list(ProgrammeEnvoye.objects.filter(
        patient=patient_profile
    ).values_list('id', flat=True))

    Message.objects.filter(id__in=message_ids, est_lu_par_destinataire=False).update(
        est_lu_par_destinataire=True
    )
    ProgrammeEnvoye.objects.filter(id__in=programme_ids, est_lu=False).update(est_lu=True)

    request.session['patient_deleted_message_notifications'] = [str(item) for item in message_ids]
    request.session['patient_deleted_action_notifications'] = [str(item) for item in programme_ids]
    request.session.modified = True

    return JsonResponse({"success": True})
@login_required
def patient_ressources(request):
    compter_visite_patient(request, 'ressources')  
    patient_profile = request.user.patient_profile
    
    # Récupérer TOUS les partages, même ceux qui sont "non_vue", "vue", etc.
    partages = RessourcePatient.objects.select_related('ressource').filter(
        patient=patient_profile
    ).order_by('-date_partage')
    
    patient_resources = []
    
    for partage in partages:
        res = partage.ressource
        
        # Construire l'URL correctement
        if res.type_ressource == "link":
            url = res.url
        elif res.fichier:
            url = res.fichier.url
        else:
            url = ""
        
        patient_resources.append({
            "id": str(res.id),
            "partage_id": partage.id,
            "title": res.titre,
            "description": res.description or "",
            "type": res.type_ressource,
            "date": partage.date_partage.isoformat() if partage.date_partage else "",
            "time": partage.date_partage.strftime('%H:%M') if partage.date_partage else "",
            "views": res.nombre_vues or 0,
            "downloads": res.nombre_telechargements or 0,
            "url": url,
            "is_file": res.type_ressource in ["pdf", "video", "image"],
            "fileName": res.fichier.name.split("/")[-1] if res.fichier else "",
            "is_today": partage.date_partage.date() == timezone.localdate() if partage.date_partage else False,
            "important": partage.statut == "non_vue",
            "statut": partage.statut,
        })
    
    # Pour AJAX (mise à jour automatique)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            "resources": patient_resources
        })
    
    context = {
        "patient_resources": patient_resources,
        "current_lang": _normaliser_code_langue(patient_profile.langue),
    }
    
    return render(request, 'Ressources du patient.html', context)
@login_required
def patient_parametres(request):
    compter_visite_patient(request, 'parametres')
    patient = request.user.patient_profile
    user = request.user
    
    if request.method == 'POST':
        # Mettre à jour les informations
        user.nom = request.POST.get('nom', user.nom)
        user.prenom = request.POST.get('prenom', user.prenom)
        user.email = request.POST.get('email', user.email)
        user.save()
        
        patient.telephone = request.POST.get('telephone', patient.telephone)
        patient.adresse = request.POST.get('adresse', patient.adresse)
        patient.langue = request.POST.get('langue', patient.langue)
        patient.save()
        
        return redirect('patient_parametres')
    
    context = {
        'user': user,
        'patient': patient,
        'settings_initial': _patient_settings_payload(user, patient),
    }
    return render(request, 'parametres.html', context)


def _normaliser_code_langue(langue):
    value = (langue or 'fr').strip().lower()
    mapping = {
        'fr': 'fr',
        'francais': 'fr',
        'français': 'fr',
        'french': 'fr',
        'en': 'en',
        'english': 'en',
        'anglais': 'en',
        'ar': 'ar',
        'arabic': 'ar',
        'arabe': 'ar',
        'العربية': 'ar',
    }
    return mapping.get(value, 'fr')


def _patient_settings_payload(user, patient):
    ergo = get_default_ergo()
    therapist = f"{ergo.prenom} {ergo.nom}".strip() if ergo else ''
    start_date = patient.date_fracture.isoformat() if getattr(patient, 'date_fracture', None) else ''
    return {
        'fullName': f"{user.prenom} {user.nom}".strip(),
        'email': user.email or '',
        'phone': patient.telephone or '',
        'therapist': therapist,
        'startDate': start_date,
        'language': _normaliser_code_langue(patient.langue),
        'darkMode': False,
        'notifications': True,
    }


@login_required
@require_http_methods(["GET", "POST"])
def patient_settings_api(request):
    patient = getattr(request.user, 'patient_profile', None)
    if not patient:
        return JsonResponse({'success': False, 'error': 'Profil patient introuvable.'}, status=403)
    user = request.user

    if request.method == "GET":
        payload = _patient_settings_payload(user, patient)
        payload['darkMode'] = bool(request.session.get('patient_dark_mode', False))
        payload['notifications'] = bool(request.session.get('patient_notifications_enabled', True))
        return JsonResponse({'success': True, 'settings': payload})

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalide'}, status=400)

    full_name = (data.get('fullName') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    language = _normaliser_code_langue(data.get('language'))

    if full_name:
        parts = full_name.split()
        user.prenom = parts[0]
        user.nom = ' '.join(parts[1:]) if len(parts) > 1 else user.nom
    if email:
        existing = User.objects.filter(email__iexact=email).exclude(id=user.id).exists()
        if existing:
            return JsonResponse({'success': False, 'error': 'Cette adresse email est déjà utilisée.'}, status=400)
        user.email = email
        user.username = email
    try:
        user.save()
    except IntegrityError:
        return JsonResponse({'success': False, 'error': 'Cette adresse email est déjà utilisée.'}, status=400)

    if phone:
        patient.telephone = phone
    patient.langue = language
    patient.save(update_fields=['telephone', 'langue'])

    request.session['patient_dark_mode'] = bool(data.get('darkMode', False))
    request.session['patient_notifications_enabled'] = bool(data.get('notifications', True))
    request.session['lang'] = language
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'settings': {
            **_patient_settings_payload(user, patient),
            'darkMode': request.session['patient_dark_mode'],
            'notifications': request.session['patient_notifications_enabled'],
        }
    })


@login_required
@require_POST
def patient_change_password_api(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalide'}, status=400)

    current_password = data.get('currentPassword') or ''
    new_password = data.get('newPassword') or ''
    confirm_password = data.get('confirmPassword') or ''

    if not current_password or not new_password or not confirm_password:
        return JsonResponse({'success': False, 'error': 'Veuillez remplir tous les champs.'}, status=400)
    if new_password != confirm_password:
        return JsonResponse({'success': False, 'error': 'Les mots de passe ne correspondent pas.'}, status=400)
    if len(new_password) < 8:
        return JsonResponse({'success': False, 'error': 'Le nouveau mot de passe doit contenir au moins 8 caractères.'}, status=400)
    if not request.user.check_password(current_password):
        return JsonResponse({'success': False, 'error': 'Mot de passe actuel incorrect.'}, status=400)

    from django.contrib.auth import update_session_auth_hash
    request.user.set_password(new_password)
    request.user.save(update_fields=['password'])
    update_session_auth_hash(request, request.user)
    return JsonResponse({'success': True})


@login_required
@require_POST
def patient_delete_own_account_api(request):
    if getattr(request.user, 'role', '') != 'patient':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    user = request.user
    logout(request)
    user.delete()
    return JsonResponse({'success': True})


# aujour
from django.http import JsonResponse
from datetime import date

# 
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import PatientProfile

@login_required
def modifier_patient(request, patient_id):
    patient = get_object_or_404(PatientProfile, id=patient_id)
    user = patient.user
    
    if request.method == 'POST':
        user.nom = request.POST.get('nom')
        user.prenom = request.POST.get('prenom')
        user.email = request.POST.get('email')
        user.save()
        
        patient.telephone = request.POST.get('telephone')
        patient.date_naissance = request.POST.get('date_naissance')
        patient.save()

        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='patient',
            action='Patient modifié',
            details={
                'nom': user.nom,
                'prenom': user.prenom,
                'email': user.email
            }
        )
        
        messages.success(request, 'Patient modifié avec succès !')
        return redirect('patients')
    
    return render(request, 'modifier_patient.html', {
        'patient': patient,
        'user': user
    }) 
    
    # 

# views.py - Version ULTRA ORGANISÉE ET DÉCORÉE

import io

@csrf_exempt
def generer_pdf_natif(request):
    """Génère un PDF très organisé et décoré"""
    if request.method == 'POST':
        try:
            # Import reportlab localement pour éviter le warning "module non trouvé" au niveau global
            try:
                from reportlab.lib.pagesizes import A4  # type: ignore[import]
                from reportlab.lib import colors  # type: ignore[import]
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore[import]
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether  # type: ignore[import]
                from reportlab.lib.units import cm, mm  # type: ignore[import]
                from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT  # type: ignore[import]
            except ImportError:
                return JsonResponse({'error': 'reportlab non installé ; pip install reportlab', 'success': False}, status=500)

            data = {}
            if request.content_type and 'application/json' in request.content_type:
                try:
                    payload = request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body
                    data = json.loads(payload)
                except (ValueError, UnicodeDecodeError):
                    data = {}
            else:
                for key in request.POST:
                    values = request.POST.getlist(key)
                    data[key] = values if len(values) > 1 else values[0]
            
            # ========== RÉCUPÉRATION DES DONNÉES ==========
            nom = data.get('last_name', '--')
            prenom = data.get('first_name', '--')
            date_naissance = data.get('birth_date', '--')
            sexe = data.get('gender', '--')
            telephone = data.get('phone', '--')
            email = data.get('email', '--')
            adresse = data.get('address', '--')
            nom_affichage = data.get('display_name', '--')
            langue_preferee = data.get('preferred_lang', 'fr')
            username = data.get('username', '--')
            
            fracture_type = data.get('fracture_type', '--')
            fracture_type_autre = data.get('fracture_type_other', '')
            if fracture_type == 'other' and fracture_type_autre:
                fracture_type = fracture_type_autre
                
            fracture_date = data.get('fracture_date', '--')
            cote_atteint = data.get('side', '--')
            main_dominante = "Oui" if data.get('dominant_hand') else "Non"
            
            traitements = data.get('treatment', [])
            if isinstance(traitements, list):
                traitement_texte = []
                for t in traitements:
                    if t == 'Plâtre':
                        traitement_texte.append('Plâtre')
                    elif t == 'Chirurgie':
                        traitement_texte.append('Intervention chirurgicale')
                    elif t == 'Orthèse':
                        traitement_texte.append('Orthèse / attelle')
                    elif t == 'other' and data.get('treatment_other'):
                        traitement_texte.append(f"Autre: {data.get('treatment_other')}")
                    else:
                        traitement_texte.append(t)
                traitement_final = ", ".join(traitement_texte) if traitement_texte else '--'
            else:
                traitement_final = traitements or '--'
            
            douleur_repos = int(data.get('pain_rest', 0))
            douleur_effort = int(data.get('pain_effort', 0))
            raideur_gonflement = data.get('swelling', '--')
            
            limitations = data.get('limits', [])
            if isinstance(limitations, list):
                limitations_texte = []
                for lim in limitations:
                    if lim == 'habillage':
                        limitations_texte.append('Habillage')
                    elif lim == 'toilette':
                        limitations_texte.append('Toilette')
                    elif lim == 'cuisine':
                        limitations_texte.append('Cuisine')
                    elif lim == 'porte':
                        limitations_texte.append('Port de charge')
                    elif lim == 'smartphone':
                        limitations_texte.append('Téléphone')
                    elif lim == 'clavier':
                        limitations_texte.append('Clavier / souris')
                    elif lim == 'conduite':
                        limitations_texte.append('Conduite')
                    elif lim == 'other' and data.get('limits_other'):
                        limitations_texte.append(f"Autre: {data.get('limits_other')}")
                    else:
                        limitations_texte.append(lim)
                limitations_final = ", ".join(limitations_texte) if limitations_texte else 'Aucune'
            else:
                limitations_final = limitations or 'Aucune'
            
            comorbidites = data.get('comorb', [])
            if isinstance(comorbidites, list):
                comorbidites_texte = []
                for com in comorbidites:
                    if com == 'Diabète':
                        comorbidites_texte.append('Diabète')
                    elif com == 'Hypertension':
                        comorbidites_texte.append('Hypertension')
                    elif com == 'Ostéoporose':
                        comorbidites_texte.append('Ostéoporose')
                    elif com == 'Arthrite':
                        comorbidites_texte.append('Arthrite')
                    elif com == 'other' and data.get('comorb_other'):
                        comorbidites_texte.append(f"Autre: {data.get('comorb_other')}")
                    else:
                        comorbidites_texte.append(com)
                comorbidites_final = ", ".join(comorbidites_texte) if comorbidites_texte else 'Aucune'
            else:
                comorbidites_final = comorbidites or 'Aucune'
            
            medicaments = data.get('meds', '--')
            allergies = data.get('allergies', '--')
            
            profession = data.get('job', '--')
            if profession == 'other' and data.get('job_other'):
                profession = data.get('job_other')
            elif profession == 'bureau':
                profession = 'Employé(e) de bureau'
            elif profession == 'manuel':
                profession = 'Travailleur manuel'
            elif profession == 'etudiant':
                profession = 'Étudiant(e)'
            elif profession == 'retraite':
                profession = 'Retraité(e)'
            elif profession == 'sans':
                profession = 'Sans emploi'
            
            impact_travail = data.get('work_impact', '--')
            if impact_travail == 'stop':
                impact_travail = 'Arrêt complet'
            elif impact_travail == 'light':
                impact_travail = 'Travail adapté / léger'
            elif impact_travail == 'remote':
                impact_travail = 'Télétravail possible'
            elif impact_travail == 'none':
                impact_travail = "Pas d'impact"
            elif impact_travail == 'na':
                impact_travail = 'Non applicable'
            
            activites = data.get('activities', [])
            if isinstance(activites, list):
                activites_texte = []
                for act in activites:
                    if act == 'Sport':
                        activites_texte.append('Sport')
                    elif act == 'Cuisine':
                        activites_texte.append('Cuisine')
                    elif act == 'Bricolage/Jardinage':
                        activites_texte.append('Bricolage/Jardinage')
                    elif act == 'Écriture/Dessin':
                        activites_texte.append('Écriture/Dessin')
                    elif act == 'Informatique':
                        activites_texte.append('Informatique')
                    elif act == 'Musique':
                        activites_texte.append('Musique')
                    elif act == 'Artisanat':
                        activites_texte.append('Artisanat')
                    elif act == 'other' and data.get('activities_other'):
                        activites_texte.append(f"Autre: {data.get('activities_other')}")
                    else:
                        activites_texte.append(act)
                activites_final = ", ".join(activites_texte) if activites_texte else 'Aucune'
            else:
                activites_final = activites or 'Aucune'
            
            objectif = data.get('main_goal', '--')
            if objectif == 'other' and data.get('main_goal_other'):
                objectif = data.get('main_goal_other')
            elif objectif == 'adl':
                objectif = 'Retrouver l\'autonomie (toilette, habillage, soins personnels)'
            elif objectif == 'prise':
                objectif = 'Améliorer la prise / préhension (tenir un verre, ouvrir un bocal)'
            elif objectif == 'douleur':
                objectif = 'Diminuer la douleur et reprendre les gestes sans appréhension'
            elif objectif == 'mobilite':
                objectif = 'Récupérer la mobilité (flexion/extension, pronation/supination)'
            elif objectif == 'force':
                objectif = 'Récupérer la force (porter, pousser, tirer)'
            elif objectif == 'fine':
                objectif = 'Améliorer la motricité fine (écriture, boutonner, smartphone)'
            elif objectif == 'travail':
                objectif = 'Reprendre le travail / gestes professionnels'
            elif objectif == 'loisirs':
                objectif = 'Reprendre les loisirs (sport, musique, bricolage)'
            
            source = data.get('source', '--')
            if source == 'other' and data.get('source_other'):
                source = data.get('source_other')
            elif source == 'medecin':
                source = 'Recommandation médecin'
            elif source == 'ergo':
                source = 'Recommandation ergothérapeute'
            elif source == 'internet':
                source = 'Recherche internet'
            elif source == 'rs':
                source = 'Réseaux sociaux'
            elif source == 'bouche':
                source = 'Bouche-à-oreille'
            
            cgu_accepte = "✓ Accepté" if data.get('cgu') else "✕ Non accepté"
            consentement_sante = "✓ Accepté" if data.get('privacy') else "✕ Non accepté"
            recevoir_rappels = "✓ Oui" if data.get('tips_optin') else "✕ Non"
            
            sexe_aff = 'Femme' if sexe == 'F' else ('Homme' if sexe == 'M' else '--')
            
            raideur_aff = {
                'light': 'Léger',
                'moderate': 'Modéré',
                'high': 'Important',
                'unsure': 'Je ne sais pas'
            }.get(raideur_gonflement, raideur_gonflement)
            
            langue_aff = {
                'fr': 'Français',
                'en': 'English',
                'ar': 'العربية'
            }.get(langue_preferee, langue_preferee)
            
            if fracture_date != '--':
                try:
                    d = datetime.strptime(fracture_date, '%Y-%m-%d')
                    fracture_date_aff = d.strftime('%d/%m/%Y')
                    now = datetime.now()
                    diff = now - d
                    jours = diff.days
                    if jours >= 7:
                        semaines = jours // 7
                        info_date = f"Il y a environ {semaines} semaine(s)"
                    else:
                        info_date = f"Il y a {jours} jour(s)"
                except:
                    fracture_date_aff = fracture_date
                    info_date = ""
            else:
                fracture_date_aff = fracture_date
                info_date = ""
            
            if date_naissance != '--':
                try:
                    d = datetime.strptime(date_naissance, '%Y-%m-%d')
                    date_naissance_aff = d.strftime('%d/%m/%Y')
                except:
                    date_naissance_aff = date_naissance
            else:
                date_naissance_aff = date_naissance
            
            # ========== CRÉATION DU PDF ULTRA ORGANISÉ ==========
            buffer = io.BytesIO()
            
            PRIMARY = colors.HexColor('#2E8B57')
            PRIMARY_LIGHT = colors.HexColor('#E8F5E9')
            GRAY_BG = colors.HexColor('#F8F9FA')
            BORDER = colors.HexColor('#E0E0E0')
            
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                   rightMargin=1.8*cm, leftMargin=1.8*cm,
                                   topMargin=1.8*cm, bottomMargin=1.8*cm)
            
            styles = getSampleStyleSheet()
            
            # Styles organisés
            title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=PRIMARY, spaceAfter=5, alignment=TA_CENTER, fontName='Helvetica-Bold')
            subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#666666'), spaceAfter=20, alignment=TA_CENTER)
            section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=16, textColor=PRIMARY, spaceAfter=12, spaceBefore=20, fontName='Helvetica-Bold')
            sub_section_style = ParagraphStyle('SubSection', parent=styles['Heading3'], fontSize=12, textColor=PRIMARY, spaceAfter=8, spaceBefore=10, fontName='Helvetica-Bold')
            label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=10, textColor=PRIMARY, fontName='Helvetica-Bold')
            value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#333333'))
            small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#666666'))
            
            story = []
            
            # ========== EN-TÊTE DÉCORÉ ==========
            # Bande supérieure
            header_line = Table([['']], colWidths=[17*cm], rowHeights=[0.3*cm])
            header_line.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PRIMARY)]))
            story.append(header_line)
            story.append(Spacer(1, 0.3*cm))
            
            story.append(Paragraph("📄 SmartWrist Rehab", title_style))
            story.append(Paragraph("Fiche d'inscription patient", subtitle_style))
            story.append(Paragraph(f"📅 Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", small_style))
            story.append(Spacer(1, 0.5*cm))
            
            header_line_bottom = Table([['']], colWidths=[17*cm], rowHeights=[0.2*cm])
            header_line_bottom.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PRIMARY_LIGHT)]))
            story.append(header_line_bottom)
            story.append(Spacer(1, 1*cm))
            
            # ========== SECTION 1: IDENTITÉ & CONTACT ==========
            story.append(Paragraph("📇 1. IDENTITÉ & CONTACT", section_style))
            story.append(Paragraph("Mieux vous connaître pour vous accompagner de façon personnalisée", small_style))
            story.append(Spacer(1, 0.5*cm))
            
            identite_data = [
                ["Nom complet", f"{nom} {prenom}"],
                ["Date de naissance", date_naissance_aff],
                ["Sexe", sexe_aff],
                ["Téléphone", telephone],
                ["Email", email],
                ["Adresse", adresse],
                ["Nom à afficher", nom_affichage],
                ["Langue préférée", langue_aff],
            ]
            
            identite_table = Table(identite_data, colWidths=[4.5*cm, 10.5*cm])
            identite_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), PRIMARY_LIGHT),
                ('TEXTCOLOR', (0,0), (0,-1), PRIMARY),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER),
                ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, GRAY_BG]),
            ]))
            story.append(identite_table)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 2: VOTRE FRACTURE ==========
            story.append(Paragraph("2. VOTRE FRACTURE", section_style))
            story.append(Paragraph("Ces informations restent confidentielles et aident à adapter votre suivi", small_style))
            story.append(Spacer(1, 0.5*cm))
            
            fracture_data = [
                ["Type de fracture", fracture_type],
                ["Date de la fracture", fracture_date_aff],
                ["Délai", info_date],
                ["Côté atteint", cote_atteint],
                ["Main dominante", main_dominante],
                ["Traitement reçu", traitement_final],
                ["Raideur / gonflement", raideur_aff],
            ]
            
            fracture_table = Table(fracture_data, colWidths=[4.5*cm, 10.5*cm])
            fracture_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), PRIMARY_LIGHT),
                ('TEXTCOLOR', (0,0), (0,-1), PRIMARY),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(fracture_table)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 3: DOULEUR ==========
            story.append(Paragraph("3. ÉVALUATION DE LA DOULEUR", section_style))
            story.append(Spacer(1, 0.3*cm))
            
            # Barres de douleur stylisées
            pain_data = [
                ["Au repos", f"{douleur_repos}/10", "■" * douleur_repos + "□" * (10 - douleur_repos)],
                ["À l'effort", f"{douleur_effort}/10", "■" * douleur_effort + "□" * (10 - douleur_effort)],
            ]
            
            pain_table = Table(pain_data, colWidths=[3.5*cm, 1.5*cm, 10*cm])
            pain_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), PRIMARY_LIGHT),
                ('TEXTCOLOR', (0,0), (0,-1), PRIMARY),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(pain_table)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 4: LIMITATIONS ==========
            story.append(Paragraph("4. LIMITATIONS ACTUELLES", section_style))
            story.append(Paragraph("Activités difficiles", small_style))
            story.append(Spacer(1, 0.3*cm))
            
            limits_box = Table([[Paragraph(limitations_final, value_style)]], colWidths=[15*cm])
            limits_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), GRAY_BG),
                ('TOPPADDING', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('BOX', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(limits_box)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 5: ANTÉCÉDENTS ==========
            story.append(Paragraph("5. ANTÉCÉDENTS MÉDICAUX", section_style))
            story.append(Spacer(1, 0.3*cm))
            
            antecedents_data = [
                ["Autres problèmes de santé", comorbidites_final],
                ["Médicaments actuels", medicaments],
                ["Allergies", allergies],
            ]
            
            antecedents_table = Table(antecedents_data, colWidths=[4.5*cm, 10.5*cm])
            antecedents_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), PRIMARY_LIGHT),
                ('TEXTCOLOR', (0,0), (0,-1), PRIMARY),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(antecedents_table)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 6: PROFESSION ==========
            story.append(Paragraph("6. CONTEXTE PROFESSIONNEL", section_style))
            story.append(Paragraph("Dites-nous ce qui compte pour vous", small_style))
            story.append(Spacer(1, 0.3*cm))
            
            pro_data = [
                ["Profession / statut", profession],
                ["Impact sur le travail", impact_travail],
            ]
            
            pro_table = Table(pro_data, colWidths=[4.5*cm, 10.5*cm])
            pro_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), PRIMARY_LIGHT),
                ('TEXTCOLOR', (0,0), (0,-1), PRIMARY),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(pro_table)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 7: ACTIVITÉS ==========
            story.append(Paragraph("7. ACTIVITÉS IMPORTANTES", section_style))
            story.append(Paragraph("Avant la fracture", small_style))
            story.append(Spacer(1, 0.3*cm))
            
            activities_box = Table([[Paragraph(activites_final, value_style)]], colWidths=[15*cm])
            activities_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), GRAY_BG),
                ('TOPPADDING', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('BOX', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(activities_box)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 8: OBJECTIF ==========
            story.append(Paragraph("8. OBJECTIF PRINCIPAL DE RÉÉDUCATION", section_style))
            story.append(Spacer(1, 0.3*cm))
            
            objectif_box = Table([[Paragraph(objectif, value_style)]], colWidths=[15*cm])
            objectif_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), PRIMARY_LIGHT),
                ('TOPPADDING', (0,0), (-1,-1), 15),
                ('BOTTOMPADDING', (0,0), (-1,-1), 15),
                ('LEFTPADDING', (0,0), (-1,-1), 15),
                ('RIGHTPADDING', (0,0), (-1,-1), 15),
                ('BOX', (0,0), (-1,-1), 2, PRIMARY),
                ('ROUNDEDCORNERS', (0,0), (-1,-1), 8),
            ]))
            story.append(objectif_box)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 9: COMPTE ==========
            story.append(Paragraph("9. COMPTE & SÉCURITÉ", section_style))
            story.append(Spacer(1, 0.3*cm))
            
            compte_data = [
                ["Nom d'utilisateur", username],
                ["Mot de passe", data.get('password', '--')],
            ]
            compte_table = Table(compte_data, colWidths=[4.5*cm, 10.5*cm])
            compte_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), PRIMARY_LIGHT),
                ('TEXTCOLOR', (0,0), (0,-1), PRIMARY),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(compte_table)
            story.append(Spacer(1, 0.8*cm))
            
            # ========== SECTION 10: CONSENTEMENTS ==========
            story.append(Paragraph("10. CONSENTEMENTS", section_style))
            story.append(Spacer(1, 0.3*cm))
            
            consent_data = [
                ["CGU acceptées", cgu_accepte],
                ["Consentement santé", consentement_sante],
                ["Recevoir des rappels", recevoir_rappels],
                ["Source de connaissance", source],
            ]
            
            consent_table = Table(consent_data, colWidths=[4.5*cm, 10.5*cm])
            consent_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (0,-1), PRIMARY_LIGHT),
                ('TEXTCOLOR', (0,0), (0,-1), PRIMARY),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(consent_table)
            story.append(Spacer(1, 0.5*cm))
            
            # Mention Google
            google_style = ParagraphStyle('Google', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#666666'), alignment=TA_CENTER)
            story.append(Paragraph("Consentement recueilli auprès du patient via un formulaire Google", google_style))
            story.append(Spacer(1, 0.5*cm))
            
            # ========== FOOTER DÉCORÉ ==========
            footer_line = Table([['']], colWidths=[17*cm], rowHeights=[0.2*cm])
            footer_line.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PRIMARY_LIGHT)]))
            story.append(footer_line)
            story.append(Spacer(1, 0.3*cm))
            
            footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
            story.append(Paragraph("© 2026 SmartWrist Rehab · Tous droits réservés", footer_style))
            
            footer_line_bottom = Table([['']], colWidths=[17*cm], rowHeights=[0.1*cm])
            footer_line_bottom.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PRIMARY)]))
            story.append(footer_line_bottom)
            
            # Génération
            doc.build(story)
            pdf = buffer.getvalue()
            buffer.close()
            
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="fiche_patient_{nom}_{prenom}.pdf"'
            return response
            
        except Exception as e:
            import traceback
            print("Erreur PDF:", traceback.format_exc())
            return JsonResponse({'error': str(e), 'success': False}, status=500)
    
    return JsonResponse({'error': 'Méthode non autorisée', 'success': False}, status=405)
import json

@login_required
@csrf_exempt
def envoyer_message_patient(request):
    """Envoyer un message à un patient depuis la page patients"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            patient_id = data.get('patient_id')
            sujet = data.get('sujet')
            contenu = data.get('message')

            if not patient_id or not sujet or not contenu:
                return JsonResponse({
                    'success': False,
                    'error': 'Données manquantes'
                }, status=400)

            # IMPORTANT :
            # ici patient_id = ID du PatientProfile, pas du User
            patient_profile = get_object_or_404(PatientProfile, id=patient_id)
            patient_user = patient_profile.user

            # Création du message
            nouveau_message = Message.objects.create(
                expediteur=request.user,              # ergothérapeute
                destinataire=patient_user,            # vrai compte utilisateur du patient
                sujet=sujet,
                contenu=contenu,
                est_lu_par_destinataire=False
            )

            tracer_action(
                utilisateur=request.user,
                patient=patient_profile,
                type_action='message',
                action='Message envoyé au patient',
                details={
                    'message_id': nouveau_message.id,
                    'sujet': sujet,
                    'contenu': contenu[:100]
                }
            )

            return JsonResponse({
                'success': True,
                'message': 'Message envoyé avec succès'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Méthode non autorisée'
    }, status=405)


# ==================== MESSAGES / COMMUNICATION ====================
from django.shortcuts import render, get_object_or_404
from .models import Message


@login_required
def messages_page(request):
    return render(request, "Messages.html")





from django.contrib.auth import get_user_model

User = get_user_model()



@login_required
def messages_conversations(request):
    ergo = get_default_ergo()

    if not ergo or request.user != ergo:
        return JsonResponse({"conversations": []})

    filter_type = request.GET.get("filter", "all")
    search = request.GET.get("search", "").strip()
    patient_filter = request.GET.get("patient_id")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    # Récupérer TOUS les patients (users avec role='patient')
    patients = User.objects.filter(
        role='patient',
        patient_profile__isnull=False
    ).distinct()

    conversations = []

    for patient in patients:
        qs = Message.objects.filter(
            Q(expediteur=patient, destinataire=ergo) |
            Q(expediteur=ergo, destinataire=patient)
        )

        if date_from:
            qs = qs.filter(date_envoi__date__gte=date_from)

        if date_to:
            qs = qs.filter(date_envoi__date__lte=date_to)

        if patient_filter and patient_filter != "all" and str(patient.id) != str(patient_filter):
            continue

        if search:
            qs = qs.filter(
                Q(contenu__icontains=search) |
                Q(piece_jointe_nom__icontains=search)
            )

        if not qs.exists():
            continue

        if filter_type == "unread":
            if not qs.filter(
                expediteur=patient,
                destinataire=ergo,
                est_lu_par_destinataire=False
            ).exists():
                continue

        elif filter_type == "attachments":
            if not qs.filter(piece_jointe__isnull=False).exclude(piece_jointe="").exists():
                continue

        elif filter_type == "sent":
            if not qs.filter(expediteur=ergo, destinataire=patient).exists():
                continue

        elif filter_type == "received":
            if not qs.filter(expediteur=patient, destinataire=ergo).exists():
                continue

        dernier_message = qs.order_by("-date_envoi").first()

        non_lus = Message.objects.filter(
            expediteur=patient,
            destinataire=ergo,
            est_lu_par_destinataire=False
        ).count()

        conversations.append({
            "id": patient.id,  # â† ID du User
            "nom": patient.nom,
            "prenom": patient.prenom,
            "initiales": f"{patient.nom[:1]}{patient.prenom[:1]}".upper() if patient.nom and patient.prenom else "P",
            "dernier_message": dernier_message.contenu if dernier_message else "",
            "dernier_message_date": dernier_message.date_envoi.isoformat() if dernier_message else "",
            "non_lus": non_lus,
        })

    conversations.sort(
        key=lambda x: x["dernier_message_date"] or "",
        reverse=True
    )

    return JsonResponse({"conversations": conversations})
@login_required
def messages_get(request, patient_id):
    ergo = get_default_ergo()

    if not ergo or request.user != ergo:
        return JsonResponse({
            "patient_name": "",
            "messages": [],
            "is_online": False,
            "last_seen": None,
        })

    patient = get_object_or_404(User, id=patient_id, patient_profile__isnull=False)

    filter_type = request.GET.get("filter", "all")
    search = request.GET.get("search", "").strip()
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    qs = Message.objects.filter(
        Q(expediteur=ergo, destinataire=patient) |
        Q(expediteur=patient, destinataire=ergo)
    ).select_related("reponse_a").order_by("date_envoi")

    if filter_type == "unread":
        qs = qs.filter(
            expediteur=patient,
            destinataire=ergo,
            est_lu_par_destinataire=False
        )
    elif filter_type == "attachments":
        qs = qs.filter(piece_jointe__isnull=False).exclude(piece_jointe="")
    elif filter_type == "sent":
        qs = qs.filter(expediteur=ergo)
    elif filter_type == "received":
        qs = qs.filter(expediteur=patient)

    if search:
        qs = qs.filter(
            Q(contenu__icontains=search) |
            Q(piece_jointe_nom__icontains=search)
        )

    if date_from:
        qs = qs.filter(date_envoi__date__gte=date_from)

    if date_to:
        qs = qs.filter(date_envoi__date__lte=date_to)

    mark_read = request.GET.get("mark_read") == "1"

    if mark_read:
        Message.objects.filter(
                expediteur=patient,
                destinataire=ergo,
                est_lu_par_destinataire=False
        ).update(est_lu_par_destinataire=True)

    messages_list = []

    for msg in qs:
        file_type = msg.piece_jointe_type or ""
        if not file_type and msg.piece_jointe:
            mime, _ = mimetypes.guess_type(msg.piece_jointe.name)
            if mime:
                if mime.startswith("image"):
                    file_type = "image"
                elif mime.startswith("video"):
                    file_type = "video"
                elif mime.startswith("audio"):
                    file_type = "audio"
                elif "pdf" in mime:
                    file_type = "pdf"
                else:
                    file_type = "file"
            else:
                file_type = "file"

        messages_list.append({
            "id": msg.id,
            "text": msg.contenu,
            "subject": msg.sujet,
            "sender": "therapist" if msg.expediteur == ergo else "patient",
            "time": msg.date_envoi.isoformat(),
            "attachment": msg.piece_jointe.url if msg.piece_jointe else None,
            "attachment_type": file_type,
            "attachment_name": msg.piece_jointe_nom or "",
            "is_read": msg.est_lu_par_destinataire if msg.expediteur == ergo else True,
            "is_edited": bool(msg.date_modification),
            "seen": msg.est_lu_par_destinataire if msg.expediteur == ergo else None,
            "is_pinned": msg.est_epingle,
            "reply_to": {
                "id": msg.reponse_a.id,
                "text": msg.reponse_a.contenu[:80] if msg.reponse_a and msg.reponse_a.contenu else "[Pièce jointe]",
                "sender": "therapist" if msg.reponse_a and msg.reponse_a.expediteur == ergo else "patient",
            } if msg.reponse_a else None,
        })

    return JsonResponse({
        "patient_name": f"{patient.prenom} {patient.nom}",
        "messages": messages_list,
        "is_online": patient.last_seen and (timezone.now() - patient.last_seen).total_seconds() < 60,
        "last_seen": patient.last_seen.isoformat() if patient.last_seen else None,
    })

@login_required
def messages_notifications(request):
    current_user = request.user

    if ergo.role != 'ergo':
        return JsonResponse({
            "count": 0,
            "notifications": []
        })

    unread_messages = Message.objects.filter(
        destinataire=ergo,
        expediteur__role='patient',
        est_lu_par_destinataire=False
    ).select_related("expediteur").order_by("-date_envoi")[:10]

    notifications = []
    for msg in unread_messages:
        notifications.append({
            "message_id": msg.id,
            "patient_id": msg.expediteur.id,
            "patient_name": f"{msg.expediteur.prenom} {msg.expediteur.nom}",
            "initiales": f"{msg.expediteur.nom[:1]}{msg.expediteur.prenom[:1]}".upper() if msg.expediteur.nom and msg.expediteur.prenom else "P",
            "text": msg.contenu[:80],
            "time": msg.date_envoi.isoformat(),
            "attachment_name": msg.piece_jointe_nom or "",
            "has_attachment": bool(msg.piece_jointe),
        })

    return JsonResponse({
        "count": unread_messages.count(),
        "notifications": notifications
    })

@login_required
def messages_unread(request):
    ergo = request.user
    unread_count = Message.objects.filter(
        destinataire=ergo,
        est_lu_par_destinataire=False
    ).count()
    return JsonResponse({"unread_count": unread_count})

@login_required
@require_POST
def messages_delete(request, patient_id):
    try:
        ergo = request.user

        if ergo.role != 'ergo':
            return JsonResponse({
                "success": False,
                "error": "Utilisateur non autorisé"
            }, status=403)

        patient = get_object_or_404(
            User,
            id=patient_id,
            role='patient',
            patient_profile__isnull=False
        )

        patient_profile = getattr(patient, 'patient_profile', None)

        qs = Message.objects.filter(
            Q(expediteur=ergo, destinataire=patient) |
            Q(expediteur=patient, destinataire=ergo)
        )

        total = qs.count()

        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='message',
            action='Conversation supprimée',
            details={
                'patient': f"{patient.prenom} {patient.nom}",
                'messages_supprimes': total
            }
        )

        qs.delete()

        return JsonResponse({
            "success": True,
            "deleted_count": total
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)

@login_required
@csrf_exempt
def ajouter_exercice_au_programme_api(request):
    """API pour ajouter un exercice de la bibliothèque au programme"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            bibliotheque_id = data.get('bibliotheque_id')
            programme_id = data.get('programme_id')
            
            from .models import BibliothequeExercice, ProgrammeExercice, Exercice
            from django.shortcuts import get_object_or_404
            
            exercice_biblio = get_object_or_404(BibliothequeExercice, id=bibliotheque_id)
            programme = get_object_or_404(ProgrammeExercice, id=programme_id)
            
            nouvel_exercice = Exercice.objects.create(
                programme=programme,
                bibliotheque_exercice=exercice_biblio,
                nom=exercice_biblio.nom,
                categorie=exercice_biblio.categorie,
                series=exercice_biblio.series,
                repetitions=exercice_biblio.repetitions,
                temps_exercice=exercice_biblio.temps_exercice,
                objectif=exercice_biblio.objectif,
                instructions=exercice_biblio.instructions,
                materiel_necessaire=exercice_biblio.materiel_necessaire,
                ordre=programme.exercices.count() + 1
            )
            tracer_action(
                utilisateur=request.user,
                patient=programme.patient,
                type_action='programme',
                action='Exercice ajouté au programme via API',
                details={
                    'exercice': nouvel_exercice.nom,
                    'programme': programme.nom
                }
            )
            programme_actualise = programme.exercices.all().order_by('-id')
            _sauvegarder_programme_envoye(
                programme.patient,
                _construire_programme_patient(programme_actualise, mode='programme_complet')
            )

            return JsonResponse({'success': True, 'exercice_id': nouvel_exercice.id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)


def tracer_action(utilisateur, type_action, action, patient=None, details=None):
    HistoriqueAction.objects.create(
        utilisateur=utilisateur,
        patient=patient,
        type_action=type_action,
        action=action,
        details=details or {}
    )


def _historique_queryset_for_user(user, patient_id='all'):
    queryset = HistoriqueAction.objects.select_related(
        'patient__user',
        'utilisateur'
    )

    if getattr(user, 'role', '') == 'patient' and hasattr(user, 'patient_profile'):
        return queryset.filter(patient=user.patient_profile)

    if patient_id != 'all' and patient_id:
        return queryset.filter(patient_id=patient_id)

    return queryset.all()


def _repair_history_text(value):
    if not isinstance(value, str) or not value:
        return value

    repaired = value
    markers = ("\u00c3", "\u00e2", "\u00f0", "\ufffd")
    if any(marker in repaired for marker in markers):
        for encoding in ("cp1252", "latin1"):
            try:
                candidate = repaired.encode(encoding).decode("utf-8")
            except Exception:
                continue
            if candidate:
                repaired = candidate
                break

    replacements = {
        "therapeute": "thérapeute",
        "Resultat": "Résultat",
        "resultat": "résultat",
    }
    for source, target in replacements.items():
        repaired = repaired.replace(source, target)
    return repaired


def _history_actor_label(event, viewer):
    if event.utilisateur_id == viewer.id:
        return "Vous"
    role = getattr(event.utilisateur, "role", "")
    if role == "patient":
        return "Le patient"
    return "L’ergothérapeute"


def _format_historique_event_for_display(event, viewer):
    action = _repair_history_text(event.action or "")
    details = event.details if isinstance(event.details, dict) else {}
    actor = _history_actor_label(event, viewer)

    programme_nom = _repair_history_text(details.get("programme") or details.get("nom") or "")
    exercice_nom = _repair_history_text(details.get("exercice") or "")
    commentaire = _repair_history_text(details.get("commentaire") or "")
    message_preview = _repair_history_text(
        details.get("contenu")
        or details.get("message")
        or details.get("nouveau_texte")
        or ""
    )

    action_lower = action.lower()
    title = action or "Action"
    description = ""

    if "visite -" in action_lower or event.type_action == "visite":
        page = _repair_history_text(details.get("page") or action.replace("Visite -", "").strip())
        labels = {
            "mon_programme": "programme patient",
            "program": "onglet programme",
            "results": "onglet résultats",
            "communication": "onglet communication",
            "history": "onglet historique",
            "media": "onglet médias",
            "progression": "progression",
            "ressources": "ressources",
            "dashboard": "tableau de bord",
        }
        page_label = labels.get(page, page or "plateforme")
        title = "Activité patient"
        description = f"{actor} a ouvert {page_label}."
        if details.get("motif"):
            description += f" Motif : {_repair_history_text(str(details.get('motif')))}."
    elif "programme consult" in action_lower:
        title = "Consultation du programme"
        if getattr(viewer, "role", "") == "patient":
            description = "Vous avez consulté votre programme."
        elif programme_nom:
            description = f"{actor} a consulté le programme « {programme_nom} »."
        else:
            description = f"{actor} a consulté le programme du patient."
    elif "programme créé" in action_lower or "programme cree" in action_lower:
        title = "Création du programme"
        description = (
            f"{actor} a créé le programme « {programme_nom} »."
            if programme_nom else
            f"{actor} a créé un programme."
        )
    elif "exercices ajoutés au programme" in action_lower or "exercices ajoutes au programme" in action_lower:
        title = "Ajout d’exercices au programme"
        nombre = details.get("nombre")
        if programme_nom and nombre:
            description = f"{actor} a ajouté {nombre} exercice(s) au programme « {programme_nom} »."
        elif programme_nom:
            description = f"{actor} a ajouté des exercices au programme « {programme_nom} »."
        else:
            description = f"{actor} a ajouté des exercices au programme."
    elif "exercice ajouté au programme" in action_lower or "exercice ajoute au programme" in action_lower:
        title = "Ajout d’un exercice au programme"
        if exercice_nom and programme_nom:
            description = f"{actor} a ajouté l’exercice « {exercice_nom} » au programme « {programme_nom} »."
        elif exercice_nom:
            description = f"{actor} a ajouté l’exercice « {exercice_nom} » au programme."
    elif "exercice supprimé du programme" in action_lower or "exercice supprime du programme" in action_lower:
        title = "Suppression d’un exercice du programme"
        if exercice_nom and programme_nom:
            description = f"{actor} a supprimé l’exercice « {exercice_nom} » du programme « {programme_nom} »."
        elif exercice_nom:
            description = f"{actor} a supprimé l’exercice « {exercice_nom} » du programme."
    elif "résultat exercice envoyé" in action_lower or "resultat exercice envoye" in action_lower:
        title = "Résultat envoyé"
        if exercice_nom:
            description = f"{actor} a envoyé un résultat pour l’exercice « {exercice_nom} »."
        else:
            description = f"{actor} a envoyé un résultat d’exercice."
        motif_parts = []
        if details.get("douleur") not in (None, ""):
            motif_parts.append(f"douleur {details.get('douleur')}/10")
        if details.get("satisfaction") not in (None, ""):
            motif_parts.append(f"satisfaction {details.get('satisfaction')}/5")
        if details.get("resultat"):
            motif_parts.append(f"résultat : {_repair_history_text(str(details.get('resultat')))[:80]}")
        if details.get("difficultes"):
            motif_parts.append(f"difficultés : {_repair_history_text(str(details.get('difficultes')))[:80]}")
        if motif_parts:
            description += " Motif : " + " ; ".join(motif_parts) + "."
    elif "resultat exercice modifie" in action_lower or "résultat exercice modifié" in action_lower:
        title = "Résultat modifié"
        description = f"{actor} a modifié un résultat d’exercice."
        if exercice_nom:
            description = f"{actor} a modifié le résultat de l’exercice « {exercice_nom} »."
        details_motif = []
        if details.get("douleur") not in (None, ""):
            details_motif.append(f"douleur {details.get('douleur')}/10")
        if details.get("satisfaction") not in (None, ""):
            details_motif.append(f"satisfaction {details.get('satisfaction')}/5")
        if details_motif:
            description += " Motif : " + " ; ".join(details_motif) + "."
    elif "resultat exercice supprime" in action_lower or "résultat exercice supprimé" in action_lower:
        title = "Résultat supprimé"
        description = f"{actor} a supprimé un résultat d’exercice."
        if exercice_nom:
            description = f"{actor} a supprimé le résultat de l’exercice « {exercice_nom} »."
    elif "résultat validé" in action_lower or "resultat valide" in action_lower:
        title = "Résultat validé"
        if exercice_nom:
            description = f"{actor} a validé le résultat de l’exercice « {exercice_nom} »."
        else:
            description = f"{actor} a validé un résultat."
        if commentaire:
            description += f" Motif : {commentaire}"
    elif "resultat refuse" in action_lower or "résultat refusé" in action_lower:
        title = "Résultat refusé"
        if exercice_nom:
            description = f"{actor} a refusé le résultat de l’exercice « {exercice_nom} »."
        else:
            description = f"{actor} a refusé un résultat."
        if commentaire:
            description += f" Motif : {commentaire}"
    elif "commentaire thérapeute" in action_lower or "commentaire therapeute" in action_lower:
        title = "Commentaire thérapeute"
        description = f"{actor} a ajouté un commentaire sur un résultat."
        if commentaire:
            description += f" Motif : {commentaire}"
    elif "message envoyé" in action_lower or "message envoye" in action_lower:
        title = "Message envoyé"
        description = f"{actor} a envoyé un message."
        if message_preview:
            description += f" « {message_preview[:120]} »"
    elif "message modifi" in action_lower:
        title = "Message modifié"
        description = f"{actor} a modifié un message."
        if message_preview:
            description += f" Motif : « {message_preview[:120]} »"
    elif "message supprim" in action_lower:
        title = "Message supprimé"
        description = f"{actor} a supprimé un message."
        if message_preview:
            description += f" Motif : « {message_preview[:120]} »"

    if not description:
        detail_lines = []
        for key, value in details.items():
            if value in (None, "", [], {}):
                continue
            detail_lines.append(f"{_repair_history_text(str(key))} : {_repair_history_text(str(value))}")
        description = " | ".join(detail_lines)

    target_url = None
    viewer_role = getattr(viewer, "role", "")
    patient_profile = getattr(event, "patient", None)
    patient_user = getattr(patient_profile, "user", None) if patient_profile else None

    if viewer_role == "patient":
        if event.type_action == "message" or "message" in action_lower:
            target_url = f"{reverse('patient_programme')}?tab=communication"
        elif "résultat" in action_lower or "resultat" in action_lower:
            target_url = f"{reverse('patient_programme')}?tab=results"
        elif event.type_action == "programme" or "programme" in action_lower:
            target_url = f"{reverse('patient_programme')}?tab=program"
        elif event.type_action == "ressource":
            target_url = reverse('patient_ressources')
        elif event.type_action == "patient":
            target_url = reverse('patient_dashboard')
    else:
        if (event.type_action == "message" or "message" in action_lower) and patient_user:
            target_url = f"{reverse('Messages')}?patient_id={patient_user.id}"
        elif (event.type_action == "programme" or "programme" in action_lower) and patient_profile:
            target_url = f"{reverse('Programmes')}?patient_id={patient_profile.id}"
        elif event.type_action == "ressource" and patient_profile:
            target_url = f"{reverse('Ressources')}?patient_id={patient_profile.id}"
        elif event.type_action == "dossier" and patient_profile:
            evaluation_id = details.get("evaluation_id")
            target_url = f"{reverse('Dossiers')}?patient_id={patient_profile.id}"
            if evaluation_id:
                target_url += f"&mode=edit_evaluation&evaluation_id={evaluation_id}"
        elif event.type_action == "patient" and patient_profile:
            target_url = reverse('patient_detail', kwargs={'id': patient_profile.id})
        elif event.type_action == "ia" and patient_profile:
            target_url = f"{reverse('IA')}?patient_id={patient_profile.id}"

    return {
        "title": title,
        "description": description,
        "action": action,
        "target_url": target_url,
    }

@login_required
def conversation(request, patient_id):
    ergo_user = request.user
    patient_user = User.objects.get(id=patient_id, role='patient')

    messages_list = Message.objects.filter(
        expediteur=ergo_user,
        destinataire=patient_user
    ) | Message.objects.filter(
        expediteur=patient_user,
        destinataire=ergo_user
    )

    messages_list = messages_list.order_by('date_envoi')

    context = {
        'patient': patient_user,
        'messages': messages_list,
    }
    return render(request, 'messages/conversation.html', context)

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Message



@login_required
def new_message(request):
    patients = User.objects.filter(patient_profile__isnull=False)

    if request.method == "POST":
        patient_id = request.POST.get("patient")
        text = request.POST.get("text")
        fichier = request.FILES.get("piece_jointe")

        patient = get_object_or_404(User, id=patient_id)

        message = Message.objects.create(
            expediteur=request.user,
            destinataire=patient,
            sujet="Message",
            contenu=text if text else "[Pièce jointe]"
        )

        if fichier:
            message.piece_jointe = fichier
            message.piece_jointe_nom = fichier.name
            message.piece_jointe_type = fichier.content_type
            message.save()

        patient_profile = getattr(patient, 'patient_profile', None)

        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='message',
            action='Message envoyé',
            details={
                'texte': message.contenu[:100],
                'piece_jointe': bool(fichier)
            }
        )

        return redirect("conversation", patient_id=patient.id)

    return render(request, "new_message.html", {
        "patients": patients
    })

@login_required
@csrf_exempt
@require_POST
def delete_single_message(request, message_id):
    user = request.user
    message = get_object_or_404(Message, id=message_id)
    patient_profile = None
    if hasattr(message.destinataire, 'patient_profile'):
        patient_profile = message.destinataire.patient_profile
    elif hasattr(message.expediteur, 'patient_profile'):
        patient_profile = message.expediteur.patient_profile

    # autoriser seulement l'expéditeur à supprimer son propre message
    if message.expediteur != user:
        return JsonResponse({"success": False, "error": "Action non autorisée"}, status=403)
    patient_profile = None
    if hasattr(message.destinataire, 'patient_profile'):
            patient_profile = message.destinataire.patient_profile
    elif hasattr(message.expediteur, 'patient_profile'):
            patient_profile = message.expediteur.patient_profile

    tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='message',
            action='Message supprimé',
            details={
                'texte': message.contenu[:100]
            }
        )
    message.delete()
    return JsonResponse({"success": True})


@login_required
@csrf_exempt
def edit_single_message(request, message_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    user = request.user
    message = get_object_or_404(Message, id=message_id)

    if message.expediteur != user:
        return JsonResponse({"success": False, "error": "Action non autorisée"}, status=403)

    nouveau_texte = request.POST.get("text", "").strip()

    if not nouveau_texte:
        return JsonResponse({"success": False, "error": "Le message ne peut pas être vide"}, status=400)

    message.contenu = nouveau_texte
    message.date_modification = timezone.now()
    patient_profile = None
    if hasattr(message.destinataire, 'patient_profile'):
        patient_profile = message.destinataire.patient_profile
    elif hasattr(message.expediteur, 'patient_profile'):
        patient_profile = message.expediteur.patient_profile

    tracer_action(
        utilisateur=request.user,
        patient=patient_profile,
        type_action='message',
        action='Message modifié',
        details={
            'nouveau_texte': nouveau_texte[:100]
        }
    )
    message.save()

    return JsonResponse({
        "success": True,
        "message": {
            "id": message.id,
            "text": message.contenu
        }
    })
@login_required
def api_historique_events(request):
    """API pour récupérer les événements d'historique avec filtres"""
    current_user = request.user
    
    # Récupérer les paramètres
    view_type = request.GET.get('view', 'all')
    patient_id = request.GET.get('patient_id', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    events = _historique_queryset_for_user(current_user, patient_id)
    
    # Filtrer par type
    if view_type != 'all':
        events = events.filter(type_action=view_type)
    
    # Filtrer par patient
    if patient_id != 'all' and patient_id:
        events = events.filter(patient_id=patient_id)
    
    # Filtrer par dates
    if date_from:
        events = events.filter(date_action__date__gte=date_from)
    if date_to:
        events = events.filter(date_action__date__lte=date_to)
    
    # Filtrer par recherche
    if search:
        events = events.filter(
            Q(action__icontains=search) |
            Q(details__icontains=search) |
            Q(patient__user__nom__icontains=search) |
            Q(patient__user__prenom__icontains=search)
        )
    
    # Formater les données
    events_list = []
    for event in events[:200]:
        patient_name = "Système"
        if event.patient:
            patient_name = f"{event.patient.user.prenom} {event.patient.user.nom}"
        formatted = _format_historique_event_for_display(event, current_user)
        event_local = localtime(event.date_action)

        events_list.append({
                'id': event.id,
                'type': event.type_action,
                'patientName': patient_name,
                'patientId': event.patient.id if event.patient else None,
                'date': event_local.strftime('%d/%m/%Y'),
                'time': event_local.strftime('%H:%M'),
                'title': formatted['title'],
                'description': formatted['description'][:240] if formatted['description'] else '',
                'targetUrl': formatted.get('target_url'),
                'can_delete': True,
            })
    
    return JsonResponse({'events': events_list})


@login_required
@require_POST
def api_delete_historique_event(request, event_id):
    current_user = request.user
    event = get_object_or_404(HistoriqueAction, id=event_id)

    if getattr(current_user, 'role', '') == 'patient':
        patient_profile = getattr(current_user, 'patient_profile', None)
        if not patient_profile or event.patient_id != patient_profile.id:
            return JsonResponse({'success': False, 'error': 'Accès refusé'}, status=403)
    elif event.utilisateur_id != current_user.id and getattr(current_user, 'role', '') == 'ergotherapeute':
        if not event.patient_id:
            return JsonResponse({'success': False, 'error': 'Accès refusé'}, status=403)

    event.delete()
    return JsonResponse({'success': True})

@login_required
@require_POST
def update_last_seen(request):
    request.user.last_seen = timezone.now()
    request.user.save(update_fields=["last_seen"])
    return JsonResponse({"success": True})

# Historique
# ==================== DOSSIERS / HISTORIQUE ====================

@login_required
@require_POST
def create_dossier(request):
    dossier = DossierPatient.objects.create(
        nom=request.POST.get('nom'),
        prenom=request.POST.get('prenom'),
    )

    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='dossier',
        action='Dossier créé',
        details={
            'dossier_id': dossier.id,
            'nom': dossier.nom,
            'prenom': dossier.prenom,
        }
    )

    return redirect('Dossiers')


@login_required
@require_POST
def modifier_dossier(request, id):
    dossier = get_object_or_404(DossierPatient, id=id)

    dossier.nom = request.POST.get('nom', dossier.nom)
    dossier.prenom = request.POST.get('prenom', dossier.prenom)
    dossier.save()

    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='dossier',
        action='Dossier modifié',
        details={
            'dossier_id': dossier.id,
            'nom': dossier.nom,
            'prenom': dossier.prenom,
        }
    )

    return redirect('Dossiers')

@login_required
@require_POST
def supprimer_dossier(request, id):
    dossier = get_object_or_404(DossierPatient, id=id)

    tracer_action(
        utilisateur=request.user,
        patient=None,
        type_action='dossier',
        action='Dossier supprimé',
        details={
            'dossier_id': dossier.id,
            'nom': dossier.nom,
            'prenom': dossier.prenom,
        }
    )

    dossier.delete()
    return redirect('Dossiers')


@require_POST
@login_required
def supprimer_patient(request, patient_id):
    try:
        patient = PatientProfile.objects.get(id=patient_id)
        user = patient.user

        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='patient',
            action='Patient supprimé',
            details={
                'patient_id': patient.id,
                'nom': user.nom,
                'prenom': user.prenom,
                'email': user.email
            }
        )

        patient.delete()
        user.delete()

        return JsonResponse({'success': True})

    except PatientProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Patient introuvable'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from django.contrib import messages
from .models import Message
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@login_required
@require_POST
def patient_send_message(request):
    try:
        text = (request.POST.get("text") or "").strip()
        reply_to_id = request.POST.get("reply_to_id")
        attachment = request.FILES.get("attachment")
        subject = (request.POST.get("subject") or "").strip()

        # ✅ Récupère l'ergo (destinataire correct)
        ergo = get_default_ergo()
        if not ergo:
            return JsonResponse({
                "success": False,
                "error": "Aucun ergothérapeute principal trouvé."
            }, status=400)

        if not text and not attachment:
            return JsonResponse({
                "success": False,
                "error": "Écrivez un message ou ajoutez un fichier."
            }, status=400)

        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id)
            except Message.DoesNotExist:
                reply_to = None

        # ✅ CRUCIAL : destinataire = ergo, pas le patient lui-même
        message = Message.objects.create(
            expediteur=request.user,      # patient
            destinataire=ergo,             # ergo â† CORRECTION ICI
            sujet=subject,
            contenu=text,
            reponse_a=reply_to,
            est_lu_par_destinataire=False
        )

        if attachment:
            message.piece_jointe = attachment
            message.piece_jointe_nom = attachment.name

            content_type = getattr(attachment, "content_type", "") or ""
            if content_type.startswith("image/"):
                message.piece_jointe_type = "image"
            elif content_type.startswith("video/"):
                message.piece_jointe_type = "video"
            elif content_type.startswith("audio/"):
                message.piece_jointe_type = "audio"
            elif "pdf" in content_type:
                message.piece_jointe_type = "pdf"
            else:
                message.piece_jointe_type = "file"

            if not message.contenu:
                message.contenu = "[Message vocal]" if message.piece_jointe_type == "audio" else "[Pièce jointe]"

        message.save()

        tracer_action(
            utilisateur=request.user,
            patient=request.user.patient_profile if hasattr(request.user, 'patient_profile') else None,
            type_action='message',
            action='Message patient envoyé',
            details={
                'texte': message.contenu[:100],
                'piece_jointe': bool(attachment),
                'reply_to': reply_to.id if reply_to else None
            }
        )
        
        return JsonResponse({
            "success": True,
            "message": {
                "id": message.id,
                "text": message.contenu or "",
                "subject": message.sujet or "",
                "time": message.date_envoi.isoformat() if message.date_envoi else "",
                "attachment": message.piece_jointe.url if message.piece_jointe else None,
                "attachment_name": message.piece_jointe_nom or "",
                "attachment_type": message.piece_jointe_type or "",
                "reply_to": {
                    "id": message.reponse_a.id,
                    "text": message.reponse_a.contenu[:80] if message.reponse_a and message.reponse_a.contenu else "[Pièce jointe]"
                } if message.reponse_a else None,
                "seen": False,
            }
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)

@login_required
def get_messages(request, patient_id):
    try:
        patient = User.objects.get(id=patient_id)
    except User.DoesNotExist:
        return JsonResponse({"messages": []})

    messages = Message.objects.filter(
        Q(expediteur=request.user, destinataire=patient) |
        Q(expediteur=patient, destinataire=request.user)
    ).order_by("date_envoi")

    messages_data = []

    for msg in messages:
        messages_data.append({
            "id": msg.id,
            "text": msg.contenu,
            "time": msg.date_envoi.isoformat(),
            "sender": "therapist" if msg.expediteur == request.user else "patient",
            "seen": msg.est_lu_par_destinataire,
            "attachment": msg.piece_jointe.url if msg.piece_jointe else None,
            "attachment_name": msg.piece_jointe.name if msg.piece_jointe else None,
            "attachment_type": "image" if msg.piece_jointe and "image" in msg.piece_jointe.name else "file"
        })

    return JsonResponse({
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "messages": messages_data,
        "is_online": True
    })
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def get_patients(request):
    users = User.objects.exclude(id=request.user.id)

    patients = []

    for u in users:
        patients.append({
            "id": u.id,
            "nom": u.last_name or "",
            "prenom": u.first_name or ""
        })

    return JsonResponse({"patients": patients})

@login_required
@require_POST
def toggle_pin_message(request, message_id):
    try:
        message = Message.objects.get(id=message_id)

        if request.user != message.expediteur and request.user != message.destinataire:
            return JsonResponse({'success': False, 'error': 'Non autorisé'})

        message.est_epingle = not message.est_epingle
        message.save()

        return JsonResponse({
            'success': True,
            'pinned': message.est_epingle
        })

    except Message.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Message introuvable'})

@login_required
def get_pinned_message(request):
    patient_user = request.user
    ergo = get_default_ergo()

    if not ergo:
        return JsonResponse({'success': False})

    message = Message.objects.filter(
        Q(expediteur=patient_user, destinataire=ergo) |
        Q(expediteur=ergo, destinataire=patient_user),
        est_epingle=True
    ).order_by('-date_envoi').first()

    if message:
        return JsonResponse({
            'success': True,
            'message_id': message.id
        })

    return JsonResponse({'success': False})

@login_required
@require_POST
def messages_send(request):
    ergo = request.user

    if ergo.role != 'ergo':
        return JsonResponse(
            {"success": False, "error": "Ergothérapeute non autorisé"},
            status=403
        )

    patient_id = request.POST.get("patient_id")
    text = (request.POST.get("text") or "").strip()
    fichier = request.FILES.get("attachment")
    reply_to_id = request.POST.get("reply_to_id")

    if not patient_id:
        return JsonResponse(
            {"success": False, "error": "Patient manquant"},
            status=400
        )

    patient = get_object_or_404(
        User,
        id=patient_id,
        role='patient',
        patient_profile__isnull=False
    )

    if not text and not fichier:
        return JsonResponse(
            {"success": False, "error": "Message vide"},
            status=400
        )

    message_parent = None
    if reply_to_id and reply_to_id not in ["null", "None", ""]:
        try:
            message_parent = Message.objects.get(id=reply_to_id)
        except Message.DoesNotExist:
            message_parent = None

    subject = (request.POST.get("subject") or "").strip()

    message = Message.objects.create(
        expediteur=ergo,
        destinataire=patient,
        sujet=subject,
        contenu=text if text else "",
        est_lu_par_destinataire=False,
        reponse_a=message_parent
    )

    if fichier:
        message.piece_jointe = fichier
        message.piece_jointe_nom = fichier.name

        content_type = getattr(fichier, "content_type", "") or ""

        if content_type.startswith("image/"):
            message.piece_jointe_type = "image"
        elif content_type.startswith("video/"):
            message.piece_jointe_type = "video"
        elif content_type.startswith("audio/"):
            message.piece_jointe_type = "audio"
        elif "pdf" in content_type:
            message.piece_jointe_type = "pdf"
        else:
            message.piece_jointe_type = "file"

        if not message.contenu:
            message.contenu = "[Message vocal]" if message.piece_jointe_type == "audio" else "[Pièce jointe]"

    message.save()

    tracer_action(
        utilisateur=ergo,
        patient=patient.patient_profile if hasattr(patient, 'patient_profile') else None,
        type_action='message',
        action='Message envoyé',
        details={
            'texte': message.contenu[:100],
            'piece_jointe': bool(fichier),
            'reply_to': message_parent.id if message_parent else None
        }
    )

    return JsonResponse({
        "success": True,
        "message": {
            "id": message.id,
            "text": message.contenu,
            "subject": message.sujet,
            "sender": "therapist",
            "time": message.date_envoi.isoformat() if message.date_envoi else "",
            "attachment": message.piece_jointe.url if message.piece_jointe else None,
            "attachment_name": message.piece_jointe_nom or "",
            "attachment_type": message.piece_jointe_type or "",
            "seen": False,
            "is_pinned": message.est_epingle,
            "reply_to": {
                "id": message.reponse_a.id,
                "text": message.reponse_a.contenu[:80] if message.reponse_a and message.reponse_a.contenu else "[Pièce jointe]",
                "sender": "therapist" if message.reponse_a and message.reponse_a.expediteur == ergo else "patient",
            } if message.reponse_a else None,
        }
    })
@login_required
def patient_messages_api(request):
    patient_user = request.user
    ergos_qs = User.objects.filter(role='ergo')

    if not ergos_qs.exists():
        return JsonResponse({
            "success": False,
            "messages": []
        })

    messages = Message.objects.filter(
        Q(expediteur=patient_user, destinataire__in=ergos_qs) |
        Q(expediteur__in=ergos_qs, destinataire=patient_user)
    ).select_related("reponse_a").order_by("date_envoi")

    messages_data = []

    for msg in messages:
        messages_data.append({
            "id": msg.id,
            "text": msg.contenu or "",
            "subject": msg.sujet or "",
            "sender": "patient" if msg.expediteur == patient_user else "therapist",
            "time": msg.date_envoi.isoformat() if msg.date_envoi else "",
            "seen": msg.est_lu_par_destinataire if msg.destinataire == patient_user else None,
            "attachment": msg.piece_jointe.url if msg.piece_jointe else None,
            "attachment_name": msg.piece_jointe_nom or "",
            "attachment_type": msg.piece_jointe_type or "",
            "is_pinned": msg.est_epingle,
            "reply_to": {
                "id": msg.reponse_a.id,
                "text": msg.reponse_a.contenu[:80] if msg.reponse_a and msg.reponse_a.contenu else "[Pièce jointe]"
            } if msg.reponse_a else None,
        })

    return JsonResponse({
        "success": True,
        "messages": messages_data
    })
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

@login_required
@require_POST
def terminer_ressource(request, partage_id):
    partage = get_object_or_404(RessourcePatient, id=partage_id)

    partage.date_fin = timezone.now()
    partage.statut = 'terminee'
    partage.save()

    return JsonResponse({'success': True})
def messages_view(request):
    afficher_archives = request.GET.get('archives') == '1'

    messages = Contact.objects.all().order_by('-date_contact')

    if afficher_archives:
        messages = messages.filter(archive=True)
    else:
        messages = messages.filter(archive=False)

    # Utiliser votre fonction algeria_localtime existante
    for msg in messages:
        msg.date_contact_local = algeria_localtime(msg.date_contact)
        msg.date_traitement_local = algeria_localtime(msg.date_traitement)

    return render(request, "message.html", {
        "messages": messages,
        "afficher_archives": afficher_archives
    })
@login_required
@require_POST
def supprimer_message_contact(request, message_id):
    message = get_object_or_404(Contact, id=message_id)
    message.delete()
    return redirect('messages')


@login_required
@require_POST
def traiter_message_contact(request, message_id):
    message = get_object_or_404(Contact, id=message_id)
    message.statut = 'traite'
    message.date_traitement = timezone.now()
    message.save(update_fields=['statut', 'date_traitement'])
    return redirect('messages')


@login_required
@require_POST
def archiver_message_contact(request, message_id):
    message = get_object_or_404(Contact, id=message_id)
    message.archive = True
    message.save(update_fields=['archive'])
    return redirect('messages')


@login_required
@require_POST
def desarchiver_message_contact(request, message_id):
    message = get_object_or_404(Contact, id=message_id)
    message.archive = False
    message.save(update_fields=['archive'])
    return redirect('messages')


@login_required
def exporter_message_contact_txt(request, message_id):
    message = get_object_or_404(Contact, id=message_id)

    contenu = (
        f"Nom : {message.nom}\n"
        f"Email : {message.email}\n"
        f"Sujet : {message.sujet}\n"
        f"Date : {timezone.localtime(message.date_contact).strftime('%d/%m/%Y %H:%M')}\n"
        f"Statut : {message.get_statut_display()}\n"
        f"Archivé : {'Oui' if message.archive else 'Non'}\n\n"
        f"Message :\n{message.message}\n"
    )

    response = HttpResponse(contenu, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="message_contact_{message.id}.txt"'
    return response
@login_required
def get_latest_messages(request):
    messages = Contact.objects.filter(archive=False).order_by('-date_contact')[:50]

    data = []
    for msg in messages:
        # Utiliser votre fonction algeria_localtime
        local_date = algeria_localtime(msg.date_contact)
        
        data.append({
            "id": msg.id,
            "nom": msg.nom or "",
            "email": msg.email or "",
            "sujet": msg.sujet or "",
            "message": msg.message or "",
            "date": local_date.strftime("%d/%m/%Y %H:%M") if local_date else "",
            "statut": msg.statut or "nouveau",
            "archive": msg.archive,
        })

    return JsonResponse({"messages": data})

# ==================== DEMANDES DE RENDEZ-VOUS PATIENT ====================

@login_required
def patient_demande_rendezvous(request):
    """Le patient envoie une demande de rendez-vous"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            patient_profile = request.user.patient_profile
            date_souhaitee = data.get('date')
            creneau_souhaite = data.get('time')
            type_souhaite = data.get('mode')
            motif = data.get('reason', '')
            
            if not date_souhaitee or not creneau_souhaite or not type_souhaite:
                return JsonResponse({'success': False, 'error': 'Champs manquants'}, status=400)
            
            demande = DemandeRendezVous.objects.create(
                patient=patient_profile,
                date_souhaitee=date_souhaitee,
                creneau_souhaite=creneau_souhaite,
                type_souhaite=type_souhaite,
                motif=motif
            )
            
            tracer_action(
                utilisateur=request.user,
                patient=patient_profile,
                type_action='seance',
                action='Demande de rendez-vous envoyée',
                details={
                    'date': date_souhaitee,
                    'creneau': creneau_souhaite,
                    'type': type_souhaite
                }
            )
            
            return JsonResponse({'success': True, 'demande_id': demande.id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
@login_required
def ergo_demandes_rendezvous(request):
    try:
        demandes = DemandeRendezVous.objects.select_related('patient__user').order_by('-date_creation')
        
        demandes_list = []
        for d in demandes:
            type_display = "Télé-ergothérapie" if d.type_souhaite == "tele" else "Présentiel"
            
            # ✅ CORRECTION : Ajouter 2 heures à la date de création
            date_creation_corrigee = d.date_creation + timedelta(hours=2)
            
            demandes_list.append({
                'id': d.id,
                'patient_id': d.patient.id,
                'patient_nom': d.patient.user.nom,
                'patient_prenom': d.patient.user.prenom,
                'date_souhaitee': d.date_souhaitee.strftime('%Y-%m-%d'),
                'date_affichage': d.date_souhaitee.strftime('%d/%m/%Y'),
                'creneau': d.creneau_souhaite,
                'type': type_display,
                'type_valeur': d.type_souhaite,
                'motif': d.motif,
                'statut': d.statut,
                'reponse': d.reponse_ergo,
                'date_creation': date_creation_corrigee.strftime('%d/%m/%Y à %H:%M'),
            })
        
        return JsonResponse({'demandes': demandes_list})
        
    except Exception as e:
        return JsonResponse({'demandes': [], 'error': str(e)})
@login_required
def ergo_repondre_demande(request, demande_id):
    """L'ergo répond à une demande de rendez-vous"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    if request.user.role != 'ergo':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'accepter' ou 'refuser'
        reponse = data.get('reponse', '')
        
        demande = get_object_or_404(DemandeRendezVous, id=demande_id)
        
        # Mettre à jour le statut
        if action == 'accepter':
            demande.statut = 'acceptee'
            message_notification = f"✅ Votre demande de rendez-vous du {demande.date_souhaitee} a été ACCEPTÉE. {reponse}"
        elif action == 'refuser':
            demande.statut = 'refusee'
            message_notification = f"❌ Votre demande de rendez-vous du {demande.date_souhaitee} a été REFUSÉE. Motif: {reponse}"
        else:
            return JsonResponse({'success': False, 'error': 'Action invalide'}, status=400)
        
        demande.reponse_ergo = reponse
        demande.date_traitement = timezone.now()
        demande.save()
        
        # Créer un message pour le patient
        Message.objects.create(
            expediteur=request.user,
            destinataire=demande.patient.user,
            sujet="Réponse à votre demande de rendez-vous",
            contenu=message_notification,
            est_lu_par_destinataire=False
        )
        
        tracer_action(
            utilisateur=request.user,
            patient=demande.patient,
            type_action='seance',
            action=f'Demande de rendez-vous {action}e',
            details={
                'demande_id': demande.id,
                'reponse': reponse
            }
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==================== SIGNALEMENTS PATIENT ====================

@login_required
def patient_signalement_rendezvous(request):
    """Le patient envoie un signalement"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            patient_profile = request.user.patient_profile
            rendez_vous_id = data.get('appointment_id')
            description = data.get('reason', '')
            type_signalement = data.get('type', 'autre')
            
            if not rendez_vous_id or not description:
                return JsonResponse({'success': False, 'error': 'Champs manquants'}, status=400)
            
            rendez_vous = get_object_or_404(RDV, id=rendez_vous_id)
            
            signalement = SignalementRendezVous.objects.create(
                patient=patient_profile,
                rendez_vous=rendez_vous,
                type_signalement=type_signalement,
                description=description
            )
            
            tracer_action(
                utilisateur=request.user,
                patient=patient_profile,
                type_action='seance',
                action='Signalement envoyé',
                details={
                    'rendez_vous_id': rendez_vous_id,
                    'type': type_signalement
                }
            )
            
            return JsonResponse({'success': True, 'signalement_id': signalement.id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)


@login_required
def ergo_signalements(request):
    """L'ergo voit tous les signalements"""
    if request.user.role != 'ergo':
        return JsonResponse({'signalements': []})
    
    signalements = SignalementRendezVous.objects.select_related(
        'patient__user', 'rendez_vous'
    ).order_by('-date_creation')
    
    signalements_list = []
    for s in signalements:
        signalements_list.append({
            'id': s.id,
            'patient_id': s.patient.id,
            'patient_nom': s.patient.user.nom,
            'patient_prenom': s.patient.user.prenom,
            'rdv_date': s.rendez_vous.date_heure.strftime('%d/%m/%Y'),
            'rdv_time': s.rendez_vous.date_heure.strftime('%H:%M'),
            'type_signalement': s.type_signalement,
            'description': s.description,
            'statut': s.statut,
            'date_creation': s.date_creation.strftime('%d/%m/%Y %H:%M'),
        })
    
    return JsonResponse({'signalements': signalements_list})
@login_required
def ergo_signalement_traiter(request, signalement_id):
    """L'ergo marque un signalement comme traité"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    if request.user.role != 'ergo':
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    
    try:
        signalement = get_object_or_404(SignalementRendezVous, id=signalement_id)
        signalement.statut = 'traite'
        signalement.date_traitement = timezone.now()
        signalement.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
@csrf_exempt
def patient_repondre_rendezvous(request, rdv_id):
    """Le patient répond à une notification de rendez-vous"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        
        if not message:
            return JsonResponse({'success': False, 'error': 'Message vide'}, status=400)
        
        patient_profile = request.user.patient_profile
        rendez_vous = get_object_or_404(RDV, id=rdv_id, patient=request.user)
        
        reponse = ReponseRendezVous.objects.create(
            rendez_vous=rendez_vous,
            patient=patient_profile,
            message=message
        )
        
        # Notification pour l'ergo (optionnelle)
        Message.objects.create(
            expediteur=request.user,
            destinataire=rendez_vous.ergo,
            sujet=f"Réponse au rendez-vous du {rendez_vous.date_heure.strftime('%d/%m/%Y')}",
            contenu=f"Le patient a répondu à votre notification concernant le rendez-vous :\n\n{message}",
            est_lu_par_destinataire=False
        )
        
        return JsonResponse({'success': True, 'reponse_id': reponse.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
def ergo_reponses_rendezvous(request):
    import datetime
    reponses = ReponseRendezVous.objects.all().order_by('-date_reponse')
    reponses_list = []

    for r in reponses:
        # ✅ Correction du décalage horaire (UTC → UTC+1)
        date_corrigee = r.date_reponse + datetime.timedelta(hours=2)

        reponses_list.append({
            'id': r.id,
            'patient_id': r.patient.id,
            'patient_nom': r.patient.user.nom,
            'patient_prenom': r.patient.user.prenom,
            'rdv_date': r.rendez_vous.date_heure.strftime('%d/%m/%Y') if r.rendez_vous else '--',
            'rdv_time': r.rendez_vous.date_heure.strftime('%H:%M') if r.rendez_vous else '--',
            'message': r.message,
            'date_reponse': date_corrigee.strftime('%d/%m/%Y à %H:%M'),
            'lu': r.lu_par_ergo,
        })

    return JsonResponse({'reponses': reponses_list})


@login_required
@csrf_exempt
def ergo_reponse_lue(request, reponse_id):
    """L'ergo marque une réponse comme lue"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
        
    try:
        reponse = get_object_or_404(ReponseRendezVous, id=reponse_id)
        reponse.lu_par_ergo = True
        reponse.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def ergo_repondre_patient(request):
    """L'ergo répond à un patient"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    try:
        data = json.loads(request.body)
        patient_profile_id = data.get('patient_id')
        message = data.get('message', '').strip()
        
        print(f"🔍 DEBUG - patient_profile_id reçu: {patient_profile_id}")
        print(f"🔍 DEBUG - message: {message}")
        print(f"🔍 DEBUG - request.user: {request.user.username} (ID: {request.user.id}, role: {request.user.role})")
        
        if not patient_profile_id or not message:
            return JsonResponse({'success': False, 'error': 'Message vide'}, status=400)
        
        # Récupérer le PatientProfile
        patient_profile = get_object_or_404(PatientProfile, id=patient_profile_id)
        patient_user = patient_profile.user
        
        print(f"🔍 DEBUG - patient trouvé: {patient_user.username} (ID: {patient_user.id})")
        
        # Créer le message
        nouveau_message = Message.objects.create(
            expediteur=request.user,
            destinataire=patient_user,
            sujet="📩 Réponse de votre ergothérapeute",
            contenu=message,
            est_lu_par_destinataire=False
        )
        
        print(f"✅ Message créé: ID {nouveau_message.id}")
        
        return JsonResponse({'success': True, 'message_id': nouveau_message.id})
        
    except Exception as e:
        print(f"âŒ ERREUR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def patient_messages_ergo(request):
    import datetime
    messages = Message.objects.filter(destinataire=request.user).order_by('-date_envoi')
    
    messages_list = []
    for msg in messages:
        # ✅ Ajouter 2 heures pour l’heure locale Algérie (UTC+1)
        date_corrigee = msg.date_envoi + datetime.timedelta(hours=2)
        
        messages_list.append({
            'id': msg.id,
            'sujet': msg.sujet,
            'contenu': msg.contenu,
            'date_envoi': date_corrigee.strftime('%d/%m/%Y %H:%M'),
            'lu': msg.est_lu_par_destinataire,
            'expediteur_nom': msg.expediteur.username,
        })
    
    return JsonResponse({'messages': messages_list})
@login_required
@csrf_exempt
def patient_message_lu(request, message_id):
    """Le patient marque un message comme lu"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    message = get_object_or_404(Message, id=message_id, destinataire=request.user)
    message.est_lu_par_destinataire = True
    message.save()
    
    return JsonResponse({'success': True})


from datetime import timedelta
from django.utils import timezone

@login_required
@csrf_exempt
def patient_repondre_ergo(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        reply_to_id = data.get('reply_to_id')
        
        if not message:
            return JsonResponse({'success': False, 'error': 'Message vide'}, status=400)
        
        ergo = get_default_ergo()
        if not ergo:
            return JsonResponse({'success': False, 'error': 'Ergothérapeute non trouvé'}, status=400)
        
        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id)
            except:
                pass
        
        # ✅ CORRECTION : Ajouter +2h pour compenser le décalage
        now = timezone.now() + timedelta(hours=2)
        
        nouveau_message = Message.objects.create(
            expediteur=request.user,
            destinataire=ergo,
            sujet="Réponse à votre message",
            contenu=message,
            reponse_a=reply_to,
            est_lu_par_destinataire=False,
            date_envoi=now
        )
        
        return JsonResponse({'success': True, 'message_id': nouveau_message.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==================== SUPPRIMER UN MESSAGE ====================
@login_required
@csrf_exempt
def supprimer_message(request, message_id):
    """Supprimer un message définitivement"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    try:
        message = get_object_or_404(Message, id=message_id)
        user = request.user
        patient_profile = None
        if hasattr(message.destinataire, 'patient_profile'):
            patient_profile = message.destinataire.patient_profile
        elif hasattr(message.expediteur, 'patient_profile'):
            patient_profile = message.expediteur.patient_profile
        
        # Vérifier que l'utilisateur est l'expéditeur ou le destinataire
        if message.expediteur != user and message.destinataire != user:
            return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
        
        # Suppression définitive
        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='message',
            action='Message supprimé',
            details={
                'message_id': message.id,
                'texte': (message.contenu or '')[:100]
            }
        )
        message.delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ==================== MODIFIER UN MESSAGE ====================
@login_required
@csrf_exempt
def modifier_message(request, message_id):
    """Modifier un message (seulement l'expéditeur et dans la limite de 5 minutes)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    data = json.loads(request.body)
    nouveau_contenu = data.get('contenu', '').strip()
    
    if not nouveau_contenu:
        return JsonResponse({'success': False, 'error': 'Message vide'}, status=400)
    
    message = get_object_or_404(Message, id=message_id)
    
    # Seul l'expéditeur peut modifier
    if message.expediteur != request.user:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    
    message.contenu = nouveau_contenu
    message.date_modification = timezone.now()
    message.save()
    
    return JsonResponse({'success': True, 'nouveau_contenu': nouveau_contenu})    

from datetime import timedelta

@login_required
def ergo_messages_patients(request):
    """L'ergo voit tous les messages des patients"""
    from django.db.models import Q
    
    messages = Message.objects.filter(
        Q(expediteur__role='patient')
    ).select_related('expediteur', 'destinataire').order_by('-date_envoi')
    
    messages_list = []
    for msg in messages:
        # ✅ CORRECTION : Ajouter +2h
        date_corrigee = msg.date_envoi + timedelta(hours=2)
        date_envoi_str = date_corrigee.strftime('%d/%m/%Y à %H:%M')
        
        messages_list.append({
            'id': msg.id,
            'patient_id': msg.expediteur.id,
            'patient_nom': msg.expediteur.nom,
            'patient_prenom': msg.expediteur.prenom,
            'contenu': msg.contenu,
            'date_envoi': date_envoi_str,
            'lu': msg.est_lu_par_destinataire if msg.destinataire == request.user else False,
            'reply_to': msg.reponse_a.contenu[:80] if msg.reponse_a else None,
        })
    
    return JsonResponse({'messages': messages_list})
@login_required
@csrf_exempt
def ergo_message_patient_lu(request, message_id):
    """L'ergo marque un message comme lu"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    message = get_object_or_404(Message, id=message_id, destinataire=request.user)
    message.est_lu_par_destinataire = True
    message.save()
    
    return JsonResponse({'success': True})

@login_required
@csrf_exempt
def ergo_repondre_message_patient(request):
    """L'ergo répond à un message de patient"""
    print("=" * 50)
    print("🔵 ergo_repondre_message_patient appelée")
    print(f"🔵 Méthode: {request.method}")
    print(f"🔵 Utilisateur: {request.user.username} (role: {request.user.role})")
    
    if request.method != 'POST':
        print("❌ Méthode non autorisée")
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    if request.user.role != 'ergo':
        print(f"❌ Non autorisé - role: {request.user.role}")
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)
    
    try:
        data = json.loads(request.body)
        print(f"🔵 Données reçues: {data}")
        
        patient_id = data.get('patient_id')
        message = data.get('message', '').strip()
        reply_to_id = data.get('reply_to_id')
        
        print(f"🔵 patient_id: {patient_id}")
        print(f"🔵 message: {message}")
        print(f"🔵 reply_to_id: {reply_to_id}")
        
        if not patient_id or not message:
            print("âŒ Message vide ou patient manquant")
            return JsonResponse({'success': False, 'error': 'Message vide'}, status=400)
        
        patient = get_object_or_404(User, id=patient_id, role='patient')
        print(f"🔵 Patient trouvé: {patient.username}")
        
        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id)
                print(f"🔵 Reply_to trouvé: {reply_to.id}")
            except Message.DoesNotExist:
                print(f"⚠️ Reply_to {reply_to_id} non trouvé")
        
        nouveau_message = Message.objects.create(
            expediteur=request.user,
            destinataire=patient,
            sujet="Réponse à votre message",
            contenu=message,
            reponse_a=reply_to,
            est_lu_par_destinataire=False
        )
        
        print(f"✅ Message créé: ID {nouveau_message.id}")
        
        return JsonResponse({'success': True, 'message_id': nouveau_message.id})
        
    except Exception as e:
        print(f"âŒ ERREUR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
@csrf_exempt
def ergo_repondre_demande(request, demande_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        reponse = data.get('reponse', '')
        
        demande = get_object_or_404(DemandeRendezVous, id=demande_id)
        
        # Heure locale pour la salutation
        now = timezone.localtime(timezone.now())
        heure = now.hour
        
        if heure < 12:
            salutation = "Bonjour"
        elif heure < 18:
            salutation = "Bon après-midi"
        else:
            salutation = "Bonsoir"
        
        ergo = get_default_ergo()
        if not ergo:
            return JsonResponse({'success': False, 'error': 'Ergothérapeute non trouvé'}, status=400)
        
        patient_prenom = demande.patient.user.prenom
        
        if action == 'accepter':
            demande.statut = 'acceptee'
            sujet_message = "Demande de rendez-vous acceptée"
            contenu_message = (
                f"{salutation} {patient_prenom},\n\n"
                "Votre demande de rendez-vous a été acceptée.\n\n"
                "Rendez-vous ajouté à votre agenda.\n\n"
                "Bien à vous,\n\n"
                "Cordialement,\n"
                "SmartWrist Rehab"
            )
            
        elif action == 'refuser':
            demande.statut = 'refusee'
            sujet_message = "Réponse à votre demande de rendez-vous"
            contenu_message = (
                f"{salutation} {patient_prenom},\n\n"
                "Je n'ai pas pu valider votre demande cette fois-ci.\n\n"
                "Ne vous découragez pas : nouvelle demande, modification, ou message direct.\n\n"
                "Bien à vous,\n\n"
                "Cordialement,\n"
                "SmartWrist Rehab"
            )
        else:
            return JsonResponse({'success': False, 'error': 'Action invalide'}, status=400)
        
        demande.reponse_ergo = reponse
        demande.date_traitement = timezone.now()
        demande.save()
        
        Message.objects.create(
            expediteur=ergo,
            destinataire=demande.patient.user,
            sujet=sujet_message,
            contenu=contenu_message,
            est_lu_par_destinataire=False
        )
        
        tracer_action(
            utilisateur=request.user,
            patient=demande.patient,
            type_action='seance',
            action=f'Demande de rendez-vous {action}e',
            details={'demande_id': demande.id, 'reponse': reponse}
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def ergo_supprimer_demande(request, demande_id):
    """L'ergo supprime une demande de rendez-vous"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    # ✅ SUPPRIME la vérification de rôle
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non authentifié'}, status=403)
    
    try:
        demande = get_object_or_404(DemandeRendezVous, id=demande_id)
        
        tracer_action(
            utilisateur=request.user,
            patient=demande.patient,
            type_action='seance',
            action='Demande de rendez-vous supprimée',
            details={
                'demande_id': demande.id,
                'date': demande.date_souhaitee.strftime('%Y-%m-%d')
            }
        )
        
        demande.delete()
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
@csrf_exempt
def ergo_supprimer_reponse(request, reponse_id):
    """L'ergo supprime une réponse de patient"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    
    try:
        reponse = get_object_or_404(ReponseRendezVous, id=reponse_id)
        
        tracer_action(
            utilisateur=request.user,
            patient=reponse.patient,
            type_action='seance',
            action='Réponse patient supprimée',
            details={'reponse_id': reponse.id}
        )
        
        reponse.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
@csrf_exempt
def api_programmes_resultat(request):
    """API pour enregistrer un résultat d'exercice (côté patient)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    try:
        media_file = None
        media_type = ''

        # Lecture JSON ou FormData
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
            exercice_id = data.get('exercice_id')
            resultat = data.get('resultat', '')
            douleur = data.get('douleur', 0)
            satisfaction = data.get('satisfaction', 0)
            difficultes = data.get('difficultes', '')
            amplitude = data.get('amplitude', 0)
        else:
            exercice_id = request.POST.get('exercice_id')
            resultat = request.POST.get('resultat', '')
            douleur = request.POST.get('douleur', 0)
            satisfaction = request.POST.get('satisfaction', 0)
            difficultes = request.POST.get('difficultes', '')
            amplitude = request.POST.get('amplitude', 0)
            media_file = request.FILES.get('media')
            media_type = request.POST.get('media_type', '')

        if not exercice_id:
            return JsonResponse({'success': False, 'error': 'Exercice non spécifié'}, status=400)

        if not hasattr(request.user, 'patient_profile'):
            return JsonResponse({'success': False, 'error': 'Utilisateur non patient'}, status=400)

        exercice = get_object_or_404(Exercice, id=exercice_id)
        patient_profile = request.user.patient_profile

        nouveau_resultat = ResultatExercice.objects.create(
            patient=patient_profile,
            exercice=exercice,
            resultat_texte=resultat or '',
            amplitude_atteinte=int(amplitude or 0),
            douleur=int(douleur or 0),
            satisfaction=int(satisfaction or 0),
            difficultes=difficultes or '',
            media_fichier=media_file,
            media_type=media_type or '',
            valide_par_ergo=False,
            statut_ergo='pending',
            commentaire_ergo=''
        )

        categorie_exercice = (exercice.categorie or '').strip().lower()
        nom_exercice = (exercice.nom or '').strip()
        if categorie_exercice in ['défi', 'defi'] or nom_exercice.startswith('[Défi]') or nom_exercice.startswith('[Defi]'):
            verifier_et_debloquer_defis(patient_profile, nouveau_resultat)

        # Historique
        tracer_action(
            utilisateur=request.user,
            patient=patient_profile,
            type_action='programme',
            action='Résultat exercice envoyé',
            details={
                'resultat_id': nouveau_resultat.id,
                'exercice': exercice.nom,
                'programme': exercice.programme.nom if exercice.programme else '',
                'resultat': nouveau_resultat.resultat_texte or '',
                'douleur': int(douleur or 0),
                'satisfaction': int(satisfaction or 0),
                'difficultes': nouveau_resultat.difficultes or '',
                'media': bool(nouveau_resultat.media_fichier),
                'date': algeria_localtime(nouveau_resultat.date_realisation).strftime('%d/%m/%Y'),
                'heure': algeria_localtime(nouveau_resultat.date_realisation).strftime('%H:%M'),
            }
        )

        # Notification immédiate pour l’ergothérapeute
        global ERGO_NOTIFICATIONS

        date_locale = algeria_localtime(nouveau_resultat.date_realisation)

        ERGO_NOTIFICATIONS.insert(0, {
            'id': f'nouveau-resultat-{nouveau_resultat.id}',
            'type': 'nouveau_resultat',
            'resultat_id': nouveau_resultat.id,
            'patient_id': patient_profile.id,
            'patient_nom': patient_profile.user.nom,
            'patient_prenom': patient_profile.user.prenom,
            'exercice_id': exercice.id,
            'exercice_nom': exercice.nom,
            'resultat': nouveau_resultat.resultat_texte or '',
            'amplitude': nouveau_resultat.amplitude_atteinte,
            'douleur': nouveau_resultat.douleur,
            'satisfaction': nouveau_resultat.satisfaction,
            'difficultes': nouveau_resultat.difficultes or '',
            'date': date_locale.strftime('%d/%m/%Y'),
            'heure': date_locale.strftime('%H:%M'),
            'datetime': date_locale.isoformat(),
        })

        evolution_journaliere = calculer_evolution_journaliere(
            patient_profile,
            exercice.programme
        )
        progression_defis = calculer_progression_defis(patient_profile, exercice.programme)

        return JsonResponse({
            'success': True,
            'evolution': evolution_journaliere,
            'progression_defis': progression_defis,
            'resultat_id': nouveau_resultat.id,
            'resultat': {
                'id': nouveau_resultat.id,
                'exercice_nom': exercice.nom,
                'resultat': nouveau_resultat.resultat_texte,
                'amplitude': nouveau_resultat.amplitude_atteinte,
                'douleur': nouveau_resultat.douleur,
                'satisfaction': nouveau_resultat.satisfaction,
                'difficultes': nouveau_resultat.difficultes,
                'objectif': exercice.objectif or '',
                'date': date_locale.strftime('%d/%m/%Y %H:%M'),
                'media_url': nouveau_resultat.media_fichier.url if nouveau_resultat.media_fichier else None,
                'media_type': nouveau_resultat.media_type if nouveau_resultat.media_fichier else '',
                'valide_par_ergo': nouveau_resultat.valide_par_ergo,
                'statut_ergo': nouveau_resultat.statut_ergo,
                'commentaire_ergo': nouveau_resultat.commentaire_ergo or '',
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_modifier_resultat_patient(request, resultat_id):
    try:
        resultat = get_object_or_404(ResultatExercice, id=resultat_id, patient=request.user.patient_profile)
        data = json.loads(request.body)

        resultat.resultat_texte = (data.get('resultat') or '').strip()
        resultat.douleur = int(data.get('douleur') or 0)
        resultat.satisfaction = int(data.get('satisfaction') or 0)
        resultat.difficultes = (data.get('difficultes') or '').strip()
        resultat.valide_par_ergo = False
        resultat.statut_ergo = 'pending'
        resultat.commentaire_ergo = ''
        resultat.save()

        tracer_action(
            utilisateur=request.user,
            patient=request.user.patient_profile,
            type_action='programme',
            action='Resultat exercice modifie',
            details={
                'resultat_id': resultat.id,
                'exercice': resultat.exercice.nom,
                'programme': resultat.exercice.programme.nom if resultat.exercice and resultat.exercice.programme else '',
                'resultat': resultat.resultat_texte,
                'douleur': resultat.douleur,
                'satisfaction': resultat.satisfaction,
                'difficultes': resultat.difficultes,
            }
        )

        date_locale = algeria_localtime(resultat.date_realisation)
        return JsonResponse({
            'success': True,
            'resultat': {
                'id': resultat.id,
                'resultat': resultat.resultat_texte,
                'douleur': resultat.douleur,
                'satisfaction': resultat.satisfaction,
                'difficultes': resultat.difficultes,
                'objectif': resultat.exercice.objectif or '',
                'date': date_locale.strftime('%d/%m/%Y %H:%M') if date_locale else '',
                'valide_par_ergo': resultat.valide_par_ergo,
                'statut_ergo': resultat.statut_ergo,
                'commentaire_ergo': resultat.commentaire_ergo or '',
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_supprimer_resultat_patient(request, resultat_id):
    try:
        resultat = get_object_or_404(ResultatExercice, id=resultat_id, patient=request.user.patient_profile)
        tracer_action(
            utilisateur=request.user,
            patient=request.user.patient_profile,
            type_action='programme',
            action='Resultat exercice supprime',
            details={
                'resultat_id': resultat.id,
                'exercice': resultat.exercice.nom,
                'programme': resultat.exercice.programme.nom if resultat.exercice and resultat.exercice.programme else '',
            }
        )
        resultat.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_commenter_resultat_ergo(request, resultat_id):
    try:
        if request.user.role != 'ergo':
            return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

        resultat = get_object_or_404(ResultatExercice, id=resultat_id)
        data = json.loads(request.body)
        resultat.commentaire_ergo = (data.get('commentaire') or '').strip()
        action_notification = 'Commentaire therapeute sur resultat'
        action_type = data.get('action')

        if action_type in ['valider', 'refuser'] and not resultat.commentaire_ergo:
            return JsonResponse({'success': False, 'error': 'Le motif est obligatoire.'}, status=400)

        if action_type == 'valider':
            resultat.valide_par_ergo = True
            resultat.statut_ergo = 'validated'
            action_notification = 'Resultat valide par therapeute'
        elif action_type == 'refuser':
            resultat.valide_par_ergo = False
            resultat.statut_ergo = 'refused'
            action_notification = 'Resultat refuse par therapeute'
        else:
            resultat.valide_par_ergo = False
            resultat.statut_ergo = 'pending'
        resultat.save()

        if action_type == 'valider':
            verifier_et_debloquer_defis(resultat.patient, resultat)

        tracer_action(
            utilisateur=request.user,
            patient=resultat.patient,
            type_action='programme',
            action=action_notification,
            details={
                'resultat_id': resultat.id,
                'exercice': resultat.exercice.nom,
                'programme': resultat.exercice.programme.nom if resultat.exercice and resultat.exercice.programme else '',
                'commentaire': resultat.commentaire_ergo or '',
                'statut': resultat.statut_ergo,
            }
        )

        return JsonResponse({
            'success': True,
            'commentaire_ergo': resultat.commentaire_ergo or '',
            'valide': resultat.valide_par_ergo,
            'statut_ergo': resultat.statut_ergo
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
def all_patients(request):
    patients = PatientProfile.objects.select_related('user').all().order_by("user__prenom", "user__nom")

    data = [
        {
            "id": p.id,  # â† ID du PatientProfile, pas du User
            "user_id": p.user.id,  # â† ID du User
            "nom": p.user.nom,
            "prenom": p.user.prenom,
            "age": p.age(),
            "email": p.user.email,
            "diagnostic": p.get_type_fracture_display(),
            "initiales": (
                f"{(p.user.nom or '')[:1]}{(p.user.prenom or '')[:1]}".upper()
                if (p.user.nom or p.user.prenom) else "P"
            )
        }
        for p in patients
    ]

    return JsonResponse({"patients": data})
@csrf_exempt
@require_http_methods(["POST"])
def marquer_patient_termine(request):
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        
        # PatientProfile est déjà importé en haut du fichier
        patient = PatientProfile.objects.get(id=patient_id)
        
        # Ajoute le champ statut_programme si pas encore fait
        # Sinon, utilise un attribut existant
        patient.statut_programme = 'termine'
        patient.save()
        
        return JsonResponse({'success': True})
    except PatientProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Patient non trouvé'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)    
def compter_visite_patient(request, page):
    """Compte chaque action du patient sur la plateforme"""
    if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
        try:
            tracer_action(
                utilisateur=request.user,
                patient=request.user.patient_profile,
                type_action='visite',
                action=f'Visite - {page}',
                details={'page': page}
            )
        except Exception as e:
            print(f"Erreur comptage visite: {e}")


@login_required
@require_POST
def api_tracer_activite_patient(request):
    if not hasattr(request.user, 'patient_profile'):
        return JsonResponse({'success': False, 'error': 'Utilisateur non patient'}, status=403)

    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = request.POST

    page = (data.get('page') or '').strip()
    motif = (data.get('motif') or '').strip()
    pages_autorisees = {
        'program': 'onglet programme',
        'results': 'onglet résultats',
        'communication': 'onglet communication',
        'history': 'onglet historique',
        'media': 'onglet médias',
        'mon_programme': 'programme patient',
    }

    if page not in pages_autorisees:
        return JsonResponse({'success': False, 'error': 'Activité inconnue'}, status=400)

    tracer_action(
        utilisateur=request.user,
        patient=request.user.patient_profile,
        type_action='visite',
        action=f'Visite - {page}',
        details={
            'page': page,
            'motif': motif or pages_autorisees[page],
        }
    )
    return JsonResponse({'success': True})
           
def verifier_et_debloquer_defis(patient, resultat_exercice=None):
    """Vérifie et débloque les défis du patient"""
    from .models import Defi, DefiPatient, ProgressionGlobale
    from django.db.models import Max, Min
    
    # Récupérer ou créer la progression du patient
    progression, created = ProgressionGlobale.objects.get_or_create(patient=patient)

    def mettre_a_jour_niveau():
        if progression.points_totaux >= 46:
            progression.niveau_actuel = 'platine'
        elif progression.points_totaux >= 26:
            progression.niveau_actuel = 'or'
        elif progression.points_totaux >= 11:
            progression.niveau_actuel = 'argent'
        else:
            progression.niveau_actuel = 'bronze'

    def valider_defi(defi):
        defi_patient, created = DefiPatient.objects.get_or_create(
            patient=patient,
            defi=defi,
            defaults={'points_gagnes': 0, 'statut': 'assigned'}
        )

        points_avant = defi_patient.points_gagnes or 0
        etait_complete = defi_patient.statut == 'completed' or points_avant > 0

        if not etait_complete:
            progression.defis_completes += 1

        points_a_ajouter = max(0, defi.points - points_avant)
        if points_a_ajouter:
            progression.points_totaux += points_a_ajouter

        defi_patient.statut = 'completed'
        defi_patient.points_gagnes = defi.points
        defi_patient.date_completion = timezone.now()
        defi_patient.save()
        return not etait_complete or points_a_ajouter > 0

    if resultat_exercice and getattr(resultat_exercice, 'exercice', None):
        exercice = resultat_exercice.exercice
        nom_exercice = (exercice.nom or '').strip()
        categorie = (exercice.categorie or '').strip().lower()
        nom_defi = nom_exercice

        if nom_defi.startswith('[Défi]'):
            nom_defi = nom_defi.replace('[Défi]', '', 1).strip()
        elif nom_defi.startswith('[Defi]'):
            nom_defi = nom_defi.replace('[Defi]', '', 1).strip()

        if categorie in ['défi', 'defi'] or nom_exercice.startswith('[Défi]') or nom_exercice.startswith('[Defi]'):
            defi_associe = Defi.objects.filter(nom__iexact=nom_defi).order_by('-id').first()
            if defi_associe and valider_defi(defi_associe):
                mettre_a_jour_niveau()
                progression.save()
                return [defi_associe]
    
    # Compter les exercices validés par l'ergo
    exercices_valides = ResultatExercice.objects.filter(
        patient=patient,
        valide_par_ergo=True
    ).count()
    
    # Compter les jours d'activité
    jours_actifs = ResultatExercice.objects.filter(
        patient=patient
    ).dates('date_realisation', 'day').count()
    
    # Meilleure amplitude
    meilleure_amplitude = ResultatExercice.objects.filter(
        patient=patient
    ).aggregate(Max('amplitude_atteinte'))['amplitude_atteinte__max'] or 0
    
    # Vérifier uniquement les défis vraiment envoyés/assignés à ce patient.
    defis_disponibles = Defi.objects.filter(
        defipatient__patient=patient
    ).exclude(
        defipatient__statut='completed'
    ).exclude(
        defipatient__points_gagnes__gt=0
    ).distinct()
    
    nouveaux_defis = []
    
    for defi in defis_disponibles:
        est_complete = False
        
        if defi.nom == "Premier pas" and exercices_valides >= 1:
            est_complete = True
        elif defi.nom == "Régulier" and jours_actifs >= 5:
            est_complete = True
        elif defi.nom == "Flexible" and meilleure_amplitude >= 30:
            est_complete = True
        elif defi.nom == "Champion" and exercices_valides >= 10:
            est_complete = True
        elif defi.nom == "Expert" and meilleure_amplitude >= 60:
            est_complete = True
        elif defi.nom == "Master" and exercices_valides >= 20:
            est_complete = True
        elif defi.nom == "Légende" and meilleure_amplitude >= 80:
            est_complete = True
        
        if est_complete:
            if valider_defi(defi):
                nouveaux_defis.append(defi)
    
    # Mettre à jour le niveau
    mettre_a_jour_niveau()
    
    progression.save()
    return nouveaux_defis
def calculer_evolution_journaliere(patient, programme=None):
    """Construit l'évolution point par point, une saisie d'exercice = un point."""
    if not patient:
        return {
            'labels': ['Aucune saisie'],
            'satisfaction_data': [0],
            'douleur_data': [0],
            'evolution_satisfaction': 0,
        }

    resultats = ResultatExercice.objects.filter(patient=patient)
    if programme is not None:
        resultats = resultats.filter(exercice__programme=programme)

    resultats = resultats.select_related('exercice').order_by('date_realisation', 'id')
    if not resultats.exists():
        return {
            'labels': ['Aucune saisie'],
            'satisfaction_data': [0],
            'douleur_data': [0],
            'evolution_satisfaction': 0,
        }

    labels = []
    satisfaction_data = []
    douleur_data = []

    for index, resultat in enumerate(resultats, start=1):
        date_locale = algeria_localtime(resultat.date_realisation) if resultat.date_realisation else None
        heure = date_locale.strftime('%d/%m %H:%M') if date_locale else ''
        nom_exercice = (resultat.exercice.nom if resultat.exercice else 'Exercice') or 'Exercice'
        if len(nom_exercice) > 18:
            nom_exercice = f"{nom_exercice[:18]}..."

        labels.append(f"{index}. {nom_exercice} {heure}".strip())
        satisfaction_data.append(int(resultat.satisfaction or 0))
        douleur_data.append(int(resultat.douleur or 0))

    if len(satisfaction_data) >= 2:
        evolution_satisfaction = round(satisfaction_data[-1] - satisfaction_data[-2], 1)
    else:
        evolution_satisfaction = 0

    return {
        'labels': labels,
        'satisfaction_data': satisfaction_data,
        'douleur_data': douleur_data,
        'evolution_satisfaction': evolution_satisfaction,
    }


def calculer_indicateurs_programmes_patient(patient):
    """Indicateurs cumulatifs du patient, independants du programme ouvert."""
    if not patient:
        return {
            'adherence': 0,
            'assiduite': 0,
            'implication': 0,
            'visites': 0,
            'moyenne_note': 0,
            'total_seances': 0,
            'total_seances_prevues': 0,
            'total_exercices_valides': 0,
            'total_exercices_reference': 0,
        }

    resultats = ResultatExercice.objects.filter(patient=patient)
    total_resultats = resultats.count()
    total_exercices_reference = Exercice.objects.filter(programme__patient=patient).count()
    exercices_realises = resultats.values('exercice_id').distinct().count()
    total_prevu = max(total_exercices_reference, total_resultats, 1 if total_exercices_reference else 0)

    resultats_detaillees = sum(
        1 for res in resultats
        if (res.resultat_texte or '').strip()
        or (res.difficultes or '').strip()
        or bool(res.media_fichier)
        or int(res.douleur or 0) > 0
        or int(res.satisfaction or 0) > 0
    )

    visites = HistoriqueAction.objects.filter(
        patient=patient,
        utilisateur=patient.user,
        type_action__in=['programme', 'message', 'ressource', 'dossier', 'ia', 'patient', 'visite', 'seance']
    ).count()

    return {
        'adherence': round((exercices_realises / total_prevu) * 100) if total_prevu else 0,
        'assiduite': resultats.dates('date_realisation', 'day').count(),
        'implication': round((resultats_detaillees / total_resultats) * 100) if total_resultats else 0,
        'visites': visites or total_resultats,
        'moyenne_note': resultats.aggregate(avg=Avg('satisfaction'))['avg'] or 0,
        'total_seances': total_resultats,
        'total_seances_prevues': total_prevu,
        'total_exercices_valides': resultats.filter(
            Q(valide_par_ergo=True) | Q(statut_ergo='validated')
        ).count(),
        'total_exercices_reference': total_exercices_reference,
    }


def calculer_progression_defis(patient, programme=None):
    """Calcule la progression avec le nouveau barème 0-60 points"""
    from .models import ProgressionGlobale, Defi, DefiPatient

    try:
        progression, created = ProgressionGlobale.objects.get_or_create(patient=patient)
    except:
        return {
            'niveau_texte': 'Bronze',
            'niveau_badge': '🥉 Bronze',
            'points': 0,
            'defis_completes': 0,
            'total_defis': 0,
            'points_restants': 10,
            'prochain_niveau': 'Argent',
            'prochain_niveau_badge': '🥈 Argent',
            'pourcentage': 0
        }
    
    if programme is not None:
        defis_programme = list(Exercice.objects.filter(
            programme=programme
        ).filter(
            Q(categorie__iexact='Défi') |
            Q(categorie__iexact='Defi') |
            Q(nom__startswith='[Défi]') |
            Q(nom__startswith='[Defi]')
        ).order_by('ordre', 'id'))

        total_defis = len(defis_programme)
        completed_defis = 0
        points = 0

        for exercice in defis_programme:
            nom_defi = (exercice.nom or '').strip()
            if nom_defi.startswith('[Défi]'):
                nom_defi = nom_defi.replace('[Défi]', '', 1).strip()
            elif nom_defi.startswith('[Defi]'):
                nom_defi = nom_defi.replace('[Defi]', '', 1).strip()

            defi = Defi.objects.filter(nom__iexact=nom_defi).order_by('-id').first()
            defi_patient = DefiPatient.objects.filter(patient=patient, defi=defi).first() if defi else None
            resultat_existe = ResultatExercice.objects.filter(patient=patient, exercice=exercice).exists()
            deja_complete = bool(defi_patient and (defi_patient.statut == 'completed' or (defi_patient.points_gagnes or 0) > 0))

            if resultat_existe or deja_complete:
                completed_defis += 1
                points_defi = defi.points if defi else 0
                points += points_defi

                if defi and not deja_complete:
                    defi_patient, _ = DefiPatient.objects.get_or_create(
                        patient=patient,
                        defi=defi,
                        defaults={'points_gagnes': 0, 'statut': 'assigned'}
                    )
                    defi_patient.statut = 'completed'
                    defi_patient.points_gagnes = points_defi
                    defi_patient.date_completion = timezone.now()
                    defi_patient.save()
    else:
        assigned_defis = DefiPatient.objects.filter(patient=patient)
        completed_assigned_defis = assigned_defis.filter(
            Q(statut='completed') | Q(points_gagnes__gt=0)
        )
        total_defis = assigned_defis.count()
        completed_defis = completed_assigned_defis.count()
        points = sum(defi_patient.points_gagnes or 0 for defi_patient in completed_assigned_defis)
    
    # NOUVEAU BARÈME
    if points >= 46:
        niveau = 'platine'
        prochain_niveau = 'Platine'
        points_restants = max(0, 60 - points)
        pourcentage = round((points / 60) * 100)
    elif points >= 26:
        niveau = 'or'
        prochain_niveau = 'Platine'
        points_restants = 46 - points
        pourcentage = round((points / 45) * 100)
    elif points >= 11:
        niveau = 'argent'
        prochain_niveau = 'Or'
        points_restants = 26 - points
        pourcentage = round((points / 25) * 100)
    else:
        niveau = 'bronze'
        prochain_niveau = 'Argent'
        points_restants = 11 - points
        pourcentage = round((points / 10) * 100)
    
    niveaux_affichage = {
        'bronze': 'Bronze',
        'argent': 'Argent',
        'or': 'Or',
        'platine': 'Platine'
    }
    niveaux_badges = {
        'bronze': '🥉 Bronze',
        'argent': '🥈 Argent',
        'or': '🥇 Or',
        'platine': '💎 Platine'
    }
    prochain_niveau_cle = {
        'Argent': 'argent',
        'Or': 'or',
        'Platine': 'platine',
    }

    if (
        progression.points_totaux != points
        or progression.defis_completes != completed_defis
        or progression.niveau_actuel != niveau
    ):
        progression.points_totaux = points
        progression.defis_completes = completed_defis
        progression.niveau_actuel = niveau
        progression.save()
    
    return {
        'niveau_texte': niveaux_affichage.get(niveau, 'Bronze'),
        'niveau_badge': niveaux_badges.get(niveau, '🥉 Bronze'),
        'points': points,
        'defis_completes': completed_defis,
        'total_defis': total_defis,
        'points_restants': points_restants,
        'prochain_niveau': prochain_niveau,
        'prochain_niveau_badge': niveaux_badges.get(prochain_niveau_cle.get(prochain_niveau, 'argent'), '🥈 Argent'),
        'pourcentage': pourcentage
    }
def _serialiser_exercice_pour_patient(exercice):
    medias = []

    for media in exercice.medias.all():
        if media.fichier:
            medias.append({
                'url': media.fichier.url,
                'type': 'video' if media.fichier.name.lower().endswith(('.mp4', '.webm', '.ogg')) else 'photo'
            })

    if exercice.media_demo:
        medias.append({
            'url': exercice.media_demo.url,
            'type': 'video' if exercice.media_demo.name.lower().endswith(('.mp4', '.webm', '.ogg')) else 'photo'
        })

    if exercice.bibliotheque_exercice:
        for media in exercice.bibliotheque_exercice.medias.all():
            if media.fichier:
                medias.append({
                    'url': media.fichier.url,
                    'type': 'video' if media.fichier.name.lower().endswith(('.mp4', '.webm', '.ogg')) else 'photo'
                })

    categorie = exercice.categorie or ''
    est_contenu_suivi = categorie.lower() in ['suivi', 'suivi ia'] or (
        int(exercice.series or 0) == 0
        and int(exercice.repetitions or 0) == 0
        and not exercice.temps_exercice
    )
    nom_exercice = exercice.nom or 'Exercice'
    if nom_exercice.strip().lower() == 'programme ia':
        nom_exercice = 'Programme'
    repos = exercice.repos or ('' if est_contenu_suivi else '45s')
    return {
        'id': exercice.id,
        'nom': nom_exercice,
        'name': {
            'fr': nom_exercice,
            'en': nom_exercice,
            'ar': nom_exercice,
        },
        'instructions': exercice.instructions or '',
        'objectif': exercice.objectif or '',
        'objective': exercice.objectif or '',
        'materiel_necessaire': exercice.materiel_necessaire or '',
        'categorie': categorie,
        'temps_exercice': exercice.temps_exercice or '',
        'series': exercice.series,
        'repetitions': exercice.repetitions,
        'repos': repos,
        'completed': False,
        'medias': medias,
    }


def _construire_programme_patient(exercices, mode='programme_complet'):
    jours_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    programme_patient = {jour: [] for jour in jours_fr}
    exercices = list(exercices)
    jour_depart = date.today().weekday()

    if mode == 'single_exercice':
        if exercices:
            jour_actuel = jours_fr[jour_depart]
            programme_patient[jour_actuel].append(_serialiser_exercice_pour_patient(exercices[0]))
        return programme_patient

    jour_actuel = jours_fr[jour_depart]
    for exercice in exercices:
        programme_patient[jour_actuel].append(_serialiser_exercice_pour_patient(exercice))

    return programme_patient


def _statut_jour_programme(jour, reference_date=None):
    jours_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    try:
        index_jour = jours_fr.index(jour)
    except ValueError:
        return 'unknown'

    aujourd_hui = date.today()
    if reference_date:
        debut_semaine = reference_date - timedelta(days=reference_date.weekday())
        date_jour = debut_semaine + timedelta(days=index_jour)
        if date_jour == aujourd_hui:
            return 'today'
        return 'past' if date_jour < aujourd_hui else 'future'

    index_aujourdhui = aujourd_hui.weekday()
    if index_jour == index_aujourdhui:
        return 'today'
    return 'past' if index_jour < index_aujourdhui else 'future'


def _fusionner_programmes_envoyes(programmes, conserver_archives_passees=True):
    jours_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    programme_fusionne = {jour: [] for jour in jours_fr}
    exercices_deja_vus = {jour: set() for jour in jours_fr}
    derniere_date_envoi = None

    for programme_envoye in list(programmes):
        if derniere_date_envoi is None:
            derniere_date_envoi = programme_envoye.date_envoi
        date_reference = None
        if programme_envoye.date_envoi:
            date_locale = algeria_localtime(programme_envoye.date_envoi)
            date_reference = date_locale.date() if date_locale else None
        programme = programme_envoye.programme if isinstance(programme_envoye.programme, dict) else {}
        for jour in jours_fr:
            if programme_envoye.archive and (
                not conserver_archives_passees or _statut_jour_programme(jour, date_reference) != 'past'
            ):
                continue

            exercices = programme.get(jour) or []
            if isinstance(exercices, list):
                for exercice in exercices:
                    if not isinstance(exercice, dict):
                        continue
                    cle_exercice = str(exercice.get('id') or exercice.get('nom') or exercice.get('title') or exercice)
                    if cle_exercice in exercices_deja_vus[jour]:
                        continue
                    exercices_deja_vus[jour].add(cle_exercice)
                    programme_fusionne[jour].append(exercice)

    return programme_fusionne, derniere_date_envoi


def _appliquer_resultats_au_programme_patient(programme_patient, patient):
    """Normalise le JSON patient et marque les exercices deja realises."""
    if not isinstance(programme_patient, dict):
        return programme_patient

    resultats = ResultatExercice.objects.filter(patient=patient).order_by('date_realisation', 'id') if patient else []
    resultats_par_exercice = {}
    for resultat in resultats:
        resultats_par_exercice[str(resultat.exercice_id)] = resultat

    for exercices in programme_patient.values():
        if not isinstance(exercices, list):
            continue
        for exercice in exercices:
            if not isinstance(exercice, dict):
                continue
            nom = exercice.get('nom') or exercice.get('title') or 'Exercice'
            if str(nom).strip().lower() == 'programme ia':
                nom = 'Programme'
            exercice['nom'] = nom
            if not isinstance(exercice.get('name'), dict):
                exercice['name'] = {'fr': nom, 'en': nom, 'ar': nom}
            else:
                exercice['name'].setdefault('fr', nom)
                exercice['name'].setdefault('en', nom)
                exercice['name'].setdefault('ar', nom)
                if str(exercice['name'].get('fr', '')).strip().lower() == 'programme ia':
                    exercice['name']['fr'] = nom
                    exercice['name']['en'] = nom
                    exercice['name']['ar'] = nom
            categorie = str(exercice.get('categorie') or '').strip().lower()
            if categorie in ['suivi', 'suivi ia'] or str(exercice.get('source') or '').startswith('suivi'):
                exercice['repos'] = ''
                exercice['temps_exercice'] = exercice.get('temps_exercice') or ''
                exercice['series'] = int(exercice.get('series') or 0)
                exercice['repetitions'] = int(exercice.get('repetitions') or 0)
            resultat = resultats_par_exercice.get(str(exercice.get('id')))
            if not resultat:
                continue
            exercice['completed'] = True
            exercice['result'] = resultat.resultat_texte or ''
            exercice['pain'] = resultat.douleur
            exercice['douleur'] = resultat.douleur
            exercice['satisfaction'] = resultat.satisfaction
            exercice['difficulties'] = resultat.difficultes or ''
            exercice['resultat_id'] = resultat.id
            exercice['statut_ergo'] = resultat.statut_ergo
            exercice['valide_par_ergo'] = resultat.valide_par_ergo

    return programme_patient


def _sauvegarder_programme_envoye(patient, programme_patient, archive_existing=True):
    from .models import ProgrammeEnvoye

    if archive_existing:
        ProgrammeEnvoye.objects.filter(patient=patient, archive=False).update(archive=True)
    return ProgrammeEnvoye.objects.create(
        patient=patient,
        programme=programme_patient,
        est_lu=False
    )


def _resolve_patient_profile(patient_id):
    patient = PatientProfile.objects.filter(id=patient_id).select_related('user').first()
    if patient:
        return patient
    return get_object_or_404(PatientProfile.objects.select_related('user'), user_id=patient_id)


def _ajouter_exercice_au_programme_patient(patient, exercice):
    from .models import ProgrammeEnvoye

    jours_fr = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    jour_actuel = jours_fr[date.today().weekday()]
    programme_actif = ProgrammeEnvoye.objects.filter(
        patient=patient,
        archive=False
    ).order_by('-date_envoi').first()

    if programme_actif and isinstance(programme_actif.programme, dict):
        programme_patient = {
            jour: list(programme_actif.programme.get(jour, []))
            for jour in jours_fr
        }
    else:
        programme_patient = {jour: [] for jour in jours_fr}

    deja_present = any(
        str(item.get('id')) == str(exercice.id)
        for exercices in programme_patient.values()
        for item in exercices
    )

    if deja_present:
        return None, True

    programme_patient[jour_actuel].insert(0, _serialiser_exercice_pour_patient(exercice))
    return _sauvegarder_programme_envoye(patient, programme_patient), False


@login_required
@csrf_exempt
def envoyer_programme_patient_api(request):
    """Envoyer au patient le programme exact sélectionné par l'ergothérapeute"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    try:
        data = json.loads(request.body)
        programme_id = data.get('programme_id')
        patient_id = data.get('patient_id')

        if not programme_id:
            return JsonResponse({'success': False, 'error': 'Programme non spécifié'}, status=400)

        programme = get_object_or_404(ProgrammeExercice, id=programme_id)
        patient = _resolve_patient_profile(patient_id) if patient_id else programme.patient
        exercices_bdd = programme.exercices.all().order_by('-id')

        if not exercices_bdd.exists():
            return JsonResponse({'success': False, 'error': 'Aucun exercice dans ce programme'}, status=400)

        programme_patient = _construire_programme_patient(exercices_bdd, mode='programme_complet')
        nouveau_programme = _sauvegarder_programme_envoye(patient, programme_patient)

        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='programme',
            action='Programme envoye au patient',
            details={
                'programme': programme.nom,
                'nombre_exercices': exercices_bdd.count(),
            }
        )

        
        return JsonResponse({
            'success': True,
            'message': f'{exercices_bdd.count()} exercice(s) envoyé(s) au patient',
            'patient_id': patient.id,
            'patient_user_id': patient.user_id,
            'patient_nom': f'{patient.user.prenom} {patient.user.nom}'.strip(),
            'programme_envoye_id': nouveau_programme.id,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
@csrf_exempt
def envoyer_un_exercice_api(request):
    """Envoyer un seul exercice au patient"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    try:
        data = json.loads(request.body)
        exercice_id = data.get('exercice_id')
        patient_id = data.get('patient_id')

        if not exercice_id or not patient_id:
            return JsonResponse({'success': False, 'error': 'Exercice ou patient non spécifié'}, status=400)

        exercice = get_object_or_404(Exercice, id=exercice_id)
        patient = _resolve_patient_profile(patient_id)

        _, deja_present = _ajouter_exercice_au_programme_patient(patient, exercice)

        if deja_present:
            return JsonResponse({
                'success': True,
                'message': f'L\'exercice "{exercice.nom}" est deja dans le programme du patient',
                'patient_id': patient.id,
                'patient_user_id': patient.user_id,
                'patient_nom': f'{patient.user.prenom} {patient.user.nom}'.strip(),
            })

        tracer_action(
            utilisateur=request.user,
            patient=patient,
            type_action='programme',
            action='Exercice envoye au patient',
            details={
                'exercice': exercice.nom,
            }
        )

        return JsonResponse({
            'success': True,
            'message': f'Exercice "{exercice.nom}" ajoute au programme du patient',
            'patient_id': patient.id,
            'patient_user_id': patient.user_id,
            'patient_nom': f'{patient.user.prenom} {patient.user.nom}'.strip(),
        })

        programme_patient = _construire_programme_patient([exercice], mode='single_exercice')
        _sauvegarder_programme_envoye(patient, programme_patient)

        return JsonResponse({
            'success': True,
            'message': f'Exercice "{exercice.nom}" envoyé au patient'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
def envoyer_exercice_direct(request, exercice_id, patient_id):
    """Version ultra simple - pas de JSON, pas de fetch"""
    from .models import Exercice, PatientProfile, ProgrammeEnvoye
    
    exercice = get_object_or_404(Exercice, id=exercice_id)
    patient = get_object_or_404(PatientProfile, id=patient_id)
    
    # Programme avec 1 exercice
    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    programme = {jour: [] for jour in jours}
    
    for jour in jours:
        programme[jour].append({
            'id': exercice.id,
            'nom': exercice.nom,
            'instructions': exercice.instructions or '',
            'series': exercice.series,
            'repetitions': exercice.repetitions,
            'completed': False
        })
    
    ProgrammeEnvoye.objects.filter(patient=patient, est_lu=False).delete()
    ProgrammeEnvoye.objects.create(patient=patient, programme=programme, est_lu=False)
    
    return JsonResponse({'success': True, 'message': f'Exercice {exercice.nom} envoyé'})

@login_required
def api_get_programme_bdd(request):
    """Récupérer le programme depuis la base de données"""
    try:
        from .models import ProgrammeEnvoye
        
        patient_profile = request.user.patient_profile
        
        # Récupérer TOUS les programmes non archivés (le plus récent en premier)
        programmes = ProgrammeEnvoye.objects.filter(
            patient=patient_profile
        ).order_by('-date_envoi')
        
        if programmes.exists():
            programme_fusionne, date_envoi = _fusionner_programmes_envoyes(programmes)
            programme_fusionne = _appliquer_resultats_au_programme_patient(programme_fusionne, patient_profile)
            total_exercices = sum(
                len(exercices)
                for exercices in programme_fusionne.values()
                if isinstance(exercices, list)
            )

            return JsonResponse({
                'success': True,
                'programme': programme_fusionne,
                'total_exercices': total_exercices,
                'date_envoi': date_envoi.isoformat() if date_envoi else None
            })
        programme_actif = ProgrammeExercice.objects.filter(
            patient=patient_profile,
            actif=True
        ).order_by('-date_debut').first()

        if programme_actif:
            exercices = programme_actif.exercices.all().order_by('-id')
            if exercices.exists():
                programme_envoye = _sauvegarder_programme_envoye(
                    patient_profile,
                    _construire_programme_patient(exercices, mode='programme_complet')
                )
                programme_envoye.programme = _appliquer_resultats_au_programme_patient(
                    programme_envoye.programme,
                    patient_profile
                )
                return JsonResponse({
                    'success': True,
                    'programme': programme_envoye.programme,
                    'date_envoi': programme_envoye.date_envoi.isoformat()
                })

        return JsonResponse({'success': False, 'programme': None})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'programme': None})
@login_required
def api_get_programme_session(request):
    """Récupérer le programme depuis la session et le supprimer après lecture"""
    try:
        patient_id = request.GET.get('patient_id')
        
        # Si pas de patient_id dans l'URL, utiliser le patient connecté
        if not patient_id and request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
            patient_id = request.user.patient_profile.id
        
        if not patient_id:
            return JsonResponse({'success': False, 'programme': None, 'error': 'Patient non spécifié'})
        
        # Récupérer le programme depuis la session
        session_key = f'programme_patient_{patient_id}'
        programme = request.session.get(session_key)
        
        # SUPPRIMER LE PROGRAMME DE LA SESSION APRÈS LECTURE
        if programme:
            del request.session[session_key]
            request.session.modified = True
            return JsonResponse({'success': True, 'programme': programme})
        else:
            return JsonResponse({'success': False, 'programme': None})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'programme': None, 'error': str(e)})
@login_required
def api_patient_messages(request):
    """Récupérer les messages du patient (depuis le thérapeute)"""
    try:
        messages = Message.objects.filter(
            destinataire=request.user,
            expediteur__role='ergo'
        ).order_by('-date_envoi')
        
        messages_list = []
        for msg in messages:
            messages_list.append({
                'id': msg.id,
                'sujet': msg.sujet,
                'contenu': msg.contenu,
                'date_envoi': msg.date_envoi.strftime('%d/%m/%Y %H:%M'),
                'lu': msg.est_lu_par_destinataire
            })
        
        return JsonResponse({'success': True, 'messages': messages_list})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def api_patient_message_lu(request, message_id):
    """Marquer un message comme lu"""
    try:
        message = get_object_or_404(Message, id=message_id, destinataire=request.user)
        message.est_lu_par_destinataire = True
        message.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
@login_required
def api_get_programme_patient(request):
    """Récupérer le programme envoyé par le thérapeute"""
    patient_id = request.GET.get('patient_id')
    if not patient_id or int(patient_id) != request.user.patient_profile.id:
        return JsonResponse({'success': False, 'error': 'Non autorisé'})
    
    import tempfile
    import os
    
    temp_file = os.path.join(tempfile.gettempdir(), f'programme_patient_{patient_id}.json')
    if os.path.exists(temp_file):
        with open(temp_file, 'r', encoding='utf-8') as f:
            programme = json.load(f)
        return JsonResponse({'success': True, 'programme': programme})
    
    return JsonResponse({'success': False, 'programme': None})

@login_required
@require_POST
def supprimer_exercice_programme(request):
    """Supprimer un exercice et NOTIFIER SPÉCIFIQUEMENT le patient"""
    exercice_id = request.POST.get('exercice_id')
    programme_id = request.POST.get('programme_id')
    
    if exercice_id:
        exercice = get_object_or_404(Exercice, id=exercice_id)
        programme_source = exercice.programme
        patient = programme_source.patient
        nom_exercice = exercice.nom
        
        # Supprimer l'exercice
        exercice.delete()
        
        # Mettre à jour le programme patient
        programme = ProgrammeExercice.objects.get(id=programme_id) if programme_id else programme_source
        exercices_restants = programme.exercices.all().order_by('-id')
        _sauvegarder_programme_envoye(
            patient,
            _construire_programme_patient(exercices_restants, mode='programme_complet')
        )
        
        # 🔥 NOTIFICATION SPÉCIFIQUE (pas un message normal)
        # Utiliser localStorage pour notifier immédiatement
        notification_key = f'swr_update_programme_{patient.id}'
        request.session[notification_key] = {
            'type': 'recharger_programme',
            'message': f'L\'exercice "{nom_exercice}" a été supprimé'
        }
        
        messages.success(request, f"✅ Exercice '{nom_exercice}' supprimé")
    
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect(request.META.get('HTTP_REFERER', '/Programmes/'))
@login_required
def api_get_resultats_patient(request):
    """Récupérer les résultats d'un patient pour l'ergo"""
    patient_id = request.GET.get('patient_id')
    programme_id = request.GET.get('programme_id')

    programme = None
    if programme_id:
        programme = ProgrammeExercice.objects.select_related('patient').filter(id=programme_id).first()

    if not patient_id and programme:
        patient_id = programme.patient_id

    if not patient_id:
        return JsonResponse({'success': False, 'error': 'Patient non spécifié'})

    patient = get_object_or_404(PatientProfile, id=patient_id)
    if programme and programme.patient_id != patient.id:
        programme = None
    elif not programme and programme_id:
        programme = ProgrammeExercice.objects.filter(id=programme_id, patient=patient).first()
    resultats = ResultatExercice.objects.filter(patient=patient)
    total_resultats = resultats.count()
    resultats = resultats.select_related('exercice', 'exercice__programme').order_by('-date_realisation')[:30]

    resultats_list = []
    for r in resultats:
        date_locale = algeria_localtime(r.date_realisation) if r.date_realisation else None
        resultats_list.append({
            'id': r.id,
            'exercice_nom': r.exercice.nom,
            'programme_id': r.exercice.programme_id,
            'programme_nom': r.exercice.programme.nom if r.exercice and r.exercice.programme else '',
            'objectif': r.exercice.objectif or '',
            'amplitude': r.amplitude_atteinte,
            'douleur': r.douleur,
            'satisfaction': r.satisfaction,
            'resultat': r.resultat_texte,
            'difficultes': r.difficultes,
            'date': date_locale.strftime('%d/%m/%Y %H:%M') if date_locale else '',
            'jour': date_locale.strftime('%d/%m/%Y') if date_locale else '',
            'heure': date_locale.strftime('%H:%M') if date_locale else '',
            'datetime': date_locale.isoformat() if date_locale else '',
            'sort_datetime': date_locale.isoformat() if date_locale else '',
            'valide': r.valide_par_ergo,
            'statut_ergo': r.statut_ergo,
            'commentaire_ergo': r.commentaire_ergo or '',
            'media_url': r.media_fichier.url if r.media_fichier else None,
            'media_type': r.media_type if r.media_fichier else ''
        })

    evaluations_patient = ProgressionPatient.objects.filter(
        patient=patient
    ).order_by('-date')[:20]

    for ev in evaluations_patient:
        ev_dt = timezone.make_aware(datetime.combine(ev.date, datetime.min.time())) if timezone.is_naive(datetime.combine(ev.date, datetime.min.time())) else datetime.combine(ev.date, datetime.min.time())
        resultats_list.append({
            'id': f'evaluation-{ev.id}',
            'type': 'evaluation_jour',
            'exercice_nom': 'Auto-évaluation du jour',
            'programme_id': programme.id if programme else '',
            'programme_nom': programme.nom if programme else '',
            'objectif': 'Comment vous sentez-vous aujourd’hui ?',
            'amplitude': 0,
            'douleur': ev.douleur,
            'fatigue': ev.fatigue,
            'humeur': ev.humeur,
            'satisfaction': ev.satisfaction,
            'resultat': 'Évaluation enregistrée',
            'difficultes': ev.notes,
            'date': ev.date.strftime('%d/%m/%Y'),
            'jour': ev.date.strftime('%d/%m/%Y'),
            'heure': '',
            'datetime': ev.date.isoformat(),
            'sort_datetime': ev_dt.isoformat(),
            'valide': True,
            'statut_ergo': 'validated',
            'commentaire_ergo': '',
            'media_url': None,
            'media_type': '',
        })

    reponses_questions_patient = ReponseQuestionJour.objects.filter(
        patient=patient
    ).select_related('question').order_by('-date_reponse')[:20]

    for rep in reponses_questions_patient:
        date_locale = algeria_localtime(rep.date_reponse) if rep.date_reponse else None
        resultats_list.append({
            'id': f'question-{rep.id}',
            'type': 'question_jour',
            'exercice_nom': 'Réponse à la question du jour',
            'programme_id': programme.id if programme else '',
            'programme_nom': programme.nom if programme else '',
            'objectif': rep.question.question,
            'amplitude': 0,
            'douleur': rep.douleur,
            'fatigue': rep.fatigue,
            'humeur': rep.humeur,
            'satisfaction': rep.satisfaction,
            'resultat': rep.reponse,
            'difficultes': rep.notes,
            'date': date_locale.strftime('%d/%m/%Y %H:%M') if date_locale else '',
            'jour': date_locale.strftime('%d/%m/%Y') if date_locale else '',
            'heure': date_locale.strftime('%H:%M') if date_locale else '',
            'datetime': date_locale.isoformat() if date_locale else '',
            'sort_datetime': date_locale.isoformat() if date_locale else '',
            'valide': True,
            'statut_ergo': 'validated',
            'commentaire_ergo': '',
            'media_url': None,
            'media_type': '',
        })

    resultats_list.sort(key=lambda item: item.get('sort_datetime') or '', reverse=True)

    visites = HistoriqueAction.objects.filter(
        patient=patient,
        utilisateur=patient.user,
        type_action__in=['programme', 'message', 'ressource', 'dossier', 'ia', 'patient', 'visite', 'seance']
    ).count()
    if visites == 0:
        visites = total_resultats

    stats_patient = calculer_indicateurs_programmes_patient(patient)

    return JsonResponse({
        'success': True,
        'resultats': resultats_list,
        'total_resultats': len(resultats_list),
        'visites': visites,
        'stats': stats_patient,
        'evolution': calculer_evolution_journaliere(patient),
        'progression_defis': calculer_progression_defis(patient),
    })
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# stockage temporaire simple en mémoire
ERGO_NOTIFICATIONS = []


@login_required
def api_ergo_notifications(request):
    """Retourne les notifications ergo en attente"""
    try:
        if request.user.role != 'ergo':
            return JsonResponse({'notifications': []}, status=403)

        notifications = list(ERGO_NOTIFICATIONS)

        resultats_recents = ResultatExercice.objects.select_related(
            'patient__user',
            'exercice'
        ).order_by('-date_realisation')[:50]

        for resultat in resultats_recents:
            date_locale = algeria_localtime(resultat.date_realisation) if resultat.date_realisation else None
            notifications.append({
                'id': f'nouveau-resultat-{resultat.id}',
                'type': 'nouveau_resultat',
                'resultat_id': resultat.id,
                'patient_id': resultat.patient.id,
                'patient_nom': resultat.patient.user.nom,
                'patient_prenom': resultat.patient.user.prenom,
                'exercice_id': resultat.exercice.id,
                'exercice_nom': resultat.exercice.nom,
                'programme_id': resultat.exercice.programme_id,
                'target_url': f'/Programmes/?programme_id={resultat.exercice.programme_id}&tab=results&resultat_id={resultat.id}',
                'resultat': resultat.resultat_texte or '',
                'amplitude': resultat.amplitude_atteinte,
                'douleur': resultat.douleur,
                'satisfaction': resultat.satisfaction,
                'difficultes': resultat.difficultes or '',
                'date': date_locale.strftime('%d/%m/%Y') if date_locale else '',
                'heure': date_locale.strftime('%H:%M') if date_locale else '',
                'datetime': date_locale.isoformat() if date_locale else '',
            })

        unread_patient_messages = Message.objects.filter(
            destinataire=request.user,
            expediteur__role='patient',
            est_lu_par_destinataire=False
        ).select_related('expediteur').order_by('-date_envoi')[:20]

        for msg in unread_patient_messages:
            notifications.append({
                'id': f'message-{msg.id}',
                'type': 'message',
                'message_id': msg.id,
                'patient_user_id': msg.expediteur.id,
                'patient_nom': msg.expediteur.nom,
                'patient_prenom': msg.expediteur.prenom,
                'text': (msg.contenu or '')[:140],
                'date': msg.date_envoi.isoformat(),
                'target_url': f'/Programmes/?patient_id={msg.expediteur.id}',
            })

        reponses_questions = ReponseQuestionJour.objects.select_related(
            'patient__user',
            'question'
        ).order_by('-date_reponse')[:20]

        for rep in reponses_questions:
            notifications.append({
                'id': f'question-jour-{rep.id}',
                'type': 'question_jour',
                'patient_id': rep.patient.id,
                'patient_nom': rep.patient.user.nom,
                'patient_prenom': rep.patient.user.prenom,
                'text': f"Question du jour: {rep.reponse}",
                'date': algeria_localtime(rep.date_reponse).strftime('%d/%m/%Y') if rep.date_reponse else '',
                'heure': algeria_localtime(rep.date_reponse).strftime('%H:%M') if rep.date_reponse else '',
                'target_url': f'/Programmes/?patient_id={rep.patient.id}&tab=results',
            })

        return JsonResponse({
            'success': True,
            'notifications': notifications
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'notifications': [],
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_ergo_clear_notification(request):
    """Vide les notifications ergo"""
    try:
        if request.user.role != 'ergo':
            return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

        ERGO_NOTIFICATIONS.clear()

        return JsonResponse({
            'success': True
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)    
@login_required
def api_get_patient_resultats(request):
    """Récupérer les résultats d'un patient (côté patient)"""
    try:
        patient_profile = request.user.patient_profile
        resultats = ResultatExercice.objects.filter(
            patient=patient_profile
        ).select_related('exercice').order_by('-date_realisation')[:50]

        resultats_list = []
        for r in resultats:
            date_locale = algeria_localtime(r.date_realisation) if r.date_realisation else None
            resultats_list.append({
                'id': r.id,
                'exercice_id': r.exercice.id,
                'exercice_nom': r.exercice.nom,
                'objectif': r.exercice.objectif or '',
                'amplitude': r.amplitude_atteinte,
                'douleur': r.douleur,
                'satisfaction': r.satisfaction,
                'resultat': r.resultat_texte,
                'difficultes': r.difficultes,
                'date': date_locale.strftime('%d/%m/%Y %H:%M') if date_locale else '',
                'jour': date_locale.strftime('%d/%m/%Y') if date_locale else '',
                'heure': date_locale.strftime('%H:%M') if date_locale else '',
                'datetime': date_locale.isoformat() if date_locale else '',
                'valide_par_ergo': r.valide_par_ergo,
                'statut_ergo': r.statut_ergo,
                'commentaire_ergo': r.commentaire_ergo or '',
                'media_url': r.media_fichier.url if r.media_fichier else None,
                'media_type': r.media_type if r.media_fichier else None
            })

        return JsonResponse({'success': True, 'resultats': resultats_list})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

