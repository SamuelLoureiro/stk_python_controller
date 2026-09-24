#!/usr/bin/env python3
"""Braquer un peu avec une touche tout-ou-rien : la fleche est battue en rythme.

Le jeu ne voit pas un appui de moins de 16 ms (une image a 60 fps, mesure) :
pour braquer moins, on espace les appuis au lieu de les raccourcir.
"""

import time


class ToucheModulee:
    """Intensite 0..1 -> appuis rythmes."""

    def __init__(self, periode=0.12, appui_minimum=0.034, periode_maxi=0.45):
        self.periode = periode                # cycle nominal
        self.appui_minimum = appui_minimum    # 2 images a 60 fps
        self.periode_maxi = periode_maxi      # au-dela, l'appui se sent passer
        self._debut = None

    def etat(self, intensite, maintenant=None):
        """True si la touche doit etre enfoncee a cet instant."""
        if maintenant is None:
            maintenant = time.time()

        if intensite <= 0.0:
            self._debut = None
            return False
        if intensite >= 1.0:
            if self._debut is None:
                self._debut = maintenant
            return True

        duree_appui = intensite * self.periode
        periode = self.periode

        if duree_appui < self.appui_minimum:
            # trop court pour le jeu : appui minimum, cycle etire
            duree_appui = self.appui_minimum
            periode = self.appui_minimum / intensite
            if periode > self.periode_maxi:
                self._debut = None
                return False

        if self._debut is None:
            self._debut = maintenant

        phase = (maintenant - self._debut) % periode
        return phase < duree_appui


def intensite_depuis_angle(ecart, angle_mini, angle_maxi, courbe=1.0,
                           plancher=0.0):
    """Angle -> intensite 0..1 : zone morte, puis courbe (> 1 = plus doux au
    centre), a partir du plancher, la plus petite intensite rendable."""
    amplitude = abs(ecart)
    if amplitude <= angle_mini:
        return 0.0
    if amplitude >= angle_maxi:
        return 1.0
    t = (amplitude - angle_mini) / (angle_maxi - angle_mini)
    return plancher + (1.0 - plancher) * (t ** courbe)
