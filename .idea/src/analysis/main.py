from ampl_solver import UFLSolver
from parser import parse_ufl_instance, find_data_directory
from pathlib import Path
import os
import sys

def run_single_instance(filename):
    """Esegue la risoluzione di un'istanza singola"""
    try:
        if not os.path.exists(filename):
           print(f"Errore: il file {filename} non esiste.")
           return False
        print(f"Processando l'istanza: {filename}")
        instance_data = parse_ufl_instance(filename)
        solver = UFLSolver()
        solver.load_instance(instance_data)

        print("Risoluzione del rilassamento lineare...")
        linear_solution = solver.solve_linear_relaxation()
        print("Soluzione del rilassamento lineare:", linear_solution)

        print("Risoluzione con Gomory cuts...")
        gomory_solution = solver.solve_with_gomory()
        print("Soluzione con Gomory cuts:", gomory_solution)
        return True
    except Exception as e:
        print(f"Errore durante la risoluzione dell'istanza: {str(e)}")
        return False
def run_all_instances():
    """Esegue la risoluzione di tutte le istanze nella directory 'data'"""
    try:
        data_dir = find_data_directory()
        if not data_dir:
            print("Directory 'data' non trovata.")
            return False

        output_dir = os.path.join(data_dir, "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        all_data = process_all_files(data_dir, output_dir)
        if not all_data:
            print("Nessun dato da processare.")
            return False

        solver = UFLSolver()
        successful_runs=0
        total_runs = len(all_data)


        for filename, instance_data in all_data.items():
            print(f"Processando {filename}...")
            try:
                solver.load_instance(instance_data)

                print("Risoluzione del rilassamento lineare...")
                linear_solution = solver.solve_linear_relaxation()
                print(f"Soluzione del rilassamento lineare per {filename}:", linear_solution)

                print("Risoluzione con Gomory cuts...")
                gomory_solution = solver.solve_with_gomory()
                print(f"Soluzione con Gomory cuts per {filename}:", gomory_solution)
                successful_runs += 1
            except Exception as e:
                print(f"Errore durante la risoluzione di {filename}: {str(e)}")
                continue
        print(f"Processamento completato: {successful_runs}/{total_runs} istanze risolte con successo.")
        return successful_runs>0

    except Exception as e:
        print(f"Errore durante il processamento delle istanze: {str(e)}")
        return False
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
    print("\n" + "="*50)
    print("           UFL SOLVER")
    print("="*50)
    print("1. Risolvi istanza singola")
    print("2. Risolvi tutte le istanze")
    print("3. Esci")
    print("="*50)

def main():
    """Funzione principale con menu interattivo"""
    while True:
        print_menu()

        try:
            choice = input("Scegli un'opzione (1-3): ").strip()

            if choice == '1':
                filename = input("Inserisci il nome del file da processare: ").strip()
                if not filename:
                    print("Nome file non valido.")
                    continue

                instance_path = get_instance_path(filename)
                print(f"Tentativo di caricamento: {instance_path}")

                success = run_single_instance(instance_path)
                if success:
                    print("\nIstanza risolta con successo!")
                else:
                    print("\nErrore nella risoluzione dell'istanza.")

            elif choice == '2':
                print("Avvio risoluzione di tutte le istanze...")
                success = run_all_instances()
                if success:
                    print("\nTutte le istanze sono state processate!")
                else:
                    print("\nErrori durante il processamento delle istanze.")

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