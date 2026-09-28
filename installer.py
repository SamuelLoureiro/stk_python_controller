#!/usr/bin/env python3
"""Script d'installation et de verification des dependances et modeles ML."""

import importlib
import os
import sys
import urllib.request
import zipfile

import config_trio as cfg

URL_VOSK = 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'
URL_POSE = ('https://storage.googleapis.com/mediapipe-models/pose_landmarker/'
            'pose_landmarker_lite/float16/1/pose_landmarker_lite.task')

PAQUETS = [
    ('oscpy', 'telephone'),
    ('keyboard', 'le serveur tape les touches'),
    ('vosk', 'voix'),
    ('sounddevice', 'micro'),
    ('cv2', 'webcam'),
    ('mediapipe', 'detection de la pose'),
]

bilan = []          # (ok, texte)


def noter(ok, texte):
    bilan.append((ok, texte))
    print('  [%s] %s' % ('OK' if ok else '!!', texte))


def verifier_paquets():
    """Verifie la version de Python et les bibliotheques requises."""
    print('1. Python et paquets')
    v = sys.version_info
    noter(v >= (3, 9), 'Python %d.%d (%s)' % (v.major, v.minor, sys.executable))
    manquants = []
    for nom, role in PAQUETS:
        try:
            importlib.import_module(nom)
            noter(True, '%-12s %s' % (nom, role))
        except ImportError:
            manquants.append(nom)
            noter(False, '%-12s MANQUANT (%s)' % (nom, role))
    if manquants:
        print('     -> pip install -r requirements.txt')
    return not manquants


def telecharger(nom, url, cible, archive_zip):
    """Telecharge et extrait un fichier ou modele si absent."""
    if os.path.exists(cible):
        noter(True, '%s deja present' % nom)
        return
    os.makedirs(cfg.MODELES, exist_ok=True)
    fichier = os.path.join(cfg.MODELES, 'telechargement.tmp') if archive_zip else cible
    print('  %s : telechargement de %s' % (nom, url))

    def progression(blocs, taille_bloc, total):
        if total > 0:
            print('\r  %3d %%' % min(100, blocs * taille_bloc * 100 // total), end='', flush=True)

    try:
        urllib.request.urlretrieve(url, fichier, progression)
        print()
        if archive_zip:
            with zipfile.ZipFile(fichier) as z:
                z.extractall(cfg.MODELES)
    except Exception as erreur:
        print()
        noter(False, '%s : telechargement impossible (%s) ; a mettre a la main dans %s'
              % (nom, erreur, cfg.MODELES))
        if os.path.exists(cible) and not archive_zip:
            os.remove(cible)
        return
    finally:
        if archive_zip and os.path.exists(fichier):
            os.remove(fichier)
    noter(os.path.exists(cible), '%s installe' % nom)


def verifier_manette():
    """Verifie la compatibilite de la manette virtuelle Xbox sous Windows."""
    print()
    print('3. Manette virtuelle (direction analogique)')
    if sys.platform != 'win32':
        noter(False, 'hors Windows : jouer avec --fleches')
        return
    try:
        import vgamepad
        vgamepad.VX360Gamepad()     # Windows emet le son de connexion d'un peripherique
        noter(True, 'manette Xbox 360 virtuelle creee')
    except ImportError:
        noter(False, 'vgamepad absent : pip install -r requirements.txt, ou --fleches')
    except Exception as erreur:
        noter(False, 'pilote ViGEmBus absent ou en panne (%s) : le reinstaller, ou --fleches'
              % erreur)


def verifier_calculs():
    """Lance les tests unitaires locaux s'ils sont presents."""
    try:
        import faux_chaise
    except ImportError:
        return
    import contextlib
    import io
    print()
    print('4. Calculs de la chaise')
    with contextlib.redirect_stdout(io.StringIO()):
        code = faux_chaise.verifier()
    noter(code == 0, 'faux_chaise.py --verifier : %s' % ('TOUT EST JUSTE' if code == 0 else 'ECHEC'))


def main():
    print()
    print('=== Installation de TRIO ===')
    print()
    paquets = verifier_paquets()
    print()
    print('2. Modeles')
    telecharger('modele de voix (~40 Mo)', URL_VOSK, cfg.MODELE_VOSK, archive_zip=True)
    telecharger('modele de pose (~6 Mo)', URL_POSE, cfg.MODELE_POSE, archive_zip=False)
    verifier_manette()
    if paquets:
        verifier_calculs()

    problemes = [texte for ok, texte in bilan if not ok]
    print()
    if not problemes:
        print('Tout est pret. Pour jouer seul : .\\lancer.ps1 --solo')
    else:
        print('%d point(s) a regler :' % len(problemes))
        for texte in problemes:
            print('  - %s' % texte)
    return 0 if not problemes else 1


if __name__ == '__main__':
    sys.exit(main())
