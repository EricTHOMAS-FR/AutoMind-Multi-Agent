@echo off
title AMMA Core - Launcher
echo Lancement d'AutoMind Multi-Agent...
echo Ne fermez pas cette fenetre noire, elle fait tourner le moteur IA en arriere-plan.

:: Se place automatiquement dans le dossier du fichier .bat
cd /d "%~dp0"

:: Lance l'application
python main_ui.py

:: Si l'application crash, la fenêtre restera ouverte pour lire l'erreur
pause