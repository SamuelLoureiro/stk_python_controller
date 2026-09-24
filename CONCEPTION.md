# CONCEPTION — analyse de l'idée et propositions

Inspiration : **BOMBANANA!** (Lefto Studio, sorti le 2 septembre 2026 sur
Steam). Trois joueurs désamorcent une bombe, et chacun n'a qu'une partie de
l'information : l'un agit sans voir, un autre voit sans entendre, le dernier
sait sans pouvoir parler. Aucun ne peut résoudre seul.
Sources : [Steam](https://store.steampowered.com/app/4656000/BOMBANANA/) ·
[site officiel](https://bombanana.leftostudio.com/) ·
[guide des rôles](https://bombanana.tips/).

Notre version : l'**aveugle** braque en faisant pivoter sa chaise, dos à l'écran ;
le **muet** voit l'écran et le guide par gestes ; le **sourd**, casque sur les
oreilles, tient la vitesse et les objets.

---

## En bref

| | |
|---|---|
| **Ce qui est fort** | Pilotage par tout le corps ; interdépendance réelle ; quatre modalités (corps, geste humain, voix, objet tangible) ; toute la chaîne analogique existe déjà ; spectaculaire en démo ; facile à évaluer |
| **Le risque n° 1** | La **latence** : une consigne qui passe par deux personnes arrive trop tard pour une course |
| **Le piège n° 1** | Le **miroir** : face à face, la droite de l'un est la gauche de l'autre |
| **Le point faible** | Le sourd voit l'écran et agit seul : de son côté, il n'y a pas d'interdépendance |
| **Ce qui est codé** | Chaise (MultiSense + ZIG SIM), direction analogique, demi-tour, flux coupé, boîtier Arduino, voix, journal pour l'évaluation, mode solo |

Pour chaque point ci-dessous : le problème concret, la proposition, **comment le
faire exactement**, et où on en est.

---

## §1. Le capteur : la chaise tourne autour de la verticale

**Le problème.** L'angle de volant du TP1 mesure la gravité dans le plan de
l'écran. Une chaise qui pivote ne change rien à la gravité : cet angle reste
figé, quoi que fasse l'aveugle.

**La proposition.** Mesurer un cap. Deux méthodes :

| Méthode | Principe | Pour | Contre |
|---|---|---|---|
| `cap` | ZIG SIM : rotation relative `q·q0⁻¹` autour de la verticale. MultiSense : `orientation/yaw` | ne dérive pas | si le téléphone cale son cap sur la boussole, **l'acier du vérin** peut le fausser |
| `gyro` | vitesse de rotation intégrée, biais retiré à la calibration | insensible à l'acier | dérive lentement |

**Comment.** C'est déjà codé dans `chaise.py`. Le calcul est exact quel que soit
le montage du téléphone : écran dessus, dessous ou incliné. Point important : il
faut la rotation **relative**. Sur le quaternion absolu, un téléphone écran vers
le bas n'a plus de cap défini (`z = w = 0`), et `faux_chaise.py --verifier` le
montre. **C'est la mesure qui tranche entre les deux** : `python chaise.py`
affiche les deux côte à côte (protocole dans le README).

**État :** codé et vérifié en simulation. Reste la mesure sur la vraie chaise.

---

## §2. La latence du relais humain

**Le problème.** Piloter, c'est une boucle : je vois, je corrige, je vois le
résultat. Au-delà d'environ 100 ms de retard, la gêne se sent (fiche de veille :
la douche qui réagit trop tard, on oscille entre trop chaud et trop froid). Or
une personne qui perçoit un geste et agit en retour met plusieurs centaines de
millisecondes. Ce sont des ordres de grandeur, pas des mesures :

| Trajet de la consigne | Relais humains | Retard approximatif |
|---|---|---|
| muet → aveugle | 1 | 0,3 à 0,6 s |
| muet → sourd → aveugle (la chaîne de Bombanana) | 2 | 0,7 à 1,2 s |

Avec la chaîne, le kart zigzague : chaque correction arrive quand elle n'est plus
la bonne. Bombanana supporte ce délai parce que désamorcer une bombe est un
puzzle ; une course, non.

**La proposition.** Séparer les deux types de signaux (fiche de veille : continu
contre discret) :

- la **direction**, continue et urgente, va **directement** du muet à l'aveugle ;
- les **objets**, discrets et tolérants au délai, peuvent passer par le sourd.

**Comment.**
- Choisir des pistes **larges** et le niveau **novice** pour les premières parties.
- Le muet apprend à **anticiper** : il montre le virage avant qu'il n'arrive.
  C'est une compétence qui s'acquiert, et c'est ce qui rend le jeu intéressant.
- Ne pas ajouter de lissage logiciel : l'inertie de la chaise lisse déjà, et
  chaque lissage ajoute du retard.
- Mesurer : le journal CSV (`--journal`) permet de compter les **inversions de
  braquage par minute**. C'est l'indicateur direct de l'oscillation.

**État :** à tester à trois. L'indicateur est déjà enregistré.

---

## §3. Le miroir (compatibilité stimulus-réponse)

**Le problème.** Le muet et l'aveugle se font face. Quand le muet montre « à
droite » (la droite de l'écran, qui est sa droite), il montre la **gauche** de
l'aveugle. L'un des deux doit inverser de tête, en pleine course, et c'est une
source d'erreurs bien connue en ergonomie. C'est le problème du professeur de
gym qui fait face à sa classe et qui fait les mouvements en miroir pour que les
élèves n'aient rien à inverser.

**La proposition : suivre le repère.** Le muet tient un objet repère (voyant, en
mousse) à hauteur de visage et le déplace. L'aveugle **tourne pour lui faire
face**, rien de plus. Ainsi :

- le muet pense en coordonnées de l'écran : virage à droite, repère vers sa
  droite ;
- l'aveugle n'a aucune notion de gauche ou de droite à manipuler : il suit ;
- l'amplitude est naturelle : un petit décalage du repère donne un petit
  braquage.

Tourner pour faire face à un repère placé à la droite du muet revient, pour
l'aveugle, à tourner vers **sa gauche**. D'où la correspondance par défaut
`CORRESPONDANCE = 'miroir'` : l'aveugle tourne à sa gauche, le kart tourne à
droite.

**Comment.** C'est déjà codé. L'autre correspondance, `'egocentrique'`, reste
disponible (`--correspondance egocentrique`) : c'est la bonne si la consigne
arrive par la voix (« droite ! ») plutôt que par un repère. Le **signe du
capteur** (qui se mesure) et le **sens du jeu** (qui est un choix de conception)
sont deux réglages séparés. C'est la leçon du volet collaboratif précédent, où
l'on avait tourné la mauvaise vis.

**État :** codé. **À tester à trois**, et c'est un excellent **test A/B** pour
l'évaluation (§8).

---

## §4. L'aveugle voit le muet

**Le constat.** Dos à l'écran mais les yeux ouverts, l'aveugle est aveugle **au
jeu**, pas au monde. C'est ce qui rend la solution du §3 possible.

**Variante plus difficile : les yeux bandés.** Il faut alors un autre canal du
muet vers l'aveugle :

| Canal | Idée | Risque |
|---|---|---|
| toucher | le muet pousse l'épaule | **il conduit à la place de l'aveugle** : à exclure |
| son non verbal | claquements de doigts, sifflet, deux « clickers » (un grave pour gauche, un aigu pour droite) | lent, uniquement du tout-ou-rien |

**Règle à afficher dans tous les cas : le muet ne touche jamais la chaise.**

---

## §5. Le sourd est autonome

**Le problème.** Le sourd voit l'écran et agit seul sur la vitesse et les objets.
Personne ne lui apporte d'information : sa surdité n'est qu'un décor. C'est
l'endroit où l'idée est la plus faible.

**La proposition : des niveaux de difficulté physiques**, avec le même code.

| Niveau | Qui voit l'écran | Effet |
|---|---|---|
| **Facile** | le muet et le sourd | le sourd gère seul la vitesse et les objets ; seul le binôme muet-aveugle doit se coordonner |
| **Difficile** | **le muet seul** : le sourd est lui aussi dos à l'écran, face au muet | le muet devient le seul œil de l'équipe : une main guide l'aveugle, l'autre fait signe au sourd. Tout passe par lui, c'est exactement le goulot d'étranglement de Bombanana |

En difficile, la surdité compte vraiment : l'aveugle, qui peut parler, ne peut
pas s'arranger à voix haute avec le sourd (« accélère, je suis en ligne
droite ! »). Toute la coordination passe par les gestes du muet.

**Comment.** Il suffit de déplacer une chaise. Le vocabulaire gestuel du §7 sert
au niveau difficile.

---

## §6. Les règles tenues par le système

Une contrainte que seul l'honneur des joueurs fait respecter finit par être
contournée. Mieux vaut qu'elle soit dans le système.

| Règle | Ce que fait le système | État |
|---|---|---|
| l'aveugle ne regarde pas l'écran | au-delà de 100° de rotation, **le kart lâche les gaz** jusqu'à son retour | codé |
| la direction ne reste jamais bloquée | flux du téléphone coupé pendant 0,5 s → direction au centre | codé |
| l'accélérateur ne reste jamais bloqué | boîtier muet pendant 0,5 s → tout est relâché | codé |
| un sauvetage n'est jamais accidentel | « help » doit être dit **deux fois** en 1,5 s. Mesuré le 2026-09-24 : en solo, des sauvetages partaient tout seuls, parce qu'avec quatre mots possibles la reconnaissance vocale ramène la musique du jeu et les paroles en français vers « help ». C'est le problème du « Midas touch » de la fiche de veille, réglé par une confirmation, réservée aux actions coûteuses | codé |
| le muet ne parle pas | *option* : un **arbitre caméra** (un suivi de visage détecte la bouche ouverte) qui fait freiner le kart | proposé, non codé ; incompatible avec un masque sur la bouche |

---

## §7. Les interacteurs

### Le masque du muet (ta question)

**Oui, mais seulement sur la bouche** : bandana, masque chirurgical ou foulard.

- Il empêche d'**articuler en silence**, la triche la plus naturelle (l'aveugle
  lirait sur les lèvres).
- Il laisse libres les **sourcils et le regard**, un canal très riche : un
  froncement dit « trop ! », des yeux écarquillés disent « attention ».
- Il rend le rôle lisible pour le public.
- Un **masque intégral** retire aussi les expressions du visage : c'est un bon
  **niveau difficile**, pas un réglage par défaut.

### Tous les objets proposés

| Pour qui | Objet | À quoi il sert | Coût |
|---|---|---|---|
| muet | **objet repère** voyant, en mousse | la cible que suit l'aveugle (§3) | nul |
| muet | masque sur la bouche | voir plus haut | nul |
| aveugle | **élastique de rappel** entre le pied étoile et l'assise | l'aveugle **sent** le neutre et l'amplitude, comme un volant qui revient au centre. C'est le seul retour sensoriel qu'il peut avoir | 5 min |
| aveugle | **butées** (cartons, pieds de table) à environ ±60° | limitent la rotation, et donc la triche | 5 min |
| aveugle | **tapis** sous la chaise | les roulettes font glisser la chaise quand on pousse avec les pieds | nul |
| sourd | **casque-micro** (casque de jeu) | le rend sourd (bruit ou musique dedans) **et** son micro ne capte que sa voix : les cris de l'aveugle ne déclenchent pas de « fire » | à emprunter |
| sourd | **piézo** sur la table | taper pour lancer un objet : physique, drôle, immédiat | dans le kit |
| sourd | **pédale à ultrason** au sol | freiner avec le pied, les mains restent libres | dans le kit |
| tous | **antisèche** du vocabulaire gestuel, collée sur le boîtier | la mémoire de travail est limitée (cours sur les facteurs humains) : 5 signes au maximum | 5 min |
| public | bandanas de couleur, un par rôle | on comprend qui fait quoi sans explication | nul |

### Le vocabulaire gestuel du muet (proposition)

Cinq signes au plus, sinon on ne les retient pas en pleine course :

| Geste du muet | Pour | Veut dire |
|---|---|---|
| repère tenu à hauteur de visage, déplacé latéralement | aveugle | la direction (continu) |
| main à plat qui pousse vers l'avant | sourd | accélère |
| poing fermé | sourd | freine |
| index pointé vers l'avant | sourd | tire l'objet |
| moulinet de la main | sourd | turbo |
| deux mains en l'air | sourd | sauvetage |

---

## §8. Le reste du kit Arduino

| Capteur | Idée | Pour qui | Priorité |
|---|---|---|---|
| Touch, Piezo, Ultrasonic | le boîtier du sourd | sourd | **codé** (`boitier_sourd.ino`) |
| **IMU 6 axes + 2ᵉ Uno** | **plan B sous la chaise** : le gyroscope seul est insensible à l'acier, et il n'y a plus d'écran qui se verrouille | aveugle | à faire si le téléphone déçoit |
| **capteur cardiaque** (pince d'oreille) | mesure du stress de chaque rôle pendant les tests | évaluation | bonus fort pour le rapport |
| EMG | poing serré de l'aveugle = turbo : il a les mains libres | aveugle | bonus |
| Gesture (PAJ7620) | gestes de la main au-dessus du boîtier pour le sourd | sourd | bonus |
| Tilt switch | retourner un objet = sauvetage | sourd | bonus ; le protocole prévoit déjà un compteur `sauvetages` |

---

## §9. L'évaluation (objectifs de l'UE : tests utilisateurs, échelles, UX)

**Ce qui se compare** (chaque équipe joue toutes les conditions, dans un ordre
contrebalancé) :

| Variable | Conditions | Question posée |
|---|---|---|
| correspondance | miroir contre égocentrique | le repère à suivre évite-t-il vraiment les erreurs de sens ? |
| difficulté | facile contre difficile | le goulot d'étranglement par le muet rend-il le jeu plus collaboratif, ou juste plus dur ? |
| rôles | rotation d'une course à l'autre | quel rôle est le plus chargé ? |

**Ce qui se mesure.**

- **Objectif**, tiré de `--journal` :
  - temps de course ;
  - nombre de `RESCUE` ;
  - nombre et durée des demi-tours ;
  - **inversions de braquage par minute** (l'oscillation, §2) ;
  - part du temps à braquage saturé.
- **Subjectif** :
  - **SUS** pour l'utilisabilité ;
  - **GEQ, module présence sociale** (empathie, sentiments négatifs,
    implication comportementale), fait pour les jeux à plusieurs ;
  - **NASA-TLX** par rôle : on s'attend à ce que le muet soit le plus chargé ;
  - un court entretien.
- **Physiologique**, en option : le capteur cardiaque du kit.

Sessions chronométrées : `.\lancer.ps1 --journal equipe1_miroir.csv --duree 180`.

---

## §10. À décider demain, à trois

- [ ] Mesurer la chaise (README, « Tester seul », étape 1) : signes, `cap` ou `gyro`, `ANGLE_MAXI`.
- [ ] Miroir ou égocentrique : faire trois tours avec chacun.
- [ ] Facile ou difficile par défaut pour la démo.
- [ ] Qui fournit le casque-micro, le repère et le masque.
- [ ] Flasher le boîtier, régler `SEUIL_PIEZO` et `FREIN_CM`.
- [ ] Le muet a-t-il le droit aux sons non verbaux (claquements) ? À fixer avant la première partie.
- [ ] Demander à l'intervenante si l'iPhone est accepté (question toujours ouverte, voir `QUESTIONS-TP1.md`).
