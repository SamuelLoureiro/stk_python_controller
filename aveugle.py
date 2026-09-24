#!/usr/bin/env python3
"""L'aveugle : l'angle de la chaise devient la direction du kart.

Securites : flux du telephone coupe -> direction au centre ; demi-tour (il se
retourne vers l'ecran) -> direction au centre et gaz coupes.
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
        return 0.0          # pas -0.0, qui s'afficherait STEER:-0.000
    vers_sa_droite = amplitude if angle > 0 else -amplitude
    return -vers_sa_droite if cfg.CORRESPONDANCE == 'miroir' else vers_sa_droite


class Aveugle:
    def __init__(self, sortie, capteur):
        self.sortie = sortie
        self.capteur = capteur
        self.angle = None
        self.consigne = 0.0
        self.demi_tour = False
        self.flux_coupe = False
        self._modulee = ToucheModulee()
        # En fleches, la plage demarre a la plus petite intensite que la
        # modulation sait rendre, sinon zone morte fantome.
        self._plancher = self._modulee.appui_minimum / self._modulee.periode_maxi

    def mettre_a_jour(self):
        e = self.capteur.etat()
        self.angle = e.angle

        flux_coupe = e.recu and not e.frais
        if flux_coupe != self.flux_coupe:
            self.flux_coupe = flux_coupe
            print('        -- FLUX DU TELEPHONE COUPE : direction au centre --'
                  if flux_coupe else '        -- flux du telephone revenu --')

        utilisable = e.frais and e.calibre and e.angle is not None

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

        # accelerate + brake ensemble s'annulent (OPPOSEES) : gaz coupes. Dans un
        # groupe, sinon un P_BRAKE fantome part entre les deux.
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
