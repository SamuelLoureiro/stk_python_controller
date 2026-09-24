# Met SuperTuxKart dans une VRAIE fenetre, plus petite que l'ecran.
#
#   .\stk_fenetre.ps1                 1280 x 720, puis lance le jeu
#   .\stk_fenetre.ps1 -Largeur 1024 -Hauteur 576
#   .\stk_fenetre.ps1 -SansLancer     modifie le reglage sans lancer le jeu
#
# Pourquoi ce script existe
# -------------------------
# Deux pieges se cumulent sur cette machine, et aucun des deux ne se voit :
#
# (Constate sur un portable ; le script sert pour tout ecran mis a l'echelle.)
#
# 1. L'ecran est en 1920x1080 mis a l'echelle a 125 %, donc 1536x864 logiques.
#    SuperTuxKart etait deja en fenetre (fullscreen="false"), mais sa fenetre
#    faisait pile 1536x864 : elle couvrait tout, barre des taches comprise.
#    Decocher "plein ecran" ne changeait donc rien de visible.
#
# 2. L'option en ligne de commande -s LARGEURxHAUTEUR est IGNOREE par STK 1.2.
#    Mesure du 2026-09-22 : lance avec "-w -s 1280x720", la fenetre mesurait
#    quand meme 1536x864 de zone interieure. Seul le fichier de configuration
#    est pris en compte.
#
# D'ou ce script : il ecrit la taille dans config.xml, ce qui marche vraiment.
#
# STK doit etre FERME : il reecrit son fichier de configuration en quittant,
# et ecraserait la modification.

param(
    [int]$Largeur = 1280,
    [int]$Hauteur = 720,
    [switch]$SansLancer,
    [string]$Fichier = "$env:APPDATA\supertuxkart\config-0.10\config.xml",
    [string]$Jeu = "C:\Program Files\SuperTuxKart 1.2.0\supertuxkart.exe"
)

if (-not (Test-Path $Fichier)) {
    Write-Host "Configuration introuvable : $Fichier" -ForegroundColor Red
    Write-Host "Lance SuperTuxKart une fois, il la creera."
    exit 1
}

$tourne = Get-Process supertuxkart -ErrorAction SilentlyContinue
if ($tourne) {
    Write-Host "SuperTuxKart tourne encore (PID $($tourne.Id))." -ForegroundColor Red
    Write-Host "Ferme-le d'abord : en quittant, il reecrit sa configuration et"
    Write-Host "ecraserait la taille qu'on vient de choisir."
    exit 1
}

# Une seule sauvegarde, la premiere fois : on veut pouvoir revenir a l'etat
# d'origine, pas garder une copie de chaque essai.
$sauvegarde = "$Fichier.avant-fenetre"
if (-not (Test-Path $sauvegarde)) {
    Copy-Item $Fichier $sauvegarde
    Write-Host "Sauvegarde : $sauvegarde"
}

$texte = Get-Content $Fichier -Raw

$avantL = if ($texte -match 'width="(\d+)"') { $Matches[1] } else { "?" }
$avantH = if ($texte -match 'height="(\d+)"') { $Matches[1] } else { "?" }

# Les trois attributs n'apparaissent qu'une fois chacun, dans le bloc <Video>.
$texte = $texte -replace '(?m)^(\s*)width="\d+"', "`${1}width=`"$Largeur`""
$texte = $texte -replace '(?m)^(\s*)height="\d+"', "`${1}height=`"$Hauteur`""
$texte = $texte -replace '(?m)^(\s*)fullscreen="[^"]*"', "`${1}fullscreen=`"false`""

Set-Content -Path $Fichier -Value $texte -Encoding utf8 -NoNewline

Write-Host ""
Write-Host "Fenetre : $avantL x $avantH  ->  $Largeur x $Hauteur" -ForegroundColor Green
Write-Host "Plein ecran : desactive"
Write-Host ""

if ($SansLancer) { return }

if (-not (Test-Path $Jeu)) {
    Write-Host "Jeu introuvable : $Jeu" -ForegroundColor Red
    Write-Host "Le reglage est enregistre, lance le jeu toi-meme."
    exit 1
}

Write-Host "Lancement..." -ForegroundColor Cyan
Start-Process $Jeu
