#!/usr/bin/env python3
"""Braquer un peu, avec une touche qui ne connait que tout ou rien.

Le probleme
-----------
Le kart se dirige a la fleche. Une fleche est enfoncee ou relachee, il n'y a
pas d'entre-deux, donc le kart braque a fond ou pas du tout. En jeu c'est
injouable : on zigzague d'un bord a l'autre de la piste.

La solution
-----------
Moduler : au lieu de tenir la fleche, on l'appuie et on la relache en rythme.
Le jeu, lui, integre -- une fleche tenue 30 ms sur 120 fait tourner le kart
environ quatre fois moins qu'une fleche tenue en continu.

    intensite 1.0   |################################|  appui continu
    intensite 0.6   |##########______##########______|
    intensite 0.3   |####____________####____________|
    intensite 0.0   |________________________________|  rien

La contrainte mesuree
---------------------
SuperTuxKart lit le clavier une fois par image. Mesure faite en injectant des
appuis de duree croissante : un appui de 8 ms n'est jamais vu, un appui de
16 ms (une image a 60 fps) l'est toujours.

Un appui plus court que ca ne braque donc pas moins : il ne braque PAS. C'est
pour ca qu'on ne raccourcit jamais l'appui en dessous de APPUI_MINIMUM. Pour
descendre encore en intensite, on ecarte les appuis au lieu de les raccourcir :

    intensite 0.15  |###_____________________###_____|  meme appui, plus espace

Sans cette precaution, les petites inclinaisons ne feraient rien du tout et on
retomberait sur le tout-ou-rien qu'on essaie justement d'eviter.
"""

import time


class ToucheModulee:
    """Transforme une intensite continue (0 a 1) en appuis rythmes.

    Une instance par touche : chacune garde sa propre phase.
    """

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
            # Braquage complet : on tient la touche, sans la relacher. Une
            # modulation a 100 % ferait quand meme un trou d'une image entre
            # deux cycles, et ce trou se sent.
            if self._debut is None:
                self._debut = maintenant
            return True

        duree_appui = intensite * self.periode
        periode = self.periode

        if duree_appui < self.appui_minimum:
            # Trop court pour que le jeu le voie. On garde l'appui au minimum
            # visible et on etire le cycle : meme intensite moyenne, mais
            # chaque appui compte.
            duree_appui = self.appui_minimum
            periode = self.appui_minimum / intensite
            if periode > self.periode_maxi:
                # Sous ce plancher, on ne sait pas braquer moins : l'appui ne
                # peut pas etre plus court et le cycle pas plus long. Mieux
                # vaut ne rien envoyer que de lacher un a-coup a intensite
                # quasi nulle.
                self._debut = None
                return False

        if self._debut is None:
            self._debut = maintenant

        phase = (maintenant - self._debut) % periode
        return phase < duree_appui


def intensite_depuis_angle(ecart, angle_mini, angle_maxi, courbe=1.0,
                           plancher=0.0):
    """Angle mesure -> intensite 0..1.

    Trois morceaux :
      - sous angle_mini, rien. C'est la zone morte : sans elle, le moindre
        mouvement de la chaise braquerait en permanence.
      - au-dela de angle_maxi, braquage complet.
      - entre les deux, proportionnel, adouci par la courbe.

    La courbe (> 1) rend le centre plus doux : a mi-chemin de la plage, une
    courbe de 1.6 ne donne que 33 % de braquage au lieu de 50 %. C'est ce qui
    permet de corriger finement une trajectoire sans sur-braquer, exactement
    comme la courbe d'un manche de jeu.

    Le plancher est la plus petite intensite que la modulation sait rendre
    (appui minimum / periode maximale). On fait commencer la plage LA, au lieu
    de zero : sinon les premiers degres apres la zone morte demandent un
    braquage que la touche ne sait pas produire, et il ne se passe rien
    jusqu'a ce qu'on atteigne le plancher -- une zone morte fantome, plus
    large que celle qu'on a reglee.
    """
    amplitude = abs(ecart)
    if amplitude <= angle_mini:
        return 0.0
    if amplitude >= angle_maxi:
        return 1.0
    t = (amplitude - angle_mini) / (angle_maxi - angle_mini)
    return plancher + (1.0 - plancher) * (t ** courbe)
