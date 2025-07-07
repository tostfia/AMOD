import os
from pathlib import Path

# Percorsi base
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data" / "instances"
RESULTS_DIR = PROJECT_ROOT / "results"
CONFIG_DIR = PROJECT_ROOT / "config"
MODEL_DIR = PROJECT_ROOT / "model"



# Parametri esperimenti
TIME_LIMIT = 3600  # secondi
THRESHOLD_GAP = 0.01 # tolleranza per i risultati
MAX_ITERATIONS = 1000
