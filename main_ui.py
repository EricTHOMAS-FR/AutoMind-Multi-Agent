import customtkinter as ctk
import tkinter.messagebox as messagebox
import threading
import json
import os
import time
from datetime import datetime
from orchestrator import AMMA_Orchestrator

# --- SÉCURITÉ : Auto-création des dossiers vitaux ---
os.makedirs("models", exist_ok=True)
os.makedirs("tools", exist_ok=True)
# ----------------------------------------------------

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AMMA_UI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AMMA - AutoMind Multi-Agent (Optimisé pour Gemma 4)")
        self.geometry("1200x800")
        
        # 1. DÉTECTION INTELLIGENTE DES MODÈLES
        self.model_files = [f for f in os.listdir("models") if f.endswith('.gguf')] if os.path.exists("models") else []
        self.model_files.sort()

        if not self.model_files: 
            self.model_files = ["Aucun modèle"]
            self.best_default_model = "Aucun modèle"
        else:
            self.best_default_model = self.model_files[0]
            for m in self.model_files:
                if "gemma-4" in m.lower():
                    self.best_default_model = m
                    break

        # --- LE PATCH ULTIME : AUTO-GUÉRISON DE LA CONFIGURATION ---
        self.config = self.load_config()
        saved_model = self.config.get("default_model", "auto")
        
        # Si la config dit "auto" ou cherche un modèle supprimé, on met à jour le fichier EN DUR.
        if saved_model == "auto" or saved_model == "" or saved_model not in self.model_files:
            self.config["default_model"] = self.best_default_model
            try:
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4)
            except Exception:
                pass
        # -----------------------------------------------------------

        # 2. ON CHARGE L'ORCHESTRATEUR (Il lira maintenant le VRAI nom du modèle !)
        self.orchestrator = AMMA_Orchestrator()
        self.config = self.load_config()
        
        # 3. INITIALISATION DES VARIABLES D'ÉTAT
        self.current_selected_agent_editor = None 
        self.current_selected_tool = None 
        self.current_chat_view = "Console"
        self.is_generating = False 
        
        # 4. THÈME ET HISTORIQUES (Message console modifié)
        self.default_btn_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        self.default_btn_hover = ctk.ThemeManager.theme["CTkButton"]["hover_color"]
        
        self.chat_histories = {
            "Console": "--- CONSOLE SYSTÈME ---\nBienvenue dans AMMA. Le système est prêt.\nNote : Ce projet est conçu pour fonctionner nativement avec Gemma 4.\n\n"
        }
        for agent in self.orchestrator.agents:
            self.chat_histories[agent] = f"--- Début de la conversation avec {agent} ---\n\n"
        
        # 5. CONFIGURATION DU GRID
        self.grid_columnconfigure(0, weight=0) 
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)
        
        # 6. CONSTRUCTION DE L'INTERFACE
        self.build_sidebar()
        self.build_main_frames()
        self.temp_slider.set(self.config.get("temperature", 0.45) * 100)
        self.penalty_slider.set(self.config.get("repeat_penalty", 1.08) * 100)
        self.update_engine_params() # Pour mettre à jour les labels
        self.select_frame("Chat")
        
        # 7. CHARGEMENT DU MODÈLE PAR DÉFAUT
        default_m = self.config.get("default_model", "Aucun modèle")
        if default_m != "Aucun modèle":
            if hasattr(self, 'model_var'):
                self.model_var.set(default_m)
            self.on_model_change(default_m)
        
        # 8. LANCEMENT DU WATCHDOG ET DU HEARTBEAT
        threading.Thread(target=self.watchdog_loop, daemon=True).start()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()

    def load_config(self):
        # Valeurs de secours si le fichier n'existe pas
        defaults = {
            "default_model": self.model_files[0] if self.model_files else "",
            "temperature": 0.45,
            "repeat_penalty": 1.08,
            "heartbeat_enabled": False,     # <-- NOUVEAU : Désactivé par défaut
            "heartbeat_interval": 30        # <-- NOUVEAU : 30 minutes par défaut
        }
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    data = json.load(f)
                    defaults.update(data) # On fusionne avec ce qui est enregistré
            except: pass
        return defaults

    def save_config(self, key, value):
        config = self.load_config()
        config[key] = value
        with open("config.json", "w") as f: json.dump(config, f, indent=4)

    def save_heartbeat_settings(self, _=None):
        val = int(self.hb_slider.get())
        enabled = self.heartbeat_switch.get() == 1
        self.hb_label.configure(text=f"Intervalle : {val} min")
        
        self.save_config("heartbeat_enabled", enabled)
        self.save_config("heartbeat_interval", val)
    # ---------------------------------------        

    def build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="AMMA Core", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.pack(pady=(20, 30), padx=20)
        
        self.btn_nav_chat = ctk.CTkButton(self.sidebar_frame, text="💬 Discussions", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", command=lambda: self.select_frame("Chat"))
        self.btn_nav_chat.pack(pady=5, padx=20, fill="x")

        self.btn_nav_agents = ctk.CTkButton(self.sidebar_frame, text="🤖 Agents (Editeur)", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", command=lambda: self.select_frame("Agents"))
        self.btn_nav_agents.pack(pady=5, padx=20, fill="x")
        
        self.btn_nav_tools = ctk.CTkButton(self.sidebar_frame, text="🛠️ Outils & API", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", command=lambda: self.select_frame("Tools"))
        self.btn_nav_tools.pack(pady=5, padx=20, fill="x")

        self.btn_nav_settings = ctk.CTkButton(self.sidebar_frame, text="⚙️ Paramètres", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", command=lambda: self.select_frame("Settings"))
        self.btn_nav_settings.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=50).pack(expand=True)

    def build_main_frames(self):
        # PAGE CHAT
        self.frame_chat = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_chat.grid_rowconfigure(0, weight=1)
        self.frame_chat.grid_columnconfigure(0, weight=0)
        self.frame_chat.grid_columnconfigure(1, weight=1)
        
        self.chat_list_col = ctk.CTkFrame(self.frame_chat, width=250, corner_radius=0)
        self.chat_list_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ctk.CTkLabel(self.chat_list_col, text="Filtres", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))
        
        self.filter_type_var = ctk.StringVar(value="Tous")
        self.filter_type = ctk.CTkOptionMenu(self.chat_list_col, variable=self.filter_type_var, values=["Tous", "User-Agent", "Agent-Agent"], command=lambda _: self.refresh_chat_sidebar())
        self.filter_type.pack(pady=5, padx=10, fill="x")
        
        self.filter_agent_var = ctk.StringVar(value="Tous les agents")
        self.filter_agent_dropdown = ctk.CTkOptionMenu(self.chat_list_col, variable=self.filter_agent_var, values=["Tous les agents"] + list(self.orchestrator.agents.keys()), command=lambda _: self.refresh_chat_sidebar())
        self.filter_agent_dropdown.pack(pady=(5, 15), padx=10, fill="x")
        
        self.btn_console_fixed = ctk.CTkButton(self.chat_list_col, text="💻 Console Système", fg_color="darkred", hover_color="red", command=lambda: self.switch_chat_view("Console"))
        self.btn_console_fixed.pack(pady=(10, 5), padx=10, fill="x")
        ctk.CTkFrame(self.chat_list_col, height=2, fg_color=("gray70", "gray30")).pack(fill="x", padx=10, pady=5)
        
        self.conversations_frame = ctk.CTkScrollableFrame(self.chat_list_col, label_text="Conversations des Agents")
        self.conversations_frame.pack(expand=True, fill="both", padx=5, pady=5)
        
        self.chat_view_col = ctk.CTkFrame(self.frame_chat, fg_color="transparent")
        self.chat_view_col.grid(row=0, column=1, sticky="nsew")
        self.chat_view_col.grid_rowconfigure(1, weight=1)
        self.chat_view_col.grid_columnconfigure(0, weight=1)
        
        self.chat_title_label = ctk.CTkLabel(self.chat_view_col, text="💻 Console Système", font=ctk.CTkFont(size=18, weight="bold"))
        self.chat_title_label.grid(row=0, column=0, pady=10, sticky="w", padx=20)
        
        self.chat_display = ctk.CTkTextbox(self.chat_view_col, wrap="word", font=ctk.CTkFont(size=14))
        self.chat_display.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.chat_display.configure(state="disabled") 
        
        self.chat_input_frame = ctk.CTkFrame(self.chat_view_col, fg_color="transparent")
        self.chat_input_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.chat_input_frame.grid_columnconfigure(0, weight=1)
        self.chat_input = ctk.CTkEntry(self.chat_input_frame, placeholder_text="Envoyez un message...", height=40)
        self.chat_input.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="ew")
        self.chat_input.bind("<Return>", lambda event: self.send_chat_message())
        self.chat_btn = ctk.CTkButton(self.chat_input_frame, text="Envoyer", width=100, height=40, command=self.send_chat_message)
        self.chat_btn.grid(row=0, column=1, padx=0, pady=0)

        # PAGE AGENTS
        self.frame_agents = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_agents.grid_rowconfigure(0, weight=1)
        self.frame_agents.grid_columnconfigure(0, weight=1)
        self.frame_agents.grid_columnconfigure(1, weight=3)
        
        self.agent_controls_col = ctk.CTkFrame(self.frame_agents, fg_color="transparent")
        self.agent_controls_col.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        self.btn_create_agent = ctk.CTkButton(self.agent_controls_col, text="➕ Créer un nouvel Agent", fg_color="green", hover_color="darkgreen", command=self.ui_create_agent_popup)
        self.btn_create_agent.pack(pady=(0, 20), fill="x")
        
        ctk.CTkLabel(self.agent_controls_col, text="Sélectionner l'agent à éditer :", anchor="w").pack(fill="x", pady=(0, 5))
        self.agent_edit_var = ctk.StringVar(value="")
        self.agent_edit_dropdown = ctk.CTkOptionMenu(self.agent_controls_col, variable=self.agent_edit_var, values=[], command=self.view_agent_files)
        self.agent_edit_dropdown.pack(pady=(0, 20), fill="x")

        # Configuration du modèle spécifique
        ctk.CTkLabel(self.agent_controls_col, text="🧠 Modèle dédié à cet agent :", anchor="w").pack(fill="x", pady=(10, 5))
        self.agent_specific_model_var = ctk.StringVar(value="Par défaut (Global)")
        
        # --- NOUVEAU : On filtre "Aucun modèle" pour ne pas l'afficher en double ---
        agent_models_list = ["Par défaut (Global)"] + [m for m in self.model_files if m != "Aucun modèle"]
        
        self.agent_model_dropdown = ctk.CTkOptionMenu(
            self.agent_controls_col, 
            values=agent_models_list, 
            variable=self.agent_specific_model_var, 
            command=self.save_agent_specific_model
        )
        self.agent_model_dropdown.pack(pady=(0, 10), fill="x")

        # Ressort pour pousser le bouton supprimer vers le bas
        ctk.CTkFrame(self.agent_controls_col, fg_color="transparent").pack(expand=True)
        
        self.btn_delete_agent = ctk.CTkButton(self.agent_controls_col, text="🗑️ Supprimer l'agent", fg_color="red", hover_color="darkred", command=self.ui_delete_agent)
        self.btn_delete_agent.pack(pady=10, fill="x")

        # Zone d'édition des fichiers
        self.agent_dossier_col = ctk.CTkFrame(self.frame_agents)
        self.agent_dossier_col.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew")
        ctk.CTkLabel(self.agent_dossier_col, text="📂 Dossier de l'agent", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 0))
        
        self.agent_files_tabview = ctk.CTkTabview(self.agent_dossier_col)
        self.agent_files_tabview.pack(expand=True, fill="both", padx=15, pady=15)
        
        # Nouveaux onglets incluant les deux types de logs
        for tab in ["Profil", "Mémoire", "Instructions", "Log Propre", "Log Détaillé"]: 
            self.agent_files_tabview.add(tab)

        # TEXTBOX : Profil
        self.txt_profile = ctk.CTkTextbox(self.agent_files_tabview.tab("Profil"), wrap="word", font=ctk.CTkFont(family="Courier", size=13))
        self.txt_profile.pack(expand=True, fill="both", padx=10, pady=(10, 5))
        ctk.CTkButton(self.agent_files_tabview.tab("Profil"), text="💾 Sauvegarder Profil", command=lambda: self.save_agent_file("profile.json", self.txt_profile)).pack(pady=5)

        # TEXTBOX : Mémoire
        self.txt_memory = ctk.CTkTextbox(self.agent_files_tabview.tab("Mémoire"), wrap="word", font=ctk.CTkFont(family="Courier", size=13))
        self.txt_memory.pack(expand=True, fill="both", padx=10, pady=(10, 5))
        ctk.CTkButton(self.agent_files_tabview.tab("Mémoire"), text="💾 Sauvegarder Mémoire", command=lambda: self.save_agent_file("memory.json", self.txt_memory)).pack(pady=5)

        # TEXTBOX : Instructions
        self.txt_instructions = ctk.CTkTextbox(self.agent_files_tabview.tab("Instructions"), wrap="word", font=ctk.CTkFont(family="Courier", size=13))
        self.txt_instructions.pack(expand=True, fill="both", padx=10, pady=(10, 5))
        ctk.CTkButton(self.agent_files_tabview.tab("Instructions"), text="💾 Sauvegarder Instructions", command=lambda: self.save_agent_file("instructions.txt", self.txt_instructions)).pack(pady=5)

        # TEXTBOX : Log Propre (Vert)
        self.txt_log_clean = ctk.CTkTextbox(self.agent_files_tabview.tab("Log Propre"), wrap="word", font=ctk.CTkFont(family="Courier", size=13), text_color="lightgreen")
        self.txt_log_clean.pack(expand=True, fill="both", padx=10, pady=(10, 5))
        self.txt_log_clean.configure(state="disabled")

        # TEXTBOX : Log Détaillé (Cyan)
        self.txt_log_detailed = ctk.CTkTextbox(self.agent_files_tabview.tab("Log Détaillé"), wrap="word", font=ctk.CTkFont(family="Courier", size=13), text_color="cyan")
        self.txt_log_detailed.pack(expand=True, fill="both", padx=10, pady=(10, 5))
        self.txt_log_detailed.configure(state="disabled")

        # PAGE OUTILS & API (MODIFIÉE)
        self.frame_tools = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_tools.grid_columnconfigure(0, weight=1)
        self.frame_tools.grid_columnconfigure(1, weight=2)
        self.frame_tools.grid_rowconfigure(0, weight=1)
        
        self.tools_list_frame = ctk.CTkFrame(self.frame_tools)
        self.tools_list_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        ctk.CTkLabel(self.tools_list_frame, text="Outils Détectés (Dossier tools/)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.tools_scroll = ctk.CTkScrollableFrame(self.tools_list_frame)
        self.tools_scroll.pack(expand=True, fill="both", padx=10, pady=10)
        
        self.tools_right_container = ctk.CTkFrame(self.frame_tools, fg_color="transparent")
        self.tools_right_container.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew")
        self.tools_right_container.grid_rowconfigure(1, weight=1) 
        self.tools_right_container.grid_columnconfigure(0, weight=1)

        # NOUVEAU : Barre de Permissions (Haut)
        self.tools_perm_frame = ctk.CTkFrame(self.tools_right_container)
        self.tools_perm_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.tools_perm_frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(self.tools_perm_frame, text="🛡️ Accès Agent :", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        
        self.perm_agent_var = ctk.StringVar(value="Sélectionnez un outil")
        self.perm_agent_dropdown = ctk.CTkOptionMenu(self.tools_perm_frame, variable=self.perm_agent_var, command=self.load_tool_permission)
        self.perm_agent_dropdown.grid(row=0, column=1, padx=10, pady=10)

        self.perm_switch_var = ctk.IntVar(value=0)
        self.perm_switch = ctk.CTkSwitch(self.tools_perm_frame, text="Bloqué", variable=self.perm_switch_var, command=self.toggle_tool_permission)
        self.perm_switch.grid(row=0, column=2, sticky="w", padx=10, pady=10)
        self.tools_perm_frame.grid_remove() # Caché au démarrage

        # Notice de l'outil (Bas)
        self.tools_view_frame = ctk.CTkFrame(self.tools_right_container)
        self.tools_view_frame.grid(row=1, column=0, sticky="nsew")
        
        self.tool_title_label = ctk.CTkLabel(self.tools_view_frame, text="Sélectionnez un outil pour voir sa notice", font=ctk.CTkFont(size=14, slant="italic"))
        self.tool_title_label.pack(pady=10)
        
        self.tool_content_view = ctk.CTkTextbox(self.tools_view_frame, wrap="word", font=ctk.CTkFont(family="Courier", size=13))
        self.tool_content_view.pack(expand=True, fill="both", padx=15, pady=15)
        self.tool_content_view.configure(state="disabled")

        # PAGE PARAMÈTRES (MODIFIÉE)
        self.frame_settings = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        ctk.CTkLabel(self.frame_settings, text="⚙️ Paramètres du Système", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=20)

        # Conteneur central pour les réglages
        self.settings_container = ctk.CTkFrame(self.frame_settings, width=600)
        self.settings_container.pack(pady=10, padx=40, fill="x")

        # --- RÉGLAGE MODÈLE GLOBAL (Dans l'onglet Paramètres) ---
        ctk.CTkLabel(self.settings_container, text="💾 Modèle Global / Fallback", font=ctk.CTkFont(weight="bold")).pack(pady=(30, 0))
        
        # On utilise le modèle déjà calculé par l'__init__ (plus robuste)
        # Si un modèle est déjà chargé, on l'affiche, sinon on prend le meilleur par défaut
        current_val = getattr(self, "current_loaded_model", self.best_default_model)
        self.model_var = ctk.StringVar(value=current_val)
        
        self.model_dropdown = ctk.CTkOptionMenu(
            self.settings_container, 
            values=self.model_files, # Utilise la liste détectée au démarrage
            variable=self.model_var, 
            command=self.on_global_model_change
        )
        self.model_dropdown.pack(pady=10)
        ctk.CTkLabel(self.settings_container, text="Ce modèle sera utilisé par défaut par tous les agents.", font=ctk.CTkFont(size=11), text_color="gray").pack()

        # --- RÉGLAGE TEMPÉRATURE ---
        ctk.CTkLabel(self.settings_container, text="🌡️ Température (Créativité)", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 0))
        ctk.CTkLabel(self.settings_container, text="Bas = Précis/Rigide | Haut = Créatif/Aléatoire", font=ctk.CTkFont(size=11), text_color="gray").pack()
        
        self.temp_val_label = ctk.CTkLabel(self.settings_container, text="1.00", font=ctk.CTkFont(size=14, weight="bold"))
        self.temp_val_label.pack()

        self.temp_slider = ctk.CTkSlider(self.settings_container, from_=10, to=150, number_of_steps=140, command=self.update_engine_params)
        self.temp_slider.set(100) # <--- NOUVEAU : 1.00 par défaut pour Gemma 4
        self.temp_slider.pack(fill="x", padx=100, pady=10)

        # --- RÉGLAGE REPEAT PENALTY ---
        ctk.CTkLabel(self.settings_container, text="🔁 Pénalité de Répétition", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 0))
        ctk.CTkLabel(self.settings_container, text="Empêche l'IA de boucler sur les mêmes mots", font=ctk.CTkFont(size=11), text_color="gray").pack()
        
        self.penalty_val_label = ctk.CTkLabel(self.settings_container, text="1.00", font=ctk.CTkFont(size=14, weight="bold"))
        self.penalty_val_label.pack()

        self.penalty_slider = ctk.CTkSlider(self.settings_container, from_=100, to=150, number_of_steps=50, command=self.update_engine_params)
        self.penalty_slider.set(100) # <--- NOUVEAU : 1.00 par défaut (aucune pénalité requise)
        self.penalty_slider.pack(fill="x", padx=100, pady=10)

        # --- SECTION HEARTBEAT ---
        ctk.CTkLabel(self.settings_container, text="💓 Heartbeat (Réveil Automatique)", font=ctk.CTkFont(weight="bold")).pack(pady=(30, 0))
        
        self.heartbeat_var = ctk.BooleanVar(value=self.config.get("heartbeat_enabled", False))
        self.heartbeat_switch = ctk.CTkSwitch(self.settings_container, text="Activer le réveil périodique", variable=self.heartbeat_var, command=self.save_heartbeat_settings)
        self.heartbeat_switch.pack(pady=10)

        self.hb_label = ctk.CTkLabel(self.settings_container, text=f"Intervalle : {self.config.get('heartbeat_interval', 30)} min")
        self.hb_label.pack()

        self.hb_slider = ctk.CTkSlider(self.settings_container, from_=1, to=120, number_of_steps=119, command=self.save_heartbeat_settings)
        self.hb_slider.set(self.config.get("heartbeat_interval", 30))
        self.hb_slider.pack(fill="x", padx=100, pady=10)

    # --- NOUVEAU : GESTION DES PERMISSIONS D'OUTILS ---
    def load_tool_permission(self, *args):
        agent = self.perm_agent_var.get()
        tool = self.current_selected_tool
        if not agent or not tool or agent == "Aucun agent": return
        
        profile_path = os.path.join("agents", agent, "profile.json")
        if os.path.exists(profile_path):
            with open(profile_path, 'r', encoding='utf-8') as f: prof = json.load(f)
            allowed = prof.get("allowed_tools", os.listdir("tools")) # Par défaut tout est permis
            
            if tool in allowed:
                self.perm_switch.select()
                self.perm_switch.configure(text="✅ Autorisé")
            else:
                self.perm_switch.deselect()
                self.perm_switch.configure(text="❌ Bloqué")

    def toggle_tool_permission(self):
        agent = self.perm_agent_var.get()
        tool = self.current_selected_tool
        if not agent or not tool or agent == "Aucun agent": return
        
        is_on = self.perm_switch.get() == 1
        if is_on: self.perm_switch.configure(text="✅ Autorisé")
        else: self.perm_switch.configure(text="❌ Bloqué")
        
        profile_path = os.path.join("agents", agent, "profile.json")
        if os.path.exists(profile_path):
            with open(profile_path, 'r', encoding='utf-8') as f: prof = json.load(f)
            allowed = prof.get("allowed_tools", os.listdir("tools"))
            
            if is_on and tool not in allowed: allowed.append(tool)
            elif not is_on and tool in allowed: allowed.remove(tool)
                
            prof["allowed_tools"] = allowed
            with open(profile_path, 'w', encoding='utf-8') as f: json.dump(prof, f, indent=4, ensure_ascii=False)
            self.log_console(f"🔐 [SÉCURITÉ] Accès à '{tool}' {'AUTORISÉ' if is_on else 'BLOQUÉ'} pour {agent}.")

    # --- RESTE DES MÉTHODES ---
    def ui_create_agent_popup(self):
        dialog = ctk.CTkInputDialog(text="Quel est le nom du nouvel agent ?", title="Créer un Agent")
        name = dialog.get_input()
        if name:
            name = name.strip().replace(" ", "_")
            if name in self.orchestrator.agents: self.log_console(f"❌ [ERREUR] L'agent {name} existe déjà !"); return
            self.orchestrator.create_new_agent(name)
            self.chat_histories[name] = f"--- Début de la conversation avec {name} ---\n\n"
            self.refresh_agent_editor_list()
            self.filter_agent_dropdown.configure(values=["Tous les agents"] + list(self.orchestrator.agents.keys()))
            self.refresh_chat_sidebar()
            self.agent_edit_var.set(name)
            self.view_agent_files(name)
            if getattr(self, "current_selected_tool", None): self.read_tool_file(self.current_selected_tool) # Refresh dropdown
            self.log_console(f"✅ [SUCCÈS] L'agent {name} a été créé !")

    def ui_delete_agent(self):
        agent_name = self.agent_edit_var.get()
        if not agent_name or agent_name not in self.orchestrator.agents: return
        if messagebox.askyesno("Confirmation", f"Voulez-vous supprimer l'agent '{agent_name}' ?"):
            self.orchestrator.delete_agent(agent_name)
            if agent_name in self.chat_histories: del self.chat_histories[agent_name]
            self.refresh_agent_editor_list()
            self.filter_agent_dropdown.configure(values=["Tous les agents"] + list(self.orchestrator.agents.keys()))
            if self.current_chat_view == agent_name: self.switch_chat_view("Console")
            self.refresh_chat_sidebar()
            if getattr(self, "current_selected_tool", None): self.read_tool_file(self.current_selected_tool) # Refresh dropdown
            self.log_console(f"🗑️ [SYSTÈME] L'agent {agent_name} a été supprimé.")

    def refresh_chat_sidebar(self):
        for widget in self.conversations_frame.winfo_children(): widget.destroy()
        f_type, f_agent = self.filter_type_var.get(), self.filter_agent_var.get()
        if f_type == "Agent-Agent": ctk.CTkLabel(self.conversations_frame, text="Aucune.", text_color="gray").pack(pady=20); return
        for agent in self.orchestrator.agents.keys():
            if f_agent == "Tous les agents" or f_agent == agent:
                ctk.CTkButton(self.conversations_frame, text=f"👤 {agent}", command=lambda a=agent: self.switch_chat_view(a)).pack(pady=2, padx=5, fill="x")

    def switch_chat_view(self, view_name):
        self.current_chat_view = view_name
        self.chat_display.configure(state="normal")
        self.chat_display.delete("0.0", "end")
        self.chat_display.insert("0.0", self.chat_histories.get(view_name, ""))
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")
        if view_name == "Console":
            self.chat_title_label.configure(text="💻 Console Système (Lecture Seule)")
            self.chat_input_frame.grid_remove() 
        else:
            self.chat_title_label.configure(text=f"💬 Conversation avec {view_name}")
            self.chat_input_frame.grid() 

    def log_console(self, message):
        self.chat_histories["Console"] += f"{message}\n"
        if self.current_chat_view == "Console":
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"{message}\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")

    def log_chat_live(self, agent_name, text_chunk):
        if self.current_chat_view == agent_name:
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", text_chunk)
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")

    def log_chat(self, agent_name, message):
        self.chat_histories[agent_name] += message
        if self.current_chat_view == agent_name:
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", message)
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")

    def stop_generation(self):
        self.orchestrator.engine.interrupted = True
        self.chat_btn.configure(state="disabled", text="Arrêt en cours...")

    def send_chat_message(self):
        if self.is_generating: return
        user_text = self.chat_input.get().strip()
        target_agent = self.current_chat_view
        if not user_text or target_agent == "Console": return
        
        self.orchestrator.engine.interrupted = False
        
        self.log_chat(target_agent, f"👤 Vous : {user_text}\n\n")
        self.chat_input.delete(0, "end")
        self.is_generating = True
        self.chat_btn.configure(text="🛑 Arrêter", fg_color="red", hover_color="darkred", command=self.stop_generation)
        self.chat_input.configure(state="disabled")
        threading.Thread(target=self.process_chat, args=(user_text, target_agent), daemon=True).start()

    def process_chat(self, user_text, agent_name):
        try:
            # 1. VÉRIFICATION DU MODÈLE
            profile_path = os.path.join("agents", agent_name, "profile.json")
            with open(profile_path, 'r', encoding='utf-8') as f:
                prof = json.load(f)
            
            target_model = prof.get("specific_model")
            # Si pas de modèle spécifique, on prend le global
            if not target_model or target_model not in self.model_files:
                target_model = self.load_config().get("default_model")

            # 2. SWITCH SÉCURISÉ (Avec sortie d'urgence)
            if getattr(self, "current_loaded_model", None) != target_model:
                self.after(0, self.log_console, f"🔄 Changement de modèle pour {agent_name} -> {target_model}...")
                self.on_model_change(target_model)
                
                # On attend avec une limite de sécurité (max 60 secondes)
                timeout = 0
                while getattr(self, "current_loaded_model", None) != target_model and timeout < 60:
                    # SI L'UTILISATEUR CLIQUE SUR ARRÊTER PENDANT LE CHARGEMENT
                    if self.orchestrator.engine.interrupted: 
                        break 
                    time.sleep(1)
                    timeout += 1

            # Si on a arrêté ou si ça a crashé pendant le switch
            if self.orchestrator.engine.interrupted:
                self.after(0, self.reset_chat_btn)
                return

            # 3. PRÉPARATION DU CALLBACK ET DU DÉBUT DE RÉPONSE
            def ui_callback(text_chunk):
                clean_chunk = text_chunk.replace("---SYSTEM_START---\n", "").replace("\n---SYSTEM_END---", "")
                self.after(0, self.log_chat_live, agent_name, clean_chunk)

            self.after(0, self.log_chat_live, agent_name, f"🤖 [{agent_name}] :\n")
            
            # 4. EXÉCUTION DE LA TÂCHE
            clean_final_text, full_logs = self.orchestrator.agents[agent_name].execute_task(
                user_text, 
                ui_callback=ui_callback, 
                peer_agents=self.orchestrator.agents
            )

            # 5. FINALISATION ET NETTOYAGE UI
            def finish_up():
                if self.current_chat_view == agent_name:
                    self.chat_display.configure(state="normal")
                    self.chat_display.delete("0.0", "end")
                    self.chat_display.insert("0.0", self.chat_histories[agent_name])
                    self.chat_display.configure(state="disabled")

                self.log_chat(agent_name, f"🤖 [{agent_name}] :\n{clean_final_text}\n\n" + "-"*30 + "\n\n")
                
                clean_logs_console = full_logs.replace("---SYSTEM_START---\n", "").replace("\n---SYSTEM_END---", "")
                if clean_logs_console != clean_final_text:
                    self.chat_histories["Console"] += f"\n--- RÉFLEXION CACHÉE DE {agent_name} ---\n{clean_logs_console}\n----------------------------------\n\n"
                
                self.reset_chat_btn()

            self.after(0, finish_up)

        except Exception as e:
            # En cas de gros bug, on log l'erreur et on libère le bouton d'envoi
            self.after(0, self.log_console, f"❌ Erreur critique dans process_chat : {e}")
            self.after(0, self.reset_chat_btn)

    def reset_chat_btn(self):
        self.is_generating = False
        self.chat_btn.configure(state="normal", text="Envoyer", fg_color=self.default_btn_color, hover_color=self.default_btn_hover, command=self.send_chat_message)
        self.chat_input.configure(state="normal")
        self.chat_input.focus()

    def on_model_change(self, selected_model):
        # On vérifie si on doit vraiment charger quelque chose
        if selected_model != "Aucun modèle" and getattr(self, "current_loaded_model", None) != selected_model:
            
            # --- IMPORTANT : On ne valide PAS current_loaded_model ici ! ---
            
            self.log_console(f"🔄 Préparation du moteur pour : {selected_model}...")
            if hasattr(self, 'chat_btn'): 
                self.chat_btn.configure(state="disabled", text="Chargement...")
            
            def loading_task():
                model_path = os.path.join("models", selected_model)
                
                # --- SÉCURITÉ 1 : On vérifie que le fichier existe VRAIMENT ---
                if not os.path.exists(model_path):
                    self.after(0, self.log_console, f"❌ ERREUR CRITIQUE : Le modèle '{selected_model}' est introuvable. Placez-le dans le dossier 'models/'.")
                    if hasattr(self, 'chat_btn'):
                        self.after(0, lambda: self.chat_btn.configure(state="normal", text="Envoyer"))
                    return # On annule la suite du chargement
                # --------------------------------------------------------------

                try:
                    # On vide l'ancien modèle pour libérer la RAM/VRAM
                    self.orchestrator.engine.llm = None 
                    
                    # On charge le nouveau
                    self.orchestrator.engine.load_model(model_path)
                    
                    # On prévient l'interface que c'est fini (Succès)
                    self.after(0, self._model_loaded, selected_model)
                    
                except Exception as e:
                    # --- SÉCURITÉ 2 : En cas d'erreur interne de Llama.cpp ---
                    self.after(0, self.log_console, f"❌ ERREUR LORS DU CHARGEMENT : {str(e)}\nLe fichier est peut-être corrompu.")
                    if hasattr(self, 'chat_btn'):
                        self.after(0, lambda: self.chat_btn.configure(state="normal", text="Envoyer"))

            threading.Thread(target=loading_task, daemon=True).start()

    def _model_loaded(self, model_name):
        # C'EST ICI qu'on donne le feu vert officiel
        self.current_loaded_model = model_name 
        
        self.log_console(f"✅ Modèle '{model_name}' prêt !\n" + "-"*30)
        if hasattr(self, 'chat_btn'): 
            self.chat_btn.configure(state="normal", text="Envoyer")

    def refresh_agent_editor_list(self):
        agents = list(self.orchestrator.agents.keys())
        self.agent_edit_dropdown.configure(values=agents)
        if agents:
            if self.agent_edit_var.get() not in agents:
                self.agent_edit_var.set(agents[0])
                self.view_agent_files(agents[0])
        else:
            self.agent_edit_var.set("")
            for txt in [self.txt_profile, self.txt_memory, self.txt_instructions]: txt.delete("0.0", "end")

    def save_agent_file(self, filename, textbox):
        agent = self.agent_edit_var.get()
        if not agent: return
        content = textbox.get("0.0", "end").strip()
        try:
            if filename.endswith(".json"): json.loads(content)
            with open(os.path.join("agents", agent, filename), 'w', encoding='utf-8') as f: f.write(content)
            self.log_console(f"✅ [EDITEUR] '{filename}' de {agent} mis à jour.")
        except json.JSONDecodeError: self.log_console(f"❌ [ERREUR] JSON invalide pour {filename}.")
        except Exception as e: self.log_console(f"❌ [ERREUR] {e}")

    def view_agent_files(self, agent_name):
        self.current_selected_agent_editor = agent_name
        
        def read(f):
            p = os.path.join("agents", agent_name, f)
            return open(p, 'r', encoding='utf-8').read() if os.path.exists(p) else ""
            
        # Mise à jour des zones de texte classiques
        self.txt_profile.delete("0.0", "end")
        self.txt_profile.insert("0.0", read("profile.json"))
        
        self.txt_memory.delete("0.0", "end")
        self.txt_memory.insert("0.0", read("memory.json"))
        
        self.txt_instructions.delete("0.0", "end")
        self.txt_instructions.insert("0.0", read("instructions.txt"))
        
        # --- Lecture des deux logs (Propre et Détaillé) ---
        
        # 1. Le Log Propre (sans les réflexions)
        self.txt_log_clean.configure(state="normal")
        self.txt_log_clean.delete("0.0", "end")
        self.txt_log_clean.insert("0.0", read("log_clean.txt"))
        self.txt_log_clean.configure(state="disabled")

        # 2. Le Log Détaillé (avec les balises <think> et l'usage des outils)
        self.txt_log_detailed.configure(state="normal")
        self.txt_log_detailed.delete("0.0", "end")
        self.txt_log_detailed.insert("0.0", read("log_detailed.txt"))
        self.txt_log_detailed.configure(state="disabled")

        # --- Synchronisation du menu déroulant du modèle (AVEC SÉCURITÉ) ---
        try:
            prof_content = read("profile.json")
            if prof_content:
                prof = json.loads(prof_content)
                spec_model = prof.get("specific_model")
                
                # PATCH ANTI-CRASH : On vérifie si un modèle spécifique est demandé
                if spec_model and spec_model != "Par défaut (Global)":
                    # SÉCURITÉ : Ce modèle existe-t-il VRAIMENT sur le disque ?
                    if spec_model not in self.model_files:
                        self.log_console(f"⚠️ Modèle '{spec_model}' introuvable pour l'agent {agent_name}. Retour au modèle Global.")
                        spec_model = "Par défaut (Global)"
                else:
                    spec_model = "Par défaut (Global)"
                    
                self.agent_specific_model_var.set(spec_model)
            else:
                self.agent_specific_model_var.set("Par défaut (Global)")
        except Exception as e:
            # En cas d'erreur de lecture JSON, on revient par sécurité au global
            self.agent_specific_model_var.set("Par défaut (Global)")

    def refresh_tools_list(self):
        for widget in self.tools_scroll.winfo_children(): widget.destroy()
        tools_path = "tools"
        if os.path.exists(tools_path):
            for f in [f for f in os.listdir(tools_path) if f.endswith(".txt")]:
                ctk.CTkButton(self.tools_scroll, text=f"📄 {f}", anchor="w", fg_color="gray30", command=lambda name=f: self.read_tool_file(name)).pack(fill="x", pady=2, padx=5)

    def read_tool_file(self, filename):
        self.current_selected_tool = filename
        with open(os.path.join("tools", filename), "r", encoding="utf-8") as f: content = f.read()
        self.tool_title_label.configure(text=f"Notice de : {filename}", font=ctk.CTkFont(size=14, weight="bold"))
        self.tool_content_view.configure(state="normal")
        self.tool_content_view.delete("0.0", "end")
        self.tool_content_view.insert("0.0", content)
        self.tool_content_view.configure(state="disabled")
        
        # Affiche la barre de permissions
        self.tools_perm_frame.grid()
        agents = list(self.orchestrator.agents.keys())
        if not agents:
            self.perm_agent_dropdown.configure(values=["Aucun agent"])
            self.perm_switch.configure(state="disabled")
        else:
            self.perm_agent_dropdown.configure(values=agents)
            if self.perm_agent_var.get() not in agents: self.perm_agent_var.set(agents[0])
            self.perm_switch.configure(state="normal")
            self.load_tool_permission()

    def select_frame(self, name):
        self.btn_nav_chat.configure(fg_color=("gray75", "gray25") if name == "Chat" else "transparent")
        self.btn_nav_agents.configure(fg_color=("gray75", "gray25") if name == "Agents" else "transparent")
        self.btn_nav_tools.configure(fg_color=("gray75", "gray25") if name == "Tools" else "transparent")
        self.btn_nav_settings.configure(fg_color=("gray75", "gray25") if name == "Settings" else "transparent")
        self.frame_chat.grid_forget()
        self.frame_agents.grid_forget()
        self.frame_tools.grid_forget()
        self.frame_settings.grid_forget()

        if name == "Chat": 
            self.frame_chat.grid(row=0, column=1, sticky="nsew")
            self.refresh_chat_sidebar()
            self.switch_chat_view(self.current_chat_view) 
        if name == "Agents": 
            self.frame_agents.grid(row=0, column=1, sticky="nsew")
            self.refresh_agent_editor_list()
        if name == "Tools":
            self.frame_tools.grid(row=0, column=1, sticky="nsew")
            self.refresh_tools_list()
            # Nettoyer la vue si on revient sur l'onglet
            if not self.current_selected_tool: self.tools_perm_frame.grid_remove()
        if name == "Settings": self.frame_settings.grid(row=0, column=1, sticky="nsew")
    
    def watchdog_loop(self):
        while True:
            time.sleep(2) # Vérifie les boîtes toutes les 2 secondes
            
            # 1. Si le système (le GPU) est déjà occupé, on ne fait rien
            if self.is_generating:
                continue 
                
            oldest_time = None
            agent_to_wake = None
            
            # 2. On scanne les boîtes de réception de tous les agents existants
            for agent_name in self.orchestrator.agents.keys():
                inbox_path = os.path.join("agents", agent_name, "inbox.json")
                if os.path.exists(inbox_path):
                    try:
                        with open(inbox_path, 'r', encoding='utf-8') as f:
                            messages = json.load(f)
                            
                            # --- NOUVEAU : On filtre pour ne garder que les non lus ---
                            messages_non_lus = [m for m in messages if not m.get("is_read", False)]
                            
                            if messages_non_lus:
                                # 3. On regarde la date du premier message non lu (le plus ancien)
                                msg_time_str = messages_non_lus[0].get("date", "2099-01-01 00:00:00")
                                msg_time = datetime.strptime(msg_time_str, "%Y-%m-%d %H:%M:%S")
                                
                                # Si c'est le plus vieux trouvé jusqu'à présent, on le sélectionne
                                if oldest_time is None or msg_time < oldest_time:
                                    oldest_time = msg_time
                                    agent_to_wake = agent_name
                    except:
                        pass
                        
            # 4. Si on a trouvé un agent avec un message en attente, on le réveille !
            if agent_to_wake and not self.is_generating:
                self.is_generating = True # On verrouille le système
                
                # Message visuel dans la console pour l'administrateur
                self.log_console(f"⏰ [WATCHDOG] Un message en attente détecté pour '{agent_to_wake}'. Réveil automatique...")
                
                # --- NOUVEAU : Le signal envoyé à l'agent (Protocole Interne Strict) ---
                trigger_message = "🔔 [ALERTE SYSTÈME AUTOMATIQUE] Tu as de nouveaux messages dans ta boîte de réception. Utilise IMMÉDIATEMENT ton outil 'read_inbox' pour les lire.\n\n⚠️ PROTOCOLE DE RÉPONSE INTERNE :\n1. L'utilisateur humain est absent. Ne donne JAMAIS la réponse finale à voix haute.\n2. Exécute la tâche demandée par ton collègue.\n3. Tu DOIS IMPÉRATIVEMENT utiliser l'outil 'contact_agent' (après avoir lu sa notice) pour renvoyer le résultat à l'expéditeur.\n4. RAPPEL SYNTAXE : Tes outils utilisent TOUJOURS le format <|tool_call>call:nom_outil{arg:<|\"|>...<|\"|>}<tool_call|>. Ne devine jamais les paramètres."
                # -----------------------------------------------------
                
                # On simule un envoi de message dans l'interface et on lance le calcul
                self.chat_input.delete(0, "end")
                self.chat_btn.configure(text="🛑 Arrêter", fg_color="red", hover_color="darkred", command=self.stop_generation)
                self.chat_input.configure(state="disabled")
                
                self.log_chat(agent_to_wake, f"⚙️ Système : {trigger_message}\n\n")
                
                threading.Thread(
                    target=self.process_chat, 
                    args=(trigger_message, agent_to_wake), 
                    daemon=True
                ).start()
                
                # Pause de sécurité pour laisser le temps au moteur de démarrer
                time.sleep(10)

    def update_engine_params(self, _=None):
        new_temp = round(self.temp_slider.get() / 100, 2)
        new_penalty = round(self.penalty_slider.get() / 100, 2)
        
        self.temp_val_label.configure(text=str(new_temp))
        self.penalty_val_label.configure(text=str(new_penalty))
        
        self.orchestrator.engine.temperature = new_temp
        self.orchestrator.engine.repeat_penalty = new_penalty
        
        # --- NOUVEAU : Sauvegarde automatique ---
        self.save_config("temperature", new_temp)
        self.save_config("repeat_penalty", new_penalty)

    def on_global_model_change(self, selected_model):
        self.save_config("default_model", selected_model)
        self.on_model_change(selected_model)

    def save_agent_specific_model(self, selected_model):
        agent = self.agent_edit_var.get()
        if not agent: return
        profile_path = os.path.join("agents", agent, "profile.json")
        with open(profile_path, 'r', encoding='utf-8') as f: prof = json.load(f)
        
        # On enregistre None si c'est "Par défaut", sinon le nom du modèle
        prof["specific_model"] = selected_model if selected_model != "Par défaut (Global)" else None
        with open(profile_path, 'w', encoding='utf-8') as f: json.dump(prof, f, indent=4, ensure_ascii=False)
        self.log_console(f"🧠 [CONFIG] Modèle '{selected_model}' assigné à {agent}.")        

    # ==========================================
    # LA BOUCLE HEARTBEAT (Placée à la fin de la classe)
    # ==========================================
    def heartbeat_loop(self):
        while True:
            enabled = self.config.get("heartbeat_enabled", False)
            interval_min = self.config.get("heartbeat_interval", 30)
            
            if enabled:
                time.sleep(interval_min * 60)
                if not self.is_generating:
                    self.log_console(f"💓 [HEARTBEAT] Pulsion de réveil envoyée aux agents.")
                    
                    hb_msg = {
                        "from": "Système (Heartbeat)",
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "content": "NOTE : Ceci est un message automatique de routine. Si tu as une tâche en cours ou inachevée dans tes fichiers ou ta mémoire, continue-la maintenant. Sinon, ignore simplement ce message."
                    }
                    
                    for agent_name in self.orchestrator.agents.keys():
                        inbox_path = os.path.join("agents", agent_name, "inbox.json")
                        try:
                            messages = []
                            if os.path.exists(inbox_path):
                                with open(inbox_path, 'r', encoding='utf-8') as f:
                                    messages = json.load(f)
                            
                            messages.append(hb_msg)
                            
                            with open(inbox_path, 'w', encoding='utf-8') as f:
                                json.dump(messages, f, indent=4, ensure_ascii=False)
                        except Exception as e:
                            print(f"Erreur Heartbeat pour {agent_name}: {e}")
            else:
                time.sleep(10)

# --- FIN DE LA CLASSE AMMA_UI ---

if __name__ == "__main__":
    app = AMMA_UI()
    app.mainloop()