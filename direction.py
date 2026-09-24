#!/usr/bin/env python3
"""Le joueur assis : l'angle de la chaise devient la direction du kart.

Il tourne a droite, le kart tourne a droite. Flux du telephone coupe -> direction
au centre.
"""

import config_trio as cfg
from modulation import ToucheModulee, intensite_depuis_angle

NOM = 'chaise'


def consigne_depuis_angle(angle, plancher=0.0):
    """Angle de la chaise (> 0 = vers la droite) -> STEER -1..+1."""
    amplitude = intensite_depuis_angle(angle, cfg.ANGLE_MINI, cfg.ANGLE_MAXI, cfg.COURBE,
                                       plancher)
    if amplitude == 0.0:
        return 0.0          # pas -0.0, qui s'afficherait STEER:-0.000
    return amplitude if angle > 0 else -amplitude


class Direction:
    def __init__(self, sortie, capteur):
        self.sortie = sortie
        self.capteur = capteur
        self.angle = None
        self.consigne = 0.0
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

        fleches = cfg.DIRECTION == 'fleches'
        if e.frais and e.calibre and e.angle is not None:
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

    def etat_texte(self):
        e = self.capteur.etat()
        if not e.recu:
            return 'en attente du telephone'
        morceaux = ['angle=%+6.1f' % e.angle if e.angle is not None else 'angle=  -  ',
                    'steer=%+5.2f' % self.consigne]
        if e.methode and e.methode != self.capteur.methode:
            morceaux.append('(repli %s)' % e.methode)
        if not e.calibre:
            morceaux.append('[NON CALIBRE]')
        if self.flux_coupe:
            morceaux.append('[FLUX COUPE]')
        return ' '.join(morceaux)

    def arreter(self):
        self.sortie.steer(0.0)
        with self.sortie.groupe():
            self.sortie.set_continuous('left', NOM, False)
            self.sortie.set_continuous('right', NOM, False)
