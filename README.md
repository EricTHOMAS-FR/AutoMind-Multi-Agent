# 🤖 AMMA (AutoMind Multi-Agent)

AMMA est une application de bureau "Zero-Config" hébergeant un écosystème d'agents IA locaux, autonomes et collaboratifs. Conçu pour fonctionner entièrement en local, AMMA s'appuie sur la puissance du *Function Calling* des modèles LLM pour interagir avec son environnement.

## ✨ Fonctionnalités Principales

* **Confidentialité Totale :** 100% du traitement est local (Llama.cpp). Aucune donnée ne quitte votre machine.
* **Système Multi-Agent Asynchrone :** Les agents possèdent leur propre mémoire, boîte de réception et To-Do list. Ils communiquent entre eux via un système de *Watchdog* et de *Heartbeat* fonctionnant en arrière-plan.
* **Bac à Sable Python (Sandbox) :** Les agents peuvent écrire, déboguer et exécuter du code Python dans un environnement virtuel isolé et sécurisé pour accomplir des tâches complexes.
* **Optimisation VRAM Dynamique :** Un moteur hybride scanne votre carte graphique (NVIDIA) au lancement pour répartir intelligemment la charge du modèle entre le GPU et le CPU.
* **Bouclier Anti-Bégaiement & Auto-Correction :** Détection en temps réel des boucles de l'IA et filet de sécurité syntaxique pour forcer les agents à corriger leurs propres erreurs de *Function Calling*.
* **Interface CustomTkinter :** Un tableau de bord sombre et élégant pour observer les pensées des agents, gérer leurs permissions et configurer le moteur.

## 🚀 Installation et Démarrage

### Prérequis
* Python 3.8 ou supérieur.
* (Recommandé) Une carte graphique NVIDIA pour l'accélération matérielle.

### Étapes
1. Clonez ce dépôt sur votre machine.
2. Installez les dépendances requises :
   ```bash
   pip install -r requirements.txt
   ```
3. **Modèle IA :** Téléchargez un modèle au format `.gguf`. Par défaut, AMMA est optimisé pour **Gemma 4** (`google_gemma-4-E4B-it-Q4_K_M.gguf`).
4. Placez votre modèle téléchargé dans le dossier `models/`.
5. Lancez l'application en double-cliquant sur `Lancer_AMMA.bat` (sous Windows) ou en exécutant :
   ```bash
   python main_ui.py
   ```

## ⚖️ Licence

Le code source de ce projet (l'orchestrateur AMMA) est distribué sous la **Licence Apache 2.0**. Vous êtes libre de l'utiliser, le modifier et le distribuer.

**⚠️ Avertissement concernant les modèles :**
Ce projet n'inclut aucun modèle d'IA. Si vous choisissez d'utiliser les modèles de la famille Gemma (Google), vous devez vous conformer à leurs propres licences et conditions d'utilisation, qui interdisent certaines utilisations malveillantes.