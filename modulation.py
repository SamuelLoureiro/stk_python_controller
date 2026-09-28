#!/usr/bin/env python3
"""Simulation d'une commande proportionnelle via des pulsations clavier."""

import time


class ToucheModulee:
    """Transforme une valeur continue (0 a 1) en trains d'impulsions de touches."""

    def __init__(self, periode=0.12, appui_minimum=0.034, periode_maxi=0.45):
        self.periode = periode                # cycle de base
        self.appui_minimum = appui_minimum    # temps mini pour prise en compte par le jeu (~2 frames a 60 fps)
        self.periode_maxi = periode_maxi      # periode max pour garder un comportement fluide
        self._debut = None

    def etat(self, intensite, maintenant=None):
        """Determine si la touche doit etre enfoncee a cet instant."""
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
            # Si le pulse est trop court, on maintient la duree mini et on espace le cycle
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
    """Calcule l'intensite de braquage (0 a 1) avec zone morte et courbe d'attenuation."""
    amplitude = abs(ecart)
    if amplitude <= angle_mini:
        return 0.0
    if amplitude >= angle_maxi:
        return 1.0
    t = (amplitude - angle_mini) / (angle_maxi - angle_mini)
    return plancher + (1.0 - plancher) * (t ** courbe)
