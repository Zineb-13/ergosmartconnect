from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
from datetime import timedelta
# --- 1. GESTION DES UTILISATEURS ET ROLES ---

class User(AbstractUser):
    ROLE_CHOICES = (
        ('patient', 'Patient'),
        ('ergo', 'Ergothérapeute'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    code= models.CharField(max_length=50)
    last_seen = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.role})"

# --- 2. DONNÉES PATIENT (PROFIL MÉDICAL) ---

class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_naissance = models.DateField()
    sexe = models.CharField(max_length=10, choices=[('F', 'Femme'), ('H', 'Homme')])
    telephone = models.CharField(max_length=20)
    adresse = models.TextField(blank=True, null=True)
    nom_affichage = models.CharField(max_length=50, blank=True, null=True)
    langue = models.CharField(max_length=30, default='Français')
    def age(self):
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )
    def progression(self):
        # exemple simple basé sur douleur
        return max(0, 100 - (self.douleur_effort * 10))
    
    # Détails Fracture
    TYPE_FRACTURE = [
        ('pouteau', 'Pouteau Colles'),
        ('scaphoide', 'Scaphoïde'),
        ('articulaire', 'Articulaire'),
        ('autre', 'Autre / Je ne sais pas'),
    ]
    type_fracture = models.CharField(max_length=50, choices=TYPE_FRACTURE)
    date_fracture = models.DateField()
    cote_atteint = models.CharField(max_length=50, choices=[('D', 'Droit'), ('G', 'Gauche'), ('B', 'Les deux')])
    main_dominante = models.BooleanField(default=False)
    
    TRAITEMENT = [
        ('platre', 'Plâtre'),
        ('chirurgie', 'Intervention chirurgicale'),
        ('orthese', 'Orthèse / Attelle'),
        ('autre', 'Autre'),
    ]
    traitement_recu = models.CharField(max_length=50, choices=TRAITEMENT)

    # Douleur et Symptômes
    douleur_repos = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    douleur_effort = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    
    RAIDEUR_CHOICES = [('leger', 'Léger'), ('modere', 'Modéré'), ('important', 'Important'), ('inconnu', 'Je ne sais pas')]
    raideur_gonflement = models.CharField(max_length=20, choices=RAIDEUR_CHOICES)

    # Limitations (Stockées en JSON ou TextField pour la flexibilité)
    limitations = models.TextField(help_text="Habillage, Toilette, Cuisine, etc.", blank=True)
    autres_problemes_sante = models.TextField(blank=True, null=True)   
    medicaments = models.TextField(blank=True)
    allergies = models.TextField(blank=True)

    # Profession et Impact
    STATUT_PRO = [
        ('bureau', 'Employé de bureau'),
        ('manuel', 'Travailleur manuel'),
        ('etudiant', 'Étudiant'),
        ('retraite', 'Retraité'),
        ('chomage', 'Sans emploi'),
        ('autre', 'Autre'),
    ]
    profession = models.CharField(max_length=50, choices=STATUT_PRO)

    impact = [
        ('arret', 'arret complet'),
        ('travailleger', 'travail adapter léger'),
        ('teletravail', 'télétravail possible'),
        ('pasimpaction', "pas d'Impact"),
        ('applicable', "non applicable"),
    ]
    impact_travail = models.CharField(max_length=100, choices=impact)
    
    act = [
        ('Sport', 'Sport'),
        ('Cuisine', 'Cuisine'),
        ('BricolageJardinage', 'Bricolage/Jardinage'),
        ('ÉcritureDessin', "Écriture/Dessin"),
        ('Informatique', "Informatique"),
        ('Musique', "Musique"),
        ('Artisanat', "Artisanat"),
    ]
    activites_anciennes = models.TextField(blank=True, choices=act)
    autres_activite = models.TextField(max_length=100)

    objectif_pri = [
        ('Retrouver_lautonomie', "Retrouver l'autonomie (toilette, habillage, soins personnels)"),
        ('Améliorer la prise', "Améliorer la prise / préhension (tenir un verre, ouvrir un bocal)"),
        ('Diminuer la douleur', "Diminuer la douleur et reprendre les gestes sans appréhension"),
        ('Récupérer la mobilité', "Récupérer la mobilité (flexion/extension, pronation/supination)"),
        ('Récupérer la force', "Récupérer la force (porter, pousser, tirer)"),
        ('Améliorer la motricité fine', "Améliorer la motricité fine (écriture, boutonner, smartphone)"),
        ('Reprendre le travail', "Reprendre le travail / gestes professionnels"),
        ('Reprendre_les_loisirs', "Reprendre les loisirs (sport, musique, bricolage)"),
    ]
    objectif_principal = models.TextField(choices=objectif_pri)
    objectif_autre = models.TextField()

    Comment_avez_vous_ent = [
        ('Recommandation_medecin', "Recommandation médecin"),
        ('Recommandation_ergotherapeute', "Recommandation ergothérapeute"),
        ('Recherche_internet', "Recherche internet"),
        ('Reseaux_sociaux', "Réseaux sociaux"),
        ('Boucheoreille', "Bouche-à-oreille"),
    ]
    Comment_avez_vous_entendu = models.TextField(choices=Comment_avez_vous_ent)
    Comment_avez_vous_entendu_autre = models.TextField()
    
    # Consentements
    cgu_accepte = models.BooleanField(default=False)
    consentement_sante = models.BooleanField(default=False)
    aide_ia_anonyme = models.BooleanField(default=False)
    recevoir_rappels = models.BooleanField(default=False)
    statut_programme = models.CharField(max_length=20, default='en_cours', choices=[
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
    ])
    def __str__(self):
        return f"Dossier de {self.user.nom}"
    def get_derniere_evaluation(self):
        """Récupère la dernière évaluation du patient"""
        return Evaluation.objects.filter(patient=self).order_by('-date').first()
    
    def get_prochaine_reeval(self):
        """Calcule la prochaine réévaluation (30 jours après la dernière)"""
        derniere = self.get_derniere_evaluation()
        if derniere and derniere.date:
            return derniere.date + timedelta(days=30)
        return None
# --- 3. SYSTÈME DE RECOMMANDATIONS (IA + ERGO) ---

class IA_Recommendation(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    programme_genere = models.TextField() # Liste d'exercices suggérés par l'IA
    date_generation = models.DateTimeField(auto_now_add=True)
    est_valide = models.BooleanField(default=False)

class Ergo_Recommendation(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    ia_source = models.OneToOneField(IA_Recommendation, on_delete=models.SET_NULL, null=True)
    programme_final = models.TextField() # Le programme après modif par l'ergo
    date_validation = models.DateTimeField(auto_now_add=True)
    commentaires_ergo = models.TextField(blank=True)

# --- 4. AUTRES FONCTIONNALITÉS ---

class RDV(models.Model):
    STATUT_CHOICES = [
        ('actif', 'Actif'),
        ('annule', 'Annulé'),
        ('reprogramme', 'Reprogrammé'),
    ]

    TYPE_CHOICES = [
        ('presentiel', 'Présentiel'),
        ('tele', 'Télé-ergothérapie'),
    ]

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rdv_patient')
    ergo = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rdv_ergo')

    date_heure = models.DateTimeField()
    duree = models.PositiveIntegerField(default=30)
    type_seance = models.CharField(max_length=20, choices=TYPE_CHOICES, default='presentiel')
    notes = models.TextField(blank=True)
    motif = models.CharField(max_length=200, blank=True)

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='actif')
    ancienne_date_heure = models.DateTimeField(null=True, blank=True)

    valide = models.BooleanField(default=True)
    notification_envoyee = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    therapist_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self):
        return f"{self.patient.prenom} {self.patient.nom} - {self.date_heure.strftime('%d/%m/%Y %H:%M')}"
class Message(models.Model):
    expediteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    destinataire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    sujet = models.CharField(max_length=200, default="Message")
    contenu = models.TextField(blank=True)
    est_epingle = models.BooleanField(default=False)
    date_envoi = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    piece_jointe = models.FileField(
        upload_to='messages_attachments/',
        blank=True,
        null=True,
        verbose_name="Pièce jointe"
    )
    piece_jointe_nom = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Nom du fichier"
    )
    piece_jointe_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Type (image/video/audio/pdf/file)"
    )

    est_lu_par_destinataire = models.BooleanField(default=False, verbose_name="Lu par destinataire")
    est_supprime_par_expediteur = models.BooleanField(default=False, verbose_name="Supprimé par expéditeur")
    est_supprime_par_destinataire = models.BooleanField(default=False, verbose_name="Supprimé par destinataire")

    # NOUVEAU : répondre à un message
    reponse_a = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reponses',
        verbose_name="Réponse à"
    )

    # NOUVEAU : date de modification
    date_modification = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"De {self.expediteur.nom} à {self.destinataire.nom} - {self.date_envoi.strftime('%d/%m/%Y %H:%M')}"

    @property
    def est_non_lu(self):
        return not self.est_lu_par_destinataire

    @property
    def a_piece_jointe(self):
        return self.piece_jointe is not None and self.piece_jointe != ''

    @property
    def est_vocal(self):
        return self.piece_jointe_type == 'audio'
class Ressource(models.Model):
    TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('video', 'Vidéo'),
        ('image', 'Image'),
        ('link', 'Lien'),
    ]

    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type_ressource = models.CharField(max_length=50, choices=TYPE_CHOICES)
    fichier = models.FileField(upload_to='ressources/', blank=True, null=True)
    url = models.URLField(blank=True, null=True)

    objectif_therapeutique = models.CharField(max_length=200, blank=True)
    consigne = models.TextField(blank=True)

    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ressources_creees'
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    nombre_vues = models.PositiveIntegerField(default=0)
    nombre_telechargements = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.titre
class RessourcePatient(models.Model):
    STATUT_CHOICES = [
        ('non_vue', 'Non vue'),
        ('vue', 'Vue'),
        ('telechargee', 'Téléchargée'),
        ('terminee', 'Terminée'),
    ]

    ressource = models.ForeignKey(
        Ressource,
        on_delete=models.CASCADE,
        related_name='partages_patient'
    )
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='ressources_recues'
    )

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='non_vue')

    date_partage = models.DateTimeField(auto_now_add=True)
    date_vue = models.DateTimeField(null=True, blank=True)
    date_telechargement = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)

    partage_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ressources_partagees_aux_patients'
    )

    commentaire_patient = models.TextField(blank=True)
    note_patient = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('ressource', 'patient')

    def __str__(self):
        return f"{self.patient.user.nom} - {self.ressource.titre} - {self.statut}"

class Contact(models.Model):
    STATUT_CHOICES = [
        ('nouveau', 'Nouveau'),
        ('traite', 'Traité'),
    ]

    nom = models.CharField(max_length=100)
    email = models.EmailField()
    sujet = models.CharField(max_length=200)
    message = models.TextField()
    date_contact = models.DateTimeField(auto_now_add=True)

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='nouveau')
    archive = models.BooleanField(default=False)
    date_traitement = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nom} - {self.sujet}"


# aujourd
# ==================== MODÈLES POUR LES ÉVALUATIONS ET BILANS ====================

class Evaluation(models.Model):
    """Modèle Évaluation (T1, T2, etc.)"""
    TYPE_CHOICES = [
        ('T1', 'Évaluation initiale'),
        ('T2', 'Réévaluation'),
    ]
    
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='evaluations', verbose_name="Patient")
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, verbose_name="Type")
    numero = models.PositiveIntegerField(default=1, verbose_name="Numéro d'évaluation")
    date = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    
    # Données MCRO
    mcro_rendement_t1 = models.FloatField(default=0, verbose_name="MCRO Rendement T1")
    mcro_satisfaction_t1 = models.FloatField(default=0, verbose_name="MCRO Satisfaction T1")
    mcro_rendement_t2 = models.FloatField(default=0, verbose_name="MCRO Rendement T2")
    mcro_satisfaction_t2 = models.FloatField(default=0, verbose_name="MCRO Satisfaction T2")
    
    # Données PRWE
    prwe_douleur = models.IntegerField(default=0, verbose_name="PRWE Douleur")
    prwe_fonction = models.IntegerField(default=0, verbose_name="PRWE Fonction")
    prwe_total = models.IntegerField(default=0, verbose_name="PRWE Total")
    
    # Synthèse
    synthese_observations = models.TextField(blank=True, verbose_name="Observations cliniques")
    synthese_impact = models.TextField(blank=True, verbose_name="Impact occupationnel")
    synthese_objectifs = models.TextField(blank=True, verbose_name="Objectifs thérapeutiques")
    synthese_recommandations = models.TextField(blank=True, verbose_name="Recommandations")
    
    # Signature
    signature_ergo = models.TextField(blank=True, verbose_name="Signature ergothérapeute")
    signature_date = models.DateField(null=True, blank=True, verbose_name="Date signature")
    signature_lieu = models.CharField(max_length=100, blank=True, verbose_name="Lieu signature")
    consentement = models.BooleanField(default=False, verbose_name="Consentement patient")
    
    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.patient.user.nom} {self.patient.user.prenom} - {self.get_type_display()} #{self.numero}"


class DonneesCliniques(models.Model):
    """Données cliniques (anamnèse, histoire, etc.) - liées au patient"""
    patient = models.OneToOneField(PatientProfile, on_delete=models.CASCADE, related_name='donnees_cliniques')
    
    # Anamnèse
    situation_familiale = models.CharField(max_length=50, blank=True, verbose_name="Situation familiale")
    vit_avec = models.CharField(max_length=100, blank=True, verbose_name="Vit avec")
    date_evaluation = models.DateField(null=True, blank=True, verbose_name="Date d'évaluation")
    ergotherapeute = models.CharField(max_length=100, blank=True, verbose_name="Ergothérapeute")
    
    # Histoire
    date_traumatisme = models.DateField(null=True, blank=True, verbose_name="Date du traumatisme")
    mecanisme_traumatisme = models.CharField(max_length=200, blank=True, verbose_name="Mécanisme")
    explication = models.TextField(blank=True, verbose_name="Explication")
    type_fracture = models.CharField(max_length=100, blank=True, verbose_name="Type de fracture")
    prise_en_charge_initiale = models.CharField(max_length=200, blank=True, verbose_name="Prise en charge initiale")
    duree_immobilisation = models.CharField(max_length=50, blank=True, verbose_name="Durée immobilisation")
    complications = models.TextField(blank=True, verbose_name="Complications")
    debut_reeducation = models.DateField(null=True, blank=True, verbose_name="Début rééducation")
    evolution = models.CharField(max_length=50, blank=True, verbose_name="Évolution")
    
    # Symptômes
    douleur_repos = models.IntegerField(default=0, verbose_name="Douleur repos EVA")
    douleur_effort = models.IntegerField(default=0, verbose_name="Douleur effort EVA")
    localisation_douleur = models.CharField(max_length=200, blank=True, verbose_name="Localisation douleur")
    presence_oedeme = models.BooleanField(default=False, verbose_name="Œdème")
    presence_faiblesse = models.BooleanField(default=False, verbose_name="Faiblesse")
    presence_troubles_sensitifs = models.BooleanField(default=False, verbose_name="Troubles sensitifs")
    presence_fatigue = models.BooleanField(default=False, verbose_name="Fatigabilité")
    
    # Antécédents
    antecedents_medicaux = models.TextField(blank=True, verbose_name="Antécédents médicaux")
    antecedents_traumatiques = models.TextField(blank=True, verbose_name="Antécédents traumatiques")
    antecedents_chirurgicaux = models.TextField(blank=True, verbose_name="Antécédents chirurgicaux")
    traitements_en_cours = models.TextField(blank=True, verbose_name="Traitements en cours")
    allergies = models.CharField(max_length=200, blank=True, verbose_name="Allergies")
    
    # Retentissement
    difficultes_avq = models.TextField(blank=True, verbose_name="Difficultés AVQ")
    impact_professionnel = models.TextField(blank=True, verbose_name="Impact professionnel")
    duree_arret = models.CharField(max_length=50, blank=True, verbose_name="Durée d'arrêt")
    soutien_familial = models.BooleanField(default=False, verbose_name="Soutien familial")
    autonomie_domicile = models.CharField(max_length=50, blank=True, verbose_name="Autonomie domicile")
    
    class Meta:
        verbose_name = "Données cliniques"
        verbose_name_plural = "Données cliniques"


class BilanArticulaire(models.Model):
    """Bilan articulaire - goniométrie"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_articulaire')
    
    # Poignet
    flexion_active_sain = models.IntegerField(default=0, verbose_name="Flexion active sain (°)")
    flexion_active_atteint = models.IntegerField(default=0, verbose_name="Flexion active atteint (°)")
    flexion_passive_atteint = models.IntegerField(default=0, verbose_name="Flexion passive atteint (°)")
    extension_active_sain = models.IntegerField(default=0, verbose_name="Extension active sain (°)")
    extension_active_atteint = models.IntegerField(default=0, verbose_name="Extension active atteint (°)")
    extension_passive_atteint = models.IntegerField(default=0, verbose_name="Extension passive atteint (°)")
    
    # Inclinaisons
    radial_active_sain = models.IntegerField(default=0, verbose_name="Inclinaison radiale active sain (°)")
    radial_active_atteint = models.IntegerField(default=0, verbose_name="Inclinaison radiale active atteint (°)")
    ulnar_active_sain = models.IntegerField(default=0, verbose_name="Inclinaison ulnaire active sain (°)")
    ulnar_active_atteint = models.IntegerField(default=0, verbose_name="Inclinaison ulnaire active atteint (°)")
    
    # Avant-bras
    pronation_active_sain = models.IntegerField(default=0, verbose_name="Pronation active sain (°)")
    pronation_active_atteint = models.IntegerField(default=0, verbose_name="Pronation active atteint (°)")
    supination_active_sain = models.IntegerField(default=0, verbose_name="Supination active sain (°)")
    supination_active_atteint = models.IntegerField(default=0, verbose_name="Supination active atteint (°)")
    
    # Doigts (stockés en JSON)
    doigts_donnees = models.JSONField(default=dict, blank=True, verbose_name="Données doigts")
    
    # Pouce
    pouce_donnees = models.JSONField(default=dict, blank=True, verbose_name="Données pouce")
    
    # Kapandji
    kapandji_sain = models.IntegerField(default=0, verbose_name="Kapandji sain (0-10)")
    kapandji_atteint = models.IntegerField(default=0, verbose_name="Kapandji atteint (0-10)")
    mouvement_qualite = models.CharField(max_length=50, blank=True, verbose_name="Qualité du mouvement")
    
    # Synthèse
    segments_concernes = models.TextField(blank=True, verbose_name="Segments concernés")
    limitation_plus_marquee = models.CharField(max_length=200, blank=True, verbose_name="Limitation la plus marquée")
    amplitude_minimale = models.CharField(max_length=50, blank=True, verbose_name="Amplitude minimale")
    importance_limitation = models.CharField(max_length=50, blank=True, verbose_name="Importance limitation")
    analyse_mobilite = models.CharField(max_length=100, blank=True, verbose_name="Analyse mobilité")
    douleur_fin_amplitude = models.BooleanField(default=False, verbose_name="Douleur fin amplitude")
    raideur_capsulaire = models.BooleanField(default=False, verbose_name="Raideur capsulaire")
    retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
    class Meta:
        verbose_name = "Bilan articulaire"
        verbose_name_plural = "Bilans articulaires"


class BilanDouleur(models.Model):
    """Bilan de douleur - EVA"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_douleur')
    
    douleur_repos = models.IntegerField(default=0, verbose_name="Douleur au repos (0-10)")
    douleur_mouvement = models.IntegerField(default=0, verbose_name="Douleur au mouvement (0-10)")
    interpretation = models.CharField(max_length=50, blank=True, verbose_name="Interprétation")
    localisation = models.CharField(max_length=200, blank=True, verbose_name="Localisation")
    type_douleur = models.CharField(max_length=50, blank=True, verbose_name="Type de douleur")
    facteurs_aggravants = models.TextField(blank=True, verbose_name="Facteurs aggravants")
    facteurs_soulageants = models.TextField(blank=True, verbose_name="Facteurs soulageants")
    retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
    class Meta:
        verbose_name = "Bilan douleur"
        verbose_name_plural = "Bilans douleur"


class BilanTrophique(models.Model):
    """Bilan trophique"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_trophique')
    
    oedeme = models.BooleanField(default=False, verbose_name="Œdème")
    oedeme_caractere = models.CharField(max_length=50, blank=True, verbose_name="Caractère œdème")
    oedeme_localisation = models.CharField(max_length=200, blank=True, verbose_name="Localisation œdème")
    
    # Mesures périmétriques
    perimetre_poignet_sain = models.FloatField(default=0, verbose_name="Périmètre poignet sain (cm)")
    perimetre_poignet_atteint = models.FloatField(default=0, verbose_name="Périmètre poignet atteint (cm)")
    perimetre_10cm_sain = models.FloatField(default=0, verbose_name="Périmètre 10cm proximal sain (cm)")
    perimetre_10cm_atteint = models.FloatField(default=0, verbose_name="Périmètre 10cm proximal atteint (cm)")
    perimetre_mcp_sain = models.FloatField(default=0, verbose_name="Périmètre têtes MCP sain (cm)")
    perimetre_mcp_atteint = models.FloatField(default=0, verbose_name="Périmètre têtes MCP atteint (cm)")
    
    couleur_peau = models.CharField(max_length=100, blank=True, verbose_name="Coloration cutanée")
    temperature = models.CharField(max_length=50, blank=True, verbose_name="Température cutanée")
    etat_cutane = models.TextField(blank=True, verbose_name="État cutané")
    cicatrice_presente = models.BooleanField(default=False, verbose_name="Cicatrice présente")
    cicatrice_caractere = models.CharField(max_length=100, blank=True, verbose_name="Caractère cicatrice")
    retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
    class Meta:
        verbose_name = "Bilan trophique"
        verbose_name_plural = "Bilans trophiques"


class BilanSensitif(models.Model):
    """Bilan sensitif"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_sensitif')
    
    # Zones testées (stockées en JSON)
    zones_testees = models.JSONField(default=dict, blank=True, verbose_name="Zones testées")
    
    interpretation_globale = models.CharField(max_length=50, blank=True, verbose_name="Interprétation globale")
    sensibilite_douloureuse = models.CharField(max_length=50, blank=True, verbose_name="Sensibilité douloureuse")
    proprioception = models.CharField(max_length=50, blank=True, verbose_name="Proprioception")
    paresthesies_spontanees = models.TextField(blank=True, verbose_name="Paresthésies spontanées")
    territoire_nerveux = models.CharField(max_length=100, blank=True, verbose_name="Territoire nerveux suspecté")
    presence_trouble = models.BooleanField(default=False, verbose_name="Présence trouble sensitif")
    type_atteinte = models.CharField(max_length=100, blank=True, verbose_name="Type d'atteinte")
    localisation_principale = models.CharField(max_length=200, blank=True, verbose_name="Localisation principale")
    retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
    class Meta:
        verbose_name = "Bilan sensitif"
        verbose_name_plural = "Bilans sensitifs"


class BilanPrehension(models.Model):
    """Bilan de préhension"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_prehension')
    
    # Scores
    score_total = models.IntegerField(default=0, verbose_name="Score total /66")
    prises_impossibles = models.IntegerField(default=0, verbose_name="Prises impossibles")
    prises_difficiles = models.IntegerField(default=0, verbose_name="Prises difficiles")
    niveau_atteinte = models.CharField(max_length=50, blank=True, verbose_name="Niveau d'atteinte")
    
    # Données détaillées (stockées en JSON)
    donnees = models.JSONField(default=dict, blank=True, verbose_name="Données détaillées des prises")
    
    # Approche vers l'objet
    mouvement_balayage = models.CharField(max_length=10, blank=True, verbose_name="Mouvement de balayage")
    approche_parabolique = models.CharField(max_length=10, blank=True, verbose_name="Approche parabolique")
    approche_directe = models.CharField(max_length=10, blank=True, verbose_name="Approche directe")
    
    # Lâcher
    lacher_volontaire = models.CharField(max_length=10, blank=True, verbose_name="Lâcher volontaire")
    lacher_involontaire = models.CharField(max_length=10, blank=True, verbose_name="Lâcher involontaire")
    
    # Force
    regulation_force = models.CharField(max_length=10, blank=True, verbose_name="Régulation de la force")
    
    # Coordination bi-manuelle (stockée en JSON)
    coordination_donnees = models.JSONField(default=dict, blank=True, verbose_name="Coordination bi-manuelle")
    
    # Synthèse
    synthese = models.TextField(blank=True, verbose_name="Synthèse")
    
    class Meta:
        verbose_name = "Bilan de préhension"
        verbose_name_plural = "Bilans de préhension"


class BilanDexterite(models.Model):
    """Bilan de dextérité"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_dexterite')
    
    # Test 1 - Manipulation d'objets
    test1_temps_sain = models.FloatField(default=0, verbose_name="Test1 temps sain (sec)")
    test1_temps_atteint = models.FloatField(default=0, verbose_name="Test1 temps atteint (sec)")
    test1_erreurs = models.TextField(blank=True, verbose_name="Test1 erreurs")
    
    # Test 2 - Enfilage de perles
    test2_temps_sain = models.FloatField(default=0, verbose_name="Test2 temps sain (sec)")
    test2_temps_atteint = models.FloatField(default=0, verbose_name="Test2 temps atteint (sec)")
    test2_erreurs = models.TextField(blank=True, verbose_name="Test2 erreurs")
    
    # Test 3 - Dévissage
    test3_temps_sain = models.FloatField(default=0, verbose_name="Test3 temps sain (sec)")
    test3_temps_atteint = models.FloatField(default=0, verbose_name="Test3 temps atteint (sec)")
    test3_erreurs = models.TextField(blank=True, verbose_name="Test3 erreurs")
    
    # Synthèse
    total_erreurs = models.IntegerField(default=0, verbose_name="Total erreurs")
    objets_echappes = models.IntegerField(default=0, verbose_name="Objets échappés")
    interruption_tache = models.BooleanField(default=False, verbose_name="Interruption tâche")
    douleur_tache = models.BooleanField(default=False, verbose_name="Douleur pendant tâche")
    fatigabilite = models.BooleanField(default=False, verbose_name="Fatigabilité observée")
    synthese = models.TextField(blank=True, verbose_name="Synthèse")
    
    class Meta:
        verbose_name = "Bilan de dextérité"
        verbose_name_plural = "Bilans de dextérité"


class BilanEndurance(models.Model):
    """Bilan d'endurance"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_endurance')
    
    # Côté sain
    sain_pressions = models.IntegerField(default=0, verbose_name="Sain - Nombre de pressions")
    sain_douleur = models.BooleanField(default=False, verbose_name="Sain - Douleur")
    sain_fatigue = models.CharField(max_length=20, blank=True, verbose_name="Sain - Fatigue")
    sain_observation = models.TextField(blank=True, verbose_name="Sain - Observation")
    
    # Côté atteint
    atteint_pressions = models.IntegerField(default=0, verbose_name="Atteint - Nombre de pressions")
    atteint_douleur = models.BooleanField(default=False, verbose_name="Atteint - Douleur")
    atteint_fatigue = models.CharField(max_length=20, blank=True, verbose_name="Atteint - Fatigue")
    atteint_observation = models.TextField(blank=True, verbose_name="Atteint - Observation")
    
    # Interprétation
    interpretation = models.CharField(max_length=100, blank=True, verbose_name="Interprétation")
    observation_clinique = models.TextField(blank=True, verbose_name="Observation clinique")
    synthese = models.TextField(blank=True, verbose_name="Synthèse")
    
    class Meta:
        verbose_name = "Bilan d'endurance"
        verbose_name_plural = "Bilans d'endurance"


# ==================== MODÈLES POUR LES PROGRAMMES ET EXERCICES ====================
# ==================== MODÈLES POUR LES PROGRAMMES ET EXERCICES ====================

class BibliothequeExercice(models.Model):
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='bibliotheque_exercices',
        null=True,
        blank=True
    )
    nom = models.CharField(max_length=255)
    categorie = models.CharField(max_length=100, blank=True)
    series = models.IntegerField(default=1)
    repetitions = models.IntegerField(default=1)
    temps_exercice = models.CharField(max_length=100, blank=True, verbose_name="Durée de l'exercice")
    repos = models.CharField(max_length=100, blank=True, default="45s", verbose_name="Temps de repos")  # ← AJOUTER
    objectif = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    materiel_necessaire = models.TextField(blank=True)
    ordre = models.IntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom

class BibliothequeExerciceMedia(models.Model):
    exercice = models.ForeignKey(
        'BibliothequeExercice',
        on_delete=models.CASCADE,
        related_name='medias'
    )
    fichier = models.FileField(upload_to='exercices_demo/')
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Media - {self.exercice.nom}"


class ProgrammeExercice(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='programmes')
    ergotherapeute = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'ergo'})
    nom = models.CharField(max_length=200, verbose_name="Nom du programme")
    description = models.TextField(blank=True, verbose_name="Description")
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    phase = models.CharField(max_length=50, default='1', verbose_name="Phase")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Programme d'exercices"
        verbose_name_plural = "Programmes d'exercices"
        ordering = ['-date_debut']
    
    def __str__(self):
        return f"{self.patient.user.nom} {self.patient.user.prenom} - {self.nom}"

class Exercice(models.Model):
    programme = models.ForeignKey(
        ProgrammeExercice,
        on_delete=models.CASCADE,
        related_name='exercices'
    )
    bibliotheque_exercice = models.ForeignKey(
        BibliothequeExercice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exercices_programme'
    )
    nom = models.CharField(max_length=255)
    categorie = models.CharField(max_length=100, blank=True)
    series = models.PositiveIntegerField(default=1)
    repetitions = models.PositiveIntegerField(default=1)
    temps_exercice = models.CharField(max_length=255, blank=True, verbose_name="Durée de l'exercice")
    repos = models.CharField(max_length=100, blank=True, default="45s", verbose_name="Temps de repos")  # ← AJOUTER
    objectif = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    materiel_necessaire = models.TextField(blank=True)
    media_demo = models.FileField(upload_to='exercices_programmes/', blank=True, null=True)
    ordre = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.nom

class ExerciceMedia(models.Model):
    exercice = models.ForeignKey(
        Exercice,
        on_delete=models.CASCADE,
        related_name='medias'
    )
    fichier = models.FileField(upload_to='exercices_programmes_media/')
    date_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Média pour {self.exercice.nom}"

class ResultatExercice(models.Model):
    """Résultat d'un exercice réalisé par le patient"""
    STATUT_ERGO_CHOICES = [
        ('pending', 'En attente'),
        ('validated', 'Validé'),
        ('refused', 'Refusé'),
    ]
    exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE, related_name='resultats')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='resultats_exercices')
    date_realisation = models.DateTimeField(auto_now_add=True, verbose_name="Date de réalisation")
    
    # Résultats
    resultat_texte = models.TextField(blank=True, verbose_name="Description du résultat")
    amplitude_atteinte = models.IntegerField(default=0, verbose_name="Amplitude atteinte (°)")
    force_atteinte = models.IntegerField(default=0, verbose_name="Force atteinte (kg)")
    douleur = models.IntegerField(default=0, verbose_name="Douleur (0-10)")
    satisfaction = models.IntegerField(default=0, verbose_name="Satisfaction (1-5)")
    difficultes = models.TextField(blank=True, verbose_name="Difficultés rencontrées")
    
    # Médias
    media_type = models.CharField(max_length=10, blank=True, verbose_name="Type de média (photo/video)")
    media_url = models.URLField(blank=True, verbose_name="URL du média")
    media_fichier = models.FileField(upload_to='resultats/', blank=True, null=True, verbose_name="Fichier média")
    
    # Validation
    valide_par_ergo = models.BooleanField(default=False, verbose_name="Validé par ergothérapeute")
    statut_ergo = models.CharField(max_length=20, choices=STATUT_ERGO_CHOICES, default='pending', verbose_name="Statut ergo")
    commentaire_ergo = models.TextField(blank=True, verbose_name="Commentaire ergothérapeute")
    
    class Meta:
        verbose_name = "Résultat d'exercice"
        verbose_name_plural = "Résultats d'exercices"
        ordering = ['-date_realisation']
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.exercice.nom} - {self.date_realisation.strftime('%d/%m/%Y')}"


# ==================== MODÈLES POUR LA PROGRESSION ET LE SUIVI ====================

class ProgressionPatient(models.Model):
    """Suivi de la progression du patient dans le temps"""
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='progressions')
    date = models.DateField(auto_now_add=True, verbose_name="Date")
    
    # Scores
    douleur = models.IntegerField(default=0, verbose_name="Douleur (0-10)")
    fatigue = models.IntegerField(default=0, verbose_name="Fatigue (1-5)")
    humeur = models.CharField(max_length=20, blank=True, verbose_name="Humeur")
    satisfaction = models.IntegerField(default=0, verbose_name="Satisfaction (1-5)")
    progression_globale = models.IntegerField(default=0, verbose_name="Progression globale (%)")
    
    # Indicateurs
    mobilite = models.IntegerField(default=0, verbose_name="Mobilité (%)")
    force = models.IntegerField(default=0, verbose_name="Force (%)")
    endurance = models.IntegerField(default=0, verbose_name="Endurance (%)")
    dexterite = models.IntegerField(default=0, verbose_name="Dextérité (%)")
    sensibilite = models.IntegerField(default=0, verbose_name="Sensibilité (%)")
    prehension = models.IntegerField(default=0, verbose_name="Préhension (%)")
    
    # Notes
    notes = models.TextField(blank=True, verbose_name="Notes du patient")
    reponse_question = models.CharField(max_length=10, blank=True, verbose_name="Réponse à la question du jour")
    
    class Meta:
        verbose_name = "Progression patient"
        verbose_name_plural = "Progressions patients"
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.date}"


class QuestionJour(models.Model):
    question = models.TextField(verbose_name="Question du jour")
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name='questions_jour',
        null=True,
        blank=True,
        verbose_name="Patient destinataire"
    )
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions_jour_creees'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Question du jour"
        verbose_name_plural = "Questions du jour"

    def __str__(self):
        cible = self.patient.user.get_full_name() if self.patient else "Tous les patients"
        return f"{cible} - {self.question[:60]}"


class ReponseQuestionJour(models.Model):
    question = models.ForeignKey(QuestionJour, on_delete=models.CASCADE, related_name='reponses')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='reponses_questions_jour')
    reponse = models.CharField(max_length=20)
    douleur = models.IntegerField(default=0)
    fatigue = models.IntegerField(default=0)
    humeur = models.CharField(max_length=20, blank=True)
    satisfaction = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    date_reponse = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_reponse']
        verbose_name = "Réponse à la question du jour"
        verbose_name_plural = "Réponses aux questions du jour"

    def __str__(self):
        return f"{self.patient.user.nom} - {self.reponse}"


class JournalPatient(models.Model):
    """Journal personnel du patient"""
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='journal')
    date = models.DateField(auto_now_add=True, verbose_name="Date")
    contenu = models.TextField(verbose_name="Contenu du journal")
    humeur = models.CharField(max_length=20, blank=True, verbose_name="Humeur")
    
    class Meta:
        verbose_name = "Journal patient"
        verbose_name_plural = "Journaux patients"
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.date}"


class Recompense(models.Model):
    """Récompenses/badges gagnés par le patient"""
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='recompenses')
    nom = models.CharField(max_length=100, verbose_name="Nom de la récompense")
    description = models.TextField(blank=True, verbose_name="Description")
    icone = models.CharField(max_length=50, default='bi-award', verbose_name="Icône Bootstrap")
    date_obtention = models.DateTimeField(auto_now_add=True, verbose_name="Date d'obtention")
    
    class Meta:
        verbose_name = "Récompense"
        verbose_name_plural = "Récompenses"
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.nom}"


class DefiPatient(models.Model):
    """Défis pour motiver le patient"""
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='defis')
    nom = models.CharField(max_length=200, verbose_name="Nom du défi")
    description = models.TextField(blank=True, verbose_name="Description")
    objectif = models.IntegerField(verbose_name="Objectif")
    progression = models.IntegerField(default=0, verbose_name="Progression actuelle")
    termine = models.BooleanField(default=False, verbose_name="Terminé")
    date_debut = models.DateField(auto_now_add=True, verbose_name="Date de début")
    date_fin = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    
    class Meta:
        verbose_name = "Défi patient"
        verbose_name_plural = "Défis patients"
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.nom}"


# ==================== MODÈLES POUR LA TRACABILITÉ ====================

class HistoriqueAction(models.Model):
    """Journal d'activité complet"""
    TYPE_CHOICES = [
        ('seance', 'Séance'),
        ('message', 'Message'),
        ('ressource', 'Ressource'),
        ('dossier', 'Dossier'),
        ('programme', 'Programme'),
        ('ia', 'IA'),
        ('patient', 'Patient'),
        ('visite', 'Visite'),
    ]
    
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historique')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='historique')
    type_action = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type d'action")
    action = models.CharField(max_length=200, verbose_name="Action réalisée")
    details = models.JSONField(default=dict, blank=True, verbose_name="Détails")
    date_action = models.DateTimeField(auto_now_add=True, verbose_name="Date de l'action")
    
    class Meta:
        verbose_name = "Historique action"
        verbose_name_plural = "Historique actions"
        ordering = ['-date_action']
    
    def __str__(self):
        return f"{self.utilisateur.username} - {self.action} - {self.date_action.strftime('%d/%m/%Y %H:%M')}"
    


    # aujour
    # ==================== MULTILINGUE ====================

class Translation(models.Model):
    """Modèle pour stocker les traductions"""
    LANG_CHOICES = [
        ('fr', 'Français'),
        ('en', 'English'),
        ('ar', 'العربية'),
    ]
    
    key = models.CharField(max_length=200, unique=True, verbose_name="Clé de traduction")
    fr = models.TextField(verbose_name="Français", blank=True)
    en = models.TextField(verbose_name="English", blank=True)
    ar = models.TextField(verbose_name="العربية", blank=True)
    
    class Meta:
        verbose_name = "Traduction"
        verbose_name_plural = "Traductions"
    
    def __str__(self):
        return self.key
    
    def get(self, lang='fr'):
        """Récupère la traduction dans la langue demandée"""
        return getattr(self, lang, self.fr)


    def get_translation(key, lang='fr'):
        """Fonction utilitaire pour récupérer une traduction"""
        try:
            t = Translation.objects.get(key=key)
            return t.get(lang)
        except Translation.DoesNotExist:
            return key
        
# dossier patient
class DossierPatient(models.Model):
    # IDENTIFICATION
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField()
    age = models.IntegerField(null=True, blank=True)


    SEXE_CHOICES = [
        ('F', 'Femme'),
        ('H', 'Homme'),
    ]
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)

    SITUATION_CHOICES = [
        ('celibataire', 'Célibataire'),
        ('marie', 'Marié(e)'),
        ('divorce', 'Divorcé(e)'),
        ('veuf', 'Veuf(ve)'),
    ]
    situation_familiale = models.CharField(max_length=20, choices=SITUATION_CHOICES)

    VIT_CHOICES = [
        ('seul', 'Seul(e)'),
        ('conjoint', 'Avec conjoint'),
        ('famille', 'Avec famille'),
        ('autre', 'Autre'),
    ]
    vit = models.CharField(max_length=20, choices=VIT_CHOICES)

    diagnostic = models.TextField()

    MEMBRE_CHOICES = [
        ('droit', 'Droit'),
        ('gauche', 'Gauche'),
    ]
    membre_atteint = models.CharField(max_length=10, choices=MEMBRE_CHOICES)

    DOMINANCE_CHOICES = [
        ('droitier', 'Droitier'),
        ('gaucher', 'Gaucher'),
    ]
    dominance = models.CharField(max_length=10, choices=DOMINANCE_CHOICES)

    profession = models.CharField(max_length=200)
    adresse = models.TextField()
    telephone = models.CharField(max_length=20)
    email = models.EmailField()

    date_evaluation = models.DateField()
    ergotherapeute = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.nom} {self.prenom}"
    
class HistoireMaladie(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    date_traumatisme = models.DateField()

    mecanisme = models.CharField(max_length=50, choices=[
        ('chute', 'Chute sur la main'),
        ('domestique', 'Accident domestique'),
        ('travail', 'Accident de travail'),
        ('sport', 'Accident sportif'),
        ('autre', 'Autre'),
    ])

    explication = models.TextField()
    type_fracture = models.CharField(max_length=200)

    prise_en_charge = models.CharField(max_length=50, choices=[
        ('platre', 'Plâtre'),
        ('chirurgie', 'Chirurgie'),
        ('reduction', 'Réduction orthopédique'),
        ('orthese', 'Orthèse'),
    ])

    duree_immobilisation = models.IntegerField(null=True, blank=True)

    complications = models.CharField(max_length=50)

    debut_reeducation = models.DateField()

    evolution = models.CharField(max_length=20, choices=[
        ('amelioration', 'Amélioration'),
        ('stabilisation', 'Stabilisation'),
        ('aggravation', 'Aggravation'),
    ])

class Symptome(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    douleur_repos = models.IntegerField(null=True, blank=True)

    douleur_effort = models.IntegerField(null=True, blank=True)


    localisation = models.TextField()

    raideur = models.BooleanField()
    oedeme = models.BooleanField()
    faiblesse = models.BooleanField()
    troubles_sensitifs = models.BooleanField()
    fatigabilite = models.BooleanField()

class Retentissement(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    habillage = models.BooleanField()
    toilette = models.BooleanField()
    cuisine = models.BooleanField()
    port_charge = models.BooleanField()
    ecriture = models.BooleanField()
    clavier = models.BooleanField()
    telephone = models.BooleanField()
    conduite = models.BooleanField()
    autre = models.TextField()

    impact_professionnel = models.CharField(max_length=50, choices=[
        ('arret', 'Arrêt de travail'),
        ('amenagement', 'Aménagement de poste'),
        ('partiel', 'Difficulté partielle'),
        ('complet', 'Reprise complète'),
    ])

    duree_arret = models.CharField(max_length=50)

    contexte_psychosocial = models.BooleanField()

    autonomie_a_domicile = models.CharField(max_length=50, choices=[
        ('totale', 'totale'),
        ('partielle', 'partielle'),
        ('dependente', 'dependente'),
    ])

class Antecedents(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    diabete = models.BooleanField()
    osteoporose = models.BooleanField()
    arthrite = models.BooleanField()
    hypertension = models.BooleanField()
    neurologiques = models.BooleanField()
    autre = models.TextField()

    traumatiques = models.TextField()
    chirurgicaux = models.TextField()
    traitements = models.TextField()
    allergies = models.TextField()

class Objectifs(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    douleur = models.BooleanField()
    mobilite = models.BooleanField()
    force = models.BooleanField()
    travail = models.BooleanField()
    activite = models.BooleanField()

class BilanMusculaire(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    segment = models.CharField(max_length=50)
    mouvement = models.CharField(max_length=50)

    cote = models.CharField(max_length=10, choices=[
        ('sain', 'Sain'),
        ('atteint', 'Atteint')
    ])

    cotation = models.CharField(max_length=5)  # 0,1,2-,2,2+,3...
    observation = models.TextField(blank=True)

class Synthese_une(models.Model):
    segments_concernes = models.CharField(max_length=200)
    mouvement = models.CharField(max_length=200)
    cotation_sain = models.CharField(max_length=200)
    cotation_atteint = models.CharField(max_length=200)
    ecart_observe = models.CharField(max_length=200)
    cotation_minimale_observe = models.CharField(max_length=200)
    intensite_globale = models.CharField(max_length=100, choices=[
        ('legere', 'légere (écart <= 1 point)'),
        ('moderee', 'Modérée (écart 2 point)'),
        ('importante', 'Importante (écart >= 3 point')
    ])
    douleur_lors_du_testing = models.BooleanField()
    douleur_oui = models.TextField()

    presence_de_compensation = models.BooleanField()
    presence_oui = models.TextField()

    retentissement_fonctionnel = models.TextField()

class Articulaire(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    segment = models.CharField(max_length=50)
    mouvement = models.CharField(max_length=50)
    norme = models.CharField(max_length=50)
    actif_sain = models.CharField(max_length=50)
    actif_atteint = models.CharField(max_length=50)
    passif_atteint = models.CharField(max_length=50)
    ecart_vs_sain = models.CharField(max_length=50)
    observations = models.CharField(max_length=50)

class Articulaire_doit(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    segment = models.CharField(max_length=50)
    mouvement = models.CharField(max_length=50)
    cote_sain = models.CharField(max_length=50)
    cote_atteint = models.CharField(max_length=50)
    observations = models.CharField(max_length=50)

class Articulaire_pouce(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    mouvement = models.CharField(max_length=50)
    cote_sain = models.CharField(max_length=50)
    cote_atteint = models.CharField(max_length=50)
    observations = models.CharField(max_length=50)

class Articulaire_opposition(models.Model):
    opposition_pouce = models.IntegerField(null=True, blank=True)

    mouvement = models.CharField(max_length=10, choices=[
        ('complet', 'complet'),
        ('legere', 'légerement limité'),
        ('limite', 'limité'),
        ('impossible', 'impossible')
    ])
    segment_concernee = models.TextField()
    mouvement_avec_limitation = models.TextField()
    mouvement_avec_limitation_amplitude_sain = models.TextField()
    mouvement_avec_limitation_amplitude_atteint = models.TextField()
    mouvement_avec_limitation_ecart_observe = models.TextField()

    amplitude_minimale = models.TextField()

    importance_globale_de_lim = models.CharField(max_length=10, choices=[
        ('legere', 'légere (écart <= 10)'),
        ('moderee', 'Modérée (écart 10-20)'),
        ('importante', 'Importante (écart >= 20)')
    ])

    presence_de_douleur = models.BooleanField()
    presence_de_douleur_oui = models.TextField()

    analyse_comparative = models.CharField(max_length=10, choices=[
        ('passive', 'Mobilité passive > actif'),
        ('active', 'Mobilité passive comparable'),
        ('mixte', 'Limitation mixte')
    ])
    analyse_comparative_interpetation = models.TextField()

    presence_de_raideur = models.BooleanField()
    presence_de_raideur_oui = models.TextField()

    retentissement = models.TextField()

class Douleur(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    repos = models.IntegerField(null=True, blank=True)

    mouvement = models.IntegerField(null=True, blank=True)


    interpretation = models.CharField(max_length=60, choices=[
        ('legere', 'Légère (0-3)'),
        ('moderer', 'Douleur modérée (4-6)'),
        ('intense', 'Douleur intense (7-10)'),
    ])
    type_douleur = models.CharField(max_length=100, choices=[
        ('mecanique', 'Mécanique (majorée au mouvement/effort)'),
        ('inflammatoire', 'inflammatoire (présente au repos/nocturne)'),
        ('mixte', 'mixte'),
    ])

    localisation = models.TextField()

    facteurs_aggravants = models.TextField()
    facteurs_soulageants = models.TextField()

    retentissement = models.TextField()

class Trophique(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    oedeme = models.BooleanField()
    caractere = models.CharField(max_length=20)
    localisation = models.CharField(max_length=50)

    coloration = models.CharField(max_length=50)
    temperature = models.CharField(max_length=50)
    etat_cutane = models.TextField()

    cicatrice = models.CharField(max_length=50)

    retentissement = models.TextField()

class Trophiquemesure(models.Model):
    site = models.CharField(max_length=50)
    sain = models.CharField(max_length=50)
    atteint = models.CharField(max_length=50)
    difference = models.CharField(max_length=50)

class Sensitif(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    interpretation = models.CharField(max_length=50)

    douleur = models.CharField(max_length=50)
    douleur_localisaton = models.CharField(max_length=50)
    proprioception = models.CharField(max_length=50)

    paresthesies = models.CharField(max_length=50)
    paresthesies_localisation = models.CharField(max_length=50)
    territoire = models.CharField(max_length=50)
    
    presence_trouble = models.BooleanField()
    type_atteinte = models.CharField(max_length=50)
    localisation = models.TextField()
    retentissement = models.TextField()

class Sensitif_table(models.Model):
    zone = models.CharField(max_length=50)
    cote_sain = models.CharField(max_length=50)
    cote_atteint = models.CharField(max_length=50)
    observation = models.CharField(max_length=50)

class Prehension(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    type_prise = models.CharField(max_length=100)

    droite = models.CharField(max_length=100)  # +, +/-, --
    gauche = models.CharField(max_length=100)

    observation = models.TextField()

class Prehension_table_deux(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    element = models.CharField(max_length=100)

    droite = models.CharField(max_length=100)  # +, +/-, --
    gauche = models.CharField(max_length=100)

    observation = models.TextField()

class Prehension_table_troi(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    type = models.CharField(max_length=100)

    droite = models.CharField(max_length=100)   
    gauche = models.CharField(max_length=100)

    observation = models.TextField()

class Prehension_table_quatre(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    element = models.CharField(max_length=100)

    droite = models.CharField(max_length=100)   
    gauche = models.CharField(max_length=100)

    observation = models.TextField()

class Prehension_table_cinq(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    type = models.CharField(max_length=100)

    activite = models.CharField(max_length=100)  

    observation = models.TextField()

class Prehension_synthese(models.Model):
    patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

    score = models.CharField(max_length=100)

    prise_impossible = models.CharField(max_length=100)  
    prise_difficile = models.CharField(max_length=100)

    interpretation = models.TextField()

class Dexterite(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    cote_sain = models.IntegerField(null=True, blank=True)

    cote_atteint = models.IntegerField(null=True, blank=True)

    ecart = models.IntegerField(null=True, blank=True)

    details = models.TextField()
    
    enfilage_cote_sain = models.IntegerField(null=True, blank=True)

    enfilage_cote_atteint = models.IntegerField(null=True, blank=True)

    enfilage_ecart = models.IntegerField(null=True, blank=True)

    enfilage_details = models.TextField()

    devisser_cote_sain = models.IntegerField(null=True, blank=True)

    devisser_cote_atteint = models.IntegerField(null=True, blank=True)

    devisser_ecart = models.IntegerField(null=True, blank=True)

    devisser_details = models.TextField()

    synthese_nombre_totale = models.IntegerField(null=True, blank=True)

    synthese_nombre_object = models.IntegerField(null=True, blank=True)


    Interruption = models.BooleanField()
    douleur = models.BooleanField()
    fatiguabilite = models.BooleanField()

class Endurence(models.Model):
    cote_sain = models.IntegerField(null=True, blank=True)

    cote_sain_douleur = models.BooleanField()
    cote_sain_fatigue = models.TextField()
    cote_sain_observation = models.TextField()

    cote_atteint = models.IntegerField(null=True, blank=True)

    cote_atteint_douleur = models.BooleanField()
    cote_atteint_fatigue = models.TextField()
    cote_atteint_observation = models.TextField()

    interpretation = models.TextField()

    observation_clinique = models.TextField()

    synthese = models.TextField()

class Mcrco(models.Model):
    nom = models.CharField(max_length=100)
    date_naissance = models.DateField()
    age = models.IntegerField(null=True, blank=True)


    SEXE_CHOICES = [
        ('F', 'Femme'),
        ('H', 'Homme'),
    ]
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    repondant = models.CharField(max_length=100)
    date_evaluation = models.DateField()
    date_prevue_reevaluation = models.DateField()
    date_reevaluation = models.DateField()
    therapeute = models.CharField(max_length=100)
    etablissement = models.CharField(max_length=100)
    programme = models.CharField(max_length=100)
    cotee_rendement_t1 = models.CharField(max_length=100)
    cotee_satisfaction_t1 = models.IntegerField(null=True, blank=True)

    cotee_rendement_t2 = models.IntegerField(null=True, blank=True)

    cotee_satisfaction_t2 = models.IntegerField(null=True, blank=True)

    cotee_moyenne_rendement_t1 = models.IntegerField(null=True, blank=True)

    cotee_moyenne_satisfaction_t1 = models.IntegerField(null=True, blank=True)

    cotee_moyenne_rendement_t2 = models.IntegerField(null=True, blank=True)

    cotee_moyenne_satisfaction_t2 =models.IntegerField(null=True, blank=True)

    changement_rendement = models.IntegerField(null=True, blank=True)

    changement_satisfaction = models.IntegerField(null=True, blank=True)


    Evaluation = models.CharField()
    reevaluation = models.CharField()

class Mcrco_table(models.Model):
    difficulte = models.CharField(max_length=100)
    importance = models.IntegerField(null=True, blank=True)

    rendement_t1 = models.IntegerField(null=True, blank=True)

    satisfaction_t1 = models.IntegerField(null=True, blank=True)

    rendement_t2 = models.IntegerField(null=True, blank=True)

    satisfaction_t2 = models.IntegerField(null=True, blank=True)



class PRWE(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)
    
    nom = models.CharField(max_length=100)
    date = models.DateField()
    signature = models.CharField(max_length=100)

    score_douleur_repos = models.IntegerField(null=True, blank=True)

    score_douleur_mouvement = models.IntegerField(null=True, blank=True)

    score_douleur_s_o_l = models.IntegerField(null=True, blank=True)

    score_douleur_comble = models.IntegerField(null=True, blank=True)

    score_douleur_frequence = models.IntegerField(null=True, blank=True)


    score_fonction_tounee_poignet = models.IntegerField(null=True, blank=True)

    score_fonction_tcoupee_viande = models.IntegerField(null=True, blank=True)

    score_fonction_boutonnee_chemise = models.IntegerField(null=True, blank=True)

    score_fonction_soulever_chaise = models.IntegerField(null=True, blank=True)

    score_fonction_utiliser_papier_toilette = models.IntegerField(null=True, blank=True)

    
    score_activite_habituelle_soins_perso = models.IntegerField(null=True, blank=True)

    score_activite_habituelle_tache_menagere = models.IntegerField(null=True, blank=True)

    score_activite_habituelle_travail = models.IntegerField(null=True, blank=True)

    score_activite_habituelle_loisir = models.IntegerField(null=True, blank=True)


    score_douleur = models.IntegerField(null=True, blank=True)

    score_fonction = models.IntegerField(null=True, blank=True)

    score_total = models.IntegerField(null=True, blank=True)


class Synthese(models.Model):
    patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

    observations = models.TextField()
    impact = models.TextField()
    objectifs = models.TextField()
    plan = models.TextField()

    signature = models.CharField(max_length=200)
    date = models.DateField()
    lieu = models.CharField(max_length=100)

#
from django.db import models
from django.contrib.auth.models import User
from Dashboard.models import PatientProfile  # Adapte selon ton projet

class AnalyseIA(models.Model):
    PRIORITE_CHOICES = [
        ('critical', 'Critique'),
        ('warning', 'Alerte'),
        ('info', 'Information'),
        ('success', 'Progression'),
    ]
    
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='analyses_ia')
    date_generation = models.DateTimeField(auto_now_add=True)
    priorite = models.CharField(max_length=20, choices=PRIORITE_CHOICES, default='info')
    confiance = models.IntegerField(default=0, help_text="Pourcentage 0-100")
    resume = models.TextField(blank=True)
    programme_genere = models.TextField(blank=True)
    est_valide = models.BooleanField(default=False)
    
    # Champs pour les détails d'analyse
    douleur_repos = models.IntegerField(default=0)
    douleur_effort = models.IntegerField(default=0)
    amplitude_mesuree = models.IntegerField(default=0)
    amplitude_objectif = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-date_generation']
        verbose_name = "Analyse IA"
        verbose_name_plural = "Analyses IA"
    
    def __str__(self):
        return f"Analyse {self.patient.user.nom} - {self.date_generation.strftime('%d/%m/%Y')}"
    
    @property
    def priorite_label(self):
        return dict(self.PRIORITE_CHOICES).get(self.priorite, '')
    
    @property
    def couleur(self):
        couleurs = {
            'critical': '#ef4444',
            'warning': '#f59e0b',
            'info': '#3b82f6',
            'success': '#10b981',
        }
        return couleurs.get(self.priorite, '#6b7280')
    
    @property
    def initiales(self):
        return f"{self.patient.user.nom[0]}{self.patient.user.prenom[0]}".upper()


class HistoriqueAnalyseIA(models.Model):
    analyse = models.ForeignKey(AnalyseIA, on_delete=models.CASCADE, related_name='historique')
    exercice_nom = models.CharField(max_length=100)
    date_analyse = models.DateTimeField(auto_now_add=True)
    resultat_mesure = models.CharField(max_length=50)
    objectif = models.CharField(max_length=50)
    anomalies = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date_analyse']
    
    def __str__(self):
        return f"{self.exercice_nom} - {self.date_analyse.strftime('%d/%m/%Y')}"
    

class DemandeRendezVous(models.Model):
    TYPE_CHOICES = [
        ('in_person', 'Présentiel'),
        ('teleconsultation', 'Téléconsultation'),
    ]
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('acceptee', 'Acceptée'),
        ('refusee', 'Refusée'),
        ('traitee', 'Traitée'),
    ]
    
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='demandes_rendezvous')
    date_souhaitee = models.DateField()
    creneau_souhaite = models.CharField(max_length=10)  # 09:00, 10:00, etc.
    type_souhaite = models.CharField(max_length=20, choices=TYPE_CHOICES)
    motif = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    reponse_ergo = models.TextField(blank=True)
    
    def __str__(self):
        return f"Demande de {self.patient.user.nom} - {self.date_souhaitee}"


class SignalementRendezVous(models.Model):
    TYPES_SIGNALEMENT = [
        ('absence', 'Absence du patient'),
        ('absence_ergo', 'Absence de l\'ergothérapeute'),
        ('erreur_horaire', 'Erreur d\'horaire'),
        ('difficulte', 'Difficulté rencontrée'),
        ('autre', 'Autre'),
    ]
    
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='signalements')
    rendez_vous = models.ForeignKey(RDV, on_delete=models.CASCADE, related_name='signalements')
    type_signalement = models.CharField(max_length=20, choices=TYPES_SIGNALEMENT, default='autre')
    description = models.TextField()
    statut = models.CharField(max_length=20, default='en_attente')  # en_attente, traite, ignore
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    reponse_ergo = models.TextField(blank=True)
    
    def __str__(self):
        return f"Signalement de {self.patient.user.nom} - {self.rendez_vous.date_heure}"


class ReponseRendezVous(models.Model):
    rendez_vous = models.ForeignKey(RDV, on_delete=models.CASCADE, related_name='reponses_patient')
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    message = models.TextField()
    date_reponse = models.DateTimeField(auto_now_add=True)
    lu_par_ergo = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Réponse de {self.patient.user.nom} pour RDV du {self.rendez_vous.date_heure}"

class ConnexionPatient(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='connexions')
    date_connexion = models.DateTimeField(auto_now_add=True)
    page_visitee = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-date_connexion']
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.date_connexion.strftime('%d/%m/%Y %H:%M')}"

# ==================== DÉFIS ET PROGRESSION ====================

# ===== MODÈLES POUR LES DÉFIS =====

# ==================== DÉFIS ET PROGRESSION ====================

class Defi(models.Model):
    NIVEAUX = [
        ('bronze', '🥉 Bronze'),
        ('argent', '🥈 Argent'),
        ('or', '🥇 Or'),
        ('platine', '💎 Platine'),
    ]
    
    nom = models.CharField(max_length=100)
    description = models.TextField()
    points = models.IntegerField(default=10)
    niveau_requis = models.CharField(max_length=20, choices=NIVEAUX, default='bronze')
    ordre = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['ordre']
    
    def __str__(self):
        return f"{self.nom} (+{self.points} pts)"


class DefiPatient(models.Model):
    STATUTS = [
        ('assigned', 'Assigné'),
        ('completed', 'Terminé'),
    ]

    patient = models.ForeignKey('PatientProfile', on_delete=models.CASCADE)
    defi = models.ForeignKey(Defi, on_delete=models.CASCADE)
    statut = models.CharField(max_length=20, choices=STATUTS, default='assigned')
    date_completion = models.DateTimeField(auto_now_add=True)
    points_gagnes = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['patient', 'defi']
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.defi.nom}"


class ProgressionGlobale(models.Model):
    patient = models.OneToOneField('PatientProfile', on_delete=models.CASCADE)
    niveau_actuel = models.CharField(max_length=20, choices=Defi.NIVEAUX, default='bronze')
    points_totaux = models.IntegerField(default=0)
    defis_completes = models.IntegerField(default=0)
    derniere_progression = models.DateField(auto_now=True)
    
    def __str__(self):
        return f"{self.patient.user.nom} - {self.get_niveau_actuel_display()}"

class ProgrammeEnvoye(models.Model):
    patient = models.ForeignKey('PatientProfile', on_delete=models.CASCADE, related_name='programmes_recus')
    programme = models.JSONField(default=dict)
    date_envoi = models.DateTimeField(auto_now_add=True)
    est_lu = models.BooleanField(default=False)
    archive = models.BooleanField(default=False)  # ← NOUVEAU CHAMP
    
    def __str__(self):
        return f"Programme pour {self.patient.user.nom} - {self.date_envoi.strftime('%d/%m/%Y %H:%M')}"


#     from django.db import models
# from django.contrib.auth.models import AbstractUser
# from django.core.validators import MinValueValidator, MaxValueValidator
# from datetime import date
# from datetime import timedelta
# # --- 1. GESTION DES UTILISATEURS ET ROLES ---



# # --- 2. DONNÉES PATIENT (PROFIL MÉDICAL) ---

# class PatientProfile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
#     date_naissance = models.DateField()
#     sexe = models.CharField(max_length=10, choices=[('F', 'Femme'), ('H', 'Homme')])
#     telephone = models.CharField(max_length=20)
#     adresse = models.TextField(blank=True, null=True)
#     nom_affichage = models.CharField(max_length=50, blank=True, null=True)
#     langue = models.CharField(max_length=30, default='Français')
#     def age(self):
#         today = date.today()
#         return today.year - self.date_naissance.year - (
#             (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
#         )
#     def progression(self):
#         # exemple simple basé sur douleur
#         return max(0, 100 - (self.douleur_effort * 10))
    
#     # Détails Fracture
#     TYPE_FRACTURE = [
#         ('pouteau', 'Pouteau Colles'),
#         ('scaphoide', 'Scaphoïde'),
#         ('articulaire', 'Articulaire'),
#         ('autre', 'Autre / Je ne sais pas'),
#     ]
#     type_fracture = models.CharField(max_length=50, choices=TYPE_FRACTURE)
#     date_fracture = models.DateField()
#     cote_atteint = models.CharField(max_length=50, choices=[('D', 'Droit'), ('G', 'Gauche'), ('B', 'Les deux')])
#     main_dominante = models.BooleanField(default=False)
    
#     TRAITEMENT = [
#         ('platre', 'Plâtre'),
#         ('chirurgie', 'Intervention chirurgicale'),
#         ('orthese', 'Orthèse / Attelle'),
#         ('autre', 'Autre'),
#     ]
#     traitement_recu = models.CharField(max_length=50, choices=TRAITEMENT)

#     # Douleur et Symptômes
#     douleur_repos = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
#     douleur_effort = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    
#     RAIDEUR_CHOICES = [('leger', 'Léger'), ('modere', 'Modéré'), ('important', 'Important'), ('inconnu', 'Je ne sais pas')]
#     raideur_gonflement = models.CharField(max_length=20, choices=RAIDEUR_CHOICES)

#     # Limitations (Stockées en JSON ou TextField pour la flexibilité)
#     limitations = models.TextField(help_text="Habillage, Toilette, Cuisine, etc.", blank=True)
#     autres_problemes_sante = models.TextField(blank=True, null=True)   
#     medicaments = models.TextField(blank=True)
#     allergies = models.TextField(blank=True)

#     # Profession et Impact
#     STATUT_PRO = [
#         ('bureau', 'Employé de bureau'),
#         ('manuel', 'Travailleur manuel'),
#         ('etudiant', 'Étudiant'),
#         ('retraite', 'Retraité'),
#         ('chomage', 'Sans emploi'),
#         ('autre', 'Autre'),
#     ]
#     profession = models.CharField(max_length=50, choices=STATUT_PRO)

#     impact = [
#         ('arret', 'arret complet'),
#         ('travailleger', 'travail adapter léger'),
#         ('teletravail', 'télétravail possible'),
#         ('pasimpaction', "pas d'Impact"),
#         ('applicable', "non applicable"),
#     ]
#     impact_travail = models.CharField(max_length=100, choices=impact)
    
#     act = [
#         ('Sport', 'Sport'),
#         ('Cuisine', 'Cuisine'),
#         ('BricolageJardinage', 'Bricolage/Jardinage'),
#         ('ÉcritureDessin', "Écriture/Dessin"),
#         ('Informatique', "Informatique"),
#         ('Musique', "Musique"),
#         ('Artisanat', "Artisanat"),
#     ]
#     activites_anciennes = models.TextField(blank=True, choices=act)
#     autres_activite = models.TextField(max_length=100)

#     objectif_pri = [
#         ('Retrouver_lautonomie', "Retrouver l'autonomie (toilette, habillage, soins personnels)"),
#         ('Améliorer la prise', "Améliorer la prise / préhension (tenir un verre, ouvrir un bocal)"),
#         ('Diminuer la douleur', "Diminuer la douleur et reprendre les gestes sans appréhension"),
#         ('Récupérer la mobilité', "Récupérer la mobilité (flexion/extension, pronation/supination)"),
#         ('Récupérer la force', "Récupérer la force (porter, pousser, tirer)"),
#         ('Améliorer la motricité fine', "Améliorer la motricité fine (écriture, boutonner, smartphone)"),
#         ('Reprendre le travail', "Reprendre le travail / gestes professionnels"),
#         ('Reprendre_les_loisirs', "Reprendre les loisirs (sport, musique, bricolage)"),
#     ]
#     objectif_principal = models.TextField(choices=objectif_pri)
#     objectif_autre = models.TextField()

#     Comment_avez_vous_ent = [
#         ('Recommandation_medecin', "Recommandation médecin"),
#         ('Recommandation_ergotherapeute', "Recommandation ergothérapeute"),
#         ('Recherche_internet', "Recherche internet"),
#         ('Reseaux_sociaux', "Réseaux sociaux"),
#         ('Boucheoreille', "Bouche-à-oreille"),
#     ]
#     Comment_avez_vous_entendu = models.TextField(choices=Comment_avez_vous_ent)
#     Comment_avez_vous_entendu_autre = models.TextField()
    
#     # Consentements
#     cgu_accepte = models.BooleanField(default=False)
#     consentement_sante = models.BooleanField(default=False)
#     aide_ia_anonyme = models.BooleanField(default=False)
#     recevoir_rappels = models.BooleanField(default=False)
#     def __str__(self):
#         return f"Dossier de {self.user.nom}"
#     def get_derniere_evaluation(self):
#         """Récupère la dernière évaluation du patient"""
#         return Evaluation.objects.filter(patient=self).order_by('-date').first()
    
#     def get_prochaine_reeval(self):
#         """Calcule la prochaine réévaluation (30 jours après la dernière)"""
#         derniere = self.get_derniere_evaluation()
#         if derniere and derniere.date:
#             return derniere.date + timedelta(days=30)
#         return None
# # --- 3. SYSTÈME DE RECOMMANDATIONS (IA + ERGO) ---

# class IA_Recommendation(models.Model):
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
#     programme_genere = models.TextField() # Liste d'exercices suggérés par l'IA
#     date_generation = models.DateTimeField(auto_now_add=True)
#     est_valide = models.BooleanField(default=False)

# class Ergo_Recommendation(models.Model):
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
#     ia_source = models.OneToOneField(IA_Recommendation, on_delete=models.SET_NULL, null=True)
#     programme_final = models.TextField() # Le programme après modif par l'ergo
#     date_validation = models.DateTimeField(auto_now_add=True)
#     commentaires_ergo = models.TextField(blank=True)

# # --- 4. AUTRES FONCTIONNALITÉS ---

# class RDV(models.Model):
#     STATUT_CHOICES = [
#         ('actif', 'Actif'),
#         ('annule', 'Annulé'),
#         ('reprogramme', 'Reprogrammé'),
#     ]

#     TYPE_CHOICES = [
#         ('presentiel', 'Présentiel'),
#         ('tele', 'Télé-ergothérapie'),
#     ]

#     patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rdv_patient')
#     ergo = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rdv_ergo')

#     date_heure = models.DateTimeField()
#     duree = models.PositiveIntegerField(default=30)
#     type_seance = models.CharField(max_length=20, choices=TYPE_CHOICES, default='presentiel')
#     notes = models.TextField(blank=True)
#     motif = models.CharField(max_length=200, blank=True)

#     statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='actif')
#     ancienne_date_heure = models.DateTimeField(null=True, blank=True)

#     valide = models.BooleanField(default=True)
#     notification_envoyee = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"{self.patient.prenom} {self.patient.nom} - {self.date_heure.strftime('%d/%m/%Y %H:%M')}"
# class Message(models.Model):
#     expediteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
#     destinataire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
#     sujet = models.CharField(max_length=200)
#     contenu = models.TextField()
#     date_envoi = models.DateTimeField(auto_now_add=True)
#     lu = models.BooleanField(default=False)
#     piece_jointe = models.FileField(upload_to='messages_attachments/', blank=True, null=True, verbose_name="Pièce jointe")
#     piece_jointe_nom = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nom du fichier")
#     piece_jointe_type = models.CharField(max_length=50, blank=True, null=True, verbose_name="Type (image/video/pdf)")
#     est_lu_par_destinataire = models.BooleanField(default=False, verbose_name="Lu par destinataire")
#     est_supprime_par_expediteur = models.BooleanField(default=False, verbose_name="Supprimé par expéditeur")
#     est_supprime_par_destinataire = models.BooleanField(default=False, verbose_name="Supprimé par destinataire")
    
#     def __str__(self):
#         return f"De {self.expediteur.nom} à {self.destinataire.nom} - {self.date_envoi.strftime('%d/%m/%Y %H:%M')}"
    
#     @property
#     def est_non_lu(self):
#         return not self.est_lu_par_destinataire
    
#     @property
#     def a_piece_jointe(self):
#         return self.piece_jointe is not None and self.piece_jointe != ''

# class Ressource(models.Model):
#     titre = models.CharField(max_length=200)
#     contenu = models.TextField() # Ou FileField pour des PDF/Vidéos
#     type_ressource = models.CharField(max_length=50) # ex: Exercice, Conseil, Vidéo

# class Contact(models.Model):
#     nom = models.CharField(max_length=100)
#     email = models.EmailField()
#     sujet = models.CharField(max_length=200)
#     message = models.TextField()
#     date_contact = models.DateTimeField(auto_now_add=True)




# # aujourd
# # ==================== MODÈLES POUR LES ÉVALUATIONS ET BILANS ====================

# class Evaluation(models.Model):
#     """Modèle Évaluation (T1, T2, etc.)"""
#     TYPE_CHOICES = [
#         ('T1', 'Évaluation initiale'),
#         ('T2', 'Réévaluation'),
#     ]
    
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='evaluations', verbose_name="Patient")
#     type = models.CharField(max_length=2, choices=TYPE_CHOICES, verbose_name="Type")
#     numero = models.PositiveIntegerField(default=1, verbose_name="Numéro d'évaluation")
#     date = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    
#     # Données MCRO
#     mcro_rendement_t1 = models.FloatField(default=0, verbose_name="MCRO Rendement T1")
#     mcro_satisfaction_t1 = models.FloatField(default=0, verbose_name="MCRO Satisfaction T1")
#     mcro_rendement_t2 = models.FloatField(default=0, verbose_name="MCRO Rendement T2")
#     mcro_satisfaction_t2 = models.FloatField(default=0, verbose_name="MCRO Satisfaction T2")
    
#     # Données PRWE
#     prwe_douleur = models.IntegerField(default=0, verbose_name="PRWE Douleur")
#     prwe_fonction = models.IntegerField(default=0, verbose_name="PRWE Fonction")
#     prwe_total = models.IntegerField(default=0, verbose_name="PRWE Total")
    
#     # Synthèse
#     synthese_observations = models.TextField(blank=True, verbose_name="Observations cliniques")
#     synthese_impact = models.TextField(blank=True, verbose_name="Impact occupationnel")
#     synthese_objectifs = models.TextField(blank=True, verbose_name="Objectifs thérapeutiques")
#     synthese_recommandations = models.TextField(blank=True, verbose_name="Recommandations")
    
#     # Signature
#     signature_ergo = models.TextField(blank=True, verbose_name="Signature ergothérapeute")
#     signature_date = models.DateField(null=True, blank=True, verbose_name="Date signature")
#     signature_lieu = models.CharField(max_length=100, blank=True, verbose_name="Lieu signature")
#     consentement = models.BooleanField(default=False, verbose_name="Consentement patient")
    
#     class Meta:
#         verbose_name = "Évaluation"
#         verbose_name_plural = "Évaluations"
#         ordering = ['-date']
    
#     def __str__(self):
#         return f"{self.patient.user.nom} {self.patient.user.prenom} - {self.get_type_display()} #{self.numero}"


# class DonneesCliniques(models.Model):
#     """Données cliniques (anamnèse, histoire, etc.) - liées au patient"""
#     patient = models.OneToOneField(PatientProfile, on_delete=models.CASCADE, related_name='donnees_cliniques')
    
#     # Anamnèse
#     situation_familiale = models.CharField(max_length=50, blank=True, verbose_name="Situation familiale")
#     vit_avec = models.CharField(max_length=100, blank=True, verbose_name="Vit avec")
#     date_evaluation = models.DateField(null=True, blank=True, verbose_name="Date d'évaluation")
#     ergotherapeute = models.CharField(max_length=100, blank=True, verbose_name="Ergothérapeute")
    
#     # Histoire
#     date_traumatisme = models.DateField(null=True, blank=True, verbose_name="Date du traumatisme")
#     mecanisme_traumatisme = models.CharField(max_length=200, blank=True, verbose_name="Mécanisme")
#     explication = models.TextField(blank=True, verbose_name="Explication")
#     type_fracture = models.CharField(max_length=100, blank=True, verbose_name="Type de fracture")
#     prise_en_charge_initiale = models.CharField(max_length=200, blank=True, verbose_name="Prise en charge initiale")
#     duree_immobilisation = models.CharField(max_length=50, blank=True, verbose_name="Durée immobilisation")
#     complications = models.TextField(blank=True, verbose_name="Complications")
#     debut_reeducation = models.DateField(null=True, blank=True, verbose_name="Début rééducation")
#     evolution = models.CharField(max_length=50, blank=True, verbose_name="Évolution")
    
#     # Symptômes
#     douleur_repos = models.IntegerField(default=0, verbose_name="Douleur repos EVA")
#     douleur_effort = models.IntegerField(default=0, verbose_name="Douleur effort EVA")
#     localisation_douleur = models.CharField(max_length=200, blank=True, verbose_name="Localisation douleur")
#     presence_oedeme = models.BooleanField(default=False, verbose_name="Œdème")
#     presence_faiblesse = models.BooleanField(default=False, verbose_name="Faiblesse")
#     presence_troubles_sensitifs = models.BooleanField(default=False, verbose_name="Troubles sensitifs")
#     presence_fatigue = models.BooleanField(default=False, verbose_name="Fatigabilité")
    
#     # Antécédents
#     antecedents_medicaux = models.TextField(blank=True, verbose_name="Antécédents médicaux")
#     antecedents_traumatiques = models.TextField(blank=True, verbose_name="Antécédents traumatiques")
#     antecedents_chirurgicaux = models.TextField(blank=True, verbose_name="Antécédents chirurgicaux")
#     traitements_en_cours = models.TextField(blank=True, verbose_name="Traitements en cours")
#     allergies = models.CharField(max_length=200, blank=True, verbose_name="Allergies")
    
#     # Retentissement
#     difficultes_avq = models.TextField(blank=True, verbose_name="Difficultés AVQ")
#     impact_professionnel = models.TextField(blank=True, verbose_name="Impact professionnel")
#     duree_arret = models.CharField(max_length=50, blank=True, verbose_name="Durée d'arrêt")
#     soutien_familial = models.BooleanField(default=False, verbose_name="Soutien familial")
#     autonomie_domicile = models.CharField(max_length=50, blank=True, verbose_name="Autonomie domicile")
    
#     class Meta:
#         verbose_name = "Données cliniques"
#         verbose_name_plural = "Données cliniques"


# class BilanMusculaire(models.Model):
#     """Bilan musculaire - échelle MRC"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_musculaire')
    
#     # Avant-bras
#     pronation_sain = models.CharField(max_length=10, blank=True, verbose_name="Pronation sain")
#     pronation_atteint = models.CharField(max_length=10, blank=True, verbose_name="Pronation atteint")
#     supination_sain = models.CharField(max_length=10, blank=True, verbose_name="Supination sain")
#     supination_atteint = models.CharField(max_length=10, blank=True, verbose_name="Supination atteint")
    
#     # Poignet
#     flexion_poignet_sain = models.CharField(max_length=10, blank=True, verbose_name="Flexion poignet sain")
#     flexion_poignet_atteint = models.CharField(max_length=10, blank=True, verbose_name="Flexion poignet atteint")
#     extension_poignet_sain = models.CharField(max_length=10, blank=True, verbose_name="Extension poignet sain")
#     extension_poignet_atteint = models.CharField(max_length=10, blank=True, verbose_name="Extension poignet atteint")
    
#     # Doigts
#     flexion_doigts_sain = models.CharField(max_length=10, blank=True, verbose_name="Flexion doigts sain")
#     flexion_doigts_atteint = models.CharField(max_length=10, blank=True, verbose_name="Flexion doigts atteint")
#     extension_doigts_sain = models.CharField(max_length=10, blank=True, verbose_name="Extension doigts sain")
#     extension_doigts_atteint = models.CharField(max_length=10, blank=True, verbose_name="Extension doigts atteint")
    
#     # Pouce
#     flexion_pouce_sain = models.CharField(max_length=10, blank=True, verbose_name="Flexion pouce sain")
#     flexion_pouce_atteint = models.CharField(max_length=10, blank=True, verbose_name="Flexion pouce atteint")
#     opposition_pouce_sain = models.CharField(max_length=10, blank=True, verbose_name="Opposition pouce sain")
#     opposition_pouce_atteint = models.CharField(max_length=10, blank=True, verbose_name="Opposition pouce atteint")
    
#     # Synthèse
#     segments_concernes = models.TextField(blank=True, verbose_name="Segments concernés")
#     deficit_plus_marque = models.CharField(max_length=200, blank=True, verbose_name="Déficit le plus marqué")
#     cotation_minimale = models.CharField(max_length=50, blank=True, verbose_name="Cotation minimale")
#     intensite_globale = models.CharField(max_length=50, blank=True, verbose_name="Intensité globale")
#     douleur_testing = models.BooleanField(default=False, verbose_name="Douleur testing")
#     compensations = models.BooleanField(default=False, verbose_name="Compensations")
#     retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
#     class Meta:
#         verbose_name = "Bilan musculaire"
#         verbose_name_plural = "Bilans musculaires"


# class BilanArticulaire(models.Model):
#     """Bilan articulaire - goniométrie"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_articulaire')
    
#     # Poignet
#     flexion_active_sain = models.IntegerField(default=0, verbose_name="Flexion active sain (°)")
#     flexion_active_atteint = models.IntegerField(default=0, verbose_name="Flexion active atteint (°)")
#     flexion_passive_atteint = models.IntegerField(default=0, verbose_name="Flexion passive atteint (°)")
#     extension_active_sain = models.IntegerField(default=0, verbose_name="Extension active sain (°)")
#     extension_active_atteint = models.IntegerField(default=0, verbose_name="Extension active atteint (°)")
#     extension_passive_atteint = models.IntegerField(default=0, verbose_name="Extension passive atteint (°)")
    
#     # Inclinaisons
#     radial_active_sain = models.IntegerField(default=0, verbose_name="Inclinaison radiale active sain (°)")
#     radial_active_atteint = models.IntegerField(default=0, verbose_name="Inclinaison radiale active atteint (°)")
#     ulnar_active_sain = models.IntegerField(default=0, verbose_name="Inclinaison ulnaire active sain (°)")
#     ulnar_active_atteint = models.IntegerField(default=0, verbose_name="Inclinaison ulnaire active atteint (°)")
    
#     # Avant-bras
#     pronation_active_sain = models.IntegerField(default=0, verbose_name="Pronation active sain (°)")
#     pronation_active_atteint = models.IntegerField(default=0, verbose_name="Pronation active atteint (°)")
#     supination_active_sain = models.IntegerField(default=0, verbose_name="Supination active sain (°)")
#     supination_active_atteint = models.IntegerField(default=0, verbose_name="Supination active atteint (°)")
    
#     # Doigts (stockés en JSON)
#     doigts_donnees = models.JSONField(default=dict, blank=True, verbose_name="Données doigts")
    
#     # Pouce
#     pouce_donnees = models.JSONField(default=dict, blank=True, verbose_name="Données pouce")
    
#     # Kapandji
#     kapandji_sain = models.IntegerField(default=0, verbose_name="Kapandji sain (0-10)")
#     kapandji_atteint = models.IntegerField(default=0, verbose_name="Kapandji atteint (0-10)")
#     mouvement_qualite = models.CharField(max_length=50, blank=True, verbose_name="Qualité du mouvement")
    
#     # Synthèse
#     segments_concernes = models.TextField(blank=True, verbose_name="Segments concernés")
#     limitation_plus_marquee = models.CharField(max_length=200, blank=True, verbose_name="Limitation la plus marquée")
#     amplitude_minimale = models.CharField(max_length=50, blank=True, verbose_name="Amplitude minimale")
#     importance_limitation = models.CharField(max_length=50, blank=True, verbose_name="Importance limitation")
#     analyse_mobilite = models.CharField(max_length=100, blank=True, verbose_name="Analyse mobilité")
#     douleur_fin_amplitude = models.BooleanField(default=False, verbose_name="Douleur fin amplitude")
#     raideur_capsulaire = models.BooleanField(default=False, verbose_name="Raideur capsulaire")
#     retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
#     class Meta:
#         verbose_name = "Bilan articulaire"
#         verbose_name_plural = "Bilans articulaires"


# class BilanDouleur(models.Model):
#     """Bilan de douleur - EVA"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_douleur')
    
#     douleur_repos = models.IntegerField(default=0, verbose_name="Douleur au repos (0-10)")
#     douleur_mouvement = models.IntegerField(default=0, verbose_name="Douleur au mouvement (0-10)")
#     interpretation = models.CharField(max_length=50, blank=True, verbose_name="Interprétation")
#     localisation = models.CharField(max_length=200, blank=True, verbose_name="Localisation")
#     type_douleur = models.CharField(max_length=50, blank=True, verbose_name="Type de douleur")
#     facteurs_aggravants = models.TextField(blank=True, verbose_name="Facteurs aggravants")
#     facteurs_soulageants = models.TextField(blank=True, verbose_name="Facteurs soulageants")
#     retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
#     class Meta:
#         verbose_name = "Bilan douleur"
#         verbose_name_plural = "Bilans douleur"


# class BilanTrophique(models.Model):
#     """Bilan trophique"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_trophique')
    
#     oedeme = models.BooleanField(default=False, verbose_name="Œdème")
#     oedeme_caractere = models.CharField(max_length=50, blank=True, verbose_name="Caractère œdème")
#     oedeme_localisation = models.CharField(max_length=200, blank=True, verbose_name="Localisation œdème")
    
#     # Mesures périmétriques
#     perimetre_poignet_sain = models.FloatField(default=0, verbose_name="Périmètre poignet sain (cm)")
#     perimetre_poignet_atteint = models.FloatField(default=0, verbose_name="Périmètre poignet atteint (cm)")
#     perimetre_10cm_sain = models.FloatField(default=0, verbose_name="Périmètre 10cm proximal sain (cm)")
#     perimetre_10cm_atteint = models.FloatField(default=0, verbose_name="Périmètre 10cm proximal atteint (cm)")
#     perimetre_mcp_sain = models.FloatField(default=0, verbose_name="Périmètre têtes MCP sain (cm)")
#     perimetre_mcp_atteint = models.FloatField(default=0, verbose_name="Périmètre têtes MCP atteint (cm)")
    
#     couleur_peau = models.CharField(max_length=100, blank=True, verbose_name="Coloration cutanée")
#     temperature = models.CharField(max_length=50, blank=True, verbose_name="Température cutanée")
#     etat_cutane = models.TextField(blank=True, verbose_name="État cutané")
#     cicatrice_presente = models.BooleanField(default=False, verbose_name="Cicatrice présente")
#     cicatrice_caractere = models.CharField(max_length=100, blank=True, verbose_name="Caractère cicatrice")
#     retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
#     class Meta:
#         verbose_name = "Bilan trophique"
#         verbose_name_plural = "Bilans trophiques"


# class BilanSensitif(models.Model):
#     """Bilan sensitif"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_sensitif')
    
#     # Zones testées (stockées en JSON)
#     zones_testees = models.JSONField(default=dict, blank=True, verbose_name="Zones testées")
    
#     interpretation_globale = models.CharField(max_length=50, blank=True, verbose_name="Interprétation globale")
#     sensibilite_douloureuse = models.CharField(max_length=50, blank=True, verbose_name="Sensibilité douloureuse")
#     proprioception = models.CharField(max_length=50, blank=True, verbose_name="Proprioception")
#     paresthesies_spontanees = models.TextField(blank=True, verbose_name="Paresthésies spontanées")
#     territoire_nerveux = models.CharField(max_length=100, blank=True, verbose_name="Territoire nerveux suspecté")
#     presence_trouble = models.BooleanField(default=False, verbose_name="Présence trouble sensitif")
#     type_atteinte = models.CharField(max_length=100, blank=True, verbose_name="Type d'atteinte")
#     localisation_principale = models.CharField(max_length=200, blank=True, verbose_name="Localisation principale")
#     retentissement_fonctionnel = models.TextField(blank=True, verbose_name="Retentissement fonctionnel")
    
#     class Meta:
#         verbose_name = "Bilan sensitif"
#         verbose_name_plural = "Bilans sensitifs"


# class BilanPrehension(models.Model):
#     """Bilan de préhension"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_prehension')
    
#     # Scores
#     score_total = models.IntegerField(default=0, verbose_name="Score total /66")
#     prises_impossibles = models.IntegerField(default=0, verbose_name="Prises impossibles")
#     prises_difficiles = models.IntegerField(default=0, verbose_name="Prises difficiles")
#     niveau_atteinte = models.CharField(max_length=50, blank=True, verbose_name="Niveau d'atteinte")
    
#     # Données détaillées (stockées en JSON)
#     donnees = models.JSONField(default=dict, blank=True, verbose_name="Données détaillées des prises")
    
#     # Approche vers l'objet
#     mouvement_balayage = models.CharField(max_length=10, blank=True, verbose_name="Mouvement de balayage")
#     approche_parabolique = models.CharField(max_length=10, blank=True, verbose_name="Approche parabolique")
#     approche_directe = models.CharField(max_length=10, blank=True, verbose_name="Approche directe")
    
#     # Lâcher
#     lacher_volontaire = models.CharField(max_length=10, blank=True, verbose_name="Lâcher volontaire")
#     lacher_involontaire = models.CharField(max_length=10, blank=True, verbose_name="Lâcher involontaire")
    
#     # Force
#     regulation_force = models.CharField(max_length=10, blank=True, verbose_name="Régulation de la force")
    
#     # Coordination bi-manuelle (stockée en JSON)
#     coordination_donnees = models.JSONField(default=dict, blank=True, verbose_name="Coordination bi-manuelle")
    
#     # Synthèse
#     synthese = models.TextField(blank=True, verbose_name="Synthèse")
    
#     class Meta:
#         verbose_name = "Bilan de préhension"
#         verbose_name_plural = "Bilans de préhension"


# class BilanDexterite(models.Model):
#     """Bilan de dextérité"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_dexterite')
    
#     # Test 1 - Manipulation d'objets
#     test1_temps_sain = models.FloatField(default=0, verbose_name="Test1 temps sain (sec)")
#     test1_temps_atteint = models.FloatField(default=0, verbose_name="Test1 temps atteint (sec)")
#     test1_erreurs = models.TextField(blank=True, verbose_name="Test1 erreurs")
    
#     # Test 2 - Enfilage de perles
#     test2_temps_sain = models.FloatField(default=0, verbose_name="Test2 temps sain (sec)")
#     test2_temps_atteint = models.FloatField(default=0, verbose_name="Test2 temps atteint (sec)")
#     test2_erreurs = models.TextField(blank=True, verbose_name="Test2 erreurs")
    
#     # Test 3 - Dévissage
#     test3_temps_sain = models.FloatField(default=0, verbose_name="Test3 temps sain (sec)")
#     test3_temps_atteint = models.FloatField(default=0, verbose_name="Test3 temps atteint (sec)")
#     test3_erreurs = models.TextField(blank=True, verbose_name="Test3 erreurs")
    
#     # Synthèse
#     total_erreurs = models.IntegerField(default=0, verbose_name="Total erreurs")
#     objets_echappes = models.IntegerField(default=0, verbose_name="Objets échappés")
#     interruption_tache = models.BooleanField(default=False, verbose_name="Interruption tâche")
#     douleur_tache = models.BooleanField(default=False, verbose_name="Douleur pendant tâche")
#     fatigabilite = models.BooleanField(default=False, verbose_name="Fatigabilité observée")
#     synthese = models.TextField(blank=True, verbose_name="Synthèse")
    
#     class Meta:
#         verbose_name = "Bilan de dextérité"
#         verbose_name_plural = "Bilans de dextérité"


# class BilanEndurance(models.Model):
#     """Bilan d'endurance"""
#     evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='bilan_endurance')
    
#     # Côté sain
#     sain_pressions = models.IntegerField(default=0, verbose_name="Sain - Nombre de pressions")
#     sain_douleur = models.BooleanField(default=False, verbose_name="Sain - Douleur")
#     sain_fatigue = models.CharField(max_length=20, blank=True, verbose_name="Sain - Fatigue")
#     sain_observation = models.TextField(blank=True, verbose_name="Sain - Observation")
    
#     # Côté atteint
#     atteint_pressions = models.IntegerField(default=0, verbose_name="Atteint - Nombre de pressions")
#     atteint_douleur = models.BooleanField(default=False, verbose_name="Atteint - Douleur")
#     atteint_fatigue = models.CharField(max_length=20, blank=True, verbose_name="Atteint - Fatigue")
#     atteint_observation = models.TextField(blank=True, verbose_name="Atteint - Observation")
    
#     # Interprétation
#     interpretation = models.CharField(max_length=100, blank=True, verbose_name="Interprétation")
#     observation_clinique = models.TextField(blank=True, verbose_name="Observation clinique")
#     synthese = models.TextField(blank=True, verbose_name="Synthèse")
    
#     class Meta:
#         verbose_name = "Bilan d'endurance"
#         verbose_name_plural = "Bilans d'endurance"


# # ==================== MODÈLES POUR LES PROGRAMMES ET EXERCICES ====================
# # ==================== MODÈLES POUR LES PROGRAMMES ET EXERCICES ====================

# class BibliothequeExercice(models.Model):
#     patient = models.ForeignKey(
#         PatientProfile,
#         on_delete=models.CASCADE,
#         related_name='bibliotheque_exercices',
#         null=True,
#         blank=True
#     )
#     nom = models.CharField(max_length=255)
#     categorie = models.CharField(max_length=100, blank=True)
#     series = models.IntegerField(default=1)
#     repetitions = models.IntegerField(default=1)
#     temps_exercice = models.CharField(max_length=100, blank=True)
#     objectif = models.TextField(blank=True)
#     instructions = models.TextField(blank=True)
#     materiel_necessaire = models.TextField(blank=True)
#     ordre = models.IntegerField(default=1)
#     created_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.nom


# class BibliothequeExerciceMedia(models.Model):
#     exercice = models.ForeignKey(
#         'BibliothequeExercice',
#         on_delete=models.CASCADE,
#         related_name='medias'
#     )
#     fichier = models.FileField(upload_to='exercices_demo/')
#     date_ajout = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Media - {self.exercice.nom}"


# class ProgrammeExercice(models.Model):
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='programmes')
#     ergotherapeute = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'ergo'})
#     nom = models.CharField(max_length=200, verbose_name="Nom du programme")
#     description = models.TextField(blank=True, verbose_name="Description")
#     date_debut = models.DateField(verbose_name="Date de début")
#     date_fin = models.DateField(blank=True, null=True, verbose_name="Date de fin")
#     phase = models.CharField(max_length=50, default='1', verbose_name="Phase")
#     actif = models.BooleanField(default=True, verbose_name="Actif")
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         verbose_name = "Programme d'exercices"
#         verbose_name_plural = "Programmes d'exercices"
#         ordering = ['-date_debut']
    
#     def __str__(self):
#         return f"{self.patient.user.nom} {self.patient.user.prenom} - {self.nom}"


# class Exercice(models.Model):
#     programme = models.ForeignKey(
#         ProgrammeExercice,
#         on_delete=models.CASCADE,
#         related_name='exercices'
#     )
#     bibliotheque_exercice = models.ForeignKey(
#         BibliothequeExercice,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='exercices_programme'
#     )
#     nom = models.CharField(max_length=255)
#     categorie = models.CharField(max_length=100, blank=True)
#     series = models.PositiveIntegerField(default=1)
#     repetitions = models.PositiveIntegerField(default=1)
#     temps_exercice = models.CharField(max_length=255, blank=True)
#     objectif = models.TextField(blank=True)
#     instructions = models.TextField(blank=True)
#     materiel_necessaire = models.TextField(blank=True)
#     media_demo = models.FileField(upload_to='exercices_programmes/', blank=True, null=True)
#     ordre = models.PositiveIntegerField(default=1)

#     def __str__(self):
#         return self.nom


# class ExerciceMedia(models.Model):
#     exercice = models.ForeignKey(
#         Exercice,
#         on_delete=models.CASCADE,
#         related_name='medias'
#     )
#     fichier = models.FileField(upload_to='exercices_programmes_media/')
#     date_upload = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Média pour {self.exercice.nom}"

# class ResultatExercice(models.Model):
#     """Résultat d'un exercice réalisé par le patient"""
#     exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE, related_name='resultats')
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='resultats_exercices')
#     date_realisation = models.DateTimeField(auto_now_add=True, verbose_name="Date de réalisation")
    
#     # Résultats
#     resultat_texte = models.TextField(blank=True, verbose_name="Description du résultat")
#     amplitude_atteinte = models.IntegerField(default=0, verbose_name="Amplitude atteinte (°)")
#     force_atteinte = models.IntegerField(default=0, verbose_name="Force atteinte (kg)")
#     douleur = models.IntegerField(default=0, verbose_name="Douleur (0-10)")
#     satisfaction = models.IntegerField(default=0, verbose_name="Satisfaction (1-5)")
#     difficultes = models.TextField(blank=True, verbose_name="Difficultés rencontrées")
    
#     # Médias
#     media_type = models.CharField(max_length=10, blank=True, verbose_name="Type de média (photo/video)")
#     media_url = models.URLField(blank=True, verbose_name="URL du média")
#     media_fichier = models.FileField(upload_to='resultats/', blank=True, null=True, verbose_name="Fichier média")
    
#     # Validation
#     valide_par_ergo = models.BooleanField(default=False, verbose_name="Validé par ergothérapeute")
#     commentaire_ergo = models.TextField(blank=True, verbose_name="Commentaire ergothérapeute")
    
#     class Meta:
#         verbose_name = "Résultat d'exercice"
#         verbose_name_plural = "Résultats d'exercices"
#         ordering = ['-date_realisation']
    
#     def __str__(self):
#         return f"{self.patient.user.nom} - {self.exercice.nom} - {self.date_realisation.strftime('%d/%m/%Y')}"


# # ==================== MODÈLES POUR LA PROGRESSION ET LE SUIVI ====================

# class ProgressionPatient(models.Model):
#     """Suivi de la progression du patient dans le temps"""
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='progressions')
#     date = models.DateField(auto_now_add=True, verbose_name="Date")
    
#     # Scores
#     douleur = models.IntegerField(default=0, verbose_name="Douleur (0-10)")
#     fatigue = models.IntegerField(default=0, verbose_name="Fatigue (1-5)")
#     humeur = models.CharField(max_length=20, blank=True, verbose_name="Humeur")
#     satisfaction = models.IntegerField(default=0, verbose_name="Satisfaction (1-5)")
#     progression_globale = models.IntegerField(default=0, verbose_name="Progression globale (%)")
    
#     # Indicateurs
#     mobilite = models.IntegerField(default=0, verbose_name="Mobilité (%)")
#     force = models.IntegerField(default=0, verbose_name="Force (%)")
#     endurance = models.IntegerField(default=0, verbose_name="Endurance (%)")
#     dexterite = models.IntegerField(default=0, verbose_name="Dextérité (%)")
#     sensibilite = models.IntegerField(default=0, verbose_name="Sensibilité (%)")
#     prehension = models.IntegerField(default=0, verbose_name="Préhension (%)")
    
#     # Notes
#     notes = models.TextField(blank=True, verbose_name="Notes du patient")
#     reponse_question = models.CharField(max_length=10, blank=True, verbose_name="Réponse à la question du jour")
    
#     class Meta:
#         verbose_name = "Progression patient"
#         verbose_name_plural = "Progressions patients"
#         ordering = ['-date']
    
#     def __str__(self):
#         return f"{self.patient.user.nom} - {self.date}"


# class JournalPatient(models.Model):
#     """Journal personnel du patient"""
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='journal')
#     date = models.DateField(auto_now_add=True, verbose_name="Date")
#     contenu = models.TextField(verbose_name="Contenu du journal")
#     humeur = models.CharField(max_length=20, blank=True, verbose_name="Humeur")
    
#     class Meta:
#         verbose_name = "Journal patient"
#         verbose_name_plural = "Journaux patients"
#         ordering = ['-date']
    
#     def __str__(self):
#         return f"{self.patient.user.nom} - {self.date}"


# class Recompense(models.Model):
#     """Récompenses/badges gagnés par le patient"""
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='recompenses')
#     nom = models.CharField(max_length=100, verbose_name="Nom de la récompense")
#     description = models.TextField(blank=True, verbose_name="Description")
#     icone = models.CharField(max_length=50, default='bi-award', verbose_name="Icône Bootstrap")
#     date_obtention = models.DateTimeField(auto_now_add=True, verbose_name="Date d'obtention")
    
#     class Meta:
#         verbose_name = "Récompense"
#         verbose_name_plural = "Récompenses"
    
#     def __str__(self):
#         return f"{self.patient.user.nom} - {self.nom}"


# class DefiPatient(models.Model):
#     """Défis pour motiver le patient"""
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='defis')
#     nom = models.CharField(max_length=200, verbose_name="Nom du défi")
#     description = models.TextField(blank=True, verbose_name="Description")
#     objectif = models.IntegerField(verbose_name="Objectif")
#     progression = models.IntegerField(default=0, verbose_name="Progression actuelle")
#     termine = models.BooleanField(default=False, verbose_name="Terminé")
#     date_debut = models.DateField(auto_now_add=True, verbose_name="Date de début")
#     date_fin = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    
#     class Meta:
#         verbose_name = "Défi patient"
#         verbose_name_plural = "Défis patients"
    
#     def __str__(self):
#         return f"{self.patient.user.nom} - {self.nom}"


# # ==================== MODÈLES POUR LA TRACABILITÉ ====================

# class HistoriqueAction(models.Model):
#     """Journal d'activité complet"""
#     TYPE_CHOICES = [
#         ('seance', 'Séance'),
#         ('message', 'Message'),
#         ('ressource', 'Ressource'),
#         ('dossier', 'Dossier'),
#         ('programme', 'Programme'),
#         ('ia', 'IA'),
#         ('patient', 'Patient'),
#     ]
    
#     utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historique')
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='historique')
#     type_action = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type d'action")
#     action = models.CharField(max_length=200, verbose_name="Action réalisée")
#     details = models.JSONField(default=dict, blank=True, verbose_name="Détails")
#     date_action = models.DateTimeField(auto_now_add=True, verbose_name="Date de l'action")
    
#     class Meta:
#         verbose_name = "Historique action"
#         verbose_name_plural = "Historique actions"
#         ordering = ['-date_action']
    
#     def __str__(self):
#         return f"{self.utilisateur.username} - {self.action} - {self.date_action.strftime('%d/%m/%Y %H:%M')}"
    


#     # aujour
#     # ==================== MULTILINGUE ====================

# class Translation(models.Model):
#     """Modèle pour stocker les traductions"""
#     LANG_CHOICES = [
#         ('fr', 'Français'),
#         ('en', 'English'),
#         ('ar', 'العربية'),
#     ]
    
#     key = models.CharField(max_length=200, unique=True, verbose_name="Clé de traduction")
#     fr = models.TextField(verbose_name="Français", blank=True)
#     en = models.TextField(verbose_name="English", blank=True)
#     ar = models.TextField(verbose_name="العربية", blank=True)
    
#     class Meta:
#         verbose_name = "Traduction"
#         verbose_name_plural = "Traductions"
    
#     def __str__(self):
#         return self.key
    
#     def get(self, lang='fr'):
#         """Récupère la traduction dans la langue demandée"""
#         return getattr(self, lang, self.fr)


#     def get_translation(key, lang='fr'):
#         """Fonction utilitaire pour récupérer une traduction"""
#         try:
#             t = Translation.objects.get(key=key)
#             return t.get(lang)
#         except Translation.DoesNotExist:
#             return key
        
# # dossier patient
# class DossierPatient(models.Model):
#     # IDENTIFICATION
#     nom = models.CharField(max_length=100)
#     prenom = models.CharField(max_length=100)
#     date_naissance = models.DateField()
#     age = models.IntegerField(null=True, blank=True)


#     SEXE_CHOICES = [
#         ('F', 'Femme'),
#         ('H', 'Homme'),
#     ]
#     sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)

#     SITUATION_CHOICES = [
#         ('celibataire', 'Célibataire'),
#         ('marie', 'Marié(e)'),
#         ('divorce', 'Divorcé(e)'),
#         ('veuf', 'Veuf(ve)'),
#     ]
#     situation_familiale = models.CharField(max_length=20, choices=SITUATION_CHOICES)

#     VIT_CHOICES = [
#         ('seul', 'Seul(e)'),
#         ('conjoint', 'Avec conjoint'),
#         ('famille', 'Avec famille'),
#         ('autre', 'Autre'),
#     ]
#     vit = models.CharField(max_length=20, choices=VIT_CHOICES)

#     diagnostic = models.TextField()

#     MEMBRE_CHOICES = [
#         ('droit', 'Droit'),
#         ('gauche', 'Gauche'),
#     ]
#     membre_atteint = models.CharField(max_length=10, choices=MEMBRE_CHOICES)

#     DOMINANCE_CHOICES = [
#         ('droitier', 'Droitier'),
#         ('gaucher', 'Gaucher'),
#     ]
#     dominance = models.CharField(max_length=10, choices=DOMINANCE_CHOICES)

#     profession = models.CharField(max_length=200)
#     adresse = models.TextField()
#     telephone = models.CharField(max_length=20)
#     email = models.EmailField()

#     date_evaluation = models.DateField()
#     ergotherapeute = models.CharField(max_length=200)

#     def __str__(self):
#         return f"{self.nom} {self.prenom}"
    
# class HistoireMaladie(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     date_traumatisme = models.DateField()

#     mecanisme = models.CharField(max_length=50, choices=[
#         ('chute', 'Chute sur la main'),
#         ('domestique', 'Accident domestique'),
#         ('travail', 'Accident de travail'),
#         ('sport', 'Accident sportif'),
#         ('autre', 'Autre'),
#     ])

#     explication = models.TextField()
#     type_fracture = models.CharField(max_length=200)

#     prise_en_charge = models.CharField(max_length=50, choices=[
#         ('platre', 'Plâtre'),
#         ('chirurgie', 'Chirurgie'),
#         ('reduction', 'Réduction orthopédique'),
#         ('orthese', 'Orthèse'),
#     ])

#     duree_immobilisation = models.IntegerField(null=True, blank=True)

#     complications = models.CharField(max_length=50)

#     debut_reeducation = models.DateField()

#     evolution = models.CharField(max_length=20, choices=[
#         ('amelioration', 'Amélioration'),
#         ('stabilisation', 'Stabilisation'),
#         ('aggravation', 'Aggravation'),
#     ])

# class Symptome(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     douleur_repos = models.IntegerField(null=True, blank=True)

#     douleur_effort = models.IntegerField(null=True, blank=True)


#     localisation = models.TextField()

#     raideur = models.BooleanField()
#     oedeme = models.BooleanField()
#     faiblesse = models.BooleanField()
#     troubles_sensitifs = models.BooleanField()
#     fatigabilite = models.BooleanField()

# class Retentissement(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     habillage = models.BooleanField()
#     toilette = models.BooleanField()
#     cuisine = models.BooleanField()
#     port_charge = models.BooleanField()
#     ecriture = models.BooleanField()
#     clavier = models.BooleanField()
#     telephone = models.BooleanField()
#     conduite = models.BooleanField()
#     autre = models.TextField()

#     impact_professionnel = models.CharField(max_length=50, choices=[
#         ('arret', 'Arrêt de travail'),
#         ('amenagement', 'Aménagement de poste'),
#         ('partiel', 'Difficulté partielle'),
#         ('complet', 'Reprise complète'),
#     ])

#     duree_arret = models.CharField(max_length=50)

#     contexte_psychosocial = models.BooleanField()

#     autonomie_a_domicile = models.CharField(max_length=50, choices=[
#         ('totale', 'totale'),
#         ('partielle', 'partielle'),
#         ('dependente', 'dependente'),
#     ])

# class Antecedents(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     diabete = models.BooleanField()
#     osteoporose = models.BooleanField()
#     arthrite = models.BooleanField()
#     hypertension = models.BooleanField()
#     neurologiques = models.BooleanField()
#     autre = models.TextField()

#     traumatiques = models.TextField()
#     chirurgicaux = models.TextField()
#     traitements = models.TextField()
#     allergies = models.TextField()

# class Objectifs(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     douleur = models.BooleanField()
#     mobilite = models.BooleanField()
#     force = models.BooleanField()
#     travail = models.BooleanField()
#     activite = models.BooleanField()

# class BilanMusculaire(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     segment = models.CharField(max_length=50)
#     mouvement = models.CharField(max_length=50)

#     cote = models.CharField(max_length=10, choices=[
#         ('sain', 'Sain'),
#         ('atteint', 'Atteint')
#     ])

#     cotation = models.CharField(max_length=5)  # 0,1,2-,2,2+,3...
#     observation = models.TextField(blank=True)

# class Synthese_une(models.Model):
#     segments_concernes = models.CharField(max_length=200)
#     mouvement = models.CharField(max_length=200)
#     cotation_sain = models.CharField(max_length=200)
#     cotation_atteint = models.CharField(max_length=200)
#     ecart_observe = models.CharField(max_length=200)
#     cotation_minimale_observe = models.CharField(max_length=200)
#     intensite_globale = models.CharField(max_length=100, choices=[
#         ('legere', 'légere (écart <= 1 point)'),
#         ('moderee', 'Modérée (écart 2 point)'),
#         ('importante', 'Importante (écart >= 3 point')
#     ])
#     douleur_lors_du_testing = models.BooleanField()
#     douleur_oui = models.TextField()

#     presence_de_compensation = models.BooleanField()
#     presence_oui = models.TextField()

#     retentissement_fonctionnel = models.TextField()

# class Articulaire(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     segment = models.CharField(max_length=50)
#     mouvement = models.CharField(max_length=50)
#     norme = models.CharField(max_length=50)
#     actif_sain = models.CharField(max_length=50)
#     actif_atteint = models.CharField(max_length=50)
#     passif_atteint = models.CharField(max_length=50)
#     ecart_vs_sain = models.CharField(max_length=50)
#     observations = models.CharField(max_length=50)

# class Articulaire_doit(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     segment = models.CharField(max_length=50)
#     mouvement = models.CharField(max_length=50)
#     cote_sain = models.CharField(max_length=50)
#     cote_atteint = models.CharField(max_length=50)
#     observations = models.CharField(max_length=50)

# class Articulaire_pouce(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     mouvement = models.CharField(max_length=50)
#     cote_sain = models.CharField(max_length=50)
#     cote_atteint = models.CharField(max_length=50)
#     observations = models.CharField(max_length=50)

# class Articulaire_opposition(models.Model):
#     opposition_pouce = models.IntegerField(null=True, blank=True)

#     mouvement = models.CharField(max_length=10, choices=[
#         ('complet', 'complet'),
#         ('legere', 'légerement limité'),
#         ('limite', 'limité'),
#         ('impossible', 'impossible')
#     ])
#     segment_concernee = models.TextField()
#     mouvement_avec_limitation = models.TextField()
#     mouvement_avec_limitation_amplitude_sain = models.TextField()
#     mouvement_avec_limitation_amplitude_atteint = models.TextField()
#     mouvement_avec_limitation_ecart_observe = models.TextField()

#     amplitude_minimale = models.TextField()

#     importance_globale_de_lim = models.CharField(max_length=10, choices=[
#         ('legere', 'légere (écart <= 10)'),
#         ('moderee', 'Modérée (écart 10-20)'),
#         ('importante', 'Importante (écart >= 20)')
#     ])

#     presence_de_douleur = models.BooleanField()
#     presence_de_douleur_oui = models.TextField()

#     analyse_comparative = models.CharField(max_length=10, choices=[
#         ('passive', 'Mobilité passive > actif'),
#         ('active', 'Mobilité passive comparable'),
#         ('mixte', 'Limitation mixte')
#     ])
#     analyse_comparative_interpetation = models.TextField()

#     presence_de_raideur = models.BooleanField()
#     presence_de_raideur_oui = models.TextField()

#     retentissement = models.TextField()

# class Douleur(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     repos = models.IntegerField(null=True, blank=True)

#     mouvement = models.IntegerField(null=True, blank=True)


#     interpretation = models.CharField(max_length=60, choices=[
#         ('legere', 'Légère (0-3)'),
#         ('moderer', 'Douleur modérée (4-6)'),
#         ('intense', 'Douleur intense (7-10)'),
#     ])
#     type_douleur = models.CharField(max_length=100, choices=[
#         ('mecanique', 'Mécanique (majorée au mouvement/effort)'),
#         ('inflammatoire', 'inflammatoire (présente au repos/nocturne)'),
#         ('mixte', 'mixte'),
#     ])

#     localisation = models.TextField()

#     facteurs_aggravants = models.TextField()
#     facteurs_soulageants = models.TextField()

#     retentissement = models.TextField()

# class Trophique(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     oedeme = models.BooleanField()
#     caractere = models.CharField(max_length=20)
#     localisation = models.CharField(max_length=50)

#     coloration = models.CharField(max_length=50)
#     temperature = models.CharField(max_length=50)
#     etat_cutane = models.TextField()

#     cicatrice = models.CharField(max_length=50)

#     retentissement = models.TextField()

# class Trophiquemesure(models.Model):
#     site = models.CharField(max_length=50)
#     sain = models.CharField(max_length=50)
#     atteint = models.CharField(max_length=50)
#     difference = models.CharField(max_length=50)

# class Sensitif(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     interpretation = models.CharField(max_length=50)

#     douleur = models.CharField(max_length=50)
#     douleur_localisaton = models.CharField(max_length=50)
#     proprioception = models.CharField(max_length=50)

#     paresthesies = models.CharField(max_length=50)
#     paresthesies_localisation = models.CharField(max_length=50)
#     territoire = models.CharField(max_length=50)
    
#     presence_trouble = models.BooleanField()
#     type_atteinte = models.CharField(max_length=50)
#     localisation = models.TextField()
#     retentissement = models.TextField()

# class Sensitif_table(models.Model):
#     zone = models.CharField(max_length=50)
#     cote_sain = models.CharField(max_length=50)
#     cote_atteint = models.CharField(max_length=50)
#     observation = models.CharField(max_length=50)

# class Prehension(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     type_prise = models.CharField(max_length=100)

#     droite = models.CharField(max_length=100)  # +, +/-, --
#     gauche = models.CharField(max_length=100)

#     observation = models.TextField()

# class Prehension_table_deux(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     element = models.CharField(max_length=100)

#     droite = models.CharField(max_length=100)  # +, +/-, --
#     gauche = models.CharField(max_length=100)

#     observation = models.TextField()

# class Prehension_table_troi(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     type = models.CharField(max_length=100)

#     droite = models.CharField(max_length=100)   
#     gauche = models.CharField(max_length=100)

#     observation = models.TextField()

# class Prehension_table_quatre(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     element = models.CharField(max_length=100)

#     droite = models.CharField(max_length=100)   
#     gauche = models.CharField(max_length=100)

#     observation = models.TextField()

# class Prehension_table_cinq(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     type = models.CharField(max_length=100)

#     activite = models.CharField(max_length=100)  

#     observation = models.TextField()

# class Prehension_synthese(models.Model):
#     patient = models.ForeignKey(DossierPatient, on_delete=models.CASCADE)

#     score = models.CharField(max_length=100)

#     prise_impossible = models.CharField(max_length=100)  
#     prise_difficile = models.CharField(max_length=100)

#     interpretation = models.TextField()

# class Dexterite(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     cote_sain = models.IntegerField(null=True, blank=True)

#     cote_atteint = models.IntegerField(null=True, blank=True)

#     ecart = models.IntegerField(null=True, blank=True)

#     details = models.TextField()
    
#     enfilage_cote_sain = models.IntegerField(null=True, blank=True)

#     enfilage_cote_atteint = models.IntegerField(null=True, blank=True)

#     enfilage_ecart = models.IntegerField(null=True, blank=True)

#     enfilage_details = models.TextField()

#     devisser_cote_sain = models.IntegerField(null=True, blank=True)

#     devisser_cote_atteint = models.IntegerField(null=True, blank=True)

#     devisser_ecart = models.IntegerField(null=True, blank=True)

#     devisser_details = models.TextField()

#     synthese_nombre_totale = models.IntegerField(null=True, blank=True)

#     synthese_nombre_object = models.IntegerField(null=True, blank=True)


#     Interruption = models.BooleanField()
#     douleur = models.BooleanField()
#     fatiguabilite = models.BooleanField()

# class Endurence(models.Model):
#     cote_sain = models.IntegerField(null=True, blank=True)

#     cote_sain_douleur = models.BooleanField()
#     cote_sain_fatigue = models.TextField()
#     cote_sain_observation = models.TextField()

#     cote_atteint = models.IntegerField(null=True, blank=True)

#     cote_atteint_douleur = models.BooleanField()
#     cote_atteint_fatigue = models.TextField()
#     cote_atteint_observation = models.TextField()

#     interpretation = models.TextField()

#     observation_clinique = models.TextField()

#     synthese = models.TextField()

# class Mcrco(models.Model):
#     nom = models.CharField(max_length=100)
#     date_naissance = models.DateField()
#     age = models.IntegerField(null=True, blank=True)


#     SEXE_CHOICES = [
#         ('F', 'Femme'),
#         ('H', 'Homme'),
#     ]
#     sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
#     repondant = models.CharField(max_length=100)
#     date_evaluation = models.DateField()
#     date_prevue_reevaluation = models.DateField()
#     date_reevaluation = models.DateField()
#     therapeute = models.CharField(max_length=100)
#     etablissement = models.CharField(max_length=100)
#     programme = models.CharField(max_length=100)
#     cotee_rendement_t1 = models.CharField(max_length=100)
#     cotee_satisfaction_t1 = models.IntegerField(null=True, blank=True)

#     cotee_rendement_t2 = models.IntegerField(null=True, blank=True)

#     cotee_satisfaction_t2 = models.IntegerField(null=True, blank=True)

#     cotee_moyenne_rendement_t1 = models.IntegerField(null=True, blank=True)

#     cotee_moyenne_satisfaction_t1 = models.IntegerField(null=True, blank=True)

#     cotee_moyenne_rendement_t2 = models.IntegerField(null=True, blank=True)

#     cotee_moyenne_satisfaction_t2 =models.IntegerField(null=True, blank=True)

#     changement_rendement = models.IntegerField(null=True, blank=True)

#     changement_satisfaction = models.IntegerField(null=True, blank=True)


#     Evaluation = models.CharField()
#     reevaluation = models.CharField()

# class Mcrco_table(models.Model):
#     difficulte = models.CharField(max_length=100)
#     importance = models.IntegerField(null=True, blank=True)

#     rendement_t1 = models.IntegerField(null=True, blank=True)

#     satisfaction_t1 = models.IntegerField(null=True, blank=True)

#     rendement_t2 = models.IntegerField(null=True, blank=True)

#     satisfaction_t2 = models.IntegerField(null=True, blank=True)



# class PRWE(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)
    
#     nom = models.CharField(max_length=100)
#     date = models.DateField()
#     signature = models.CharField(max_length=100)

#     score_douleur_repos = models.IntegerField(null=True, blank=True)

#     score_douleur_mouvement = models.IntegerField(null=True, blank=True)

#     score_douleur_s_o_l = models.IntegerField(null=True, blank=True)

#     score_douleur_comble = models.IntegerField(null=True, blank=True)

#     score_douleur_frequence = models.IntegerField(null=True, blank=True)


#     score_fonction_tounee_poignet = models.IntegerField(null=True, blank=True)

#     score_fonction_tcoupee_viande = models.IntegerField(null=True, blank=True)

#     score_fonction_boutonnee_chemise = models.IntegerField(null=True, blank=True)

#     score_fonction_soulever_chaise = models.IntegerField(null=True, blank=True)

#     score_fonction_utiliser_papier_toilette = models.IntegerField(null=True, blank=True)

    
#     score_activite_habituelle_soins_perso = models.IntegerField(null=True, blank=True)

#     score_activite_habituelle_tache_menagere = models.IntegerField(null=True, blank=True)

#     score_activite_habituelle_travail = models.IntegerField(null=True, blank=True)

#     score_activite_habituelle_loisir = models.IntegerField(null=True, blank=True)


#     score_douleur = models.IntegerField(null=True, blank=True)

#     score_fonction = models.IntegerField(null=True, blank=True)

#     score_total = models.IntegerField(null=True, blank=True)


# class Synthese(models.Model):
#     patient = models.OneToOneField(DossierPatient, on_delete=models.CASCADE)

#     observations = models.TextField()
#     impact = models.TextField()
#     objectifs = models.TextField()
#     plan = models.TextField()

#     signature = models.CharField(max_length=200)
#     date = models.DateField()
#     lieu = models.CharField(max_length=100)

# #
# from django.db import models
# from django.contrib.auth.models import User
# from Dashboard.models import PatientProfile  # Adapte selon ton projet

# class AnalyseIA(models.Model):
#     PRIORITE_CHOICES = [
#         ('critical', 'Critique'),
#         ('warning', 'Alerte'),
#         ('info', 'Information'),
#         ('success', 'Progression'),
#     ]
    
#     patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='analyses_ia')
#     date_generation = models.DateTimeField(auto_now_add=True)
#     priorite = models.CharField(max_length=20, choices=PRIORITE_CHOICES, default='info')
#     confiance = models.IntegerField(default=0, help_text="Pourcentage 0-100")
#     resume = models.TextField(blank=True)
#     programme_genere = models.TextField(blank=True)
#     est_valide = models.BooleanField(default=False)
    
#     # Champs pour les détails d'analyse
#     douleur_repos = models.IntegerField(default=0)
#     douleur_effort = models.IntegerField(default=0)
#     amplitude_mesuree = models.IntegerField(default=0)
#     amplitude_objectif = models.IntegerField(default=0)
    
#     class Meta:
#         ordering = ['-date_generation']
#         verbose_name = "Analyse IA"
#         verbose_name_plural = "Analyses IA"
    
#     def __str__(self):
#         return f"Analyse {self.patient.user.nom} - {self.date_generation.strftime('%d/%m/%Y')}"
    
#     @property
#     def priorite_label(self):
#         return dict(self.PRIORITE_CHOICES).get(self.priorite, '')
    
#     @property
#     def couleur(self):
#         couleurs = {
#             'critical': '#ef4444',
#             'warning': '#f59e0b',
#             'info': '#3b82f6',
#             'success': '#10b981',
#         }
#         return couleurs.get(self.priorite, '#6b7280')
    
#     @property
#     def initiales(self):
#         return f"{self.patient.user.nom[0]}{self.patient.user.prenom[0]}".upper()


# class HistoriqueAnalyseIA(models.Model):
#     analyse = models.ForeignKey(AnalyseIA, on_delete=models.CASCADE, related_name='historique')
#     exercice_nom = models.CharField(max_length=100)
#     date_analyse = models.DateTimeField(auto_now_add=True)
#     resultat_mesure = models.CharField(max_length=50)
#     objectif = models.CharField(max_length=50)
#     anomalies = models.TextField(blank=True)
    
#     class Meta:
#         ordering = ['-date_analyse']
    
#     def __str__(self):
#           return f"{self.exercice_nom} - {self.date_analyse.strftime('%d/%m/%Y')}"
