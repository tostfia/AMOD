from ampl_solver import UFLSolver
from gomory_cut import GomoryCut
from parser import parse_ufl_instance, parse_ufl_to_model #find_data_directory
from pathlib import Path
from facilityLocation import FacilityLocationModel
import glob
import os
import sys

def load_model(filename: str) -> FacilityLocationModel:
    """Carica il modello da un file."""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Errore: il file {filename} non esiste.")
    print(f"Processando l'istanza: {filename}")
    return parse_ufl_to_model(filename)

def run_single_instance(filename: str) -> bool:
    """Esegue la risoluzione di un'istanza singola."""
    try:
        model = load_model(filename)
        print(f"Caricato: {model}")

        solver = UFLSolver()
        solver.load_instance_from_model(model)
        gomory_cut= GomoryCut()

        # Carica e confronta con soluzione ottima se disponibile
        try:
            linear_solution = solver.solve_instance(model)
            opt_solution = solver.load_optimal_solution(filename)
            solver.compare_with_optimal(filename, model, linear_solution, opt_solution)
        except FileNotFoundError:
            print("Soluzione ottima non disponibile per il confronto")

        print("\n" + "="*60)

        # Applica i tagli di Gomory
        gomory_solver = GomoryCut(ampl_solver=solver, max_iterations=20)
        final_solution, final_objective = gomory_solver.solve_with_gomory_cuts(model, solver)

        # Stampa statistiche finali
        stats = gomory_solver.get_statistics()
        print(f"\n=== STATISTICHE GOMORY CUTS ===")
        print(f"Iterazioni totali: {stats['total_iterations']}")
        print(f"Tagli aggiunti: {stats['total_cuts']}")

        if stats['total_cuts'] > 0:
            print("Dettaglio tagli:")
            for i, cut in enumerate(stats['cuts_info']):
                print(f"  {i+1}. {cut['constraint'].replace('con ', '').replace(':', '')}")

        return True

    except FileNotFoundError as e:
        print(str(e))
    except Exception as e:
        print(f"Errore durante la risoluzione dell'istanza: {str(e)}")
        import traceback
        print("Traceback completo:")
        traceback.print_exc()
    return False
def run_all_instances(directory):
    """Esegue la risoluzione di tutte le istanze in una directory"""
    success_count = 0
    total_count = 0

    for filepath in glob.glob(os.path.join(directory, '*.txt')):
        total_count += 1
        print(f"\n{'='*80}")
        print(f"ISTANZA {total_count}: {os.path.basename(filepath)}")
        print('='*80)

        try:
            model = FacilityLocationModel.from_file(filepath)
            print(f"Caricato: {model}")

            # Crea il solver e carica l'istanza
            solver = UFLSolver()
            solver.load_instance_from_model(model)

            print("=== RISOLUZIONE RILASSAMENTO LINEARE ===")
            linear_solution = solver.solve_instance(model)

            # Carica e confronta con soluzione ottima se disponibile
            try:
                opt_solution = solver.load_optimal_solution(filepath)
                solver.compare_with_optimal(filepath, model, linear_solution, opt_solution)
            except FileNotFoundError:
                print("Soluzione ottima non disponibile per il confronto")

            print("\n" + "="*60)

            # Applica i tagli di Gomory
            gomory_solver = GomoryCut(ampl_solver=solver, max_iterations=15)
            final_solution, final_objective = gomory_solver.solve_with_gomory_cuts(model, solver)

            # Stampa statistiche
            stats = gomory_solver.get_statistics()
            print(f"\n=== STATISTICHE ISTANZA {os.path.basename(filepath)} ===")
            print(f"Iterazioni: {stats['total_iterations']}, Tagli: {stats['total_cuts']}")

            success_count += 1

        except Exception as e:
            print(f"Errore durante la risoluzione dell'istanza {filepath}: {str(e)}")

    print(f"\n{'='*80}")
    print(f"RIEPILOGO: {success_count}/{total_count} istanze risolte con successo")
    print('='*80)

def get_instance_path(filename):
    """Costruisce il percorso completo per il file di istanza"""
    current_path = Path(__file__).parent.parent.parent

    # Gestisce diversi formati di input
    if not filename.startswith('/') and not filename.startswith('\\'):
        # Se non è un percorso assoluto, costruisce il percorso relativo
        if not filename.startswith('data'):
            instance_path = current_path/ "data" / "instances" / "or-library" / filename
        else:
            instance_path = current_path / filename
    else:
        instance_path = Path(filename)

    return str(instance_path)
def print_menu():
    """Stampa il menu delle opzioni"""
    print("\n" + "="*60)
    print("           UFL SOLVER CON TAGLI DI GOMORY")
    print("="*60)
    print("1. Risolvi istanza singola")
    print("2. Risolvi tutte le istanze")
    print("3. Esci")
    print("="*60)

def process_single_instance():
    """Gestisce l'opzione per risolvere un'istanza singola."""
    filename = input("Inserisci il nome del file da processare: ").strip()
    if not filename:
        print("Nome file non valido.")
        return

    instance_path = get_instance_path(filename)
    print(f"Tentativo di caricamento: {instance_path}")

    success = run_single_instance(instance_path)
    if success:
        print("\nIstanza risolta con successo!")
    else:
        print("\nErrore nella risoluzione dell'istanza.")

def process_all_instances():
    """Gestisce l'opzione per risolvere tutte le istanze."""
    print("Avvio risoluzione di tutte le istanze...")
    directory = Path(__file__).parent.parent.parent / "data" / "instances" / "or-library"

    if not directory.exists():
        print(f"Errore: directory {directory} non trovata")
        return

    run_all_instances(directory)

def main():
    """Funzione principale con menu interattivo."""
    while True:
        print_menu()

        try:
            choice = input("Scegli un'opzione (1-3): ").strip()

            if choice == '1':
                process_single_instance()
            elif choice == '2':
                process_all_instances()
            elif choice == '3':
                print("Arrivederci!")
                sys.exit(0)
            else:
                print("Opzione non valida. Scegli 1, 2 o 3.")

        except KeyboardInterrupt:
            print("\n\nInterruzione da tastiera. Arrivederci!")
            sys.exit(0)
        except Exception as e:
            print(f"Errore inaspettato: {e}")

        # Pausa prima di mostrare di nuovo il menu
        input("\nPremi Invio per continuare...")

if __name__ == "__main__":
    main()