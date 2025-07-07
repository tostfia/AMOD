

import sys
from utility.utils import *
from algorithm.gomory import *
from analysis.reporting import *
from config import DATA_DIR, RESULTS_DIR





def print_menu():
    print("\n" + "=" * 60)
    print("           UFL SOLVER CON TAGLI DI GOMORY")
    print("=" * 60)
    print("1. Risolvi tutte le istanze esistenti")
    print("2. Risolvi singola istanza esistente")
    # --- MODIFICA 2: Cambia il testo delle opzioni per chiarezza ---
    print("3. Genera TUTTE le istanze UFL da config.ini")
    print("4. Esci")
    print("=" * 60)

def process_single_instance(filepath: Path) -> dict | None:
    """
    Elabora una singola istanza, genera il suo grafico di convergenza
    e restituisce un dizionario riassuntivo.
    """
    try:
        print(f"\n\U0001F501 Elaborazione: {filepath.name}")
        instance_name = filepath.stem

        model = FacilityLocationModel.from_file(filepath)
        gomory = Gomory(model)
        all_instance_stats = gomory.solve_problem(str(filepath))

        if not all_instance_stats:
            print(f"Nessuna statistica generata per {instance_name}.")
            return None

        # Genera il grafico di convergenza per questa singola istanza
        plot_path = RESULTS_DIR / instance_name / f"{instance_name}_convergence_plot.png"
        plot_single_instance_convergence(all_instance_stats, plot_path)

        # Prepara e restituisci il dizionario riassuntivo
        initial_stats = all_instance_stats[0]
        final_stats = all_instance_stats[-1]

        summary = {
            'instance_name': instance_name,
            'initial_gap': initial_stats.get('relative_gap', 0),
            'final_gap': final_stats.get('relative_gap', 0),
            'gap_closure': initial_stats.get('relative_gap', 0) - final_stats.get('relative_gap', 0),
            'total_cuts': final_stats.get('n_cuts', 0),
            'total_iterations': final_stats.get('iteration', 0),
            'total_time_ms': final_stats.get('elapsed_time_ms', 0),
            'final_status': final_stats.get('status', 'unknown')
        }
        return summary

    except Exception as e:
        print(f"\U0001F6AB Errore critico durante l'elaborazione di {filepath.name}: {e}")
        return None



def process_all_instances():
    """Elabora tutte le istanze e genera un report CSV e grafici comparativi."""
    directory = DATA_DIR
    txt_files = sorted(list(directory.rglob('*.txt')))

    if not txt_files:
        print("Nessun file .txt trovato.")
        return

    all_summaries = []
    for file_path in txt_files:
        summary = process_single_instance(file_path)
        if summary:
            all_summaries.append(summary)

    if all_summaries:
        # Chiama l'unica funzione necessaria per il report complessivo
        save_summary_report(all_summaries, RESULTS_DIR)


# La funzione process_single_instance_interactive rimane invariata...
def process_single_instance_interactive():
    # ... (il tuo codice esistente qui)
    txt_files = sorted(list(DATA_DIR.rglob('*.txt')))
    if not txt_files:
        print("Nessun file .txt trovato.")
        return
    for i, file_path in enumerate(txt_files, 1):
        print(f"{i}. {file_path.relative_to(DATA_DIR.parent)}")
    try:
        choice = int(input(f"Seleziona un file (1-{len(txt_files)}): ")) - 1
        if 0 <= choice < len(txt_files):
            process_single_instance(txt_files[choice])
        else:
            print("Selezione non valida.")
    except (ValueError, IndexError):
        print("Input non valido.")


def main():
    while True:
        print_menu()
        choice = input("Scegli un'opzione (1-4): ").strip()

        if choice == '1':
            print("\n--- AVVIO RISOLUZIONE DI TUTTE LE ISTANZE ESISTENTI ---")
            process_all_instances()

        elif choice == '2':
            print("\n--- SELEZIONA UNA SINGOLA ISTANZA DA RISOLVERE ---")
            process_single_instance_interactive()

        # --- MODIFICA 3: Aggiungi il nuovo caso per la generazione ---
        elif choice == '3':
            print("\n--- AVVIO GENERAZIONE ISTANZE DA CONFIG.INI ---")
            if generate_all_ufl_from_config:
                generate_all_ufl_from_config('config.ini')
                print("\nGenerazione completata. Le nuove istanze sono state salvate.")
                print("Puoi ora risolverle usando l'opzione '1' o '2'.")
            else:
                print("Funzione di generazione non disponibile. Controlla l'import.")
        elif choice == '4':
            print("Arrivederci!")
            sys.exit()

        else:
            print("Scelta non valida. Riprova.")

        input("\nPremi Invio per continuare...")



if __name__ == "__main__":
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    main()