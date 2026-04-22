import json
import shutil
import os
import re
import shutil
import time
import math
from datetime import datetime # NOUVEAU : Pour horodater les messages
from database import DatabaseManager
from llm_engine import LLMEngine

class AMMA_Agent:
    def __init__(self, name, role, engine: LLMEngine, db: DatabaseManager, sandbox=None):
        self.name = name
        self.engine = engine
        self.db = db
        self.sandbox = sandbox
        self.short_term_memory = [] 
        self.has_been_woken_up = False 
        
        # 1. ON CRÉE LE DOSSIER EN PREMIER (CRITIQUE)
        self.agent_dir = os.path.join("agents", self.name)
        
        # 2. MAINTENANT ON PEUT UTILISER agent_dir POUR LE RESTE
        self.log_detailed_path = os.path.join(self.agent_dir, "log_detailed.txt")
        self.log_clean_path = os.path.join(self.agent_dir, "log_clean.txt")
        
        self.profile_path = os.path.join(self.agent_dir, "profile.json")
        self.memory_path = os.path.join(self.agent_dir, "memory.json")
        self.inbox_path = os.path.join(self.agent_dir, "inbox.json")
        self.todo_path = os.path.join(self.agent_dir, "todo.json") # NOUVEAU : La To-Do List
        self.instructions_path = os.path.join(self.agent_dir, "instructions.txt")
        self.tools_dir = "tools"
        
        self._init_agent_files(role)

    def _init_agent_files(self, initial_role):
        if not os.path.exists(self.agent_dir):
            template_dir = os.path.join("templates", "default_agent")
            if os.path.exists(template_dir):
                shutil.copytree(template_dir, self.agent_dir)
                print(f"[{self.name}] Dossier créé.")
                if os.path.exists(self.profile_path):
                    with open(self.profile_path, 'r', encoding='utf-8') as f:
                        profile_data = json.load(f)
                    profile_data["name"] = self.name
                    profile_data["role"] = initial_role
                    if os.path.exists(self.tools_dir):
                        profile_data["allowed_tools"] = [f for f in os.listdir(self.tools_dir) if f.endswith('.txt')]
                    with open(self.profile_path, 'w', encoding='utf-8') as f:
                        json.dump(profile_data, f, indent=4, ensure_ascii=False)
        
        # NOUVEAU : Création de la boite de réception vide si elle n'existe pas
        if not os.path.exists(self.inbox_path):
            with open(self.inbox_path, 'w', encoding='utf-8') as f: json.dump([], f)
            
        # NOUVEAU : Création de la To-Do List avec une consigne initiale
        if not os.path.exists(self.todo_path):
            initial_todo = [
                "📌 [GUIDE SYSTÈME] Ceci est ta To-Do List (Mémoire de travail). Ajoute tes tâches ici pour ne rien oublier, et raye-les avec l'outil approprié quand elles sont terminées."
            ]
            with open(self.todo_path, 'w', encoding='utf-8') as f: 
                json.dump(initial_todo, f, indent=4, ensure_ascii=False)

    def _get_profile_data(self):
        with open(self.profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_instructions(self):
        with open(self.instructions_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _get_available_tools_summary(self):
        if not os.path.exists(self.tools_dir):
            return "Aucun outil externe disponible."
        tool_files = [f for f in os.listdir(self.tools_dir) if f.endswith('.txt')]
        if not tool_files: return "Aucun outil externe disponible."
            
        profile = self._get_profile_data()
        allowed_tools = profile.get("allowed_tools", tool_files)
        available_tools = [f for f in tool_files if f in allowed_tools]
        
        if not available_tools:
            return "Aucun outil externe n'est autorisé pour ton profil."
            
        summary = "--- SOMMAIRE DES OUTILS DISPONIBLES ---\n"
        summary += "Si tu as besoin d'un outil, utilise <read_file> avec son chemin d'accès exact pour lire sa notice.\n"
        for file in available_tools: summary += f"- tools/{file}\n"
        return summary + "---------------------------------------\n"

    def _build_prompt(self, new_task_or_context):
        # On repasse sur un prompt système pur et classique
        prompt = "<start_of_turn>system\n"
        prompt += f"Lis attentivement tes instructions ci-dessous.\n\n--- INSTRUCTIONS DE BASE ---\n{self._get_instructions()}\n\n"
        prompt += self._get_available_tools_summary() + "\n"
        
        # --- INJECTION DE LA TO-DO LIST ---
        todo_list = []
        if os.path.exists(self.todo_path):
            try:
                with open(self.todo_path, 'r', encoding='utf-8') as f:
                    todo_list = json.load(f)
            except: pass
            
        if todo_list:
            prompt += "📝 --- TA MÉMOIRE DE TRAVAIL (TO-DO LIST) ---\n"
            prompt += "Voici les tâches que tu as notées et qui sont toujours en cours :\n"
            for idx, t in enumerate(todo_list):
                prompt += f"{idx+1}. {t}\n"
            prompt += "N'oublie pas de les rayer avec <complete_task> quand elles sont achevées.\n---------------------------------------------\n\n"
        # --------------------------------------------

        # LA CLOCHETTE DE NOTIFICATION
        inbox_count = 0
        if os.path.exists(self.inbox_path):
            try:
                with open(self.inbox_path, 'r', encoding='utf-8') as f:
                    # --- MISE À JOUR : Ne compter que les messages non lus ---
                    messages = json.load(f)
                    messages_non_lus = [m for m in messages if not m.get("is_read", False)]
                    inbox_count = len(messages_non_lus)
            except: pass
            
        if inbox_count > 0:
            prompt += f"🔔 [ALERTE SYSTÈME AUTOMATIQUE] Tu as {inbox_count} message(s) dans ta boîte de réception. Utilise IMMÉDIATEMENT ton outil read_inbox pour les lire. RÈGLES SUR LA MESSAGERIE : 1. PROPRIÉTÉ : Cette boîte t'appartient à TOI. Ne dis jamais à l'utilisateur \"J'ai lu votre boîte\". 2. Si un collègue te demande d'accomplir une tâche, exécute-la D'ABORD avec tes outils. 3. Une fois terminée, envoie-lui le résultat via contact_agent (si demandé). 4. INTERDICTION DE DEVINER : Lis la notice de contact_agent dans tools/ avant de l'utiliser."
        
        prompt += f"--- TON IDENTITÉ ---\n{json.dumps(self._get_profile_data(), indent=2, ensure_ascii=False)}\n-----------------------------\n<end_of_turn>\n"
        
        # ⚠️ CORRECTION CRITIQUE : J'ai totalement supprimé la fausse phrase "J'ai compris..." 
        # qui lui donnait le mauvais exemple. L'historique commencera directement !
            
        if self.short_term_memory:
            for msg in self.short_term_memory[-12:]: 
                if msg["role"] == "user": prompt += f"<start_of_turn>user\n{msg['content']}<end_of_turn>\n"
                elif msg["role"] == "ai": prompt += f"<start_of_turn>model\n{msg['content']}<end_of_turn>\n"
                elif msg["role"] == "system": 
                    # --- NOUVEAU : On gère le conflit de la directive ---
                    prompt += f"<start_of_turn>system\n[SYSTÈME] :\n{msg['content']}"
                    if "🔔 [ALERTE SYSTÈME AUTOMATIQUE]" not in msg["content"]:
                        prompt += "\n\n-> RAPPEL DE LA DIRECTIVE : Si tu as fini de rassembler tes informations pour répondre à l'utilisateur, n'utilise plus d'outil et adresse-toi directement à lui. Sinon, continue tes recherches sans répéter la même action."
                    prompt += "<end_of_turn>\n"
                    # ----------------------------------------------------
            
        if new_task_or_context: prompt += f"<start_of_turn>user\n{new_task_or_context}<end_of_turn>\n"
        
        # On lui donne la parole pour sa VRAIE première réponse
        prompt += "<start_of_turn>model\n"
        return prompt

    def _write_logs(self, is_user, text):
        import datetime
        import re
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. LOG DÉTAILLÉ (On garde absolument tout pour le débogage)
        role_detailed = "👤 Vous" if is_user else f"🤖 {self.name} (Brut)"
        with open(self.log_detailed_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {role_detailed} :\n{text}\n\n{'-'*50}\n")
            
        # 2. LOG ÉPURÉ (La version propre)
        role_clean = "👤 Vous" if is_user else f"🤖 {self.name}"
        clean_text = text
        
        if not is_user:
            # Supprime tout ce qui est entre des balises (ex: <think>...</think>, <contact_agent>...</contact_agent>)
            clean_text = re.sub(r'<([a-zA-Z_]+)>.*?</\1>', '', clean_text, flags=re.DOTALL)
            # Nettoie les balises orphelines restantes (ex: <status>)
            clean_text = re.sub(r'<[^>]+>', '', clean_text)
            clean_text = clean_text.strip()
            
        # On écrit dans le log épuré SEULEMENT s'il reste du texte !
        if clean_text: 
            with open(self.log_clean_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {role_clean} :\n{clean_text}\n\n{'-'*50}\n")

    def execute_task(self, task, ui_callback=None, peer_agents=None):        
        self._write_logs(is_user=True, text=task)  # <--- NOUVEAU : On logue le message de l'utilisateur
        
        # --- Injection automatique de l'historique ---
        if not self.has_been_woken_up:
            self.has_been_woken_up = True
            
            # Le script Python lit l'historique à la place de l'agent
            log_path = self.log_detailed_path
            historique = "Aucun historique récent."
            
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    # On garde uniquement les 4000 derniers caractères pour ne pas surcharger la RAM
                    historique = content[-4000:] if len(content) > 4000 else content
            
            msg_reveil = f"Tu viens d'être rechargé en mémoire. Pour te remettre immédiatement dans le contexte, voici un extrait de tes dernières interactions :\n\n<historique_recent>\n{historique}\n</historique_recent>\n\nPrends note de ce contexte silencieusement. Si une ALERTE SYSTÈME suit ce message, tu dois la traiter en priorité absolue."
            
            self.short_term_memory.append({"role": "system", "content": msg_reveil})
            if ui_callback: ui_callback(f"\n[⏰ {self.name} sort du mode veille et charge son contexte...]\n\n")
        # -------------------------------------------------------

        # --- NOUVEAU : On donne le vrai rôle au déclencheur du Watchdog ---
        if task.startswith("🔔 [ALERTE SYSTÈME AUTOMATIQUE]"):
            self.short_term_memory.append({"role": "system", "content": task})
        else:
            self.short_term_memory.append({"role": "user", "content": task})
        # ------------------------------------------------------------------
        
        task_finished = False
        loop_counter = 0     
        final_ui_output = "" 
        action_history = []
        
        while not task_finished and loop_counter < 20:
            if self.engine.interrupted:
                final_ui_output += "\n[🛑 Processus d'autonomie interrompu]\n"
                break

            loop_counter += 1
            prompt = self._build_prompt("")
            
            response = self.engine.generate(prompt, agent_name=self.name, stream_callback=ui_callback)
            
            if "<start_of_turn>user" in response: response = response.split("<start_of_turn>user")[0]
            
            # --- LE GREFFIER ARCHIVE LA RÉPONSE ---
            self._write_logs(is_user=False, text=response)
            # -------------------------------------------------------
            
            # --- AUTO-RELANCE APRÈS LE BOUCLIER ---
            if "[ALERTE SYSTÈME" in response:
                if ui_callback: ui_callback("\n[⚙️ Système : Bégaiement détecté, relance automatique de l'agent...]\n")
                
                # 1. On sauvegarde sa phrase ratée dans sa mémoire courte
                self.short_term_memory.append({"role": "model", "content": response}) 
                
                # 2. On ajoute une "fausse" directive utilisateur pour le forcer à réagir
                instruction_reprise = "Système : Interruption confirmée. Tu tournais en boucle. Reprends ton explication ou ta tâche proprement depuis le début, sans répéter la même chose."
                self.short_term_memory.append({"role": "user", "content": instruction_reprise})
                
                # 3. On relance immédiatement la boucle de réflexion !
                continue
            # ------------------------------------------------
            
            clean_response = response.replace("<end_of_turn>", "").replace("</start_of_turn>", "").replace("<start_of_turn>model\n", "").replace("<start_of_turn>model", "").replace("<start_of_turn>", "").strip()
            
            # 1. On extrait l'action brute en supprimant TOTALEMENT la pensée native de la vue UI
            action_text = re.sub(r'<\|channel>thought.*?<channel\|>', '', clean_response, flags=re.DOTALL).strip()
            
            # --- MÉMOIRE À COURT TERME (Mode Agent) ---
            # On stocke la réponse exacte de Gemma (avec ses pensées natives intactes) dans la mémoire
            if clean_response.strip():
                if self.short_term_memory and self.short_term_memory[-1]["role"] == "ai":
                    self.short_term_memory[-1]["content"] += f"\n\n{clean_response}"
                else:
                    self.short_term_memory.append({"role": "ai", "content": clean_response})
            # ------------------------------------------

            # --- LE PARSEUR NATIF "FUNCTION CALLING" GEMMA 4 ---
            active_tool_name = None
            tool_argument = ""
            
            # On cherche la syntaxe stricte : <|tool_call>call:nom_outil{arg:<|"|>valeur<|"|>}<tool_call|>
            # Note : on rend le "arg:" optionnel au cas où l'agent l'oublie pour un outil sans argument (comme read_inbox)
            tool_match = re.search(r'<\|tool_call>call:([a-zA-Z0-9_.-]+)(?:\{(?:arg:<\|"\|>(.*?)<\|"\|>)?\})?<tool_call\|>', action_text, re.DOTALL)
            
            if tool_match:
                active_tool_name = tool_match.group(1) # ex: "list_files"
                tool_argument = tool_match.group(2).strip() if tool_match.group(2) else ""
            
            # --- PRÉPARATION DE L'AFFICHAGE UI ---
            display_response = action_text.replace("<status>en cours</status>", "").replace("<status>fini</status>", "").strip()
            
            # Si un outil s'exécute, on efface proprement sa syntaxe barbare de la vue utilisateur
            if active_tool_name:
                tool_regex = r'<\|tool_call>.*?(?:<\|tool_response>|$)'
                display_response = re.sub(tool_regex, '', display_response, flags=re.DOTALL).strip()

            if display_response:
                final_ui_output += f"{display_response}\n\n"
            # -------------------------------------

            tool_used = False
            log_system = ""
            current_action = "none"

            if active_tool_name:
                
                if active_tool_name == "list_files":
                    folder_path = tool_argument
                    current_action = f"list_{folder_path}"
                    if ".." in folder_path: 
                        log_system = "Erreur : Accès refusé."
                    else:
                        full_path = os.path.abspath(os.path.join(os.getcwd(), folder_path))
                        if os.path.exists(full_path) and os.path.isdir(full_path):
                            items = os.listdir(full_path)
                            formatted_items = [f"📁 [DOSSIER] {i}" if os.path.isdir(os.path.join(full_path, i)) else f"📄 [FICHIER] {i}" for i in items]
                            log_system = f"Contenu du dossier '{folder_path}' :\n" + "\n".join(formatted_items)
                        else: 
                            log_system = f"Erreur : Le dossier '{folder_path}' n'existe pas."
                    tool_used = True
                        
                elif active_tool_name == "read_file":
                    file_path = tool_argument
                    current_action = f"read_{file_path}"
                    if ".." in file_path: 
                        log_system = "Erreur : Accès refusé."
                    else:
                        full_path = os.path.abspath(os.path.join(os.getcwd(), file_path))
                        if os.path.exists(full_path) and os.path.isfile(full_path):
                            try:
                                file_size = os.path.getsize(full_path)
                                if file_size > 20000:
                                    log_system = (
                                        f"⚠️ [SYSTÈME] : Le fichier '{file_path}' est trop volumineux ({file_size} octets) "
                                        f"pour être lu entièrement avec 'read_file'.\n"
                                        f"INSTRUCTION : Utilise plutôt l'outil 'read_pages' "
                                        f"sur une portion spécifique du document."
                                    )
                                else:
                                    with open(full_path, 'r', encoding='utf-8') as f: 
                                        log_system = f"Contenu de '{file_path}':\n{f.read()}"
                            except Exception as e:
                                log_system = f"Erreur lors de la lecture : {e}"
                        else: 
                            log_system = f"Erreur : Impossible de trouver '{file_path}'."
                    tool_used = True

                elif active_tool_name == "edit_file":
                    try:
                        edit_data = json.loads(tool_argument)
                        file_path = edit_data.get("file", "")
                        search_text = edit_data.get("search", "")
                        replace_text = edit_data.get("replace", "")
                        current_action = f"edit_{file_path}"
                        if ".." in file_path: 
                            log_system = "Erreur : Accès refusé."
                        else:
                            full_path = os.path.abspath(os.path.join(os.getcwd(), file_path))
                            if os.path.exists(full_path) and os.path.isfile(full_path):
                                with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
                                count = content.count(search_text)
                                if count == 1:
                                    with open(full_path, 'w', encoding='utf-8') as f: f.write(content.replace(search_text, replace_text))
                                    log_system = f"Succès : Le fichier '{file_path}' a été mis à jour."
                                elif count == 0: 
                                    log_system = f"Erreur : Le texte recherché n'existe pas."
                                else: 
                                    log_system = f"Erreur : Le texte recherché apparaît {count} fois. Bloqué par sécurité."
                            else: 
                                log_system = f"Erreur : Le fichier '{file_path}' est introuvable."
                        tool_used = True
                    except:
                        log_system = "Erreur : Format JSON invalide dans edit_file."
                        tool_used = True

                elif active_tool_name == "run_python":
                    clean_code = tool_argument.replace("```python", "").replace("```", "").replace("\\n", "\n").strip()
                    current_action = f"python_{clean_code[:10]}"
                    res = self.sandbox.execute_python_code(clean_code)
                    log_system = f"Résultat console Python :\n{res['output']}\n{res['error']}".strip()
                    tool_used = True
                        
                elif active_tool_name == "calculate":
                    expression = tool_argument
                    current_action = f"calc_{expression[:10]}"
                    try:
                        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
                        result = eval(expression, {"__builtins__": {}}, allowed_names)
                        log_system = f"Résultat de la calculatrice : {result}"
                    except Exception as e:
                        log_system = f"Erreur de calcul : {e}. Utilise uniquement des chiffres et opérateurs valides."
                    tool_used = True

                elif active_tool_name == "search_text":
                    try:
                        data = json.loads(tool_argument)
                        filepath = data.get("file", "").strip()
                        keyword = data.get("keyword", "")
                        
                        if not os.path.exists(filepath):
                            log_system = f"❌ Erreur : Le fichier {filepath} n'existe pas."
                        elif not keyword:
                            log_system = "❌ Erreur : Le mot-clé (keyword) est vide."
                        else:
                            found_lines = []
                            with open(filepath, 'r', encoding='utf-8') as f:
                                for line_num, line in enumerate(f, 1):
                                    if keyword.lower() in line.lower():
                                        found_lines.append(str(line_num))
                            
                            if found_lines:
                                results = ", ".join(found_lines[:50])
                                log_system = f"✅ Mot '{keyword}' trouvé aux lignes : {results}"
                                if len(found_lines) > 50:
                                    log_system += " (et d'autres...)"
                            else:
                                log_system = f"❌ Le mot '{keyword}' n'a pas été trouvé dans ce fichier."
                    except Exception as e:
                        log_system = f"❌ Erreur JSON ou lecture : {e}"
                    tool_used = True

                elif active_tool_name == "read_pages":
                    try:
                        data = json.loads(tool_argument)
                        filepath = data.get("file", "").strip()
                        start_line = int(data.get("start", 1))
                        end_line = int(data.get("end", 100))
                        
                        if end_line - start_line > 500:
                            end_line = start_line + 500
                            
                        if not os.path.exists(filepath):
                            log_system = f"❌ Erreur : Le fichier {filepath} n'existe pas."
                        else:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                lines = f.readlines()[start_line-1 : end_line]
                                content = "".join(lines)
                                
                            if content.strip():
                                log_system = f"📄 Contenu des lignes {start_line} à {end_line} :\n{content}"
                            else:
                                log_system = "❌ Ces lignes sont vides ou n'existent pas."
                    except Exception as e:
                        log_system = f"❌ Erreur JSON, syntaxe ou limites : {e}"
                    tool_used = True                

                elif active_tool_name == "manage_file":
                    try:
                        data = json.loads(tool_argument)
                        action = data.get("action")
                        path = data.get("path", "").strip()
                        content = data.get("content", "")
                        current_action = f"file_{action}"

                        if ".." in path or os.path.isabs(path):
                            log_system = "❌ ALERTE SÉCURITÉ : Action refusée."
                        elif not path:
                            log_system = "❌ Erreur : Le chemin (path) est vide."
                        else:
                            if action == "create_folder":
                                os.makedirs(path, exist_ok=True)
                                log_system = f"✅ Dossier créé avec succès : {path}"
                            elif action == "delete_folder":
                                if os.path.exists(path) and os.path.isdir(path):
                                    shutil.rmtree(path)
                                    log_system = f"✅ Dossier supprimé : {path}"
                                else:
                                    log_system = f"❌ Erreur : Le dossier {path} n'existe pas."
                            elif action == "create_file":
                                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                                with open(path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                log_system = f"✅ Fichier créé avec succès : {path}"
                            elif action == "delete_file":
                                if os.path.exists(path) and os.path.isfile(path):
                                    os.remove(path)
                                    log_system = f"✅ Fichier supprimé : {path}"
                                else:
                                    log_system = f"❌ Erreur : Le fichier {path} n'existe pas."
                            else:
                                log_system = f"❌ Erreur : Action '{action}' inconnue."
                    except Exception as e:
                        log_system = f"❌ Erreur JSON ou Système : {e}"
                    tool_used = True

                elif active_tool_name == "read_inbox":
                    current_action = "read_inbox"
                    if os.path.exists(self.inbox_path):
                        with open(self.inbox_path, 'r', encoding='utf-8') as f:
                            messages = json.load(f)
                        
                        # --- NOUVEAU : On filtre pour ne prendre que les messages non lus ---
                        messages_non_lus = [m for m in messages if not m.get("is_read", False)]
                        
                        if not messages_non_lus:
                            log_system = "Ta boîte de réception est vide ou tous les messages ont déjà été lus."
                        else:
                            log_system = "📬 NOUVEAUX MESSAGES :\n"
                            for idx, msg in enumerate(messages_non_lus):
                                log_system += f"--- Message {idx+1} ---\nDe : {msg['expediteur']}\nDate : {msg['date']}\nContenu : {msg['contenu']}\n\n"
                                msg["is_read"] = True # On le marque comme lu !
                            
                            # On sauvegarde le fichier complet (lus et non lus) sans rien effacer
                            with open(self.inbox_path, 'w', encoding='utf-8') as f: 
                                json.dump(messages, f, indent=4, ensure_ascii=False)
                                
                            log_system += "(Tous ces messages ont été marqués comme lus dans tes archives)."
                    else:
                        log_system = "Erreur : Fichier inbox introuvable."
                    tool_used = True
                
                elif active_tool_name == "contact_agent":
                    current_action = "contact_agent"
                    try:
                        # 1. On parse le JSON
                        contact_data = json.loads(tool_argument)
                        
                        # 2. VÉRIFICATION STRICTE DES CLÉS
                        target_agent = contact_data.get("agent")
                        message_content = contact_data.get("message")
                        
                        if not target_agent or not message_content:
                            log_system = (
                                "❌ Erreur JSON : Format invalide. Tu as inventé des clés ou oublié les bonnes.\n"
                                "RAPPEL : L'argument DOIT être un JSON contenant STRICTEMENT les clés 'agent' et 'message'.\n"
                                "Exemple valide : {\"agent\": \"Alice\", \"message\": \"Bonjour !\"}"
                            )
                        # 3. VÉRIFICATION DE L'AUTO-CONTACT
                        elif target_agent.lower() == self.name.lower():
                            log_system = "❌ Erreur : Tu ne peux pas te contacter toi-même !"
                        # 4. ENVOI DU MESSAGE
                        else:
                            target_inbox_path = os.path.join("agents", target_agent, "inbox.json")
                            if not os.path.exists(os.path.dirname(target_inbox_path)):
                                log_system = f"❌ Erreur : L'agent '{target_agent}' est introuvable. As-tu bien respecté les majuscules ? Utilise 'list_files' sur le dossier 'agents' pour vérifier."
                            else:
                                target_inbox = []
                                if os.path.exists(target_inbox_path):
                                    with open(target_inbox_path, 'r', encoding='utf-8') as f:
                                        try: target_inbox = json.load(f)
                                        except: target_inbox = []
                                
                                nouveau_message = {
                                    "expediteur": self.name,
                                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "contenu": message_content,
                                    "is_read": False # <--- CRITIQUE POUR LE WATCHDOG
                                }
                                target_inbox.append(nouveau_message)
                                
                                with open(target_inbox_path, 'w', encoding='utf-8') as f:
                                    json.dump(target_inbox, f, indent=4, ensure_ascii=False)
                                
                                log_system = f"Succès : Ton message a été déposé dans la boîte de {target_agent}."
                                if ui_callback: ui_callback(f"\n[✉️ Message déposé dans la boite de {target_agent}]\n")
                                
                    except json.JSONDecodeError:
                        log_system = "❌ Erreur : Format JSON invalide. Vérifie tes guillemets et tes accolades."
                    except Exception as e:
                        log_system = f"❌ Erreur inattendue dans contact_agent : {e}"
                        
                    tool_used = True
                
                elif active_tool_name == "add_task":
                    new_task = tool_argument
                    current_action = f"add_task"
                    if hasattr(self, 'todo_path') and os.path.exists(self.todo_path):
                        with open(self.todo_path, 'r', encoding='utf-8') as f:
                            todos = json.load(f)
                        todos.append(new_task)
                        with open(self.todo_path, 'w', encoding='utf-8') as f:
                            json.dump(todos, f, indent=4, ensure_ascii=False)
                        log_system = f"Succès : La tâche '{new_task}' a été ajoutée à ta To-Do List."
                    else:
                         log_system = "Erreur: Fichier To-Do introuvable."
                    tool_used = True
                    
                elif active_tool_name == "complete_task":
                    done_task = tool_argument
                    current_action = f"complete_task"
                    if hasattr(self, 'todo_path') and os.path.exists(self.todo_path):
                        with open(self.todo_path, 'r', encoding='utf-8') as f:
                            todos = json.load(f)
                        
                        found = False
                        for t in todos:
                            if done_task.lower() in t.lower() or t.lower() in done_task.lower():
                                todos.remove(t)
                                found = True
                                break
                                
                        with open(self.todo_path, 'w', encoding='utf-8') as f:
                            json.dump(todos, f, indent=4, ensure_ascii=False)
                            
                        if found:
                            log_system = f"Succès : La tâche a été rayée de ta To-Do List."
                        else:
                            log_system = f"Erreur : Impossible de trouver une tâche correspondant à '{done_task}'."
                    else:
                        log_system = "Erreur: Fichier To-Do introuvable."
                    tool_used = True

            # --- LE FILET DE SÉCURITÉ ABSOLU (Syntaxe & Outil inconnu) ---
            if "<tool_call|>" in clean_response and not tool_used:
                if not active_tool_name:
                    erreur_motif = "Erreur de formatage. Tu as oublié le délimiteur <|\"|> autour de ton argument ou mal écrit les balises."
                else:
                    erreur_motif = f"L'outil '{active_tool_name}' n'existe pas dans le système."

                log_system = (
                    f"❌ ERREUR OUTIL : Ton appel a été rejeté par le parseur.\n"
                    f"Raison : {erreur_motif}\n\n"
                    "RAPPEL CRITIQUE : Ne nettoie pas la syntaxe ! Dans Gemma 4, tu DOIS IMPÉRATIVEMENT encadrer ton argument (même si c'est du JSON) avec les balises de protection <|\"|> pour que le système puisse le lire sans erreur.\n"
                    "FAUX : {arg:{\"agent\": \"Bob\"}}\n"
                    "VRAI : {arg:<|\"|>{\"agent\": \"Bob\"}<|\"|>}\n\n"
                    "Recommence ton appel en ajoutant exactement <|\"|> avant et après ton argument, ou utilise 'read_file' pour lire les notices dans 'tools/' si tu as un doute sur le nom de l'outil. INTERDICTION D'ABANDONNER, Corrige immédiatement ta syntaxe et relance l'outil."
                )
                
                alerte_syntaxe = f"\n<|tool_response>response:erreur{{result:<|\"|>\n{log_system}\n<|\"|>}}<tool_response|>\n"
                
                if self.short_term_memory and self.short_term_memory[-1]["role"] == "ai":
                    self.short_term_memory[-1]["content"] += alerte_syntaxe
                else:
                    self.short_term_memory.append({"role": "ai", "content": alerte_syntaxe})
                
                system_display_full = f"\n\n---SYSTEM_START---\n⚙️ [SYSTÈME] :\n{log_system}\n---SYSTEM_END---\n\n"
                final_ui_output += system_display_full
                self._write_logs(is_user=False, text=f"⚙️ [ERREUR OUTIL] :\n{log_system}")
                if ui_callback: ui_callback(f"\n\n⚙️ [SYSTÈME] :\n{log_system}\n\n")
                
                continue
            # -------------------------------------------------

            if tool_used:
                action_history.append(current_action)
                if len(action_history) >= 3 and action_history[-1] == action_history[-2] == action_history[-3]:
                    log_system += "\n\n⚠️ ALERTE SYSTÈME : Tu tournes en rond. Change de stratégie ou réponds directement à l'utilisateur."
                    action_history.clear() 
                
                # --- LE RETOUR D'OUTIL NATIF GEMMA 4 ---
                # Injection de la balise <|tool_response> que le modèle attend
                native_tool_response = f"\n<|tool_response>response:{active_tool_name}{{result:<|\"|>\n{log_system}\n<|\"|>}}<tool_response|>\n"
                
                if self.short_term_memory and self.short_term_memory[-1]["role"] == "ai":
                    self.short_term_memory[-1]["content"] += native_tool_response
                else:
                    self.short_term_memory.append({"role": "ai", "content": native_tool_response})
                # --------------------------------------------------

                system_display_full = f"\n\n---SYSTEM_START---\n⚙️ [SYSTÈME] :\n{log_system}\n---SYSTEM_END---\n\n"
                system_display_ui = f"\n\n⚙️ [SYSTÈME] :\n{log_system}\n\n"
                
                self._write_logs(is_user=False, text=f"⚙️ [RETOUR OUTIL / SYSTÈME] :\n{log_system}")

                if ui_callback: ui_callback(system_display_ui)
                final_ui_output += system_display_full 

            # Vérification de fin de tâche
            if ("<status>en cours</status>" in clean_response or tool_used) and not self.engine.interrupted:
                task_finished = False 
                if ui_callback: ui_callback("\n[...L'agent réfléchit à la suite...]\n\n")
            else:
                task_finished = True
                
                # --- LE NETTOYAGE ABSOLU (Mode Humain) ---
                for i in range(len(self.short_term_memory)):
                    if self.short_term_memory[i]["role"] == "ai":
                        mem_content = self.short_term_memory[i]["content"]
                        cleaned_mem = re.sub(
                            r'<\|channel>thought.*?<channel\|>', 
                            '', 
                            mem_content, 
                            flags=re.DOTALL
                        ).strip()
                        self.short_term_memory[i]["content"] = cleaned_mem
                # --------------------------------------------------

            loop_counter += 1  

        # --- LE GRAND NETTOYAGE (UI) ---
        final_clean_text = final_ui_output
        
        # Le regex nettoie la syntaxe natif et le status
        final_clean_text = re.sub(r'<\|tool_call>.*?(?:<\|tool_response>|$)', '', final_clean_text, flags=re.DOTALL)
        final_clean_text = re.sub(r'---SYSTEM_START---.*?---SYSTEM_END---', '', final_clean_text, flags=re.DOTALL)
        final_clean_text = re.sub(r'\[✉️.*?\]\n', '', final_clean_text, flags=re.DOTALL)
        final_clean_text = re.sub(r'\[\.\.\.L\'agent réfléchit à la suite\.\.\.\]\n\n', '', final_clean_text)
        final_clean_text = re.sub(r'\n{3,}', '\n\n', final_clean_text).strip()
        final_clean_text = re.sub(r'<status>.*?>?', '', final_clean_text)

        return final_clean_text, final_ui_output.strip()