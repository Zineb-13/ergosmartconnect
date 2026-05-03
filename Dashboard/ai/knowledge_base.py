# -*- coding: utf-8 -*-
"""
Base de connaissances ergothérapique pour la rééducation post-fracture du poignet.
Source : protocoles cliniques (IA.docx + lama.docx) fournis par l'ergothérapeute.

Ce fichier sert de référence à Llama pour générer des plans d'intervention
basés sur des règles cliniques validées (et non pas inventées par le modèle).
"""

KNOWLEDGE_BASE = """
# BASE DE CONNAISSANCES — RÉÉDUCATION ERGOTHÉRAPIQUE DU POIGNET POST-FRACTURE

## 1. GESTION DE LA DOULEUR (EVA 0-10)

### Condition A — Douleur intense (EVA ≥ 7/10)
Objectifs : ↓ douleur à ≤ 4/10, permettre mobilisation minimale.
Modalités : repos relatif, fractionnement des tâches, cryothérapie, mobilisation infra-douloureuse.

Exercices CABINET :
- Patient assis, avant-bras posé. L'ergo fléchit doucement le poignet sans dépasser 3/10 douleur — 5-6 mouvements lents.
- Ouvrir/fermer la main très lentement, uniquement dans l'indolore — 10 répétitions.

Exercices DOMICILE :
- Tremper la main dans eau froide (10-15°C) — 5-10 min, 2x/jour. Matériel : bassine, eau froide.
- Surélever l'avant-bras sur 2 coussins — 15 min, 3x/jour.
- Ouvrir/fermer la main lentement sans douleur — 10 rép, 2x/jour.
- Flexion/extension très légère du poignet (1-2 cm) — 10 rép.

### Condition B — Douleur modérée (EVA 4-6)
Exercices DOMICILE supplémentaires :
- Flexion active petite amplitude — 10 rép.
- Extension active petite amplitude — 10 rép.
- Tenir un verre en plastique vide — 5 sec × 5.
- Presser doucement une balle mousse — 10 pressions.

Progression : quand douleur → 3/10, augmenter amplitude puis ajouter résistance légère.

### Condition C — Douleur légère (EVA 0-3)
Passer aux protocoles de mobilité et de force.

---

## 2. ŒDÈME

Objectifs : ↓ volume, améliorer confort et mobilité.

Exercices CABINET :
- Drainage manuel centripète (de la main vers l'épaule) avec crème — 2-3 min.

Exercices DOMICILE :
- Surélévation : avant-bras sur 2 coussins — 15-20 min, 4x/jour.
- Trempage eau froide — 10 min.
- Ouvrir/fermer la main (pompage) — 20 rép.
- Flexion/extension des doigts (comme piano) — 20 rép.

Cotation œdème : 0/5 = œdème massif | 5/5 = pas d'œdème.

---

## 3. MOBILITÉ ARTICULAIRE

### 3.1 FLEXION POIGNET

#### Si flexion < 30° (très réduite)
CABINET : mobilisation passive (5-6 lents) ; flexion active assistée par main saine (10).
DOMICILE :
- Glisser la main sur serviette posée sur table, vers soi — 10 aller-retour, 2x/j.
- Main saine attrape les doigts et fléchit doucement — 10, maintien 5 sec.
- Tenir un verre vide et l'approcher — 5 répétitions.

Progression : passif → actif assisté → actif → avec objet léger.

#### Si flexion 30-50° (modérée)
- Flexion active lente — 15 rép.
- Flexion active avec maintien 5 sec en fin d'amplitude — 10 rép.
- Tenir un verre à mi-hauteur — 5 rép.

### 3.2 EXTENSION POIGNET

#### Si extension < 30°
- Extension active assistée (main saine pousse le dos de la main) — 10 rép.
- Glisser paume sur table pour amener la main vers l'avant — 10 rép.
- Maintenir extension 5 sec — 5-6 rép.
- Appui palmaire très léger sur table — 5 sec × 5.

### 3.3 PRONATION / SUPINATION

#### Si amplitude < 40°
- Avant-bras posé, tourner paume vers le haut/bas — 15 rép.
- Tenir un crayon ou cuillère, faire pivoter — 10 rotations.
- Visser/dévisser un bouchon de bouteille large — 5 + 5.
- Tourner une clé dans une serrure — 5 allers-retours.

---

## 4. FORCE MUSCULAIRE (Échelle MRC 0-5)

### MRC 2 à 2+ (mouvement sans/avec gravité minimale)
- Flexion/extension poignet, avant-bras posé — 10 rép.
- Pronation/supination, coude au corps — 10 rép.
- Ouvrir/fermer main avec balle mousse très souple — 15 rép.
- Tenir gobelet vide — 5 sec × 5.

Progression : quand 10 rép faciles → actif contre gravité (avant-bras non posé).

### MRC 3 à 4
- Presser balle mousse — 15 rép.
- Malaxer pâte à modeler (écraser, étirer) — 2-3 min.
- Tirer élastique (Theraband faible) — 10 rép.
- Porter gobelet avec 50 mL d'eau — 5 aller-retours.

---

## 5. PRÉHENSION

### 5.1 Prise cylindrique (verre, bouteille)
- Bouteille d'eau vide → 100 mL → pleine (250-500 mL) — 5 sec × 5 chacune.
- Transporter la bouteille sur 1 mètre — 3 allers-retours.

### 5.2 Prise sphérique (balle, fruit)
- Saisir balle de tennis (sans presser) — 5 sec × 5.
- Attraper orange/pomme — 5 rép.

### 5.3 Prise tridigitale (pouce-index-majeur)
- Tenir une cuillère — 10 sec × 5.
- Tenir un stylo — tracer 3 lignes.
- Pince à linge : ouvrir/fermer — 10 ouvertures.

### 5.4 Prise latérale (pouce contre côté index)
- Saisir une carte de crédit sur la table — 10 prises.
- Saisir une clé — 5 rép.

### 5.5 Manipulation
- Ouvrir/fermer un bouchon large — 5 + 5.
- Déplacer 5 pions d'un côté à l'autre — 5 allers-retours.

Cotation préhension : 0/5 = impossible | 5/5 = normale.

---

## 6. DEXTÉRITÉ

### 6.1 Enfilage
- Enfiler 5 grosses perles (1-2 cm) sur lacet — 3 essais.
- Enfiler 5 perles petites (0,5 cm) — 3 essais.

### 6.2 Manipuler des pièces
- Retourner pièce entre pouce et index — 10 retournements.
- Empiler 5 pièces — 5 fois.

### 6.3 Boutonner / déboutonner
- Boutonner 3 boutons moyens (planche/chemise) — 5 cycles.
- Déboutonner — 5 cycles.

### 6.4 Écrire
- Tracer lignes horizontales/verticales — 2 min.
- Écrire son prénom — 3 fois.
- Écrire phrase courte — 1 phrase.

### 6.5 Pincer pâte à modeler
- Pincer petit pois de pâte — 10 pincées.
- Faire petite boule — 5 boules.

---

## 7. ENDURANCE

- Presser balle en rythme (1 pression/sec) — 10 rép, +5 par semaine.
- Tenir verre rempli sans poser — 5 sec, +5 sec toutes les 3 séances.
- Essuyer table avec chiffon — 1 min, +1 min/semaine.
- Écrire sans pause — 2 min, +1 min/semaine.

Cotation : 0/5 = fatigue en < 30 sec | 5/5 = effort 5 min sans fatigue.

---

## 8. SENSIBILITÉ

- Frotter doucement coton sur paume/doigts — 30 sec.
- Toucher successivement coton, éponge, papier — 2-3 min.
- Idem yeux fermés, deviner texture — 2-3 min.
- Massage doux avec crème hydratante — 2 min.
- Bains alternés : eau froide (15°C) 1 min / chaude (40°C) 1 min — 5 cycles.

---

## 9. AVQ (Activités de la Vie Quotidienne)

### Alimentation
- Tenir verre vide → avec 50 mL → porter à la bouche.
- Tenir cuillère, porter à la bouche.
- Piquer aliment mou avec fourchette.

### Toilette
- Tenir brosse à dents, simuler brossage — 30 sec.
- Se laver le visage avec éponge — 1 min.
- S'essuyer avec serviette — 30 sec.

### Habillage
- Boutonner 3 boutons sur chemise (sur soi) — 5 cycles.
- Fermer fermeture éclair — 5 fois.
- Enfiler veste à manches larges (côté atteint d'abord) — 3 fois.

### Cuisine
- Couper pâte à modeler avec couteau émoussé — 5 coupes.
- Ouvrir bocal (ouvre-bocal si besoin) — 2 essais.
- Mélanger préparation avec cuillère en bois — 1 min.

---

## 10. COORDINATION BIMANUELLE

- Tenir feuille d'une main, plier avec l'autre — 5 pliages.
- Ouvrir bocal (1 main stabilise, l'autre tourne) — 3 essais.
- Verser eau d'une carafe dans un verre — 3 fois.
- Rouler boule de pâte à modeler à 2 mains — 5 boules.
- Essuyer table avec chiffon (2 mains en appui) — 1 min.

---

## 11. PROGRAMME DOMICILE TYPE (1 page patient)

À faire 1 à 2 fois par jour, 15-20 minutes :

1. Eau froide (anti-douleur/œdème) — 5-10 min.
2. Glisser main sur serviette (flexion/extension) — 10 aller-retour.
3. Presser la balle mousse — 15 pressions.
4. Tenir la cuillère (prise tridigitale) — 5 × 5 sec.
5. Enfiler 5 perles — 3 essais.
6. Toucher coton/éponge — 1 min.
7. Boutonner 2 boutons — 5 cycles.

Consigne douleur : ne pas dépasser 4/10. Si > 4, réduire répétitions.

---

## 12. PRINCIPES ERGOTHÉRAPIQUES GLOBAUX

OBJECTIFS COURT TERME : diminuer la douleur, réduire l'œdème, initier la mobilité.
OBJECTIFS MOYEN TERME : améliorer mobilité articulaire, force, préhension, dextérité.
OBJECTIFS LONG TERME : reprise des AVQ, reprise du travail, qualité de vie.

RÔLE DE L'ERGOTHÉRAPEUTE :
- Analyser les occupations significatives (MCRO).
- Adapter les exercices au niveau du patient.
- Surveiller la douleur et la fatigue.
- Éviter les compensations.
- Rendre l'activité significative pour le patient.
- Assurer la progression : passif → actif assisté → actif → avec résistance.

PRWE (Patient-Rated Wrist Evaluation) :
- Score < 30/110 : atteinte légère.
- Score 30-60/110 : atteinte modérée.
- Score > 60/110 : atteinte sévère.
"""


def get_knowledge_base() -> str:
    """Retourne la base de connaissances complète."""
    return KNOWLEDGE_BASE