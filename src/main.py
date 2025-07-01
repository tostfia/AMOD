import sys
import logging
import warnings
from pathlib import Path
from config import *
from plotter.plott import *
from utility.facilityLocation import FacilityLocationModel
from utility.utils import *
from analysis.solver import *
from analysis.gomory import *
import pandas as pd

columns = ["name", "nvar", "nconstraints", "optimal_sol", "sol", "sol_is_integer", "status", "ncuts", "elapsed_time",
           "gap", "relative_gap", "iterations"]
logging.basicConfig(filename='resolution.log', format='%(asctime)s - %(message)s', level=logging.INFO,
                    datefmt='%d-%b-%y %H:%M:%S')
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings('ignore')


def print_menu():
    print("\n" + "=" * 60)
    print("           UFL SOLVER CON TAGLI DI GOMORY")
    print("=" * 60)
    print("1. Risolvi tutte le istanze")
    print("2. Genera istanza casuale")
    print("3. Risolvi singola istanza")
    print("4. Esci")
    print("=" * 60)


def process_single_instance(filepath: Path) -> dict:
    try:
        print(f"\n\U0001F501 Elaborazione: {filepath.name}")
        stats = pd.DataFrame(columns=columns)
        model = FacilityLocationModel.from_file(filepath)
        solveInstance(model, filepath.name, stats)



    except Exception as e:
        logging.error(f"Errore in {filepath}: {e}")
        return {'success': False, 'message': str(e), 'filename': filepath.name}


def process_all_instances():
    directory = DATA_DIR
    txt_files = list(directory.rglob('*.txt'))
    results = []
    for file_path in txt_files:
        process_single_instance(file_path)

    return results


def process_single_instance_interactive():
    txt_files = list(DATA_DIR.rglob('*.txt'))
    for i, file_path in enumerate(txt_files, 1):
        print(f"{i}. {file_path.name}")
    try:
        choice = int(input("Seleziona un file: ")) - 1
        process_single_instance(txt_files[choice])
    except:
        print("Errore di selezione.")


def generate_random_instance():
    user_input = input("Inserisci ID, facilities, clienti (es: 1 10 50): ")
    try:
        stats = pd.DataFrame(columns=columns)
        instance_id, num_f, num_c = map(int, user_input.split())
        model = generateInstance(instance_id, num_f, num_c)
        solveInstance(model, f"{instance_id}.txt", stats)
    except Exception as e:
        print(f"Errore: {e}")





def main():
    while True:
        print_menu()
        choice = input("Scegli un'opzione (1-4): ").strip()
        flushLog("resolution.log")
        if choice == '1':
            process_all_instances()
        elif choice == '2':
            generate_random_instance()
        elif choice == '3':
            process_single_instance_interactive()
        elif choice == '4':
            print("Arrivederci!")
            sys.exit()
        else:
            print("Scelta non valida.")
        input("Premi Invio per continuare...")


if __name__ == "__main__":
    main()
