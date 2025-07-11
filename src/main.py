
import traceback
import sys
from utility.utils import *
from algorithm.gomory import *
from analysis.reporting import *
from config import DATA_DIR, RESULTS_DIR


CUT_MODES_AVAILABLE = ['GFC', 'GMI', 'BEST']


def print_menu():
    print("\n" + "=" * 60)
    print("           UFL SOLVER CON TAGLI DI GOMORY")
    print("=" * 60)
    print("1. Risolvi tutte le istanze esistenti")
    print("2. Risolvi singola istanza esistente")
    print("3. Genera TUTTE le istanze UFL da config.ini")
    print("4. Esci")
    print("=" * 60)




def process_single_instance_interactive():
    """
    Permette all'utente di scegliere un'istanza e poi la modalità di taglio
    da applicare (una o tutte).
    """
    # 1. Scelta dell'istanza
    txt_files = sorted(list(DATA_DIR.rglob('*.txt')))
    if not txt_files:
        print("Nessun file .txt trovato.")
        return

    for i, file_path in enumerate(txt_files, 1):
        print(f"{i}. {file_path.relative_to(DATA_DIR.parent)}")

    try:
        choice = int(input(f"Seleziona un file (1-{len(txt_files)}): ")) - 1
        if not (0 <= choice < len(txt_files)):
            print("Selezione non valida.")
            return

        selected_file = txt_files[choice]
        instance_name = selected_file.stem

        # Scelta della modalità di taglio
        print("\nScegli la modalità di taglio:")
        for i, mode in enumerate(CUT_MODES_AVAILABLE):
            print(f"{i+1}. {mode}")
        print(f"{len(CUT_MODES_AVAILABLE)+1}. Esegui TUTTE le modalità (per confronto)")

        mode_choice = int(input(f"Seleziona una modalità (1-{len(CUT_MODES_AVAILABLE)+1}): ")) - 1

        modes_to_run = []
        if 0 <= mode_choice < len(CUT_MODES_AVAILABLE):
            modes_to_run.append(CUT_MODES_AVAILABLE[mode_choice])
        elif mode_choice == len(CUT_MODES_AVAILABLE):
            modes_to_run = CUT_MODES_AVAILABLE
        else:
            print("Selezione modalità non valida.")
            return

        #  Esecuzione e raccolta risultati
        all_summaries = []
        model = FacilityLocationModel.from_file(selected_file)
        gomory_solver = Gomory(model)

        for mode in modes_to_run:
            print(f"\n-> Esecuzione su {instance_name} [Modalità: {mode}]")
            all_stats = gomory_solver.solve_problem(str(selected_file), cut_mode=mode)

            if not all_stats: continue

            # Plotting condizionale
            if len(all_stats) > 1:
                print(f"--> Istanza ha richiesto tagli. Genero grafico di convergenza.")
                report_dir = RESULTS_DIR / "single_instance_reports" / instance_name
                report_dir.mkdir(parents=True, exist_ok=True)
                plot_path = report_dir / f"convergence_{instance_name}_{mode}.png"
                plot_single_instance_convergence(all_stats, plot_path)

            # Preparazione riassunto (codice duplicato da sopra, si potrebbe refattorizzare in una funzione helper)
            initial_stats, final_stats = all_stats[0], all_stats[-1]
            initial_gap = initial_stats.get('relative_gap', 1)
            final_gap = final_stats.get('relative_gap', 1)
            status = final_stats.get('status', 'unknown')
            category = 'Errore'
            if status == 'optimal' and initial_gap < 1e-6:
                category = 'LP Ottimo Intero'
            elif status == 'optimal' and final_gap < THRESHOLD_GAP:
                category = 'Risolto con Tagli'
            elif status == 'optimal':
                category = 'Limite Raggiunto (Gap Residuo)'
            else:
                category = f'Non Risolto ({status})'
            summary = {
                'instance_name': instance_name, 'cut_mode': mode,
                'initial_gap': initial_stats.get('relative_gap', 0),
                'final_gap': final_stats.get('relative_gap', 0),
                'gap_closure': initial_stats.get('relative_gap', 0) - final_stats.get('relative_gap', 0),
                'total_cuts': final_stats.get('n_cuts', 0),
                'total_iterations': final_stats.get('iterations', 0),
                'total_time_ms': final_stats.get('elapsed_time', 0),
                'final_status': final_stats.get('status', 'unknown'),
                'solution_category': category
            }
            all_summaries.append(summary)

        #Stampa e Reporting finale
        if all_summaries:
            print("\n--- Riepilogo Risultati a Schermo ---")
            for s in all_summaries:
                print(f"Modalità: {s['cut_mode']:<5} | Stato: {s['final_status']:<25} | Gap Finale: {s['final_gap']:.4f} | Iter: {s['total_iterations']}")

            # Se abbiamo eseguito più modalità, ha senso generare un report comparativo
            if len(all_summaries) > 1:
                print("\nGenerazione report comparativo per la singola istanza...")
                report_dir = RESULTS_DIR / "single_instance_reports" / instance_name
                save_summary_report(all_summaries, report_dir)

    except (ValueError, IndexError):
        print("Input non valido.")
    except Exception as e:
        print(f"\U0001F6AB Errore critico durante l'elaborazione interattiva: {e}")
        traceback.print_exc()

def process_all_instances_for_one_mode(mode: str):
    """
    Funzione cuore che elabora tutte le istanze per UNA SOLA modalità di taglio
    e genera un report specifico per quella modalità.
    """
    print(f"\n--- AVVIO ELABORAZIONE COMPLETA IN MODALITÀ: {mode} ---")

    directory = DATA_DIR
    txt_files = sorted(list(directory.rglob('*.txt')))
    if not txt_files:
        print("Nessun file .txt trovato.")
        return

    all_summaries = []
    for file_path in txt_files:
        instance_name = file_path.stem
        print(f"\n-> Elaborazione: {instance_name} [Modalità: {mode}]")

        try:
            model = FacilityLocationModel.from_file(file_path)
            gomory_solver = Gomory(model)
            all_stats = gomory_solver.solve_problem(str(file_path), cut_mode=mode)

            if not all_stats:
                print(f"Nessuna statistica per {instance_name} in modalità {mode}.")
                continue

            if len(all_stats) > 1:
                print(f"--> L'istanza ha richiesto tagli. Genero grafico di convergenza.")
                # Genera il grafico di convergenza solo se significativo
                report_dir = RESULTS_DIR / f"report_{mode}"
                plot_dir = report_dir / "convergence_plots" / instance_name
                plot_dir.mkdir(parents=True, exist_ok=True)
                plot_path = plot_dir / f"convergence_{instance_name}.png"
                plot_single_instance_convergence(all_stats, plot_path)
            else:
                print(f"--> L'istanza è stata risolta al rilassamento LP iniziale. Grafico di convergenza non necessario.")

            initial_stats, final_stats = all_stats[0], all_stats[-1]
            initial_gap = initial_stats.get('relative_gap', 1)
            final_gap = final_stats.get('relative_gap', 1)
            status = final_stats.get('status', 'unknown')
            category = 'Errore'
            if status == 'optimal' and initial_gap < 1e-6:
                category = 'LP Ottimo Intero'
            elif status == 'optimal' and final_gap < THRESHOLD_GAP:
                category = 'Risolto con Tagli'
            elif status == 'optimal':
                category = 'Limite Raggiunto (Gap Residuo)'
            else:
                category = f'Non Risolto ({status})'

            summary = {
                'instance_name': instance_name, 'cut_mode': mode,
                'initial_gap': initial_stats.get('relative_gap', 0),
                'final_gap': final_stats.get('relative_gap', 0),
                'gap_closure': initial_stats.get('relative_gap', 0) - final_stats.get('relative_gap', 0),
                'total_cuts': final_stats.get('n_cuts', 0),
                'total_iterations': final_stats.get('iterations', 0),
                'total_time_ms': final_stats.get('elapsed_time', 0),
                'final_status': final_stats.get('status', 'unknown'),
                'solution_category': category
            }
            all_summaries.append(summary)

        except Exception as e:
            print(f"\U0001F6AB Errore critico durante l'elaborazione di {file_path.name}: {e}")
            traceback.print_exc()

    if all_summaries:
        # Salva il report in una sottocartella specifica per la modalità
        report_dir = RESULTS_DIR / f"report_{mode}"
        save_summary_report(all_summaries, report_dir)




def main():
    while True:
        print_menu()
        choice = input("Scegli un'opzione (1-4): ").strip()

        if choice == '1':
            print("\n--- AVVIO RISOLUZIONE DI TUTTE LE ISTANZE ESISTENTI ---")
            for i, mode in enumerate(CUT_MODES_AVAILABLE):
                print(f"{i+1}. {mode}")
            try:
                mode_choice = int(input(f"Seleziona una modalità (1-{len(CUT_MODES_AVAILABLE)}): ")) - 1
                if 0 <= mode_choice < len(CUT_MODES_AVAILABLE):
                    selected_mode = CUT_MODES_AVAILABLE[mode_choice]
                    process_all_instances_for_one_mode(selected_mode)
                else:
                    print("Selezione non valida.")
            except (ValueError, IndexError):
                print("Input non valido.")

        elif choice == '2':
            print("\n--- SELEZIONA UNA SINGOLA ISTANZA DA RISOLVERE ---")
            process_single_instance_interactive()

        elif choice == '3':
            print("\n--- AVVIO GENERAZIONE ISTANZE DA CONFIG.INI ---")
            try:
                generate_all_ufl_from_config('config.ini')
                print("\nGenerazione completata. Le nuove istanze sono state salvate.")
                print("Puoi ora risolverle usando l'opzione '1' o '2'.")
            except Exception as e:
                print(f"\U0001F6AB Errore durante la generazione delle istanze: {e}")

        elif choice == '4':
            print("Arrivederci!")
            sys.exit()

        else:
            print("Scelta non valida. Riprova.")

        input("\nPremi Invio per continuare...")



if __name__ == "__main__":
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    main()