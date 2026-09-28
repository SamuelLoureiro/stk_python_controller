#!/usr/bin/env python3
"""Module de vision par ordinateur pour detecter les gestes d'acceleration, freinage et high-five."""

import argparse
import collections
import math
import sys
import threading
import time

import config_trio as cfg

NOM = 'webcam'
NEZ, EPAULE_G, EPAULE_D, POIGNET_G, POIGNET_D = 0, 11, 12, 15, 16
OREILLE_G, OREILLE_D = 7, 8
SQUELETTE = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
             (11, 23), (12, 24), (23, 24)]
GESTES = {0: 'rien', 1: 'freiner', 2: 'accelerer'}


def personne_debout(poses):
    """Trouve la personne debout en cherchant le visage situe le plus haut."""
    candidates = [p for p in poses if p[NEZ][1] < cfg.LIGNE_DEBOUT]
    return min(candidates, key=lambda p: p[NEZ][1]) if candidates else None


def hauteurs_mains(pose, largeur, hauteur):
    """Evalue la hauteur relative de chaque poignet par rapport aux epaules."""
    epaules = abs(pose[EPAULE_G][0] - pose[EPAULE_D][0]) * largeur or 1.0
    resultat = []
    for poignet, epaule in ((POIGNET_G, EPAULE_G), (POIGNET_D, EPAULE_D)):
        if pose[poignet][2] < cfg.VISIBILITE_MIN:
            resultat.append(None)
        else:
            resultat.append((pose[epaule][1] - pose[poignet][1]) * hauteur / epaules)
    return resultat


def personne_assise(poses, debout):
    """Identifie la pose du joueur assis sur la chaise."""
    autres = [p for p in poses if p is not debout]
    return max(autres, key=lambda p: p[NEZ][1]) if autres else None


def distance_high_five(debout, assise, largeur, hauteur):
    """Calcule la distance entre la main levee du joueur assis et la main du joueur debout."""
    epaules = abs(debout[EPAULE_G][0] - debout[EPAULE_D][0]) * largeur or 1.0
    levees = [assise[p] for p, h in zip((POIGNET_G, POIGNET_D),
                                        hauteurs_mains(assise, largeur, hauteur))
              if h is not None and h > cfg.MARGE_MAIN]
    mains = [debout[p] for p in (POIGNET_G, POIGNET_D) if debout[p][2] >= cfg.VISIBILITE_MIN]
    if not levees or not mains:
        return None
    return min(math.hypot((a[0] - b[0]) * largeur, (a[1] - b[1]) * hauteur)
               for a in levees for b in mains) / epaules


def distance_tete(pose, poignet, largeur, hauteur):
    """Calcule la distance d'un poignet au centre de la tete normalisee."""
    epaules = abs(pose[EPAULE_G][0] - pose[EPAULE_D][0]) * largeur or 1.0
    og, od = pose[OREILLE_G], pose[OREILLE_D]
    if min(og[2], od[2]) >= cfg.VISIBILITE_TETE:
        tx, ty = (og[0] + od[0]) / 2, (og[1] + od[1]) / 2
    else:
        tx, ty = pose[NEZ][0], pose[NEZ][1]
    return math.hypot((pose[poignet][0] - tx) * largeur,
                      (pose[poignet][1] - ty) * hauteur) / epaules


def mains_sur_tete(pose, largeur, hauteur):
    """Verifie si les deux mains sont posees sur la tete (geste frein)."""
    if min(pose[EPAULE_G][2], pose[EPAULE_D][2]) < cfg.VISIBILITE_MIN:
        return None
    epaules_y = (pose[EPAULE_G][1] + pose[EPAULE_D][1]) / 2
    for poignet in (POIGNET_G, POIGNET_D):
        if pose[poignet][2] < cfg.VISIBILITE_TETE or pose[poignet][1] >= epaules_y:
            return None
    return max(distance_tete(pose, p, largeur, hauteur) for p in (POIGNET_G, POIGNET_D))


def ecart_mains(pose, largeur, hauteur):
    """Difference de hauteur entre les mains pour le geste 6-7."""
    hauteurs = hauteurs_mains(pose, largeur, hauteur)
    if None in hauteurs or max(hauteurs) > cfg.MARGE_MAIN:
        return None
    return hauteurs[1] - hauteurs[0]


class SixSept:
    """Detecteur du mouvement alternatif rapide des mains pour l'acceleration."""

    def __init__(self):
        self.signe = 0
        self.bascules = collections.deque()
        self.d = None

    def observer(self, d, t):
        self.d = d
        if d is not None:
            cote = 1 if d > cfg.SIXSEPT_SEUIL else -1 if d < -cfg.SIXSEPT_SEUIL else 0
            # Seuil d'hysteresis pour eviter les faux positifs au neutre
            if cote and cote != self.signe:
                if self.signe:
                    self.bascules.append(t)
                self.signe = cote
        while self.bascules and t - self.bascules[0] > cfg.SIXSEPT_FENETRE:
            self.bascules.popleft()
        return (len(self.bascules) >= cfg.SIXSEPT_BASCULES
                and t - self.bascules[-1] <= cfg.SIXSEPT_MAINTIEN)


def analyser(poses, largeur, hauteur, sixsept, t):
    """Identifie le geste effectif selon l'ordre de priorite (frein, 6-7, mains levees)."""
    debout = personne_debout(poses)
    if debout is None:
        sixsept.observer(None, t)
        return 'absent', None
    fait_67 = sixsept.observer(ecart_mains(debout, largeur, hauteur), t)
    tete = mains_sur_tete(debout, largeur, hauteur)
    if tete is not None and tete < cfg.FREIN_DISTANCE_TETE:
        return 'freiner', debout
    if fait_67:
        return 'accelerer', debout
    # Les mains sur la tete sont exclues des mains levees simples
    levees = sum(1 for h, p in zip(hauteurs_mains(debout, largeur, hauteur),
                                   (POIGNET_G, POIGNET_D))
                 if h is not None and h > cfg.MARGE_MAIN
                 and distance_tete(debout, p, largeur, hauteur) >= cfg.FREIN_DISTANCE_TETE)
    return GESTES[levees], debout


class Filtre:
    """Filtre temporel pour stabiliser la detection des gestes."""

    def __init__(self):
        self.stable = 'absent'
        self._candidat = None
        self._depuis = 0.0

    def mettre(self, geste, t):
        if geste == self.stable:
            self._candidat = None
        else:
            if geste != self._candidat:
                self._candidat, self._depuis = geste, t
            attente = cfg.ABSENCE_MAX if geste == 'absent' else cfg.ATTENTE_GESTE
            if t - self._depuis >= attente:
                self.stable, self._candidat = geste, None
        return self.stable


class Webcam:
    """Capture video et pipeline MediaPipe pour le pilotage par gestes."""

    def __init__(self, sortie=None, camera=None):
        self.sortie = sortie
        self.camera = cfg.CAMERA_INDEX if camera is None else camera
        self.erreur = None
        self.ips = 0.0
        self._verrou = threading.Lock()
        self._arret = threading.Event()
        self._filtre = Filtre()
        self._sixsept = SixSept()
        self._tape = None           # distance de contact pour le high-five
        self._en_tape = False
        self._tapes = 0             # compteur de high-fives detectes
        self._tapes_envoyes = 0     # impulsions fire transmises
        self._image = None
        self._poses = []
        self._debout = None
        self._brut = 'absent'
        self._derniere = 0.0
        self._numero = 0
        self._affichee = -1
        self._capture = None
        self._detecteur = None
        self._fil = None

    def demarrer(self):
        """Charge le modele MediaPipe et demarre le flux video."""
        import os
        import cv2
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        if not os.path.isfile(cfg.MODELE_POSE):
            raise RuntimeError('modele de pose introuvable : %s\n'
                               'Lance une fois : python installer.py' % cfg.MODELE_POSE)
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=cfg.MODELE_POSE),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=2)
        self._detecteur = vision.PoseLandmarker.create_from_options(options)
        self._capture = cv2.VideoCapture(self.camera, cv2.CAP_DSHOW)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.CAMERA_LARGEUR)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.CAMERA_HAUTEUR)
        if not self._capture.isOpened():
            raise RuntimeError('camera %d introuvable (essayer --camera 1)' % self.camera)
        self._fil = threading.Thread(target=self._boucle, daemon=True)
        self._fil.start()
        print('[webcam] camera %d ouverte.' % self.camera)

    def _boucle(self):
        """Thread de traitement video continu."""
        import cv2
        import mediapipe as mp
        horodatage = 0
        debut, images = time.time(), 0
        try:
            while not self._arret.is_set():
                ok, image = self._capture.read()
                if not ok:
                    time.sleep(0.01)
                    continue
                # MediaPipe exige des horodatages strictement croissants
                horodatage = max(horodatage + 1, int(time.monotonic() * 1000))
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                resultat = self._detecteur.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), horodatage)
                poses = [[(p.x, p.y, p.visibility) for p in pose]
                         for pose in resultat.pose_landmarks]
                hauteur, largeur = image.shape[:2]
                t = time.time()
                geste, debout = analyser(poses, largeur, hauteur, self._sixsept, t)
                assise = personne_assise(poses, debout) if debout else None
                tape = distance_high_five(debout, assise, largeur, hauteur) if assise else None
                en_tape = tape is not None and tape < cfg.HIGH_FIVE_DISTANCE
                images += 1
                with self._verrou:
                    self._image, self._poses, self._debout, self._brut = image, poses, debout, geste
                    self._tape = tape
                    if en_tape and not self._en_tape:
                        self._tapes += 1
                    self._en_tape = en_tape
                    # Le bras tendu pour le high five ne doit pas freiner par erreur
                    self._filtre.mettre(self._filtre.stable if en_tape else geste, t)
                    self._derniere = t
                    self._numero += 1
                    if t - debut >= 1.0:
                        self.ips, debut, images = images / (t - debut), t, 0
        except Exception as erreur:
            self.erreur = erreur
            print('        [webcam] ARRETEE : %s' % erreur)

    def geste(self):
        """Renvoie le geste stable actuellement filtre."""
        with self._verrou:
            if time.time() - self._derniere > cfg.ABSENCE_MAX:
                return 'absent'
            return self._filtre.stable

    def mettre_a_jour(self):
        """Transmet les commandes d'acceleration, freinage et high-five a SortieSTK."""
        if self.sortie is None:
            return
        g = self.geste()
        with self._verrou:
            nouveau = self._tapes != self._tapes_envoyes
            self._tapes_envoyes = self._tapes
        if nouveau:
            self.sortie.pulse('fire', cfg.HIGH_FIVE_REPOS)
        with self.sortie.groupe():
            self.sortie.set_continuous('accelerate', NOM, g == 'accelerer')
            self.sortie.set_continuous('brake', NOM, g == 'freiner')

    def mesures(self):
        """Renvoie les valeurs brutes de position des mains pour le debug."""
        with self._verrou:
            if self._image is None or self._debout is None:
                return None
            hauteur, largeur = self._image.shape[:2]
            return (self._debout[NEZ][1], hauteurs_mains(self._debout, largeur, hauteur),
                    self._sixsept.d, mains_sur_tete(self._debout, largeur, hauteur))

    def detail_gestes(self):
        """Formate les metriques en chaine pour l'overlay video."""
        m = self.mesures()
        if m is None:
            return '6-7 -  tete -  tape -'
        _, _, d, tete = m
        with self._verrou:
            tape = self._tape
        return '6-7 d=%s  tete %s  tape %s' % ('-' if d is None else '%+.2f' % d,
                                              '-' if tete is None else '%.2f' % tete,
                                              '-' if tape is None else '%.2f' % tape)

    def afficher(self):
        """Affiche la fenetre OpenCV avec le squelette et les indicateurs."""
        import cv2
        with self._verrou:
            nouvelle = self._image is not None and self._numero != self._affichee
            if nouvelle:
                image = self._image.copy()
                poses, debout, brut = self._poses, self._debout, self._brut
                self._affichee = self._numero
        if nouvelle:
            hauteur, largeur = image.shape[:2]
            ligne = int(cfg.LIGNE_DEBOUT * hauteur)
            cv2.line(image, (0, ligne), (largeur, ligne), (0, 200, 255), 1)
            for pose in poses:
                couleur = (0, 220, 0) if pose is debout else (140, 140, 140)
                for a, b in SQUELETTE:
                    cv2.line(image, (int(pose[a][0] * largeur), int(pose[a][1] * hauteur)),
                             (int(pose[b][0] * largeur), int(pose[b][1] * hauteur)), couleur, 2)
            if debout is not None:
                for h, i in zip(hauteurs_mains(debout, largeur, hauteur), (POIGNET_G, POIGNET_D)):
                    levee = h is not None and h > cfg.MARGE_MAIN
                    cv2.circle(image, (int(debout[i][0] * largeur), int(debout[i][1] * hauteur)),
                               12, (0, 255, 0) if levee else (0, 0, 255), -1)
            if cfg.MIROIR:
                image = cv2.flip(image, 1)
            texte = '%s (brut : %s)  %.0f im/s' % (self.geste().upper(), brut, self.ips)
            cv2.putText(image, texte, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
            cv2.putText(image, texte, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            detail = self.detail_gestes()
            cv2.putText(image, detail, (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(image, detail, (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.imshow('TRIO - webcam', image)
        touche = cv2.waitKey(1) & 0xFF
        return chr(touche).lower() if touche != 255 else None

    def etat_texte(self):
        """Statut condense pour la console."""
        if self.erreur:
            return 'ARRETEE'
        return '%s (%.0f im/s)' % (self.geste(), self.ips)

    def arreter(self):
        """Libere la camera et ferme les fenetres OpenCV."""
        import cv2
        self._arret.set()
        if self._fil:
            self._fil.join(timeout=2)
        if self._capture:
            self._capture.release()
        if self._detecteur:
            self._detecteur.close()
        cv2.destroyAllWindows()
        if self.sortie is not None:
            with self.sortie.groupe():
                self.sortie.set_continuous('accelerate', NOM, False)
                self.sortie.set_continuous('brake', NOM, False)


def main():
    """Utilitaire de calibration visuelle pour la camera."""
    p = argparse.ArgumentParser(description='Reglage de la webcam : la personne debout.')
    p.add_argument('--camera', type=int, default=None)
    p.add_argument('--duree', type=float, default=None, metavar='S')
    args = p.parse_args()

    webcam = Webcam(camera=args.camera)
    try:
        webcam.demarrer()
    except RuntimeError as erreur:
        print(erreur)
        return 1
    print('Q dans la fenetre pour quitter. LIGNE_DEBOUT = %.2f, MARGE_MAIN = %.2f'
          % (cfg.LIGNE_DEBOUT, cfg.MARGE_MAIN))
    fin = time.time() + args.duree if args.duree else None
    prochaine = 0.0
    try:
        while not (fin and time.time() >= fin):
            if webcam.afficher() == 'q' or webcam.erreur:
                break
            if time.time() >= prochaine:
                prochaine = time.time() + 0.5
                m = webcam.mesures()
                if m is None:
                    detail = 'personne debout non vue'
                else:
                    nez, (g, d), _, _ = m
                    detail = 'nez %.2f  main G %s  main D %s  %s' % (
                        nez, '-' if g is None else '%+.2f' % g, '-' if d is None else '%+.2f' % d,
                        webcam.detail_gestes())
                print('%-10s %-62s %.0f im/s' % (webcam.geste(), detail, webcam.ips), flush=True)
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        webcam.arreter()
    return 0


if __name__ == '__main__':
    sys.exit(main())
