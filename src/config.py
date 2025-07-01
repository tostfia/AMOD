import os
from pathlib import Path

# Percorsi base
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data" / "instances"
RESULTS_DIR = PROJECT_ROOT / "results"
CONFIG_DIR = PROJECT_ROOT / "config"
MODEL_DIR = PROJECT_ROOT / "model"

# Configurazioni solver
SOLVER_CONFIGS = {
    'cplex': CONFIG_DIR / "solver_configs" / "cplex_settings.txt",
    'gurobi': CONFIG_DIR / "solver_configs" / "gurobi_settings.txt",
    'cbc': CONFIG_DIR / "solver_configs" / "cbc_settings.txt"
}

# Parametri esperimenti
TIME_LIMIT = 3600  # secondi
THRESHOLD_GAP = 0.05 # tolleranza per i risultati
MAX_ITERATIONS = 1000
#Rapporto bilanciato: Usa un rapporto facilities:customers di circa 1:2.5 o 1:3
#Numero medio-alto di facilities (~10–25) e clienti (~25–50)