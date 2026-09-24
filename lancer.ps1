# Ouvre le jeu a trois en deux fenetres : le serveur, puis trio.py.
#
#   .\lancer.ps1                    pour de vrai, a trois
#   .\lancer.ps1 --solo             tester seul, assis face a l'ecran
#   .\lancer.ps1 --solo --fleches   idem, direction par fleches (si la manette est ignoree)
#   .\lancer.ps1 -Muet --solo       serveur muet : rien n'est tape, on lit les commandes
#
# Tout ce qui n'est pas -Muet est passe tel quel a trio.py (--aveugle, --voix,
# --arduino, --journal f.csv, --duree 180...).
#
# Le serveur est serveur.py : c'est lui qui comprend STEER, la direction
# analogique, et il connait aussi tout le vocabulaire clavier. Il cree la
# manette virtuelle : lancer SuperTuxKart APRES lui.
#
# Quel python : celui de l'environnement actif ($env:VIRTUAL_ENV), sinon un
# .venv dans ce dossier, sinon le premier "python" du PATH. Il est choisi une
# fois ici et transmis aux deux fenetres, pour qu'elles tournent avec le meme.
#
# Le script se relance lui-meme avec -File et -Role : construire la ligne de
# commande enfant par concatenation de chaines deplace les guillemets. $Sources
# est en Position 0, sinon un argument comme "--solo" serait pris pour la
# valeur d'un autre parametre.

param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)] $Sources,
    [switch]$Muet,
    [ValidateSet('', 'serveur', 'jeu')] [string]$Role = '',
    [string]$SourcesTexte = '',
    [string]$Py = ''
)

$TRIO = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $Py) {
    $venvLocal = Join-Path $TRIO ".venv\Scripts\python.exe"
    if ($env:VIRTUAL_ENV -and (Test-Path (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"))) {
        $Py = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    } elseif (Test-Path $venvLocal) {
        $Py = $venvLocal
    } else {
        $commande = Get-Command python -ErrorAction SilentlyContinue
        if ($commande) { $Py = $commande.Source }
    }
}
if (-not $Py -or -not (Test-Path $Py)) {
    Write-Host "Python introuvable. Active l'environnement du projet, ou cree-le :" -ForegroundColor Red
    Write-Host "  python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements.txt"
    exit 1
}

# --- Ce qui tourne DANS la fenetre serveur -------------------------------
if ($Role -eq 'serveur') {
    Set-Location $TRIO
    if ($Muet) {
        $host.UI.RawUI.WindowTitle = 'SERVEUR MUET (aucune touche tapee)'
        $muet = Join-Path $TRIO 'serveur_muet.py'
        if (-not (Test-Path $muet)) {
            Write-Host "serveur_muet.py absent (outil de test, hors du depot)." -ForegroundColor Red
            return
        }
        & $Py $muet
    } else {
        $host.UI.RawUI.WindowTitle = 'SERVEUR STK (manette + clavier)'
        & $Py (Join-Path $TRIO 'serveur.py') -d
    }
    return
}

# --- Ce qui tourne DANS la fenetre du jeu --------------------------------
if ($Role -eq 'jeu') {
    Set-Location $TRIO
    $host.UI.RawUI.WindowTitle = 'TRIO'
    $liste = @()
    if ($SourcesTexte) {
        $liste = $SourcesTexte.Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    }
    & $Py (Join-Path $TRIO 'trio.py') @liste
    return
}

# --- Le lancement proprement dit -----------------------------------------
$moi = $MyInvocation.MyCommand.Path

# Start-Process recolle les arguments avec des espaces SANS les proteger : un
# chemin "C:\Users\Jean Dupont\..." ou la liste "--solo --fleches" seraient
# coupes en morceaux. On les entoure donc de guillemets nous-memes.
function Entre-Guillemets([string]$texte) { '"' + $texte + '"' }

Write-Host ""
Write-Host "Python utilise : $Py" -ForegroundColor DarkGray

$argsServeur = @('-NoExit', '-File', (Entre-Guillemets $moi), '-Role', 'serveur',
                 '-Py', (Entre-Guillemets $Py))
if ($Muet) { $argsServeur += '-Muet' }

Write-Host "=== SERVEUR ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList $argsServeur

Start-Sleep -Seconds 1

$argsJeu = @('-NoExit', '-File', (Entre-Guillemets $moi), '-Role', 'jeu',
             '-Py', (Entre-Guillemets $Py))
if ($Sources) { $argsJeu += @('-SourcesTexte', (Entre-Guillemets ($Sources -join ' '))) }

Write-Host "=== TRIO ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList $argsJeu

Write-Host ""
Write-Host "Deux fenetres ouvertes. Il reste a :" -ForegroundColor Yellow
Write-Host "  1. suivre la calibration dans la fenetre TRIO (trois bips, ne pas bouger)"
Write-Host "  2. lancer SuperTuxKart EN MODE FENETRE (apres le serveur) et demarrer une course"
Write-Host "  3. cliquer dans la fenetre du jeu pour lui donner le focus"
Write-Host "  4. Q dans la fenetre TRIO, ou Ctrl+C, pour tout relacher"
Write-Host ""
