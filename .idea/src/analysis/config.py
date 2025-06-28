import os
from pathlib import Path

# Percorsi base
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "instances"
RESULTS_DIR = PROJECT_ROOT / "results"
CONFIG_DIR = PROJECT_ROOT / "config"

# Configurazioni solver
SOLVER_CONFIGS = {
    'cplex': CONFIG_DIR / "solver_configs" / "cplex_settings.txt",
    'gurobi': CONFIG_DIR / "solver_configs" / "gurobi_settings.txt",
    'cbc': CONFIG_DIR / "solver_configs" / "cbc_settings.txt"
}

# Parametri esperimenti
DEFAULT_TIME_LIMIT = 3600  # secondi
TOLERANCE = 0.01
MAX_ITERATIONS = 20