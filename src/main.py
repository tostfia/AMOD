import sys

from config import *
from plotter.plott import *
from utility.facilityLocation import FacilityLocationModel
from utility.utils import *


def print_menu():
    """Stampa il menu delle opzioni"""
    print("\n" + "=" * 60)
    print("           UFL SOLVER CON TAGLI DI GOMORY")
    print("=" * 60)
    print("1. Risolvi tutte le istanze")
    print("2. Genera istanza casuale")
    print("3. Esci")
    print("=" * 60)


def process_all_instances():
    """Gestisce l'opzione per risolvere tutte le istanze."""
    print("Avvio risoluzione di tutte le istanze...")
    directory = DATA_DIR
    if not directory.exists():
        print(f"Errore: directory {directory} non trovata")
        return
    # lista di dizionari
    results = []
    successful_instances = 0
    failed_instances = 0
    # Genera i tagli di Gomory per ogni istanza nella directory
    txt_files = list(directory.rglob('*.txt'))
    for i, file in enumerate(txt_files, 1):
        try:

            model = FacilityLocationModel.from_file(file)
            print(f"Caricato: {model}")
            A, b, c = create_ufl_matrix(model.get_num_facilities(), model.get_num_customers(),
                                        model.get_assignment_costs(), model.get_fixed_costs())
            gomory_solver = GomoryCut(A, b, c)
            result = gomory_solver.solve_with_gomory_cuts(MAX_ITERATIONS, verbose=True)
            if result:
                results.append({
                    "file": file.name,
                    "total_cost": result['objective_value'],
                    "variables": result['variables'],
                    "iterations": result['iterations'],
                    "cuts_added": result['cuts_added'],
                    "cuts_history": result('cuts_history', []),

                })
                successful_instances += 1
                print_summary_table(results)
                plot_gomory_efficiency(results)
                for idx, result in enumerate(results):
                    if 0 <= idx < len(results):
                        plot_individual_convergence(results[idx])
                # Stampa i risultati per ogni istanza
                print(f"✓ Successo: {file.name} - Obj: {result['objective_value']:.2f}, "
                      f"Iter: {result['iterations']}, Tagli: {result['cuts_added']}")
            else:
                failed_instances += 1
                print(f"✗ Fallito: {file.name} - Nessun risultato ottenuto")
        except Exception as e:
            print(f"Errore durante la risoluzione dell'istanza {file}: {str(e)}")
            continue

        # Salva i risultati


def main():
    """Funzione principale con menu interattivo."""
    while True:
        print_menu()

        try:
            choice = input("Scegli un'opzione (1-3): ").strip()
            if choice == '1':
                process_all_instances()
            elif choice == '2':
                try:
                    user = input("Inserisci il numero dell'istanza da generare, il numero di facilities e il numero di clienti (es: 1 10 50): ").strip()
                    instance_id, num_facilities, num_customers = map(int, user.split())
                    model = generateInstance(instance_id, num_facilities, num_customers)
                    print(f"Istanza generata: {model}")
                except ValueError:
                    print("Errore: assicurati di inserire tre numeri separati da spazio.")
                except Exception as e:
                    print(f"Errore inaspettato: {e}")
            elif choice == '3':
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
