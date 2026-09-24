#!/usr/bin/env python3
"""Le sourd : casque sur les oreilles, il tient la vitesse et gere les objets.

    boitier Arduino (UDP 6010)   doigt pose     -> accelerer (tenu)
                                 tape (piezo)   -> lancer l'objet
                                 pedale (ultrason, en option) -> freiner
    voix (Vosk)                  "fire"   -> lancer l'objet
                                 "turbo"  -> nitro
                                 "help"   -> sauvetage
                                 "center" -> recentrer la chaise de l'aveugle

Pourquoi un ecouteur Vosk ecrit ici
-----------------------------------
Le VoiceWorker des autres branches du depot change d'interface d'une branche
a l'autre (sur main il recoit un objet, sur performance une fonction). Ce
dossier doit tourner seul : quarante lignes ici valent mieux qu'une
dependance vers une branche qui bouge.

Les faux declenchements
-----------------------
Vosk ne reconnait QUE les mots de MOTS_VOIX : tout son est ramene vers le
plus proche, y compris la musique du jeu et des paroles en francais. Pour une
action couteuse comme le sauvetage, le mot doit donc etre dit DEUX FOIS
(MOTS_A_REPETER). python tester_voix.py --mots montre ce que Vosk entend.

Le boitier envoie un ETAT, pas des evenements
---------------------------------------------
Toutes les 50 ms :  touche=1 dist=23 tapes=12 piezo=412

  - un paquet perdu ne bloque rien : le suivant redit tout ;
  - un tir part quand le COMPTEUR tapes augmente, pas sur un message "tape"
    qui pourrait se perdre ou arriver deux fois ;
  - si plus rien n'arrive pendant WATCHDOG_ARDUINO, on relache tout. C'est la
    lecon du projet : le silence doit valoir relachement (ZIG SIM n'envoie
    pas de "doigt leve", le drift.ino de l'equipe renvoie son relachement
    trois fois).
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

# Compteurs du boitier -> action ponctuelle. Un capteur de plus sur la carte
# (tilt switch, EMG...) = un compteur de plus dans le paquet et une ligne ici.
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
        except Exception as erreur:     # le thread ne doit pas mourir en silence
            self.erreur = erreur
            print('        [voix] ARRETEE : %s' % erreur)

    def _ecouter(self):
        import sounddevice as sd
        import vosk
        vosk.SetLogLevel(-1)
        modele = vosk.Model(cfg.MODELE_VOSK)
        # Grammaire restreinte : Vosk ne peut entendre QUE ces mots. "[unk]"
        # absorbe tout le reste, sinon il forcerait chaque bruit vers un mot-cle.
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
        """Declenche chaque NOUVELLE occurrence d'un mot-cle dans la phrase en cours.

        Vosk renvoie des resultats partiels qui s'allongent tant qu'on parle :
        "fire" puis "fire [unk]" puis "fire [unk] fire". Declencher a chaque
        partiel lancerait un objet par partiel ; un simple delai ne suffit pas
        non plus (une phrase longue garde le meme "fire" plus d'une seconde).
        On compte donc les occurrences deja traitees, et on remet a zero a la
        fin de la phrase.
        """
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
        # Juste apres une action, une nouvelle occurrence est une revision de
        # Vosk, pas une nouvelle demande.
        if maintenant - self._dates.get(mot, 0.0) < cfg.DELAI_VOIX:
            return

        fenetre = cfg.MOTS_A_REPETER.get(mot)
        if fenetre is not None:
            # Mot a repeter : la 1re occurrence arme, la 2e dans la fenetre
            # agit. "help help" dit d'une traite compte aussi : les deux
            # occurrences arrivent ensemble, et le delai ci-dessus ne s'applique
            # qu'APRES une action.
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
            except OSError:
                # Sous Windows, un ICMP "port injoignable" remonte en erreur
                # sur le recvfrom suivant (WSAECONNRESET). Sans consequence.
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
            # Premier paquet, ou carte redemarree (compteur revenu a zero) :
            # on prend la valeur comme origine, sans rien declencher.
            if avant is None or valeur < avant:
                continue
            # Plafond a 3 : apres une longue coupure, on ne rattrape pas une
            # rafale de tirs d'un coup.
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
