
from pathlib import Path

# Percorsi base
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data" / "instances"
RESULTS_DIR = PROJECT_ROOT / "results"
CONFIG_DIR = PROJECT_ROOT / "config"
MODEL_DIR = PROJECT_ROOT / "model"



# Parametri esperimenti
TIME_LIMIT = 3600  # secondi
THRESHOLD_GAP = 1e-9 # tolleranza per i risultati
MAX_ITERATIONS = 1000
NUMERICAL_TOLERANCE = 1e-6
