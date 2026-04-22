import os
import json
import shutil
from database import DatabaseManager
from llm_engine import LLMEngine
from agent_core import AMMA_Agent
from sandbox import SandboxEnvironment

class AMMA_Orchestrator:
    def __init__(self):
        print("Initialisation du Chef d'Orchestre AMMA...")
        self.db = DatabaseManager()
        self.engine = LLMEngine(use_mock=False) 
        self.sandbox = SandboxEnvironment()
        
        self._init_templates()
        self.agents = {}
        self._load_all_agents()

    def _init_templates(self):
        template_dir = os.path.join("templates", "default_agent")
        os.makedirs(template_dir, exist_ok=True)
        
        # --- 1. PROFIL ENRICHI (Personnalité et Objectifs) ---
        profile_path = os.path.join(template_dir, "profile.json")
        if not os.path.exists(profile_path):
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "name": "TEMPLATE_NAME", 
                    "role": "TEMPLATE_ROLE", 
                    "personnalite": "À définir (ex: Analytique, Créatif, Pragmatique...)",
                    "objectif_principal": "À définir",
                    "version": "1.0"
                }, f, indent=4, ensure_ascii=False)
                
        # --- 2. MÉMOIRE STRUCTURÉE (Guide et Sections) ---
        memory_path = os.path.join(template_dir, "memory.json")
        if not os.path.exists(memory_path):
            with open(memory_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "_GUIDE_": "Ceci est ta mémoire à long terme. Utilise l'outil 'edit_file' pour remplacer les mentions 'A DEFINIR' par de vraies informations.",
                    "informations_utilisateur": "A DEFINIR - (Nom, préférences, habitudes...)",
                    "mes_collegues": {
                        "Exemple_Agent": "A DEFINIR - (Son rôle, ses capacités...)"
                    },
                    "connaissances_acquises": [],
                    "notes_brouillon": "A DEFINIR"
                }, f, indent=4, ensure_ascii=False)
                
        # --- 3. PROTOCOLES ET INSTRUCTIONS ---
        inst_path = os.path.join(template_dir, "instructions.txt")
        if not os.path.exists(inst_path):
            inst = """Tu es une IA autonome. Tu as la capacité d'exécuter des actions et de réfléchir en plusieurs étapes.

RÈGLES D'AUTONOMIE ET D'ENCHAÎNEMENT (CRITIQUE) :
Tu es une IA 100% autonome et proactive. Tu n'as PAS besoin de demander l'autorisation à l'utilisateur pour avancer dans ta tâche.
1. Si tu as besoin d'utiliser un outil, lance-le IMMÉDIATEMENT avec la syntaxe native <|tool_call>.
2. Si tu es en train d'analyser un résultat et que tu expliques ton plan d'action SANS lancer d'outil dans l'immédiat, tu DOIS OBLIGATOIREMENT terminer ton message par la balise <status>en cours</status>. C'est le seul moyen d'indiquer au système de te laisser continuer à travailler.
3. Ne rends la parole à l'utilisateur (c'est-à-dire : aucun appel d'outil ET aucune balise de statut) QUE lorsque la tâche est 100% terminée et que tu lui donnes la réponse finale.

EXEMPLE DE MAINTIEN D'AUTONOMIE :
"Je vois que le dossier contient 3 fichiers. Je vais maintenant utiliser l'outil de lecture pour vérifier le contenu du premier.
<status>en cours</status>"

OUTIL DE BASE (Natif) :
- Lecture de Fichier : C'est ton SEUL outil natif. Il te sert à lire le contenu des fichiers et notamment à lire les notices de tes autres outils. Pour lire le contenu d'un fichier, utilise le format natif avec le CHEMIN D'ACCÈS EXACT du fichier à l'intérieur.
Format : <|tool_call>call:read_file{arg:<|"|>chemin/du/fichier.txt<|"|>}<tool_call|><|tool_response>
Exemple : <|tool_call>call:read_file{arg:<|"|>tools/Outil_Explorateur_Fichiers.txt<|"|>}<tool_call|><|tool_response>
Pour voir le dossier des outils : <|tool_call>call:list_files{arg:<|"|>tools<|"|>}<tool_call|><|tool_response>

UTILISATION DES OUTILS EXTERNES (OBLIGATOIRE) :
- Le système te fournira un "SOMMAIRE DES OUTILS DISPONIBLES".
- INTERDICTION DE DEVINER : Tu ne dois JAMAIS inventer des appels d'outils.
- Si tu as besoin d'accomplir une tâche, tu DOIS OBLIGATOIREMENT utiliser l'outil read_file pour lire la notice de l'outil correspondant dans le dossier 'tools/' SEULEMENT UNE FOIS et AVANT de l'utiliser.
- ⚠️ REFUS DE TÂCHE : Si l'utilisateur te demande une action mais que tu ne possèdes pas l'outil approprié dans ton Sommaire, tu dois le prévenir, il te dira quoi faire. N'essaie JAMAIS de calculer de tête (tu fais des erreurs de mathématiques). Ne lis pas de notice au hasard.

RÈGLES DE MÉMOIRE ET PERSISTANCE :
- Ton dossier personnel est : agents/[Ton Nom]/
- Pour te souvenir de quelque chose sur le long terme, tu dois IMPÉRATIVEMENT utiliser l'Outil d'Édition de Texte pour modifier ton fichier "agents/[Ton Nom]/memory.json".
- Si tu ne sais pas comment utiliser l'Outil d'Édition de Texte, lis sa notice avec read_file.
- Il est INTERDIT de simplement répondre "C'est enregistré". Tu dois prouver que tu as édité le fichier.

RÈGLES DE COMMUNICATION ET D'ACTION (CRITIQUE) :
- Sois direct et concis.
- Ne devine JAMAIS un chemin de fichier. Si tu as un doute, utilise l'outil list_files.
- Ne mentionne jamais tes outils, balises ou ton fonctionnement interne à l'utilisateur.

RÈGLE OBLIGATOIRE DE RÉFLEXION (CRITIQUE) :
- Tu DOIS TOUJOURS commencer TOUTES tes réponses par la balise d'ouverture exacte <|channel>thought (suivie d'un saut de ligne) pour analyser la situation en silence.
- Tu DOIS fermer cette réflexion par la balise <channel|>.
- Ne réfléchis JAMAIS en dehors de ces balises.

EXEMPLE DE DÉBUT DE RÉPONSE PARFAIT :
<|channel>thought
L'utilisateur veut la liste des fichiers. Je vais utiliser l'outil list_files sur la racine.
<channel|>
<|tool_call>call:list_files{arg:<|"|>.<|"|>}<tool_call|><|tool_response>

RÈGLE D'OR DES OUTILS ET SYNTAXE NATIVE (CRITIQUE) :
Pour utiliser un outil, tu DOIS IMPÉRATIVEMENT utiliser le format de "Function Calling" natif suivant. 

Format strict à respecter :
<|tool_call>call:nom_de_l_outil{arg:<|"|>valeur_ou_json_ici<|"|>}<tool_call|><|tool_response>

EXEMPLES D'UTILISATION :
- Pour l'explorateur de fichier: <|tool_call>call:list_files{arg:<|"|>.<|"|>}<tool_call|><|tool_response>
- Pour lire un fichier : <|tool_call>call:read_file{arg:<|"|>tools/Outil_Explorateur_Fichiers.txt<|"|>}<tool_call|><|tool_response>

RÈGLE DE FIN DE TOUR ET DE RÉPONSE (CRITIQUE) :
- ⚠️ L'utilisateur NE VOIT PAS tes outils ni les réponses du système. Tu es le SEUL à y avoir accès.
- Par conséquent, si tu trouves une information avec un outil (comme une liste de fichiers, un résultat de calcul, ou le contenu d'un document), tu DOIS LA RÉÉCRIRE EN ENTIER dans ton message pour l'utilisateur. Ne dis jamais "Je vous ai listé les fichiers" sans effectivement écrire la liste complète dans ta réponse.
- Tant que tu cherches des informations et que tu n'as pas la réponse finale, tu peux enchaîner les appels d'outils.
- Quand tu as TOUTES les informations nécessaires, RÉDIGE TA RÉPONSE COMPLÈTE à l'utilisateur.
- C'est UNIQUEMENT APRÈS avoir rédigé ta réponse finale et complète que tu dois t'arrêter d'écrire.
"""
            with open(inst_path, 'w', encoding='utf-8') as f:
                f.write(inst)

    def _load_all_agents(self):
        if not os.path.exists("agents") or not os.listdir("agents"):
            self.create_new_agent("AMMA_Bot", "Je suis AMMA Bot, l'agent système principal en charge de superviser et de t'assister dans tes projets.")
        else:
            for agent_name in os.listdir("agents"):
                agent_dir = os.path.join("agents", agent_name)
                if os.path.isdir(agent_dir):
                    role = "À définir"
                    profile_path = os.path.join(agent_dir, "profile.json")
                    if os.path.exists(profile_path):
                        try:
                            with open(profile_path, 'r', encoding='utf-8') as f:
                                profile = json.load(f)
                                role = profile.get("role", role)
                        except: pass
                        
                    self.agents[agent_name] = AMMA_Agent(
                        name=agent_name, role=role, engine=self.engine, db=self.db, sandbox=self.sandbox
                    )

    def create_new_agent(self, name, role="À définir par l'utilisateur"):
        self.agents[name] = AMMA_Agent(
            name=name, role=role, engine=self.engine, db=self.db, sandbox=self.sandbox
        )
        return True

    def delete_agent(self, name):
        if name in self.agents:
            del self.agents[name]
        
        agent_dir = os.path.join("agents", name)
        if os.path.exists(agent_dir):
            shutil.rmtree(agent_dir) # Supprime le dossier et tout son contenu
        return True