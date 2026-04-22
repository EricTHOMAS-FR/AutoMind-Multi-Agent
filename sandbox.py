import subprocess
import os
import tempfile
import time

class SandboxEnvironment:
    def __init__(self):
        self.workspace_dir = os.path.join(os.getcwd(), "amma_environment", "workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)

    def execute_python_code(self, code):
        # Création d'un fichier temporaire
        filename = f"temp_exec_{int(time.time())}.py"
        filepath = os.path.join(self.workspace_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            # NOUVEAU : Configuration pour cacher la fenêtre sous Windows !
            startupinfo = None
            if os.name == 'nt': # Si on est sur Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                ["python", filepath],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=startupinfo # On applique le camouflage
            )
            
            stdout_clean = result.stdout
            stderr_clean = result.stderr
            
            # --- SÉCURITÉ : NETTOYAGE DES CHEMINS ABSOLUS ---
            # On masque le vrai chemin de l'ordinateur par un faux chemin virtuel
            if self.workspace_dir in stdout_clean:
                stdout_clean = stdout_clean.replace(self.workspace_dir, "/sandbox/workspace")
            if self.workspace_dir in stderr_clean:
                stderr_clean = stderr_clean.replace(self.workspace_dir, "/sandbox/workspace")
                
            # Au cas où, on masque aussi le répertoire courant global
            current_dir = os.getcwd()
            if current_dir in stdout_clean:
                stdout_clean = stdout_clean.replace(current_dir, "/sandbox")
            if current_dir in stderr_clean:
                stderr_clean = stderr_clean.replace(current_dir, "/sandbox")
            # ------------------------------------------------
            
            return {
                "output": stdout_clean,
                "error": stderr_clean
            }
        except subprocess.TimeoutExpired:
            return {"output": "", "error": "Erreur : Temps d'exécution dépassé (10 secondes max)."}
        except Exception as e:
            error_msg = str(e)
            if self.workspace_dir in error_msg:
                error_msg = error_msg.replace(self.workspace_dir, "/sandbox/workspace")
            return {"output": "", "error": error_msg}
        finally:
            # Nettoyage
            if os.path.exists(filepath):
                os.remove(filepath)