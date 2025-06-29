from ampl_solver import *
from gomory_cut import GomoryCut
from plot_gomory_efficiency import *
from parser import *
from facilityLocation import FacilityLocationModel
from utils import generateInstance
from pathlib import Path
from config import *
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
        solver=UFLSolver()


        # Carica e confronta con soluzione ottima se disponibile
        solver.load_instance_from_model(model)
        solver.solve_instance()



        # Applica i tagli di Gomory
        gomory_solver = GomoryCut(n_facilities=model.num_facilities, n_customers=model.num_customers,
                                  fixed_cost=model.fixed_costs, allocation_cost=model.assignment_costs)
        result = gomory_solver.solve_with_gomory_cuts(MAX_ITERATIONS, TOLERANCE)


        gomory_solver.close()

        # Stampa statistiche finali

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
             # Applica i tagli di Gomory
            gomory_solver = GomoryCut(n_facilities=model.num_facilities, n_customers=model.num_customers,
                                      fixed_cost=model.fixed_costs, allocation_cost=model.assignment_costs)
            result = gomory_solver.solve_with_gomory_cuts(MAX_ITERATIONS, TOLERANCE)



            # Recupera l’ottimo dal file (già usato internamente, quindi riusalo qui)
            gomory_solver.close()

            # Stampa statistiche


            success_count += 1

        except Exception as e:
            print(f"Errore durante la risoluzione dell'istanza {filepath}: {str(e)}")

    print(f"\n{'='*80}")
    print(f"RIEPILOGO: {success_count}/{total_count} istanze risolte con successo")
    print('='*80)


def print_menu():
    """Stampa il menu delle opzioni"""
    print("\n" + "="*60)
    print("           UFL SOLVER CON TAGLI DI GOMORY")
    print("="*60)
    print("1. Risolvi istanza singola")
    print("2. Risolvi tutte le istanze")
    print("3. Genera istanza casuale e risolvi con tagli di Gomory")
    print("4. Esci")
    print("="*60)

def process_single_instance():
    """Gestisce l'opzione per risolvere un'istanza singola."""
    filename = input("Inserisci il nome del file da processare: ").strip()
    if not filename:
        print("Nome file non valido.")
        return
    if filename.startswith('cap'):
        instance_path = DATA_DIR/  "or-library" / filename
        print(f"Tentativo di caricamento: {instance_path}")
    else:
        instance_path= DATA_DIR/ "random"/filename
    success = run_single_instance(instance_path)
    if success:
        print("\nIstanza risolta con successo!")
    else:
        print("\nErrore nella risoluzione dell'istanza.")

def process_all_instances():
    """Gestisce l'opzione per risolvere tutte le istanze."""
    print("Avvio risoluzione di tutte le istanze...")
    directory = DATA_DIR / "or-library"

    if not directory.exists():
        print(f"Errore: directory {directory} non trovata")
        return

    run_all_instances(directory)

def main():
    """Funzione principale con menu interattivo."""
    while True:
        print_menu()

        try:
            choice = input("Scegli un'opzione (1-4): ").strip()

            if choice == '1':
                process_single_instance()
            elif choice == '2':
                process_all_instances()
            elif choice == '3':
                try:
                    user = input("Inserisci il numero dell'istanza da generare, il numero di facilities e il numero di clienti (es: 1 10 50): ").strip()
                    instance_id, num_facilities, num_customers = map(int, user.split())

                    model = generateInstance(instance_id, num_facilities, num_customers)
                    print(f"Istanza generata: {model}")
                    fixed_costs = model.get_fixed_costs()
                    assignment_costs = model.get_assignment_costs()
                    gomory = GomoryCut(num_facilities, num_customers, fixed_costs, assignment_costs)
                    gomory.solve_with_gomory_cuts(MAX_ITERATIONS, TOLERANCE)

                except ValueError:
                    print("Errore: assicurati di inserire tre numeri separati da spazio.")
                except Exception as e:
                    print(f"Errore inaspettato: {e}")

            elif choice == '4':
                    print("Uscita dal programma. Arrivederci!")
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