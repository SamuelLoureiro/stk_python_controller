#!/usr/bin/env python3
"""Le sourd : la voix (Vosk) et le boitier Arduino.

Le boitier envoie son ETAT toutes les 50 ms (touche=1 dist=23 tapes=12 piezo=412) :
un tir part quand le compteur tapes augmente, et le silence vaut relachement.
"""

import collections
import json
import os
import queue
import socket
import threading
import time

import config_trio as cfg

NOM_ARDUINO = 'arduino'

COMPTEURS = {
    'tapes': 'fire',
    'nitros': 'turbo',
    'sauvetages': 'rescue',
}


# ------------------------------------------------------------------------ voix

class VoixSourd(threading.Thread):
    """Ecoute le micro et declenche une action par mot-cle reconnu."""

    def __init__(self, sortie, recentrer=None):
        super().__init__(daemon=True)
        self.sortie = sortie
        self.recentrer = recentrer
        self.erreur = None
        self.pret = False
        self.dernier_mot = ''
        self._arret = threading.Event()
        self._audio = queue.Queue()
        self._declenches = {}       # mot -> occurrences deja traitees dans la phrase
        self._dates = {}            # mot -> dernier declenchement
        self._armes = {}            # mot a repeter -> date de sa 1re occurrence

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
        """Declenche chaque nouvelle occurrence d'un mot-cle dans la phrase : les
        resultats partiels de Vosk s'allongent ("fire", "fire [unk] fire")."""
        compte = collections.Counter(m for m in texte.lower().split() if m in cfg.MOTS_VOIX)
        for mot, n in compte.items():
            deja = self._declenches.get(mot, 0)
            if n > deja:
                self._declenches[mot] = n
                for _ in range(n - deja):
                    self._declencher(mot)
        if final:
            self._declenches = {}

    def _declencher(self, mot):
        maintenant = time.monotonic()
        # Juste apres une action : revision de Vosk, pas une nouvelle demande.
        if maintenant - self._dates.get(mot, 0.0) < cfg.DELAI_VOIX:
            return

        fenetre = cfg.MOTS_A_REPETER.get(mot)
        if fenetre is not None:
            # 1re occurrence : on arme. 2e dans la fenetre : on agit.
            arme = self._armes.get(mot)
            if arme is None or maintenant - arme > fenetre:
                self._armes[mot] = maintenant
                self.dernier_mot = mot + ' (1/2)'
                print('        [voix] "%s" (1/2) : redis-le dans les %.1f s pour agir'
                      % (mot, fenetre))
                return
            del self._armes[mot]

        self._dates[mot] = maintenant
        self.dernier_mot = mot
        action = cfg.MOTS_VOIX[mot]
        if action == 'recentrer':
            fait = self.recentrer() if self.recentrer else False
            print('        [voix] "%s" -> chaise recentree' % mot if fait
                  else '        [voix] "%s" -> pas de chaise a recentrer' % mot)
        else:
            print('        [voix] "%s" -> %s' % (mot, action))
            self.sortie.pulse(action)

    def etat_texte(self):
        if self.erreur:
            return 'ARRETEE'
        if not self.pret:
            return 'demarrage...'
        return 'ecoute' + (' (dernier : %s)' % self.dernier_mot if self.dernier_mot else '')

    def arreter(self):
        self._arret.set()
        self.join(timeout=2)


# --------------------------------------------------------------------- Arduino

class ArduinoSourd:
    """Recoit l'etat du boitier et le traduit en demandes pour SortieSTK."""

    def __init__(self, sortie, port=None):
        self.sortie = sortie
        self.port = port if port is not None else cfg.PORT_ARDUINO
        self.champs = {}
        self.adresse = None
        self.vivant = False
        self.accel = False
        self.frein = False
        self.n_paquets = 0
        self._sock = None
        self._dernier = 0.0
        self._compteurs = {}        # dernier compteur vu, par nom

    def demarrer(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(('0.0.0.0', self.port))
        except OSError as erreur:
            s.close()
            raise RuntimeError('le port %d est deja utilise (%s)' % (self.port, erreur))
        s.setblocking(False)
        self._sock = s
        print('[arduino] ecoute sur le port %d.' % self.port)

    def _lire(self):
        while True:
            try:
                donnees, adresse = self._sock.recvfrom(512)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:         # WSAECONNRESET sous Windows, sans consequence
                return
            self._paquet(donnees.decode('ascii', 'replace'), adresse)

    def _paquet(self, texte, adresse):
        champs = {}
        for morceau in texte.split():
            cle, egal, valeur = morceau.partition('=')
            if not egal:
                continue
            try:
                champs[cle] = int(float(valeur))
            except ValueError:
                continue
        if not champs:
            return
        self.n_paquets += 1
        self._dernier = time.time()
        self.adresse = adresse[0]
        self.champs = champs

        for nom, action in COMPTEURS.items():
            if nom not in champs:
                continue
            valeur, avant = champs[nom], self._compteurs.get(nom)
            self._compteurs[nom] = valeur
            # premier paquet, ou carte redemarree
            if avant is None or valeur < avant:
                continue
            # plafond : pas de rafale de tirs apres une coupure
            for _ in range(min(valeur - avant, 3)):
                self.sortie.pulse(action)

    def mettre_a_jour(self):
        self._lire()
        vivant = bool(self._dernier) and time.time() - self._dernier < cfg.WATCHDOG_ARDUINO
        if vivant != self.vivant:
            self.vivant = vivant
            print('        [arduino] boitier connecte (%s)' % self.adresse if vivant
                  else '        [arduino] BOITIER MUET : tout est relache')

        self.accel = vivant and self.champs.get('touche', 0) == 1
        distance = self.champs.get('dist', -1)
        self.frein = (vivant and cfg.FREIN_CM is not None
                      and 0 <= distance < cfg.FREIN_CM)

        with self.sortie.groupe():
            self.sortie.set_continuous('accelerate', NOM_ARDUINO, self.accel)
            self.sortie.set_continuous('brake', NOM_ARDUINO, self.frein)

    def etat_texte(self):
        if not self._dernier:
            return 'en attente sur le port %d' % self.port
        if not self.vivant:
            return 'MUET depuis %.0f s' % (time.time() - self._dernier)
        return ' '.join('%s=%d' % kv for kv in sorted(self.champs.items()))

    def arreter(self):
        with self.sortie.groupe():
            self.sortie.set_continuous('accelerate', NOM_ARDUINO, False)
            self.sortie.set_continuous('brake', NOM_ARDUINO, False)
        if self._sock:
            self._sock.close()
            self._sock = None
