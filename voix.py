#!/usr/bin/env python3
"""La voix (Vosk, hors ligne) : "fire", "help me", "turbo"."""

import collections
import json
import os
import queue
import threading
import time

import config_trio as cfg


def reperer(texte):
    """Les expressions de MOTS_VOIX presentes dans le texte, dans l'ordre dit."""
    mots = texte.lower().split()
    trouvees = []
    for expression in cfg.MOTS_VOIX:
        e = expression.split()
        trouvees += [(i, expression) for i in range(len(mots) - len(e) + 1)
                     if mots[i:i + len(e)] == e]
    return [expression for _, expression in sorted(trouvees)]


def compter(texte):
    return collections.Counter(reperer(texte))


class Voix(threading.Thread):
    def __init__(self, sortie):
        super().__init__(daemon=True)
        self.sortie = sortie
        self.erreur = None
        self.pret = False
        self.dernier = ''
        self._arret = threading.Event()
        self._audio = queue.Queue()
        self._declenches = {}       # expression -> occurrences deja traitees dans la phrase
        self._dates = {}            # expression -> dernier declenchement

    def verifier(self):
        """Leve RuntimeError avec la marche a suivre si la voix ne peut pas demarrer."""
        if not os.path.isdir(cfg.MODELE_VOSK):
            raise RuntimeError('modele Vosk introuvable : %s\n'
                               'Lance une fois : python installer.py' % cfg.MODELE_VOSK)
        try:
            import sounddevice  # noqa: F401
            import vosk  # noqa: F401
        except ImportError as erreur:
            raise RuntimeError('paquets vosk / sounddevice absents (%s)' % erreur)

    def run(self):
        try:
            self._ecouter()
        except Exception as erreur:
            self.erreur = erreur
            print('        [voix] ARRETEE : %s' % erreur)

    def _ecouter(self):
        import sounddevice as sd
        import vosk
        vosk.SetLogLevel(-1)
        modele = vosk.Model(cfg.MODELE_VOSK)
        # "[unk]" absorbe les sons hors liste.
        grammaire = json.dumps(list(cfg.MOTS_VOIX) + ['[unk]'])
        reconnaisseur = vosk.KaldiRecognizer(modele, 16000, grammaire)
        with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype='int16',
                               channels=1, device=cfg.MICRO, callback=self._rappel):
            self.pret = True
            while not self._arret.is_set():
                try:
                    bloc = self._audio.get(timeout=0.5)
                except queue.Empty:
                    continue
                if reconnaisseur.AcceptWaveform(bloc):
                    self._traiter(json.loads(reconnaisseur.Result()).get('text', ''), True)
                else:
                    self._traiter(json.loads(reconnaisseur.PartialResult()).get('partial', ''),
                                  False)

    def _rappel(self, indata, frames, time_info, status):
        self._audio.put(bytes(indata))

    def _traiter(self, texte, final):
        """Declenche chaque nouvelle occurrence dans la phrase : les resultats
        partiels de Vosk s'allongent ("fire", "fire [unk] fire")."""
        vues = collections.Counter()
        for expression in reperer(texte):
            vues[expression] += 1
            if vues[expression] > self._declenches.get(expression, 0):
                self._declenches[expression] = vues[expression]
                self._declencher(expression)
        if final:
            self._declenches = {}

    def _declencher(self, expression):
        maintenant = time.monotonic()
        # Juste apres une action : revision de Vosk, pas une nouvelle demande.
        if maintenant - self._dates.get(expression, 0.0) < cfg.DELAI_VOIX:
            return
        self._dates[expression] = maintenant
        self.dernier = expression
        action = cfg.MOTS_VOIX[expression]
        print('        [voix] "%s" -> %s' % (expression, action))
        self.sortie.pulse(action)

    def etat_texte(self):
        if self.erreur:
            return 'ARRETEE'
        if not self.pret:
            return 'demarrage...'
        return 'ecoute' + (' (dernier : %s)' % self.dernier if self.dernier else '')

    def arreter(self):
        self._arret.set()
        self.join(timeout=2)
