from llama_cpp import Llama
import os
import subprocess
import gc       # NOUVEAU : Le nettoyeur de mémoire
import time     # NOUVEAU : Pour la pause

class LLMEngine:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        self.llm = None
        self.interrupted = False 
        
        # --- NOUVEAU : Valeurs modifiables par l'UI ---
        self.temperature = 0.45       # On part sur ta nouvelle base stable
        self.repeat_penalty = 1.08    # Idem 

    def _get_optimal_gpu_layers(self, model_path):
        """
        Fonction radar : Scanne la VRAM NVIDIA et calcule le ratio idéal
        """
        try:
            # --- NOUVEAU : Configuration pour cacher la fenêtre sous Windows ---
            creation_flags = 0
            if os.name == 'nt':  # 'nt' signifie que le système est Windows
                creation_flags = subprocess.CREATE_NO_WINDOW
            # -------------------------------------------------------------------

            # 1. On demande à Windows (via NVIDIA) combien de VRAM est libre (en Mégaoctets)
            result = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=memory.free', '--format=csv,nounits,noheader'],
                encoding='utf-8',
                creationflags=creation_flags  # <--- L'astuce est ajoutée ici !
            )
            free_vram_gb = int(result.strip().split('\n')[0]) / 1024.0
            
            # 2. On regarde combien pèse le modèle (en Gigaoctets)
            model_size_gb = os.path.getsize(model_path) / (1024**3)
            
            # 3. On garde une "Marge de sécurité" pour Windows et la mémoire de l'IA (Contexte)
            buffer_gb = 2.5 
            available_vram = free_vram_gb - buffer_gb
            
            print(f"\n🖥️ [AUTO-SCAN MATÉRIEL]")
            print(f"├─ Poids du modèle : {model_size_gb:.1f} Go")
            print(f"├─ VRAM NVIDIA dispo : {free_vram_gb:.1f} Go")
            
            if available_vram <= 0:
                print("└─ ⚠️ VRAM insuffisante. Mode CPU (Processeur) activé.")
                return 0
                
            if available_vram >= model_size_gb:
                print("└─ 🚀 Place suffisante ! Mode GPU Max (-1) activé.")
                return -1
                
            # 4. Le calcul du Mode Hybride
            # La plupart des gros modèles (14B à 32B) ont environ 50 à 60 couches (layers).
            # On calcule le pourcentage du modèle qui rentre, et on l'applique sur 55 couches.
            ratio = available_vram / model_size_gb
            estimated_layers = int(ratio * 55)
            
            print(f"└─ ⚖️ Mode Hybride activé : {estimated_layers} couches envoyées au GPU.")
            return estimated_layers

        except Exception as e:
            # Si le PC n'a pas de carte NVIDIA ou que la commande plante
            print("\n🖥️ [AUTO-SCAN MATÉRIEL]")
            print("└─ ⚠️ Aucune carte NVIDIA détectée. Mode CPU (Processeur) activé.")
            return 0


    def load_model(self, model_path):
        # --- NOUVEAU : Le nettoyage forcé ---
        if self.llm is not None:
            print("🧹 Déchargement de l'ancien modèle pour libérer la VRAM NVIDIA...")
            del self.llm         # On détruit l'objet
            self.llm = None      # On coupe le lien
            gc.collect()         # On force Python à vider la RAM
            time.sleep(1.5)      # On laisse 1.5 seconde au radar NVIDIA pour voir que la voie est libre
        # ------------------------------------

        print(f"Chargement du modèle : {os.path.basename(model_path)}")
        
        # Le radar scanne MAINTENANT, alors que la carte est vide !
        optimal_layers = self._get_optimal_gpu_layers(model_path)
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=32768,         
            n_gpu_layers=optimal_layers, 
            verbose=False       
        )
        print("Modèle chargé et prêt !")

    def generate(self, prompt, agent_name="", stream_callback=None):
        if self.use_mock:
            return "Ceci est une réponse de test."
            
        if not self.llm:
            return "❌ Erreur : Aucun modèle n'est chargé."

        stop_sequences = ["<end_of_turn>", "<start_of_turn>user", "<start_of_turn>model", "<|tool_response>"]

        response_text = ""
        try:
            stream = self.llm.create_completion(
                prompt=prompt,
                max_tokens=4096,                   # <--- On lui donne plus d'espace pour répondre
                stop=stop_sequences,
                stream=True,
                temperature=self.temperature,      
                top_p=0.95,                        # <--- NOUVEAU : Recommandation DeepMind
                top_k=64,                          # <--- NOUVEAU : Recommandation DeepMind
                repeat_penalty=self.repeat_penalty 
            )
            
            for chunk in stream:
                # 1. LA SAUVEGARDE D'URGENCE (Interruption manuelle)
                if self.interrupted:
                    msg = "\n\n[INTERRUPTION MÉCANIQUE]"
                    response_text += msg
                    if stream_callback: stream_callback(msg)
                    break  # On casse la boucle, mais on retourne quand même le texte !
                    
                word = chunk["choices"][0]["text"]
                response_text += word
                
                if stream_callback:
                    stream_callback(word)
                
                # 2. LE BOUCLIER ANTI-BÉGAIEMENT (Densité sur 200 caractères)
                # On ne lance l'analyse que si on a déjà un peu de texte
                if len(response_text) > 20:
                    window = response_text[-200:]  # On isole les 200 derniers caractères
                    boucle_detectee = False
                    
                    # On teste des suites de caractères de 1 à 50 lettres
                    max_len = min(50, len(window) // 2)
                    for length in range(1, max_len + 1):
                        seq = window[-length:] # On prend la toute dernière suite tapée
                        
                        # Ton algorithme dégressif exact : 150 pour 1 car, 75 pour 2, 50 pour 3...
                        max_allowed = max(3, 150 // length) 
                        
                        # Si cette suite apparaît trop de fois dans les 200 derniers caractères
                        if window.count(seq) > max_allowed:
                            boucle_detectee = True
                            break
                            
                    if boucle_detectee:
                        msg_alerte = "\n\n[ALERTE SYSTÈME : Tu as répété la même suite de caractères de façon anormale. Si c'est normal, continue. Sinon, arrête-toi, ferme tes balises et réfléchis à ta prochaine action.]"
                        response_text += msg_alerte
                        if stream_callback: stream_callback(msg_alerte)
                        break  # Arrêt d'urgence du moteur !
                
        except Exception as e:
            return f"❌ Erreur lors de la génération : {e}"

        # On retourne le texte (même s'il a été coupé en plein milieu)
        return response_text.strip()