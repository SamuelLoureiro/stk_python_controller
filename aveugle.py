#!/usr/bin/env python3
"""L'aveugle : dos a l'ecran, il braque le kart en faisant pivoter sa chaise.

    angle de la chaise  ->  zone morte + courbe  ->  STEER:<-1..+1>  ->  manette virtuelle

Par defaut la direction est ANALOGIQUE : elle part vers
serveur.py, qui la donne a l'axe d'une manette Xbox virtuelle.
La chaise tourne continument, le kart aussi. Avec DIRECTION = 'fleches'
(option --fleches de trio.py), la meme consigne bat la fleche en rythme :
c'est le repli si le jeu ignore la manette.

Deux securites, parce que l'aveugle ne voit pas l'ecran et ne peut donc pas
s'apercevoir que quelque chose cloche :

  - FLUX COUPE : plus de message du telephone depuis SILENCE_MAX (ecran
    verrouille, appli fermee, Wi-Fi). Direction au centre, sinon le kart
    garderait le dernier braquage recu jusqu'au mur.
  - DEMI-TOUR : l'aveugle pivote au-dela de ANGLE_DEMI_TOUR, il est en train
    de se retourner pour regarder l'ecran. Direction au centre ET le kart
    lache les gaz : cette source demande 'accelerate' et 'brake' en meme
    temps, et SortieSTK annule les paires opposees (OPPOSEES). La regle du
    jeu est tenue par le systeme, pas seulement par l'honneur des joueurs.
"""

import config_trio as cfg
from modulation import ToucheModulee, intensite_depuis_angle

NOM = 'aveugle'
NOM_TRICHE = 'demi-tour'


def consigne_depuis_angle(angle, plancher=0.0):
    """Angle de la chaise (> 0 = l'aveugle tourne a SA droite) -> STEER -1..+1."""
    amplitude = intensite_depuis_angle(angle, cfg.ANGLE_MINI, cfg.ANGLE_MAXI, cfg.COURBE,
                                       plancher)
    if amplitude == 0.0:
        return 0.0          # et pas -0.0, qui s'afficherait STEER:-0.000
    vers_sa_droite = amplitude if angle > 0 else -amplitude
    # En miroir, l'aveugle qui tourne vers sa droite fait partir le kart a
    # gauche : c'est la gauche de l'ecran, vue par le muet qui lui fait face.
    return -vers_sa_droite if cfg.CORRESPONDANCE == 'miroir' else vers_sa_droite


class Aveugle:
    """Traduit l'etat de la chaise en consigne de direction pour SortieSTK."""

    def __init__(self, sortie, capteur):
        self.sortie = sortie
        self.capteur = capteur
        self.angle = None
        self.consigne = 0.0
        self.demi_tour = False
        self.flux_coupe = False
        self._modulee = ToucheModulee()
        # En fleches, la plage demarre a la plus petite intensite que la
        # modulation sait rendre, sinon les premiers degres apres la zone
        # morte ne braquent pas du tout (zone morte fantome, cf. modulation.py).
        m = self._modulee
        self._plancher = m.appui_minimum / m.periode_maxi

    def mettre_a_jour(self):
        e = self.capteur.etat()
        self.angle = e.angle

        flux_coupe = e.recu and not e.frais
        if flux_coupe != self.flux_coupe:
            self.flux_coupe = flux_coupe
            print('        -- FLUX DU TELEPHONE COUPE : direction au centre --'
                  if flux_coupe else '        -- flux du telephone revenu --')

        utilisable = e.frais and e.calibre and e.angle is not None

        # Hysteresis : on entre dans le demi-tour a ANGLE_DEMI_TOUR, on n'en
        # sort qu'en revenant sous ANGLE_DEMI_TOUR - HYSTERESIS. Sans elle, un
        # aveugle qui hesite pile a la limite ferait clignoter les gaz.
        if utilisable and cfg.ANGLE_DEMI_TOUR is not None:
            seuil = cfg.ANGLE_DEMI_TOUR - (cfg.HYSTERESIS_DEMI_TOUR if self.demi_tour else 0.0)
            demi_tour = abs(e.angle) > seuil
            if demi_tour != self.demi_tour:
                self.demi_tour = demi_tour
                print('        -- DEMI-TOUR : l aveugle se retourne, le kart lache les gaz --'
                      if demi_tour else '        -- l aveugle est revenu face au muet --')

        fleches = cfg.DIRECTION == 'fleches'
        if utilisable and not self.demi_tour:
            self.consigne = consigne_depuis_angle(e.angle, self._plancher if fleches else 0.0)
        else:
            self.consigne = 0.0

        if fleches:
            enfoncee = self._modulee.etat(abs(self.consigne))
            with self.sortie.groupe():
                self.sortie.set_continuous('left', NOM, enfoncee and self.consigne < 0)
                self.sortie.set_continuous('right', NOM, enfoncee and self.consigne > 0)
        else:
            self.sortie.steer(self.consigne)

        # Toujours declare, meme a False : c'est ce qui relache les gaz a la
        # fin du demi-tour. Les deux ensemble dans un groupe : une par une, la
        # sortie passerait un instant par "frein seul" et un P_BRAKE fantome
        # partirait au jeu.
        with self.sortie.groupe():
            self.sortie.set_continuous('accelerate', NOM_TRICHE, self.demi_tour)
            self.sortie.set_continuous('brake', NOM_TRICHE, self.demi_tour)

    def etat_texte(self):
        e = self.capteur.etat()
        if not e.recu:
            return 'en attente du telephone'
        morceaux = ['chaise=%+6.1f' % e.angle if e.angle is not None else 'chaise=  -  ',
                    'steer=%+5.2f' % self.consigne]
        if e.methode and e.methode != self.capteur.methode:
            morceaux.append('(repli %s)' % e.methode)
        if not e.calibre:
            morceaux.append('[NON CALIBRE]')
        if self.flux_coupe:
            morceaux.append('[FLUX COUPE]')
        if self.demi_tour:
            morceaux.append('[DEMI-TOUR]')
        return ' '.join(morceaux)

    def arreter(self):
        self.sortie.steer(0.0)
        with self.sortie.groupe():
            self.sortie.set_continuous('left', NOM, False)
            self.sortie.set_continuous('right', NOM, False)
            self.sortie.set_continuous('accelerate', NOM_TRICHE, False)
            self.sortie.set_continuous('brake', NOM_TRICHE, False)
