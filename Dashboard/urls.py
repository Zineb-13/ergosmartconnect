from . import views
from django.urls import path
from django.views.generic import TemplateView
from Dashboard.views import ergo_supprimer_demande
urlpatterns = [
    path('', views.index, name='index'),
    path("page_connexion/", views.page_connexion, name="page_connexion"),
    path('inscription/', views.inscr, name='inscription'),
    path('ergotherapeute/', views.ergotherapeute, name='ergotherapeute'),
    path('patient/', views.patient, name='patient'),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("contact/", views.contact_view, name="contact"),
    path("register/", views.register_patient, name="register"),

    path('patients/', views.patients, name='patients'),
    path('Dossiers/', views.Dossiers, name='Dossiers'),
    path('Programmes/', views.Programmes, name='Programmes'),
    path('IA/', views.IA, name='IA'),
    path('Agenda/', views.Agenda, name='Agenda'),
    path('Messages/', views.Messages, name='Messages'),
    path('Ressources/', views.Ressources, name='Ressources'),
    path('Historique/', views.Historique, name='Historique'),
    path("patient/<int:id>/", views.patient_detail, name="patient_detail"),

    # ===== ESPACE PATIENT =====
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('patient/programme/', views.patient_programme, name='patient_programme'),
    path('patient/progression/', views.patient_progression, name='patient_progression'),
    path('patient/rendezvous/', views.patient_rendezvous, name='patient_rendezvous'),
    path('patient/messages/', views.patient_messages, name='patient_messages'),
    path('patient/ressources/', views.patient_ressources, name='patient_ressources'),
    path('patient/parametres/', views.patient_parametres, name='patient_parametres'),
    path('patient/parametres/api/', views.patient_settings_api, name='patient_settings_api'),
    path('patient/parametres/password/', views.patient_change_password_api, name='patient_change_password_api'),
    path('patient/parametres/delete-account/', views.patient_delete_own_account_api, name='patient_delete_own_account_api'),
    path('patient/dashboard/evaluation/', views.api_patient_dashboard_evaluation, name='api_patient_dashboard_evaluation'),

    path('patient/modifier/<int:patient_id>/', views.modifier_patient, name='modifier_patient'),
    path('generer-pdf/', views.generer_pdf_natif, name='generer_pdf'),
    path('envoyer-message-patient/', views.envoyer_message_patient, name='envoyer_message_patient'),
    path('test-tracabilite/', TemplateView.as_view(template_name='test_tracabilite.html'), name='test_tracabilite'),

    # ===== IA =====
    path('ia/', views.page_ia, name='page_ia'),
    path('ia/generer/<int:patient_id>/', views.generer_analyse_ia, name='generer_analyse_ia'),
    path('ia/valider/<int:analyse_id>/', views.valider_analyse_ia, name='valider_analyse_ia'),

    # ===== PROGRAMMES =====
    path('api/exercice/ajouter-au-programme/', views.ajouter_exercice_au_programme_api, name='ajouter_exercice_au_programme_api'),

    # ===== MESSAGES / COMMUNICATION =====
    path("messages/", views.messages_page, name="messages_page"),
    path("api/patients/", views.all_patients, name="all_patients"),
    path("messages/conversations/", views.messages_conversations, name="messages_conversations"),
    path("messages/get/<int:patient_id>/", views.messages_get, name="messages_get"),
    path("messages/send/", views.messages_send, name="messages_send"),
    path("messages/unread/", views.messages_unread, name="messages_unread"),
    path("messages/notifications/", views.messages_notifications, name="messages_notifications"),
    path("messages/update-last-seen/", views.update_last_seen, name="update_last_seen"),
    path("messages/new/", views.new_message, name="new_message"),
    path("messages/<int:patient_id>/", views.conversation, name="conversation"),

    # suppression conversation complète
    path("messages/delete/<int:patient_id>/", views.messages_delete, name="messages_delete"),

    # actions sur un seul message
    path("messages/message/<int:message_id>/delete/", views.delete_single_message, name="delete_single_message"),
    path("messages/message/<int:message_id>/edit/", views.edit_single_message, name="edit_single_message"),
    path("messages/message/<int:message_id>/pin/", views.toggle_pin_message, name='toggle_pin_message'),

    # ===== AGENDA =====
    path('Agenda/api/rdvs/', views.agenda_rdv_list, name='agenda_rdv_list'),
    path('Agenda/api/rdvs/create/', views.agenda_rdv_create, name='agenda_rdv_create'),
    path('Agenda/api/rdvs/<int:rdv_id>/update/', views.agenda_rdv_update, name='agenda_rdv_update'),
    path('Agenda/api/rdvs/<int:rdv_id>/cancel/', views.agenda_rdv_cancel, name='agenda_rdv_cancel'),
    path('Agenda/api/rdvs/<int:rdv_id>/delete/', views.agenda_rdv_delete, name='agenda_rdv_delete'),
    path('Agenda/api/rdvs/<int:rdv_id>/notify/', views.agenda_rdv_notify, name='agenda_rdv_notify'),

    # ===== RESSOURCES =====
    path('ressources/partager/', views.partager_ressource_patient, name='partager_ressource_patient'),
    path('ressources/vue/<int:partage_id>/', views.marquer_ressource_vue, name='marquer_ressource_vue'),
    path('ressources/telecharger/<int:partage_id>/', views.marquer_ressource_telechargee, name='marquer_ressource_telechargee'),
    path('ressources/terminer/<int:partage_id>/', views.marquer_ressource_terminee, name='marquer_ressource_terminee'),
    path('ressources/ajouter/', views.ajouter_ressource, name='ajouter_ressource'),
    path('ressources/modifier/<int:ressource_id>/', views.modifier_ressource, name='modifier_ressource'),
    path('ressources/supprimer/<int:ressource_id>/', views.supprimer_ressource, name='supprimer_ressource'),
    path('ressources/download/<int:ressource_id>/', views.tracer_telechargement_ressource, name='tracer_telechargement_ressource'),
    path('api/question-jour/envoyer/', views.api_envoyer_question_jour, name='api_envoyer_question_jour'),

    # ===== HISTORIQUE =====
    path('api/historique/events/', views.api_historique_events, name='api_historique_events'),
    path('api/historique/trace-patient/', views.api_tracer_activite_patient, name='api_tracer_activite_patient'),
    path('api/historique/delete/<int:event_id>/', views.api_delete_historique_event, name='api_delete_historique_event'),

    # ===== PATIENT =====
    path('supprimer-patient/<int:patient_id>/', views.supprimer_patient, name='supprimer_patient'),
    path('patient/messages/send/', views.patient_send_message, name='patient_send_message'),
    path('patient/messages/notifications/', views.patient_messages_notifications, name='patient_messages_notifications'),
    path('patient/messages/notification/read/<int:message_id>/', views.patient_read_notification, name='patient_read_notification'),
    path('patient/messages/notification/action/read/<int:action_id>/', views.patient_read_action_notification, name='patient_read_action_notification'),
    path('patient/messages/notifications/read-all/', views.patient_read_all_notifications, name='patient_read_all_notifications'),
    path('patient/messages/notification/delete/', views.patient_delete_notification, name='patient_delete_notification'),
    path('patient/messages/notifications/delete-all/', views.patient_delete_all_notifications, name='patient_delete_all_notifications'),
    path("patient/messages/api/", views.patient_messages_api, name="patient_messages_api"),

    # ===== CONTACT =====
    path("messages/contact/<int:message_id>/supprimer/", views.supprimer_message_contact, name="supprimer_message_contact"),
    path("messages/contact/<int:message_id>/traiter/", views.traiter_message_contact, name="traiter_message_contact"),
    path("messages/contact/<int:message_id>/archiver/", views.archiver_message_contact, name="archiver_message_contact"),
    path("messages/contact/<int:message_id>/desarchiver/", views.desarchiver_message_contact, name="desarchiver_message_contact"),
    path("messages/contact/<int:message_id>/export-txt/", views.exporter_message_contact_txt, name="exporter_message_contact_txt"),
    path('messages/api/', views.get_latest_messages, name='api_messages'),
    path('messages-view/', views.messages_view, name='messages_view'),
    path('ressources/vision-ergo/<int:ressource_id>/', views.tracer_vision_ressource_ergo, name='tracer_vision_ressource_ergo'),
    # Demandes de rendez-vous
    path('api/demande-rendezvous/', views.patient_demande_rendezvous, name='patient_demande_rendezvous'),
    path('api/ergo-demandes/', views.ergo_demandes_rendezvous, name='ergo_demandes_rendezvous'),
    path('api/ergo-repondre-demande/<int:demande_id>/', views.ergo_repondre_demande, name='ergo_repondre_demande'),

    # Signalements
    path('api/signalement-rendezvous/', views.patient_signalement_rendezvous, name='patient_signalement_rendezvous'),
    path('api/ergo-signalements/', views.ergo_signalements, name='ergo_signalements'),
    path('api/ergo-signalement-traiter/<int:signalement_id>/', views.ergo_signalement_traiter, name='ergo_signalement_traiter'),    
    # Réponses patients
    path('api/patient-repondre-rendezvous/<int:rdv_id>/', views.patient_repondre_rendezvous, name='patient_repondre_rendezvous'),
    path('api/ergo-reponses-rendezvous/', views.ergo_reponses_rendezvous, name='ergo_reponses_rendezvous'),
    path('api/ergo-reponse-lue/<int:reponse_id>/', views.ergo_reponse_lue, name='ergo_reponse_lue'),
    path('api/ergo-repondre-patient/', views.ergo_repondre_patient, name='ergo_repondre_patient'),
    path('api/patient-messages-ergo/', views.patient_messages_ergo, name='patient_messages_ergo'),
    path('api/patient-message-lu/<int:message_id>/', views.patient_message_lu, name='patient_message_lu'),
    path('api/patient-repondre-ergo/', views.patient_repondre_ergo, name='patient_repondre_ergo'),
    # Gestion des messages
    path('api/message/supprimer/<int:message_id>/', views.supprimer_message, name='supprimer_message'),
    path('api/message/modifier/<int:message_id>/', views.modifier_message, name='modifier_message'),
    # ===== MESSAGES ERGO VERS PATIENT =====
    path('api/ergo-messages-patients/', views.ergo_messages_patients, name='ergo_messages_patients'),
    path('api/ergo-message-patient-lu/<int:message_id>/', views.ergo_message_patient_lu, name='ergo_message_patient_lu'),
    path('api/ergo-repondre-message-patient/', views.ergo_repondre_message_patient, name='ergo_repondre_message_patient'),
    path('api/ergo-supprimer-demande/<int:demande_id>/', ergo_supprimer_demande, name='ergo_supprimer_demande'),
    path('api/ergo-supprimer-reponse/<int:reponse_id>/', views.ergo_supprimer_reponse, name='ergo_supprimer_reponse'),
    path('api/programmes/resultat/', views.api_programmes_resultat, name='api_programmes_resultat'),
    path('api/patient/resultat/modifier/<int:resultat_id>/', views.api_modifier_resultat_patient, name='api_modifier_resultat_patient'),
    path('api/patient/resultat/supprimer/<int:resultat_id>/', views.api_supprimer_resultat_patient, name='api_supprimer_resultat_patient'),
    path('api/ergo/resultat/commenter/<int:resultat_id>/', views.api_commenter_resultat_ergo, name='api_commenter_resultat_ergo'),
    # Dans ton fichier urls.py (dashboard ou principal)
    path('api/patient/marquer-termine/', views.marquer_patient_termine, name='marquer_patient_termine'),
    path('ajax/ajouter-exercice/', views.ajouter_exercice_bibliotheque_ajax, name='ajax_ajouter_exercice'),
    path('api/envoyer-programme-patient/', views.envoyer_programme_patient_api, name='envoyer_programme_patient'),
    path('api/envoyer-contenu-therapeutique/', views.api_envoyer_contenu_therapeutique, name='api_envoyer_contenu_therapeutique'),
    path('api/patient/messages/', views.api_patient_messages, name='api_patient_messages'),
    path('api/patient/message/lu/<int:message_id>/', views.api_patient_message_lu, name='api_patient_message_lu'),
    path('api/get-programme-patient/', views.api_get_programme_patient, name='api_get_programme_patient'),
    path('api/get-programme-session/', views.api_get_programme_session, name='api_get_programme_session'),
    path('api/get-programme-bdd/', views.api_get_programme_bdd, name='api_get_programme_bdd'),
    path('api/envoyer-un-exercice/', views.envoyer_un_exercice_api, name='envoyer_un_exercice'),
    path('envoyer-exercice/<int:exercice_id>/<int:patient_id>/', views.envoyer_exercice_direct, name='envoyer_exercice_direct'),
    path('supprimer-exercice-programme/', views.supprimer_exercice_programme, name='supprimer_exercice_programme'),
    path('api/get-resultats-patient/', views.api_get_resultats_patient, name='api_get_resultats_patient'),
    path('api/patient/resultats/', views.api_get_patient_resultats, name='api_get_patient_resultats'),
    path('api/ergo-notifications/', views.api_ergo_notifications, name='api_ergo_notifications'),
    path('api/ergo-clear-notification/', views.api_ergo_clear_notification, name='api_ergo_clear_notification'),
    # Bouton "📋 Générer le plan d'intervention"
    path('ergo/ai/generate-plan/', views.generate_plan_view, name='ai_generate_plan'),
    path('ergo/ai/analyze/', views.analyze_view, name='ai_analyze'),
    path('api/ia/analyse/<int:analyse_id>/action/', views.api_action_analyse_ia, name='api_action_analyse_ia'),

]







# from . import views
# from django.urls import path
# from django.views.generic import TemplateView

# urlpatterns = [
#     path('', views.index, name='index'),
#     path("page_connexion/", views.page_connexion, name="page_connexion"),
#     path('inscription/', views.inscr, name='inscription'),
#     path('ergotherapeute/', views.ergotherapeute, name='ergotherapeute'),
#     path('patient/', views.patient, name='patient'),
#     path("login/", views.login_view, name="login"),
#     path("logout/", views.logout_view, name="logout"),
#     path("contact/", views.contact_view, name="contact"),
#     path("messages/", views.messages_view, name="messages"),
#     path("register/", views.register_patient, name="register"),
#     path('patients/', views.patients, name='patients'),  # â† URL pour patients
#     path('Dossiers/', views.Dossiers, name='Dossiers'),  # â† URL pour Dossiers
#     path('Programmes/', views.Programmes, name='Programmes'),  # â† URL pour Programmes
#     path('IA/', views.IA, name='IA'),  # â† URL pour IA
#     path('Agenda/', views.Agenda, name='Agenda'),  # â† URL pour Agenda
#     path('Messages/', views.Messages, name='Messages'),  # â† URL pour Messages
#     path('Ressources/', views.Ressources, name='Ressources'),  # â† URL pour Ressources
#     path('Historique/', views.Historique, name='Historique'),  # â† URL pour Historique
#     path("patient/<int:id>/", views.patient_detail, name="patient_detail"), # pour chaque pateint accéder à son espace 


    
#     # ===== ESPACE PATIENT =====
#     path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
#     path('patient/programme/', views.patient_programme, name='patient_programme'),
#     path('patient/progression/', views.patient_progression, name='patient_progression'),
#     path('patient/rendezvous/', views.patient_rendezvous, name='patient_rendezvous'),
#     path('patient/messages/', views.patient_messages, name='patient_messages'),
#     path('patient/ressources/', views.patient_ressources, name='patient_ressources'),
#     path('patient/parametres/', views.patient_parametres, name='patient_parametres'),

# # nouvau
#     path('patient/modifier/<int:patient_id>/', views.modifier_patient, name='modifier_patient'),
#     path('generer-pdf/', views.generer_pdf_natif, name='generer_pdf'),
#     path('envoyer-message-patient/', views.envoyer_message_patient, name='envoyer_message_patient'),
#     path('test-tracabilite/', TemplateView.as_view(template_name='test_tracabilite.html'), name='test_tracabilite'),
#     path('ia/', views.page_ia, name='page_ia'),
#     path('ia/generer/<int:patient_id>/', views.generer_analyse_ia, name='generer_analyse_ia'),
#     path('ia/valider/<int:analyse_id>/', views.valider_analyse_ia, name='valider_analyse_ia'),
#     path('api/exercice/ajouter-au-programme/', views.ajouter_exercice_au_programme_api, name='ajouter_exercice_au_programme_api'),
        
#         # ===== MESSAGES / COMMUNICATION =====
#     path("messages/conversations/", views.messages_conversations, name="messages_conversations"),
#     path("messages/get/<int:patient_id>/", views.messages_get, name="messages_get"),
#     path("messages/send/", views.messages_send, name="messages_send"),
#     path("messages/unread/", views.messages_unread, name="messages_unread"),
#     path("messages/delete/<int:patient_id>/", views.messages_delete, name="messages_delete"),

#     path("api/patients/", views.all_patients, name="all_patients"),
#     path("messages/message/<int:message_id>/delete/", views.delete_single_message, name="delete_single_message"),
#     path("messages/message/<int:message_id>/edit/", views.edit_single_message, name="edit_single_message"),
#     path("messages/notifications/", views.messages_notifications, name="messages_notifications"),
#     path('Agenda/api/rdvs/', views.agenda_rdv_list, name='agenda_rdv_list'),
#     path('Agenda/api/rdvs/create/', views.agenda_rdv_create, name='agenda_rdv_create'),
#     path('Agenda/api/rdvs/<int:rdv_id>/update/', views.agenda_rdv_update, name='agenda_rdv_update'),
#     path('Agenda/api/rdvs/<int:rdv_id>/cancel/', views.agenda_rdv_cancel, name='agenda_rdv_cancel'),
#     path('Agenda/api/rdvs/<int:rdv_id>/delete/', views.agenda_rdv_delete, name='agenda_rdv_delete'),
#     path('Agenda/api/rdvs/<int:rdv_id>/notify/', views.agenda_rdv_notify, name='agenda_rdv_notify'),
#     path("messages/update-last-seen/", views.update_last_seen, name="update_last_seen"),
#     path('ressources/partager/', views.partager_ressource_patient, name='partager_ressource_patient'),
#     path('ressources/vue/<int:partage_id>/', views.marquer_ressource_vue, name='marquer_ressource_vue'),
#     path('ressources/telecharger/<int:partage_id>/', views.marquer_ressource_telechargee, name='marquer_ressource_telechargee'),
#     path('ressources/terminer/<int:partage_id>/', views.marquer_ressource_terminee, name='marquer_ressource_terminee'),
#     path('ressources/ajouter/', views.ajouter_ressource, name='ajouter_ressource'),
#     path('ressources/modifier/<int:ressource_id>/', views.modifier_ressource, name='modifier_ressource'),
#     path('ressources/supprimer/<int:ressource_id>/', views.supprimer_ressource, name='supprimer_ressource'),
#     path('api/historique/events/', views.api_historique_events, name='api_historique_events'),
#     path('ressources/download/<int:ressource_id>/', views.tracer_telechargement_ressource, name='tracer_telechargement_ressource'),
#     path('supprimer-patient/<int:patient_id>/', views.supprimer_patient, name='supprimer_patient'),    
#     path('patient/messages/send/', views.patient_send_message, name='patient_send_message'),
#     path('messages/message/<int:message_id>/pin/', views.toggle_pin_message, name='toggle_pin_message'),
#     path('messages/get-pinned/', views.get_pinned_message),
#     path('patient/messages/notifications/', views.patient_messages_notifications, name='patient_messages_notifications'),
#     path('patient/messages/notification/read/<int:message_id>/', views.patient_read_notification, name='patient_read_notification'),
# ]













# from . import views
# from django.urls import path
# from django.views.generic import TemplateView

# urlpatterns = [
#     path('', views.index, name='index'),
#     path("page_connexion/", views.page_connexion, name="page_connexion"),
#     path('inscription/', views.inscr, name='inscription'),
#     path('ergotherapeute/', views.ergotherapeute, name='ergotherapeute'),
#     path('patient/', views.patient, name='patient'),
#     path("login/", views.login_view, name="login"),
#     path("logout/", views.logout_view, name="logout"),
#     path("contact/", views.contact_view, name="contact"),
#     path("messages/", views.messages_view, name="messages"),
#     path("register/", views.register_patient, name="register"),
#     path('patients/', views.patients, name='patients'),  # â† URL pour patients
#     path('Dossiers/', views.Dossiers, name='Dossiers'),  # â† URL pour Dossiers
#     path('Programmes/', views.Programmes, name='Programmes'),  # â† URL pour Programmes
#     path('IA/', views.IA, name='IA'),  # â† URL pour IA
#     path('Agenda/', views.Agenda, name='Agenda'),  # â† URL pour Agenda
#     path('Messages/', views.Messages, name='Messages'),  # â† URL pour Messages
#     path('Ressources/', views.Ressources, name='Ressources'),  # â† URL pour Ressources
#     path('Historique/', views.Historique, name='Historique'),  # â† URL pour Historique
#     path("patient/<int:id>/", views.patient_detail, name="patient_detail"), # pour chaque pateint accéder à son espace 


    
#     # ===== ESPACE PATIENT =====
#     path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
#     path('patient/programme/', views.patient_programme, name='patient_programme'),
#     path('patient/progression/', views.patient_progression, name='patient_progression'),
#     path('patient/rendezvous/', views.patient_rendezvous, name='patient_rendezvous'),
#     path('patient/messages/', views.patient_messages, name='patient_messages'),
#     path('patient/ressources/', views.patient_ressources, name='patient_ressources'),
#     path('patient/parametres/', views.patient_parametres, name='patient_parametres'),

# # nouvau
#     path('patient/modifier/<int:patient_id>/', views.modifier_patient, name='modifier_patient'),
#     path('generer-pdf/', views.generer_pdf_natif, name='generer_pdf'),
#     path('envoyer-message-patient/', views.envoyer_message_patient, name='envoyer_message_patient'),
#     path('test-tracabilite/', TemplateView.as_view(template_name='test_tracabilite.html'), name='test_tracabilite'),
#     path('ia/', views.page_ia, name='page_ia'),
#     path('ia/generer/<int:patient_id>/', views.generer_analyse_ia, name='generer_analyse_ia'),
#     path('ia/valider/<int:analyse_id>/', views.valider_analyse_ia, name='valider_analyse_ia'),
#     path('api/exercice/ajouter-au-programme/', views.ajouter_exercice_au_programme_api, name='ajouter_exercice_au_programme_api'),
        
#         # ===== MESSAGES / COMMUNICATION =====
#     path("messages/", views.messages_page, name="messages_page"),
#     path("messages/conversations/", views.messages_conversations, name="messages_conversations"),
#     path("messages/get/<int:patient_id>/", views.messages_get, name="messages_get"),
#     path("messages/send/", views.messages_send, name="messages_send"),
#     path("messages/unread/", views.messages_unread, name="messages_unread"),
#     path("messages/delete/<int:patient_id>/", views.messages_delete, name="messages_delete"),

#     path("api/patients/", views.all_patients, name="all_patients"),
#     path("messages/new/", views.new_message, name="new_message"),
#     path("messages/<int:patient_id>/", views.conversation, name="conversation"),
#     path("messages/send/<int:patient_id>/", views.send_message, name="send_message"),
#     path("messages/message/<int:message_id>/delete/", views.delete_single_message, name="delete_single_message"),
#     path("messages/message/<int:message_id>/edit/", views.edit_single_message, name="edit_single_message"),
#     path("messages/notifications/", views.messages_notifications, name="messages_notifications"),
#     path('Agenda/api/rdvs/', views.agenda_rdv_list, name='agenda_rdv_list'),
#     path('Agenda/api/rdvs/create/', views.agenda_rdv_create, name='agenda_rdv_create'),
#     path('Agenda/api/rdvs/<int:rdv_id>/update/', views.agenda_rdv_update, name='agenda_rdv_update'),
#     path('Agenda/api/rdvs/<int:rdv_id>/cancel/', views.agenda_rdv_cancel, name='agenda_rdv_cancel'),
#     path('Agenda/api/rdvs/<int:rdv_id>/delete/', views.agenda_rdv_delete, name='agenda_rdv_delete'),
#     path('Agenda/api/rdvs/<int:rdv_id>/notify/', views.agenda_rdv_notify, name='agenda_rdv_notify'),
#     path("messages/update-last-seen/", views.update_last_seen, name="update_last_seen"),
#     path('ressources/partager/', views.partager_ressource_patient, name='partager_ressource_patient'),
#     path('ressources/vue/<int:partage_id>/', views.marquer_ressource_vue, name='marquer_ressource_vue'),
#     path('ressources/telecharger/<int:partage_id>/', views.marquer_ressource_telechargee, name='marquer_ressource_telechargee'),
#     path('ressources/terminer/<int:partage_id>/', views.marquer_ressource_terminee, name='marquer_ressource_terminee'),
#     path('ressources/ajouter/', views.ajouter_ressource, name='ajouter_ressource'),
#     path('ressources/modifier/<int:ressource_id>/', views.modifier_ressource, name='modifier_ressource'),
#     path('ressources/supprimer/<int:ressource_id>/', views.supprimer_ressource, name='supprimer_ressource'),
#     path('api/historique/events/', views.api_historique_events, name='api_historique_events'),
#     path('ressources/download/<int:ressource_id>/', views.tracer_telechargement_ressource, name='tracer_telechargement_ressource'),
#     path('supprimer-patient/<int:patient_id>/', views.supprimer_patient, name='supprimer_patient'),    
#     path('patient/messages/send/', views.patient_send_message, name='patient_send_message'),
#     path('messages/get/<int:patient_id>/', views.get_messages),
#     path('api/patients/', views.get_patients),
#     path('messages/message/<int:message_id>/pin/', views.toggle_pin_message, name='toggle_pin_message'),
#     path('messages/get-pinned/', views.get_pinned_message),
#     path('patient/messages/notifications/', views.patient_messages_notifications, name='patient_messages_notifications'),
#     path('patient/messages/notification/read/<int:message_id>/', views.patient_read_notification, name='patient_read_notification'),
# ]

